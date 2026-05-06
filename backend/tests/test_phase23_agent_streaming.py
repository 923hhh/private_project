"""Phase 23: Agent SSE streaming for the formal workbench."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def override_db_session():
    """Override DB dependency for stream endpoint tests."""

    async def _override_get_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_agent_assist_stream_endpoint_emits_stage_events():
    """SSE endpoint should emit connected, staged events, payload and done."""

    mocked_payload = {
        "run_id": "agent-run-stream-1",
        "status": "completed",
        "summary": "流式协作已完成。",
        "request_context": {
            "work_order_id": "WO-20260331-09",
            "asset_code": "ENG-LX200-09",
            "report_source": "巡检上报",
            "priority": "high",
            "maintenance_level": "standard",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "启动困难",
            "symptom_description": "发动机冷启动困难",
            "selected_chunk_ids": [11],
            "has_image": False,
        },
        "execution_brief": {
            "status": "review_required",
            "decision": "需先完成人工授权。",
            "recommended_path": "标准检修流程",
            "next_actions": ["先完成人工授权。"],
            "blocking_issues": [],
            "authorization_required": True,
        },
        "effective_query": "冷启动困难 火花塞",
        "effective_keywords": ["冷启动困难", "火花塞"],
        "image_analysis": None,
        "knowledge_results": [],
        "related_cases": [],
        "task_plan_preview": [],
        "risk_findings": [],
        "case_suggestions": [],
        "agents": [],
        "tool_calls": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def fake_assist_stream(self, request, emit):
        await emit(
            {
                "event": "stage_start",
                "data": {"stage": "retrieval", "title": "知识召回与引用整理", "message": "正在召回。"},
            }
        )
        await emit(
            {
                "event": "tool_call",
                "data": {
                    "tool_name": "require_human_authorization",
                    "title": "人工授权判定",
                    "status": "required",
                    "summary": "当前需要人工授权。",
                    "blocking": True,
                    "requires_human_authorization": True,
                    "details": ["当前工单优先级为紧急。"],
                },
            }
        )
        await emit({"event": "payload", "data": mocked_payload})
        return mocked_payload

    with patch(
        "app.routers.agents.AgentOrchestrationService.assist_stream",
        new=fake_assist_stream,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            event_order: list[str] = []
            payload_data = ""
            async with client.stream(
                "GET",
                "/api/v1/agents/assist/stream",
                params={
                    "query": "发动机冷启动困难",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                },
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line.removeprefix("event:").strip()
                        event_order.append(event_type)
                    elif line.startswith("data:") and event_order and event_order[-1] == "payload":
                        payload_data = line.removeprefix("data:").strip()

    assert "connected" in event_order
    assert "stage_start" in event_order
    assert "tool_call" in event_order
    assert "payload" in event_order
    assert event_order[-1] == "done"
    assert "agent-run-stream-1" in payload_data


@pytest.mark.asyncio
async def test_agent_assist_stream_supports_selected_chunk_ids_query():
    """Repeated selected_chunk_ids query params should be preserved in the request model."""
    captured_chunk_ids: list[int] = []

    async def fake_assist_stream(self, request, emit):
        captured_chunk_ids.extend(request.selected_chunk_ids)
        await emit({"event": "payload", "data": {"run_id": "agent-run-stream-2"}})
        return {"run_id": "agent-run-stream-2"}

    with patch(
        "app.routers.agents.AgentOrchestrationService.assist_stream",
        new=fake_assist_stream,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "GET",
                "/api/v1/agents/assist/stream",
                params=[
                    ("query", "发动机异响"),
                    ("equipment_type", "摩托车发动机"),
                    ("selected_chunk_ids", "11"),
                    ("selected_chunk_ids", "12"),
                ],
            ) as response:
                assert response.status_code == 200
                async for _ in response.aiter_lines():
                    pass

    assert captured_chunk_ids == [11, 12]
