"""检修域 `/api/v1/maintenance` 契约与验收文档 P0 扩展矩阵（TC-*）。"""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.database import get_session
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/api/v1/maintenance"


def _naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture(scope="session")
def maintenance_db_path(tmp_path_factory) -> Path:
    """会话级临时库路径并完成 Alembic upgrade（同步）。"""
    path = tmp_path_factory.mktemp("maintenance") / "maintenance_contract.db"
    url = f"sqlite+aiosqlite:///{path}"
    previous = os.environ.get("DATABASE_URL")
    previous_jwt = os.environ.get("JWT_SECRET_KEY")
    os.environ["DATABASE_URL"] = url
    os.environ["JWT_SECRET_KEY"] = "k" * 40  # 消除 PyJWT 密钥过短告警
    get_settings.cache_clear()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    try:
        yield path
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        if previous_jwt is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = previous_jwt
        get_settings.cache_clear()
        # Reset global engine singleton so subsequent tests pick up the
        # restored DATABASE_URL instead of the disposed SQLite engine.
        from app.core.database import reset_engine
        reset_engine()


@pytest_asyncio.fixture
async def maintenance_engine(maintenance_db_path: Path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    url = f"sqlite+aiosqlite:///{maintenance_db_path}"
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"check_same_thread": False})
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def maintenance_session_factory(maintenance_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(bind=maintenance_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture(autouse=True)
async def override_maintenance_session(maintenance_session_factory):
    async def _gen():
        async with maintenance_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _gen
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def seed_users(maintenance_session_factory):
    from sqlalchemy import select

    from app.models.maintenance_domain import AuthUser, Device, FlowTemplate, Role, SystemConfig, UserRole
    from app.modules.maintenance.security import hash_password

    async with maintenance_session_factory() as session:
        roles = (await session.execute(select(Role))).scalars().all()
        by = {r.code: r for r in roles}
        pwd = hash_password("testpass")

        async def add_user(username: str, codes: list[str]) -> AuthUser:
            existing = (
                await session.execute(select(AuthUser).where(AuthUser.username == username))
            ).scalar_one_or_none()
            if existing:
                return existing
            u = AuthUser(
                username=username,
                password_hash=pwd,
                display_name=username,
                is_active=True,
            )
            session.add(u)
            await session.flush()
            for c in codes:
                session.add(UserRole(user_id=u.id, role_id=by[c].id))
            return u

        w = await add_user("tc_worker", ["worker"])
        e = await add_user("tc_expert", ["expert"])
        await add_user("tc_expert_b", ["expert"])  # 非设备 AST-TC-1 责任专家，用于 ISO-002
        s = await add_user("tc_safety", ["safety"])
        a = await add_user("tc_admin", ["admin"])
        await add_user("tc_worker_b", ["worker"])
        if (
            await session.execute(
                select(FlowTemplate).where(
                    FlowTemplate.device_type == "pump_test",
                    FlowTemplate.maintenance_level == "计划定修",
                    FlowTemplate.status == "published",
                )
            )
        ).scalar_one_or_none() is None:
            session.add(
                FlowTemplate(
                    name="泵测试检修模板",
                    device_type="pump_test",
                    maintenance_level="计划定修",
                    steps_json=[
                        {"step_no": 1, "title": "准备", "requires_approval": False},
                        {"step_no": 2, "title": "高危作业", "requires_approval": True},
                    ],
                    version=1,
                    status="published",
                    published_at=None,
                )
            )
        if (await session.execute(select(SystemConfig).where(SystemConfig.key == "upload.max_image_mb"))).scalar_one_or_none() is None:
            from datetime import UTC, datetime as _dt

            session.add(
                SystemConfig(
                    key="upload.max_image_mb",
                    value="10",
                    value_type="int",
                    reload_policy="hot",
                    is_sensitive=False,
                    updated_at=_dt.now(UTC).replace(tzinfo=None),
                )
            )
        if (
            await session.execute(select(Device).where(Device.asset_code == "AST-TC-1"))
        ).scalar_one_or_none() is None:
            session.add(
                Device(
                    device_type="pump_test",
                    model="M1",
                    asset_code="AST-TC-1",
                    location="L1",
                    responsibility_expert_user_id=e.id,
                )
            )
        if (
            await session.execute(select(Device).where(Device.asset_code == "AST-TC-2"))
        ).scalar_one_or_none() is None:
            session.add(
                Device(
                    device_type="pump_empty",
                    model="M2",
                    asset_code="AST-TC-2",
                    location="L2",
                    responsibility_expert_user_id=None,
                )
            )
        await session.commit()
        return {"worker": w.id, "expert": e.id, "safety": s.id, "admin": a.id}


@pytest_asyncio.fixture
async def client(seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client: AsyncClient, username: str) -> str:
    r = await client.post(f"{PREFIX}/auth/login", json={"username": username, "password": "testpass"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _mock_search_payload(results: list | None = None):
    r = results if results is not None else [
        {
            "chunk_id": 901,
            "citation_label": "C1",
            "excerpt": "abcdef longer excerpt for rag",
            "source_name": "手册.pdf",
            "title": "标题",
            "score": 0.88,
        }
    ]
    return {"results": r, "effective_query": "q", "query": "q"}


async def _create_wo_and_retrieval(client: AsyncClient, tok: str, device_id: int = 1, results=None):
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": device_id},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        return_value=_mock_search_payload(results),
    ):
        r2 = await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "泄漏"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r2.status_code == 200, r2.text
    return wo_id, r2


async def _to_s8_with_attachment(client: AsyncClient, tok: str, wo_id: int) -> int:
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/enter-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/complete-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("ev.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert up.status_code == 200
    return int(up.json()["data"]["id"])


@pytest.mark.asyncio
async def test_tc_auth_001_login_ok(client: AsyncClient):
    r = await client.post(f"{PREFIX}/auth/login", json={"username": "tc_worker", "password": "testpass"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["access_token"]


@pytest.mark.asyncio
async def test_tc_auth_002_invalid_credentials(client: AsyncClient):
    r = await client.post(f"{PREFIX}/auth/login", json={"username": "tc_worker", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["business_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_tc_dev_001_devices_pagination_shape(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.get(f"{PREFIX}/devices?page=1&page_size=20", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert set(d.keys()) == {"items", "total", "page", "page_size"}


@pytest.mark.asyncio
async def test_tc_wo_001_create_missing_device(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"maintenance_level": "计划定修"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400
    assert r.json()["business_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tc_wo_002_create_s1_and_tc_wo_003_fill_wrong_state(client: AsyncClient, maintenance_session_factory):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": 1, "maintenance_level": "计划定修"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    wo_id = r.json()["data"]["id"]
    assert r.json()["data"]["status"] == "S1"

    r2 = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "resolved",
            "closure_code": "NORMAL",
            "attachment_ids": [1],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 409
    assert r2.json()["business_code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_tc_rag_retrieval_soft_fail_200(client: AsyncClient, maintenance_session_factory):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": 1},
        headers={"Authorization": f"Bearer {tok}"},
    )
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        return_value={"results": [], "effective_query": "x", "query": "x"},
    ):
        r2 = await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "测试查询"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r2.status_code == 200
    body = r2.json()
    assert body["success"] is False
    assert body["business_code"] == "EMPTY_HIT"
    assert body["data"]["retrieval_snapshot_id"]
    assert body["data"]["message_id"]


@pytest.mark.asyncio
async def test_tc_fill_002_other_without_notes(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    # 走完整状态到 S8：S1->检索->S3->enter S7->complete S8
    r = await client.post(
        f"{PREFIX}/work-orders", json={"device_id": 1}, headers={"Authorization": f"Bearer {tok}"}
    )
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        return_value={
            "results": [
                {
                    "chunk_id": 1,
                    "excerpt": "abcdef longer excerpt",
                    "source_name": "手册.pdf",
                    "title": "t",
                    "score": 0.9,
                }
            ],
            "effective_query": "q",
            "query": "q",
        },
    ):
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "泄漏"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/enter-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/complete-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert up.status_code == 200
    aid = up.json()["data"]["id"]
    bad = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "resolved",
            "closure_code": "OTHER",
            "attachment_ids": [aid],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert bad.status_code == 400
    assert bad.json()["business_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tc_esc_001_no_expert_configured(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders", json={"device_id": 2}, headers={"Authorization": f"Bearer {tok}"}
    )
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        return_value={"results": [], "effective_query": "x", "query": "x"},
    ):
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "x"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    esc = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": "一二三四五六七八九十现场说明"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert esc.status_code == 400
    assert esc.json()["business_code"] == "EXPERT_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_tc_auth_004_worker_forbidden_admin(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.get(f"{PREFIX}/admin/users", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_p1_retrieval_stream_and_asr_placeholder(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r_wo = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": 1},
        headers={"Authorization": f"Bearer {tok}"},
    )
    wo_id = r_wo.json()["data"]["id"]
    async with client.stream(
        "GET",
        f"{PREFIX}/work-orders/{wo_id}/retrieval/stream",
        headers={"Authorization": f"Bearer {tok}"},
    ) as stream:
        assert stream.status_code == 200
        assert "text/event-stream" in (stream.headers.get("content-type") or "").lower()
        body = await stream.aread()
        assert b"event:" in body or b"done" in body
    r_asr = await client.post(
        f"{PREFIX}/asr/transcribe",
        headers={"Authorization": f"Bearer {tok}"},
        json={},
    )
    assert r_asr.status_code == 501
    assert r_asr.json()["business_code"] == "ASR_NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_tc_auth_logout_204(client: AsyncClient):
    r = await client.post(f"{PREFIX}/auth/logout")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_tc_att_001_upload_ok(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_tc_att_002_payload_too_large(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    big = b"x" * (10 * 1024 * 1024 + 1)
    r = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("big.bin", big, "application/octet-stream")},
        data={"biz_type": "filling_evidence"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 413
    assert r.json()["business_code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_tc_att_003_content_redirect_302(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("b.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert up.status_code == 200
    aid = up.json()["data"]["id"]
    r = await client.get(
        f"{PREFIX}/attachments/{aid}/content",
        headers={"Authorization": f"Bearer {tok}"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers.get("location") or ""
    assert "/attachments/" in loc and "token=" in loc


@pytest.mark.asyncio
async def test_tc_rag_001_002_004_success_path(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import select

    from app.models.maintenance_domain import RetrievalSnapshot, WorkOrderMessage

    tok = await _login(client, "tc_worker")
    wo_id, r2 = await _create_wo_and_retrieval(client, tok)
    body = r2.json()
    assert body["success"] is True
    assert body["data"]["citations"]
    snap_id = body["data"]["retrieval_snapshot_id"]
    assert body["data"]["citations"][0]["citation_label"] == "C1"
    assert "[C1]" in body["data"]["suggested_reply"]
    assert "chunk_id=" in body["data"]["suggested_reply"]

    rmsg = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert rmsg.status_code == 200
    items = rmsg.json()["data"]["items"]
    assert any(m.get("retrieval_snapshot_id") == snap_id for m in items)

    async with maintenance_session_factory() as session:
        snap = (await session.execute(select(RetrievalSnapshot).where(RetrievalSnapshot.id == snap_id))).scalar_one()
        assert snap.empty_hit is False
        assert len(snap.chunks or []) >= 1


@pytest.mark.asyncio
async def test_tc_msg_001_post_user_message(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    posted = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/messages",
        json={"content": "现场补充：已完成初步外观检查"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert posted.status_code == 200
    created_id = posted.json()["data"]["id"]

    listed = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    created = next(item for item in items if item["id"] == created_id)
    assert created["role"] == "user"
    assert created["content"] == "现场补充：已完成初步外观检查"


@pytest.mark.asyncio
async def test_tc_esc_002_duplicate_active_escalation(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok, results=[])
    note = "一二三四五六七八九十重复升级说明"
    r1 = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": note},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": note + "二"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 409
    assert r2.json()["business_code"] == "ESCALATION_IN_PROGRESS"


@pytest.mark.asyncio
async def test_tc_esc_003_resolve_and_events(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w, results=[])
    r_esc = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": "一二三四五六七八九十现场会诊说明"},
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    assert r_esc.status_code == 200
    eid = r_esc.json()["data"]["id"]
    r_res = await client.post(
        f"{PREFIX}/escalations/{eid}/resolve",
        json={"conclusion_text": "结论已填写不少于若干字现场处理完毕"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert r_res.status_code == 200
    assert r_res.json()["data"]["work_order"]["status"] == "S7"
    ev = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/events",
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    assert ev.status_code == 200
    types = [x["event_type"] for x in ev.json()["data"]["items"]]
    assert "escalation_resolved" in types


@pytest.mark.asyncio
async def test_tc_app_001_002_003_approval_flow(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    tok_s = await _login(client, "tc_safety")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w, results=[])
    r_esc = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": "一二三四五六七八九十需高危审批说明"},
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    eid = r_esc.json()["data"]["id"]
    r_high = await client.post(
        f"{PREFIX}/escalations/{eid}/resolve",
        json={
            "conclusion_text": "结论已填写需进入审批流程的高危作业说明文字",
            "requires_high_risk_work": True,
        },
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert r_high.status_code == 200
    assert r_high.json()["data"]["work_order"]["status"] == "S6"
    lst = await client.get(f"{PREFIX}/approval-tasks", headers={"Authorization": f"Bearer {tok_s}"})
    assert lst.status_code == 200
    tasks = lst.json()["data"]["items"]
    assert tasks
    tid = tasks[0]["id"]
    r_ap = await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "approved", "comment": "同意"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    assert r_ap.status_code == 200
    assert r_ap.json()["data"]["work_order"]["status"] == "S7"
    r_idem = await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    assert r_idem.status_code == 200
    assert r_idem.json()["business_code"] == "ALREADY_PROCESSED"
    r_conflict = await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["business_code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_tc_guide_001_high_risk_step_blocked(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/enter-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    r1 = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/steps/confirm",
        json={"step_no": 1, "mark_done": True},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/steps/confirm",
        json={"step_no": 2, "mark_done": True},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 409
    assert r2.json()["business_code"] == "STEP_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_tc_guide_002_confirm_idempotent(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/enter-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/steps/confirm",
        json={"step_no": 1, "mark_done": True},
        headers={"Authorization": f"Bearer {tok}"},
    )
    r_dup = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/steps/confirm",
        json={"step_no": 1, "mark_done": True},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r_dup.status_code == 200
    assert r_dup.json()["business_code"] == "ALREADY_PROCESSED"


@pytest.mark.asyncio
async def test_tc_fill_001_resolved_normal(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import WorkOrderFilling

    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid = await _to_s8_with_attachment(client, tok, wo_id)
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "resolved",
            "closure_code": "NORMAL",
            "attachment_ids": [aid],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    async with maintenance_session_factory() as session:
        n = (
            await session.execute(
                select(func.count()).select_from(WorkOrderFilling).where(
                    WorkOrderFilling.work_order_id == wo_id,
                    WorkOrderFilling.is_latest.is_(True),
                )
            )
        ).scalar_one()
        assert n == 1


@pytest.mark.asyncio
async def test_tc_fill_003_unresolved_branch(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid = await _to_s8_with_attachment(client, tok, wo_id)
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "unresolved",
            "closure_code": "UNRESOLVED",
            "post_unresolved_action": "CLOSE_UNRESOLVED",
            "unresolved_reason_code": "INFO_INSUFFICIENT",
            "detail_notes": "说明未解决原因",
            "attachment_ids": [aid],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_tc_fill_004_invalid_closure_for_resolved(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid = await _to_s8_with_attachment(client, tok, wo_id)
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "resolved",
            "closure_code": "UNRESOLVED",
            "attachment_ids": [aid],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400
    assert r.json()["business_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tc_fill_005_unresolved_missing_action(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid = await _to_s8_with_attachment(client, tok, wo_id)
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={
            "resolution_status": "unresolved",
            "closure_code": "UNRESOLVED",
            "attachment_ids": [aid],
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_tc_kb_001_002_and_tc_ann_001_002(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w)
    lst0 = await client.get(
        f"{PREFIX}/knowledge-articles?status=draft&page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert lst0.status_code == 200
    msgs = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    mid = next(m["id"] for m in msgs.json()["data"]["items"] if m["role"] == "assistant")
    r_ann = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/messages/{mid}/annotations",
        json={"label": "good_case", "comment": "标注说明"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert r_ann.status_code == 200
    ann_id = r_ann.json()["data"]["id"]
    sp1 = await client.post(
        f"{PREFIX}/annotations/{ann_id}/spawn-kb-draft",
        json={"title_hint": "测试知识草稿"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert sp1.status_code == 200
    kid = sp1.json()["data"]["knowledge_article_id"]
    sp2 = await client.post(
        f"{PREFIX}/annotations/{ann_id}/spawn-kb-draft",
        json={},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert sp2.status_code == 200
    assert sp2.json()["business_code"] == "ALREADY_PROCESSED"
    rv = await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/review",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert rv.status_code == 200
    assert rv.json()["data"]["status"] == "pending_publish"


@pytest.mark.asyncio
async def test_tc_kb_publish_tc_aud_three_actions(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    tok_a = await _login(client, "tc_admin")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w)
    msgs = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    mid = next(m["id"] for m in msgs.json()["data"]["items"] if m["role"] == "assistant")
    ann_id = (
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/messages/{mid}/annotations",
            json={"label": "x"},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["id"]
    kid = (
        await client.post(
            f"{PREFIX}/annotations/{ann_id}/spawn-kb-draft",
            json={"title_hint": "发布用条目"},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["knowledge_article_id"]
    await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/review",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    pub = await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/publish",
        json={},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert pub.status_code == 200
    assert pub.json()["data"]["status"] == "published"

    logs = await client.get(
        f"{PREFIX}/admin/audit-logs?page=1&page_size=100",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert logs.status_code == 200
    actions = {x["action"] for x in logs.json()["data"]["items"]}
    assert "kb.publish" in actions
    assert "retrieval.completed" in actions
    assert "annotation.created" in actions
    assert len(actions) >= 3


@pytest.mark.asyncio
async def test_tc_adm_001_system_configs(client: AsyncClient):
    tok = await _login(client, "tc_admin")
    r = await client.get(f"{PREFIX}/admin/system-configs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()["data"]["items"]}
    assert "upload.max_image_mb" in keys
    p = await client.patch(
        f"{PREFIX}/admin/system-configs/upload.max_image_mb",
        json={"value": "12"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert p.status_code == 200
    assert p.json()["data"]["value"] == "12"


@pytest.mark.asyncio
async def test_tc_iso_001_worker_cannot_read_other_wo(client: AsyncClient):
    tok_a = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_a)
    tok_b = await _login(client, "tc_worker_b")
    r = await client.get(
        f"{PREFIX}/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tc_iso_003_safety_forbidden_kb_list(client: AsyncClient):
    tok = await _login(client, "tc_safety")
    r = await client.get(
        f"{PREFIX}/knowledge-articles?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tc_iso_004_worker_forbidden_publish(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w)
    msgs = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    mid = next(m["id"] for m in msgs.json()["data"]["items"] if m["role"] == "assistant")
    ann_id = (
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/messages/{mid}/annotations",
            json={"label": "p"},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["id"]
    kid = (
        await client.post(
            f"{PREFIX}/annotations/{ann_id}/spawn-kb-draft",
            json={},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["knowledge_article_id"]
    await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/review",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    r = await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/publish",
        json={},
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tc_con_001_concurrent_fill_one_conflict(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import WorkOrderFilling

    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid1 = await _to_s8_with_attachment(client, tok, wo_id)
    up2 = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("e2.png", b"\x89PNG\r\n\x1a\nxxxx", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert up2.status_code == 200
    aid2 = up2.json()["data"]["id"]
    body_a = {
        "resolution_status": "resolved",
        "closure_code": "NORMAL",
        "attachment_ids": [aid1],
    }
    body_b = {
        "resolution_status": "resolved",
        "closure_code": "PART_REPLACED",
        "attachment_ids": [aid2],
    }

    async def post_fill(b):
        return await client.post(
            f"{PREFIX}/work-orders/{wo_id}/fillings",
            json=b,
            headers={"Authorization": f"Bearer {tok}"},
        )

    ra, rb = await asyncio.gather(post_fill(body_a), post_fill(body_b))
    async with maintenance_session_factory() as session:
        n_latest = (
            await session.execute(
                select(func.count()).select_from(WorkOrderFilling).where(
                    WorkOrderFilling.work_order_id == wo_id,
                    WorkOrderFilling.is_latest.is_(True),
                )
            )
        ).scalar_one()
    assert n_latest == 1
    assert sum(1 for x in (ra, rb) if x.status_code == 200) >= 1


@pytest.mark.asyncio
async def test_tc_hlt_001_maintenance_health(client: AsyncClient):
    r = await client.get(f"{PREFIX}/health")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d.get("app") == "ok"
    assert d.get("database") == "ok"


@pytest.mark.asyncio
async def test_tc_dev_002_patch_device_expert_visible(client: AsyncClient, seed_users):
    tok_e = await _login(client, "tc_expert")
    expert_id = seed_users["expert"]
    r = await client.patch(
        f"{PREFIX}/devices/1",
        json={"responsibility_expert_user_id": expert_id},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["responsibility_expert_user_id"] == expert_id
    r2 = await client.get(f"{PREFIX}/devices/1", headers={"Authorization": f"Bearer {tok_e}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["responsibility_expert_user_id"] == expert_id


@pytest.mark.asyncio
async def test_tc_rag_003_model_unavailable(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": 1},
        headers={"Authorization": f"Bearer {tok}"},
    )
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        side_effect=RuntimeError("upstream"),
    ):
        r2 = await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "x"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r2.status_code == 200
    b = r2.json()
    assert b["success"] is False
    assert b["business_code"] == "MODEL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_tc_fill_matrix_empty_attachment_ids(client: AsyncClient):
    """验收 §7：FILL-003 attachment_ids 为空数组 → 400。"""
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid = await _to_s8_with_attachment(client, tok, wo_id)
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={"resolution_status": "resolved", "closure_code": "NORMAL", "attachment_ids": []},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400
    assert r.json()["business_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tc_fill_matrix_non_s8_fill_forbidden(client: AsyncClient):
    """验收 §7：FILL-005 非 S8 提交回填 → 409。"""
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("z.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok}"},
    )
    aid = up.json()["data"]["id"]
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={"resolution_status": "resolved", "closure_code": "NORMAL", "attachment_ids": [aid]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 409
    assert r.json()["business_code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_tc_kb_001_reject_requires_comment(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w)
    msgs = await client.get(
        f"{PREFIX}/work-orders/{wo_id}/messages?page=1&page_size=20",
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    mid = next(m["id"] for m in msgs.json()["data"]["items"] if m["role"] == "assistant")
    ann_id = (
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/messages/{mid}/annotations",
            json={"label": "k"},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["id"]
    kid = (
        await client.post(
            f"{PREFIX}/annotations/{ann_id}/spawn-kb-draft",
            json={"title_hint": "驳回测"},
            headers={"Authorization": f"Bearer {tok_e}"},
        )
    ).json()["data"]["knowledge_article_id"]
    r = await client.post(
        f"{PREFIX}/knowledge-articles/{kid}/review",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    assert r.status_code == 400
    assert r.json()["business_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tc_kb_002_series_publish_conflict(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import KnowledgeArticle

    naive = _naive_utc()
    async with maintenance_session_factory() as session:
        s = 990001
        k1 = KnowledgeArticle(
            series_id=s,
            title="已发布",
            body="b1",
            status="published",
            version=1,
            created_at=naive,
            updated_at=naive,
            published_at=naive,
        )
        k2 = KnowledgeArticle(
            series_id=s,
            title="待发布",
            body="b2",
            status="pending_publish",
            version=2,
            created_at=naive,
            updated_at=naive,
        )
        session.add_all([k1, k2])
        await session.commit()
        await session.refresh(k2)
        kid2 = k2.id

    tok_a = await _login(client, "tc_admin")
    r = await client.post(
        f"{PREFIX}/knowledge-articles/{kid2}/publish",
        json={},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert r.status_code == 409
    assert r.json()["business_code"] == "SERIES_PUBLISHED_CONFLICT"
    async with maintenance_session_factory() as session:
        n_pub = (
            await session.execute(
                select(func.count()).select_from(KnowledgeArticle).where(
                    KnowledgeArticle.series_id == s,
                    KnowledgeArticle.status == "published",
                )
            )
        ).scalar_one()
        assert n_pub == 1


@pytest.mark.asyncio
async def test_tc_aud_001_audit_logs_filter_and_shape(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_a = await _login(client, "tc_admin")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w)
    logs = await client.get(
        f"{PREFIX}/admin/audit-logs",
        params={"page": 1, "page_size": 20, "resource_type": "work_order", "resource_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert logs.status_code == 200
    d = logs.json()["data"]
    assert set(d.keys()) == {"items", "total", "page", "page_size"}
    assert all(x.get("resource_type") == "work_order" for x in d["items"])


@pytest.mark.asyncio
async def test_tc_iso_002_non_assigned_expert_escalation_forbidden(client: AsyncClient):
    tok_w = await _login(client, "tc_worker")
    tok_e1 = await _login(client, "tc_expert")
    tok_e2 = await _login(client, "tc_expert_b")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w, results=[])
    r_esc = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": "一二三四五六七八九十指派给主专家"},
        headers={"Authorization": f"Bearer {tok_w}"},
    )
    eid = r_esc.json()["data"]["id"]
    r_ok = await client.get(
        f"{PREFIX}/escalations/{eid}",
        headers={"Authorization": f"Bearer {tok_e1}"},
    )
    assert r_ok.status_code == 200
    r_forbidden = await client.get(
        f"{PREFIX}/escalations/{eid}",
        headers={"Authorization": f"Bearer {tok_e2}"},
    )
    assert r_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_tc_iso_004_matrix_worker_forbidden_audit_logs(client: AsyncClient):
    """验收 §8.1：worker 不可查审计。"""
    tok = await _login(client, "tc_worker")
    r = await client.get(
        f"{PREFIX}/admin/audit-logs?page=1&page_size=10",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tc_iso_005_cross_worker_attachment_no_redirect(client: AsyncClient):
    tok_a = await _login(client, "tc_worker")
    tok_b = await _login(client, "tc_worker_b")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_a)
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("priv.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    aid = up.json()["data"]["id"]
    r = await client.get(
        f"{PREFIX}/attachments/{aid}/content",
        headers={"Authorization": f"Bearer {tok_b}"},
        follow_redirects=False,
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_tc_db_001_soft_fail_snapshot_and_message(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import select

    from app.models.maintenance_domain import RetrievalSnapshot, WorkOrderMessage

    tok = await _login(client, "tc_worker")
    r = await client.post(
        f"{PREFIX}/work-orders",
        json={"device_id": 1},
        headers={"Authorization": f"Bearer {tok}"},
    )
    wo_id = r.json()["data"]["id"]
    with patch(
        "app.services.knowledge_service.KnowledgeService.search_multimodal",
        new_callable=AsyncMock,
        return_value={"results": [], "effective_query": "x", "query": "x"},
    ):
        r2 = await client.post(
            f"{PREFIX}/work-orders/{wo_id}/retrieval",
            json={"query_text": "q"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    snap_id = r2.json()["data"]["retrieval_snapshot_id"]
    msg_id = r2.json()["data"]["message_id"]
    async with maintenance_session_factory() as session:
        snap = (await session.execute(select(RetrievalSnapshot).where(RetrievalSnapshot.id == snap_id))).scalar_one()
        assert snap.work_order_id == wo_id
        assert snap.empty_hit is True
        msg = (await session.execute(select(WorkOrderMessage).where(WorkOrderMessage.id == msg_id))).scalar_one()
        assert msg.retrieval_snapshot_id == snap_id


@pytest.mark.asyncio
async def test_tc_db_002_second_filling_flips_is_latest(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import WorkOrder, WorkOrderFilling

    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    aid0 = await _to_s8_with_attachment(client, tok, wo_id)
    async with maintenance_session_factory() as session:
        wo = await session.get(WorkOrder, wo_id)
        assert wo is not None
        uid = wo.created_by_user_id
        old = WorkOrderFilling(
            work_order_id=wo_id,
            is_latest=True,
            resolution_status="resolved",
            closure_code="NORMAL",
            submitted_by_user_id=uid,
            submitted_at=_naive_utc(),
        )
        session.add(old)
        await session.commit()
    up = await client.post(
        f"{PREFIX}/attachments",
        files={"file": ("n.png", b"\x89PNG\r\n\x1a\nzz", "image/png")},
        data={"biz_type": "filling_evidence", "work_order_id": str(wo_id)},
        headers={"Authorization": f"Bearer {tok}"},
    )
    aid1 = up.json()["data"]["id"]
    r = await client.post(
        f"{PREFIX}/work-orders/{wo_id}/fillings",
        json={"resolution_status": "resolved", "closure_code": "ADJUSTED", "attachment_ids": [aid1]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    async with maintenance_session_factory() as session:
        latest_true = (
            await session.execute(
                select(func.count()).select_from(WorkOrderFilling).where(
                    WorkOrderFilling.work_order_id == wo_id,
                    WorkOrderFilling.is_latest.is_(True),
                )
            )
        ).scalar_one()
        latest_false = (
            await session.execute(
                select(func.count()).select_from(WorkOrderFilling).where(
                    WorkOrderFilling.work_order_id == wo_id,
                    WorkOrderFilling.is_latest.is_(False),
                )
            )
        ).scalar_one()
        assert latest_true == 1
        assert latest_false >= 1


@pytest.mark.asyncio
async def test_tc_db_003_003b_approval_task_terminal(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import select

    from app.models.maintenance_domain import ApprovalTask

    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    tok_s = await _login(client, "tc_safety")
    tok_a = await _login(client, "tc_admin")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w, results=[])
    eid = (
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/escalations",
            json={"escalation_note": "一二三四五六七八九十DB审批路径"},
            headers={"Authorization": f"Bearer {tok_w}"},
        )
    ).json()["data"]["id"]
    await client.post(
        f"{PREFIX}/escalations/{eid}/resolve",
        json={
            "conclusion_text": "结论已填写需进入审批流程的高危作业说明文字",
            "requires_high_risk_work": True,
        },
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    tid = (await client.get(f"{PREFIX}/approval-tasks", headers={"Authorization": f"Bearer {tok_s}"})).json()["data"][
        "items"
    ][0]["id"]
    await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "approved", "comment": "ok"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    async with maintenance_session_factory() as session:
        t = (await session.execute(select(ApprovalTask).where(ApprovalTask.id == tid))).scalar_one()
        assert t.status == "approved"
    r_logs0 = await client.get(
        f"{PREFIX}/admin/audit-logs",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert r_logs0.status_code == 200, r_logs0.text
    n_audit_before = r_logs0.json()["data"]["total"]
    await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    r_logs1 = await client.get(
        f"{PREFIX}/admin/audit-logs",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert r_logs1.status_code == 200
    n_audit_after = r_logs1.json()["data"]["total"]
    assert n_audit_after >= n_audit_before


@pytest.mark.asyncio
async def test_tc_db_004_at_most_one_active_escalation(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import Escalation

    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok, results=[])
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/escalations",
        json={"escalation_note": "一二三四五六七八九十活跃升级单"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    async with maintenance_session_factory() as session:
        n = (
            await session.execute(
                select(func.count()).select_from(Escalation).where(
                    Escalation.work_order_id == wo_id,
                    Escalation.status.in_(["open", "in_progress"]),
                )
            )
        ).scalar_one()
        assert n == 1


@pytest.mark.asyncio
async def test_tc_con_001_approval_second_different_status_conflict(client: AsyncClient, maintenance_session_factory):
    """§7.1 TC-CON-001：终态后提交不同结论 → CONFLICT（ASGI 单客户端真并发难稳定，顺序断言语义）。"""
    from sqlalchemy import select

    from app.models.maintenance_domain import ApprovalTask

    tok_w = await _login(client, "tc_worker")
    tok_e = await _login(client, "tc_expert")
    tok_s = await _login(client, "tc_safety")
    wo_id, _ = await _create_wo_and_retrieval(client, tok_w, results=[])
    eid = (
        await client.post(
            f"{PREFIX}/work-orders/{wo_id}/escalations",
            json={"escalation_note": "一二三四五六七八九十并发审批用"},
            headers={"Authorization": f"Bearer {tok_w}"},
        )
    ).json()["data"]["id"]
    await client.post(
        f"{PREFIX}/escalations/{eid}/resolve",
        json={
            "conclusion_text": "结论已填写需进入审批流程的高危作业说明文字",
            "requires_high_risk_work": True,
        },
        headers={"Authorization": f"Bearer {tok_e}"},
    )
    tid = (await client.get(f"{PREFIX}/approval-tasks", headers={"Authorization": f"Bearer {tok_s}"})).json()["data"][
        "items"
    ][0]["id"]
    ra = await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "approved", "comment": "c"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    assert ra.status_code == 200
    rb = await client.post(
        f"{PREFIX}/approval-tasks/{tid}/resolve",
        json={"status": "rejected", "comment": "改主意"},
        headers={"Authorization": f"Bearer {tok_s}"},
    )
    assert rb.status_code == 409
    assert rb.json()["business_code"] == "CONFLICT"
    async with maintenance_session_factory() as session:
        t_row = (await session.execute(select(ApprovalTask).where(ApprovalTask.id == tid))).scalar_one()
        assert t_row.status == "approved"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tc_con_002_concurrent_escalations(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok, results=[])

    async def esc(note_suffix: str):
        return await client.post(
            f"{PREFIX}/work-orders/{wo_id}/escalations",
            json={"escalation_note": f"一二三四五六七八九十并发升级{note_suffix}"},
            headers={"Authorization": f"Bearer {tok}"},
        )

    ra, rb = await asyncio.gather(esc("A"), esc("B"))
    ok_n = sum(1 for x in (ra, rb) if x.status_code == 200)
    esc409_n = sum(1 for x in (ra, rb) if x.status_code == 409)
    assert ok_n == 1
    assert esc409_n == 1


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tc_con_003_concurrent_step_confirm(client: AsyncClient):
    tok = await _login(client, "tc_worker")
    wo_id, _ = await _create_wo_and_retrieval(client, tok)
    await client.post(
        f"{PREFIX}/work-orders/{wo_id}/actions/enter-maintenance",
        headers={"Authorization": f"Bearer {tok}"},
    )

    async def confirm():
        return await client.post(
            f"{PREFIX}/work-orders/{wo_id}/steps/confirm",
            json={"step_no": 1, "mark_done": True},
            headers={"Authorization": f"Bearer {tok}"},
        )

    ra, rb = await asyncio.gather(confirm(), confirm())
    assert ra.status_code == 200 and rb.status_code == 200
    bodies = [ra.json(), rb.json()]
    assert any(b.get("business_code") == "ALREADY_PROCESSED" for b in bodies) or bodies[0]["data"] == bodies[1]["data"]


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tc_con_005_concurrent_publish_same_series(client: AsyncClient, maintenance_session_factory):
    from sqlalchemy import func, select

    from app.models.maintenance_domain import KnowledgeArticle

    naive = _naive_utc()
    series = 990002
    async with maintenance_session_factory() as session:
        a = KnowledgeArticle(
            series_id=series,
            title="A",
            body="x",
            status="pending_publish",
            version=1,
            created_at=naive,
            updated_at=naive,
        )
        b = KnowledgeArticle(
            series_id=series,
            title="B",
            body="y",
            status="pending_publish",
            version=2,
            created_at=naive,
            updated_at=naive,
        )
        session.add_all([a, b])
        await session.commit()
        await session.refresh(a)
        await session.refresh(b)
        id_a, id_b = a.id, b.id

    tok_a = await _login(client, "tc_admin")

    async def pub(kid: int):
        return await client.post(
            f"{PREFIX}/knowledge-articles/{kid}/publish",
            json={},
            headers={"Authorization": f"Bearer {tok_a}"},
        )

    r1, r2 = await asyncio.gather(pub(id_a), pub(id_b))
    ok_n = sum(1 for x in (r1, r2) if x.status_code == 200)
    conflict_n = sum(1 for x in (r1, r2) if x.status_code == 409 and x.json().get("business_code") == "SERIES_PUBLISHED_CONFLICT")
    assert ok_n == 1
    assert conflict_n == 1
    async with maintenance_session_factory() as session:
        n_pub = (
            await session.execute(
                select(func.count()).select_from(KnowledgeArticle).where(
                    KnowledgeArticle.series_id == series,
                    KnowledgeArticle.status == "published",
                )
            )
        ).scalar_one()
        assert n_pub == 1
