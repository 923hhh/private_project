"""Phase 16: 案例沉淀、审核与人工修正测试."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app
from app.schemas.cases import MaintenanceCaseCreate


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


def build_case_payload(status: str = "pending_review", source_document_id: int | None = None) -> dict:
    return {
        "id": 301,
        "title": "摩托车发动机 LX200 启动困难案例",
        "work_order_id": "WO-20260331-01",
        "asset_code": "ENG-LX200-01",
        "report_source": "巡检上报",
        "priority": "high",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": "启动困难",
        "task_id": 101,
        "symptom_description": "发动机启动困难，点火异常，伴随冷启动失败。",
        "processing_steps": [
            "确认熄火断电并完成安全隔离。",
            "检查火花塞、电极积碳和点火线圈连接状态。",
            "更换异常火花塞并完成试车验证。",
        ],
        "resolution_summary": "已更换火花塞并清理积碳，试车后恢复正常启动。",
        "attachment_name": "spark-plug.jpg",
        "attachment_url": "https://example.com/spark-plug.jpg",
        "knowledge_refs": [
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
                "excerpt": "发动机启动困难时，应优先检查火花塞与供油系统。",
            }
        ],
        "status": status,
        "reviewer_name": "评审老师" if status != "pending_review" else None,
        "review_note": "案例描述完整，适合纳入知识库。" if status != "pending_review" else None,
        "reviewed_at": None,
        "source_document_id": source_document_id,
        "corrections": [
            {
                "id": 1,
                "correction_target": "summary",
                "original_content": "更换点火线圈",
                "corrected_content": "更换火花塞并清理积碳",
                "note": "根据现场记录修正最终总结。",
                "status": "accepted",
                "created_at": None,
            }
        ],
        "created_at": None,
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_create_maintenance_case_endpoint():
    """上传案例端点返回待审核案例详情。"""
    with patch(
        "app.routers.cases.MaintenanceCaseService.create_case",
        new=AsyncMock(return_value=build_case_payload()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/cases",
                json={
                    "title": "摩托车发动机 LX200 启动困难案例",
                    "work_order_id": "WO-20260331-01",
                    "asset_code": "ENG-LX200-01",
                    "report_source": "巡检上报",
                    "priority": "high",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "fault_type": "启动困难",
                    "task_id": 101,
                    "symptom_description": "发动机启动困难，点火异常，伴随冷启动失败。",
                    "processing_steps": [
                        "确认熄火断电并完成安全隔离。",
                        "检查火花塞、电极积碳和点火线圈连接状态。",
                    ],
                    "resolution_summary": "已更换火花塞并清理积碳，试车后恢复正常启动。",
                    "knowledge_refs": [
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
                            "excerpt": "发动机启动困难时，应优先检查火花塞与供油系统。",
                        }
                    ],
                },
            )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending_review"
    assert data["task_id"] == 101
    assert data["work_order_id"] == "WO-20260331-01"
    assert data["priority"] == "high"
    assert data["knowledge_refs"][0]["chunk_id"] == 11


@pytest.mark.asyncio
async def test_list_maintenance_cases_endpoint():
    """案例列表端点返回摘要列表。"""
    mocked_cases = [
        {
            "id": 301,
            "title": "摩托车发动机 LX200 启动困难案例",
            "work_order_id": "WO-20260331-01",
            "asset_code": "ENG-LX200-01",
            "report_source": "巡检上报",
            "priority": "high",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "启动困难",
            "status": "pending_review",
            "task_id": 101,
            "source_document_id": None,
            "created_at": None,
            "updated_at": None,
        }
    ]

    with patch(
        "app.routers.cases.MaintenanceCaseService.list_cases",
        new=AsyncMock(return_value=mocked_cases),
    ) as mocked_list_cases:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/cases?limit=5&status=pending_review&priority=high&work_order_id=WO-20260331"
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["cases"][0]["work_order_id"] == "WO-20260331-01"
    assert data["cases"][0]["priority"] == "high"
    assert data["cases"][0]["status"] == "pending_review"
    mocked_list_cases.assert_awaited_once_with(
        limit=5,
        status_filter="pending_review",
        priority_filter="high",
        work_order_id="WO-20260331",
    )


@pytest.mark.asyncio
async def test_add_case_correction_endpoint():
    """人工修正端点返回更新后的案例详情。"""
    with patch(
        "app.routers.cases.MaintenanceCaseService.add_correction",
        new=AsyncMock(return_value=build_case_payload()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/cases/301/corrections",
                json={
                    "correction_target": "summary",
                    "original_content": "更换点火线圈",
                    "corrected_content": "更换火花塞并清理积碳",
                    "note": "根据现场照片修正。",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["corrections"][0]["correction_target"] == "summary"
    assert data["corrections"][0]["corrected_content"] == "更换火花塞并清理积碳"


@pytest.mark.asyncio
async def test_review_case_endpoint_approves_and_returns_source_document():
    """审核通过端点会返回已入库文档标识。"""
    with patch(
        "app.routers.cases.MaintenanceCaseService.review_case",
        new=AsyncMock(return_value=build_case_payload(status="approved", source_document_id=88)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/cases/301/review",
                json={
                    "action": "approve",
                    "reviewer_name": "评审老师",
                    "review_note": "案例描述完整，允许入库。",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["source_document_id"] == 88


def test_maintenance_case_requires_steps_or_summary():
    """案例上传时至少需要处理步骤或结果总结。"""
    with pytest.raises(ValueError):
        MaintenanceCaseCreate(
            title="摩托车发动机 LX200 启动困难案例",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            symptom_description="发动机启动困难。",
            processing_steps=[],
            resolution_summary=None,
        )
