"""Phase 22: Agent tool registry and safety guardrails."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.agents import AgentAssistRequest
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.services.maintenance_safety_service import MaintenanceSafetyService


@pytest.mark.asyncio
async def test_agent_assist_returns_tool_calls_and_authorization_flags():
    """Emergency work orders should surface tool calls and authorization requirements."""
    service = AgentOrchestrationService(session=SimpleNamespace())
    service.knowledge_service.search_multimodal = AsyncMock(
        return_value={
            "query": "发动机温度偏高并伴随焦糊味，需要先确认冷却状态。",
            "effective_query": "发动机 温度偏高 焦糊味 冷却状态",
            "effective_keywords": ["温度偏高", "焦糊味", "冷却状态"],
            "image_analysis": None,
            "results": [],
        }
    )
    service._store_run = AsyncMock()
    service.task_service._load_knowledge_refs = AsyncMock(
        return_value=[
            {
                "chunk_id": 11,
                "document_id": 2,
                "title": "摩托车发动机维修手册",
                "source_name": "manual.pdf",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "温度偏高",
                "section_reference": "1.1",
                "page_reference": "P1",
                "excerpt": "拆检前必须确认发动机完成停机冷却。",
            }
        ]
    )
    service.task_service._ensure_template = AsyncMock(
        return_value=SimpleNamespace(
            steps=[
                SimpleNamespace(
                    title="试车验证与结果确认",
                    instruction_template="执行试车并确认 {symptom_text} 是否解除。",
                    risk_warning="高温状态下禁止直接试车。",
                    caution="确保周边区域清场。",
                    confirmation_text="已完成试车验证",
                    required_tools=["试车检测表"],
                    required_materials=["结果确认单"],
                    estimated_minutes=18,
                )
            ]
        )
    )
    service.case_service.recommend_cases = AsyncMock(return_value=[])

    payload = await service.assist(
        AgentAssistRequest(
            query="发动机温度偏高并伴随焦糊味，需要先确认冷却状态。",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            maintenance_level="emergency",
            priority="urgent",
            selected_chunk_ids=[11],
        )
    )

    assert [item["tool_name"] for item in payload["tool_calls"]] == [
        "query_device_telemetry",
        "fetch_historical_repairs",
        "validate_safety_preconditions",
        "require_human_authorization",
    ]
    assert payload["execution_brief"]["authorization_required"] is True
    assert payload["execution_brief"]["status"] == "review_required"
    assert payload["task_plan_preview"][0]["requires_manual_authorization"] is True
    assert payload["task_plan_preview"][0]["safety_preconditions"]


def test_build_step_guardrails_marks_urgent_validation_step():
    """Urgent validation steps should require manual authorization."""
    payload = MaintenanceSafetyService.build_step_guardrails(
        step_title="试车验证与结果确认",
        step_order=5,
        maintenance_level="standard",
        priority="urgent",
        symptom_description="发动机高温并伴随机油渗漏风险",
        has_image=True,
        knowledge_locked=True,
        risk_warning="试车前确认高温部位已冷却。",
    )

    assert payload["requires_manual_authorization"] is True
    assert payload["authorization_hint"] is not None
    assert any("试车区域" in item for item in payload["safety_preconditions"])
