"""Phase 15: 标准化检修任务与作业闭环测试."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app
from app.modules.tasks.application.task_service import MaintenanceTaskService
from app.schemas.tasks import MaintenanceTaskCreate


@pytest.fixture(autouse=True)
def override_db_session():
    """覆盖数据库依赖，避免测试受本机驱动影响。"""

    async def _override_get_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


def build_task_payload(status: str = "in_progress", completed_steps: int = 0) -> dict:
    return {
        "id": 101,
        "title": "摩托车发动机 LX200 / 启动困难检修任务",
        "work_order_id": "WO-20260331-01",
        "asset_code": "ENG-LX200-01",
        "report_source": "巡检上报",
        "priority": "high",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "maintenance_level": "standard",
        "fault_type": "启动困难",
        "symptom_description": "发动机启动困难，点火异常。",
        "status": status,
        "advice_card": "智能建议：优先检查点火与供油系统。",
        "total_steps": 3,
        "completed_steps": completed_steps,
        "source_refs": [
            {
                "chunk_id": 11,
                "document_id": 2,
                "title": "发动机标准检修流程",
                "source_name": "engine_manual.pdf",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "section_reference": "第 2 章",
                "page_reference": "P12",
                "excerpt": "先检查火花塞、供油和压缩比。",
            }
        ],
        "steps": [
            {
                "id": 1,
                "step_order": 1,
                "title": "检修前安全隔离",
                "instruction": "确认发动机已停机断电。",
                "risk_warning": "禁止带电拆检。",
                "caution": "佩戴绝缘手套。",
                "confirmation_text": "已完成检修前安全隔离",
                "status": "completed" if completed_steps > 0 else "pending",
                "completion_note": "已执行" if completed_steps > 0 else None,
                "completed_at": None,
                "knowledge_refs": [],
            },
            {
                "id": 2,
                "step_order": 2,
                "title": "关键部件排查",
                "instruction": "检查点火和供油系统。",
                "risk_warning": "防止误喷油。",
                "caution": "先排查火花塞。",
                "confirmation_text": "已完成关键部件排查",
                "status": "pending",
                "completion_note": None,
                "completed_at": None,
                "knowledge_refs": [],
            },
        ],
        "created_at": None,
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_create_maintenance_task_endpoint():
    """创建任务端点返回标准步骤和智能建议。"""
    with patch(
        "app.routers.tasks.MaintenanceTaskService.create_task",
        new=AsyncMock(return_value=build_task_payload()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "work_order_id": "WO-20260331-01",
                    "asset_code": "ENG-LX200-01",
                    "report_source": "巡检上报",
                    "priority": "high",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "maintenance_level": "standard",
                    "fault_type": "启动困难",
                    "symptom_description": "发动机启动困难，点火异常。",
                    "source_chunk_ids": [11],
                },
            )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "摩托车发动机 LX200 / 启动困难检修任务"
    assert data["work_order_id"] == "WO-20260331-01"
    assert data["priority"] == "high"
    assert data["total_steps"] == 3
    assert data["advice_card"]


@pytest.mark.asyncio
async def test_create_task_serializes_datetime_inside_source_snapshot():
    """知识引用快照中的 datetime 应在入库前转成 JSON 安全字符串。"""
    session = SimpleNamespace(
        add=lambda *_args, **_kwargs: None,
        flush=AsyncMock(),
        commit=AsyncMock(),
    )
    service = MaintenanceTaskService(session=session)
    now = datetime.now(timezone.utc)
    template = SimpleNamespace(
        id=1,
        steps=[
            SimpleNamespace(
                id=11,
                step_order=1,
                title="检查火花塞",
                instruction_template="检查 {equipment_type}",
                risk_warning=None,
                caution=None,
                confirmation_text="已检查",
                required_tools=[],
                required_materials=[],
                estimated_minutes=5,
            )
        ],
    )
    service._ensure_template = AsyncMock(return_value=template)
    service._load_knowledge_refs = AsyncMock(
        return_value=[
            {
                "chunk_id": 1299,
                "title": "摩托车发动机维修手册",
                "_document_updated_at": now,
            }
        ]
    )
    service.get_task_detail = AsyncMock(return_value={"id": 1})

    captured: list[object] = []

    def capture_add(obj):
        captured.append(obj)
        if getattr(obj, "id", None) is None and obj.__class__.__name__ == "MaintenanceTask":
            obj.id = 1

    session.add = capture_add

    await service.create_task(
        MaintenanceTaskCreate(
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            maintenance_level="standard",
            fault_type="启动困难",
            symptom_description="发动机启动困难",
            source_chunk_ids=[1299],
        )
    )

    task = next(item for item in captured if item.__class__.__name__ == "MaintenanceTask")
    step = next(item for item in captured if item.__class__.__name__ == "MaintenanceTaskStep")
    assert task.source_snapshot[0]["_document_updated_at"] == now.isoformat()
    assert step.knowledge_refs[0]["_document_updated_at"] == now.isoformat()


@pytest.mark.asyncio
async def test_update_diagnosis_context_serializes_datetime_inside_source_snapshot():
    """诊断结果回写时也要避免把 datetime 直接写入 JSON 列。"""
    task = SimpleNamespace(
        diagnosis_report=None,
        source_chunk_ids=[],
        source_snapshot=[],
        status="pending",
        steps=[],
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: task)),
        commit=AsyncMock(),
    )
    service = MaintenanceTaskService(session=session)
    now = datetime.now(timezone.utc)

    await service.update_diagnosis_context(
        24,
        diagnosis_report="已生成诊断报告",
        source_chunk_ids=[1299],
        source_refs=[{"chunk_id": 1299, "_document_updated_at": now}],
    )

    assert task.source_snapshot == [{"chunk_id": 1299, "_document_updated_at": now.isoformat()}]
    assert task.status == "completed"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_task_detail_builds_fallback_timeline_when_report_exists():
    """若任务已有诊断结果但尚无 execution_timeline，应自动补完整闭环时间线。"""
    updated_at = datetime.now(timezone.utc)
    task = SimpleNamespace(
        id=24,
        title="摩托车检修任务",
        work_order_id=None,
        asset_code="ENG-01",
        report_source=None,
        priority="medium",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        maintenance_level="standard",
        fault_type="启动困难",
        symptom_description="启动困难",
        status="pending",
        advice_card=None,
        diagnosis_report="已生成诊断报告",
        source_snapshot=[],
        execution_timeline=[],
        steps=[],
        created_at=updated_at,
        updated_at=updated_at,
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: task)),
    )
    service = MaintenanceTaskService(session=session)

    detail = await service.get_task_detail(24)

    assert detail["status"] == "completed"
    assert len(detail["execution_timeline"]) == 4
    assert [event["type"] for event in detail["execution_timeline"]] == [
        "node_start",
        "node_finish",
        "report",
        "done",
    ]
    assert detail["execution_timeline"][-1]["title"] == "诊断结果已回写"


@pytest.mark.asyncio
async def test_update_maintenance_task_step_endpoint():
    """步骤更新端点会返回更新后的任务详情。"""
    with patch(
        "app.routers.tasks.MaintenanceTaskService.update_task_step",
        new=AsyncMock(return_value=build_task_payload(completed_steps=1)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/tasks/101/steps/1",
                json={"status": "completed", "completion_note": "已完成安全隔离"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["completed_steps"] == 1
    assert data["steps"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_maintenance_task_endpoint():
    """删除任务端点会调用服务层删除并返回 204。"""
    with patch(
        "app.routers.tasks.MaintenanceTaskService.delete_task",
        new=AsyncMock(return_value=None),
    ) as mocked_delete_task:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/tasks/101")

    assert response.status_code == 204
    mocked_delete_task.assert_awaited_once_with(101)


@pytest.mark.asyncio
async def test_upsert_maintenance_task_execution_timeline_endpoint():
    """时间线写入端点返回 204，并调用服务层写入。"""
    with patch(
        "app.routers.tasks.MaintenanceTaskService.upsert_execution_timeline",
        new=AsyncMock(return_value=None),
    ) as mocked_upsert:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/tasks/101/execution-timeline",
                json={
                    "events": [
                        {
                            "id": "connected-1",
                            "type": "connected",
                            "title": "SSE 连接建立",
                            "description": "已连接",
                            "time": "12:00:00",
                        }
                    ]
                },
            )

    assert response.status_code == 204
    mocked_upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_maintenance_history_endpoint():
    """历史端点返回任务摘要列表。"""
    mocked_history = [
        {
            "id": 101,
            "title": "摩托车发动机 LX200 / 启动困难检修任务",
            "work_order_id": "WO-20260331-01",
            "asset_code": "ENG-LX200-01",
            "report_source": "巡检上报",
            "priority": "high",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "maintenance_level": "standard",
            "status": "in_progress",
            "total_steps": 3,
            "completed_steps": 1,
            "created_at": None,
            "updated_at": None,
        }
    ]

    with patch(
        "app.routers.tasks.MaintenanceTaskService.list_history",
        new=AsyncMock(return_value=mocked_history),
    ) as mocked_list_history:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/history?limit=5&status=in_progress&priority=high&work_order_id=WO-20260331"
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["tasks"][0]["work_order_id"] == "WO-20260331-01"
    assert data["tasks"][0]["priority"] == "high"
    assert data["tasks"][0]["equipment_model"] == "LX200"
    mocked_list_history.assert_awaited_once_with(
        limit=5,
        status_filter="in_progress",
        priority_filter="high",
        work_order_id="WO-20260331",
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upsert_execution_timeline_marks_task_completed_when_report_is_saved():
    """一旦诊断报告被回写，任务与未完成步骤应立即切换为 completed。"""
    task = SimpleNamespace(
        id=101,
        status="pending",
        execution_timeline=[],
        diagnosis_report=None,
        steps=[
            SimpleNamespace(status="pending", completed_at=None),
            SimpleNamespace(status="in_progress", completed_at=None),
        ],
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: task)),
        commit=AsyncMock(),
    )
    service = MaintenanceTaskService(session=session)

    await service.upsert_execution_timeline(
        101,
        [{"id": "report-1", "type": "report", "title": "报告生成", "description": "已生成", "time": "12:00:00"}],
        diagnosis_report="■ 诊断结论\n已生成稳定诊断报告",
    )

    assert task.status == "completed"
    assert task.diagnosis_report == "■ 诊断结论\n已生成稳定诊断报告"
    assert all(step.status == "completed" for step in task.steps)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_history_uses_diagnosis_report_as_completion_signal():
    """历史列表在状态字段滞后时，也应按已保存报告显示为完成态。"""
    task = SimpleNamespace(
        id=7,
        title="摩托车检修任务",
        work_order_id=None,
        asset_code=None,
        report_source=None,
        priority="medium",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        maintenance_level="routine",
        status="pending",
        diagnosis_report="已生成报告",
        steps=[
            SimpleNamespace(status="pending"),
            SimpleNamespace(status="completed"),
        ],
        created_at=None,
        updated_at=None,
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [task]))),
    )
    service = MaintenanceTaskService(session=session)

    history = await service.list_history(limit=10)

    assert history[0]["status"] == "completed"
    assert history[0]["completed_steps"] == 2


@pytest.mark.asyncio
async def test_export_maintenance_task_endpoint():
    """导出端点返回任务详情和导出摘要。"""
    mocked_export = {
        "task": build_task_payload(status="completed", completed_steps=3),
        "exported_at": "2026-03-28T23:58:00",
        "export_summary": "任务已完成，共 3 步。",
    }

    with patch(
        "app.routers.tasks.MaintenanceTaskService.export_task",
        new=AsyncMock(return_value=mocked_export),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/export/101")

    assert response.status_code == 200
    data = response.json()
    assert data["task"]["status"] == "completed"
    assert data["export_summary"] == "任务已完成，共 3 步。"


def test_maintenance_task_requires_symptom_or_sources():
    """创建任务时至少要有故障描述或知识条目。"""
    with pytest.raises(ValueError):
        MaintenanceTaskCreate(
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            maintenance_level="standard",
        )
