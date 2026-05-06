"""Phase 18: 正式工作台与 Agent 协作骨架测试."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app
from app.schemas.agents import AgentAssistRequest
from app.services.agent_orchestration_service import AgentOrchestrationService


@pytest.fixture(autouse=True)
def override_db_session():
    """覆盖数据库依赖，避免端点测试落到真实数据库。"""

    async def _override_get_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_workbench_overview_endpoint():
    """工作台概览端点返回聚合统计和最近业务项。"""
    mocked_payload = {
        "generated_at": datetime.now(timezone.utc),
        "stats": [
            {"key": "knowledge_documents", "label": "知识文档", "value": 12, "accent": "cyan"},
            {"key": "knowledge_chunks", "label": "知识分段", "value": 88, "accent": "blue"},
        ],
        "featured_queries": ["火花塞", "冷启动困难"],
        "agent_capabilities": ["KnowledgeRetrieverAgent", "WorkOrderPlannerAgent"],
        "quality_highlights": [
            {
                "key": "eval_top1",
                "label": "Top1 命中率",
                "value": "66.67%",
                "description": "8/12",
                "accent": "cyan",
            }
        ],
        "runtime_highlights": [
            {
                "key": "runtime_search_requests",
                "label": "知识检索请求",
                "value": "12",
                "description": "平均 42 ms",
                "accent": "blue",
            }
        ],
        "recent_tasks": [
            {
                "id": 1,
                "title": "LX200 启动困难检修任务",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "maintenance_level": "standard",
                "status": "in_progress",
                "total_steps": 5,
                "completed_steps": 2,
                "updated_at": datetime.now(timezone.utc),
            }
        ],
        "recent_cases": [
            {
                "id": 3,
                "title": "火花塞积碳复盘案例",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "status": "pending_review",
                "task_id": 1,
                "updated_at": datetime.now(timezone.utc),
            }
        ],
    }

    with patch(
        "app.routers.workbench.WorkbenchOverviewService.build_overview",
        new=AsyncMock(return_value=mocked_payload),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/workbench/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"][0]["label"] == "知识文档"
    assert payload["featured_queries"] == ["火花塞", "冷启动困难"]
    assert payload["quality_highlights"][0]["label"] == "Top1 命中率"
    assert payload["runtime_highlights"][0]["value"] == "12"
    assert payload["recent_tasks"][0]["equipment_model"] == "LX200"


@pytest.mark.asyncio
async def test_agent_assist_endpoint():
    """Agent 协作端点返回统一的协作摘要结构。"""
    mocked_payload = {
        "run_id": "agent-run-123",
        "status": "completed",
        "summary": "已完成知识召回、步骤规划和风险校验。",
        "request_context": {
            "work_order_id": "WO-20260331-01",
            "asset_code": "ENG-LX200-01",
            "report_source": "巡检上报",
            "priority": "high",
            "maintenance_level": "standard",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "启动困难",
            "symptom_description": "发动机冷启动困难，伴随火花塞积碳",
            "selected_chunk_ids": [11, 12],
            "has_image": False,
        },
        "execution_brief": {
            "status": "ready",
            "decision": "知识依据、步骤预案和风险提示已形成，可进入标准检修执行准备。",
            "recommended_path": "标准检修流程",
            "next_actions": ["先锁定 2 条知识依据，并记录章节或页码。"],
        },
        "effective_query": "冷启动困难 火花塞 积碳",
        "effective_keywords": ["冷启动困难", "火花塞", "积碳"],
        "image_analysis": None,
        "knowledge_results": [],
        "related_cases": [
            {
                "id": 5,
                "title": "火花塞积碳复盘案例",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "status": "approved",
                "task_id": 2,
                "updated_at": datetime.now(timezone.utc),
                "match_reason": "同型号 LX200、已审核入库",
            }
        ],
        "task_plan_preview": [
            {
                "step_order": 1,
                "title": "检修前安全隔离",
                "instruction": "先完成安全隔离。",
                "risk_warning": "高温状态下禁止拆检。",
                "caution": None,
                "confirmation_text": "已确认",
            }
        ],
        "risk_findings": ["高温状态下禁止拆检。"],
        "case_suggestions": ["建议检修完成后沉淀案例。"],
        "agents": [
            {
                "agent_name": "KnowledgeRetrieverAgent",
                "title": "知识召回与引用整理",
                "status": "completed",
                "summary": "命中 3 条知识。",
                "citations": ["发动机维修手册#P1"],
            }
        ],
        "created_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.routers.agents.AgentOrchestrationService.assist",
        new=AsyncMock(return_value=mocked_payload),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/assist",
                json={
                    "query": "发动机冷启动困难，伴随火花塞积碳",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "agent-run-123"
    assert payload["agents"][0]["agent_name"] == "KnowledgeRetrieverAgent"
    assert payload["task_plan_preview"][0]["title"] == "检修前安全隔离"
    assert payload["request_context"]["work_order_id"] == "WO-20260331-01"
    assert payload["execution_brief"]["status"] == "ready"
    assert payload["related_cases"][0]["title"] == "火花塞积碳复盘案例"


@pytest.mark.asyncio
async def test_agent_assist_supports_selected_chunk_only_input():
    """即使只有已选知识条目，也应能生成 Agent 协作预案。"""
    service = AgentOrchestrationService(session=SimpleNamespace())
    service.knowledge_service.search_multimodal = AsyncMock()
    service._store_run = AsyncMock()
    service.task_service._load_knowledge_refs = AsyncMock(
        return_value=[
            {
                "chunk_id": 11,
                "document_id": 2,
                "title": "摩托车发动机维修手册",
                "source_name": "manual.pdf",
                "equipment_type": "摩托车发动机",
                "equipment_model": None,
                "fault_type": "启动困难",
                "section_reference": "1.1",
                "page_reference": "P1",
                "excerpt": "检查火花塞积碳和点火系统连接状态。",
            }
        ]
    )
    service.task_service._ensure_template = AsyncMock(
        return_value=SimpleNamespace(
            steps=[
                SimpleNamespace(
                    title="检修前安全确认",
                    instruction_template="确认 {equipment_type}{equipment_model_suffix} 已熄火后开始检修。",
                    risk_warning="高温状态下严禁直接拆检。",
                    caution="检查防护状态。",
                    confirmation_text="已完成安全确认",
                )
            ]
        )
    )
    service.case_service.recommend_cases = AsyncMock(return_value=[])

    payload = await service.assist(AgentAssistRequest(selected_chunk_ids=[11]))

    service.knowledge_service.search_multimodal.assert_not_called()
    service._store_run.assert_awaited_once()
    assert payload["task_plan_preview"][0]["title"] == "检修前安全确认"
    assert payload["agents"][0]["agent_name"] == "KnowledgeRetrieverAgent"
    assert payload["request_context"]["selected_chunk_ids"] == [11]


@pytest.mark.asyncio
async def test_build_diagnosis_report_uses_llm_for_procedural_queries():
    """步骤类问题也应进入正式生成链路，而不是在本地快速拼装后提前返回。"""

    class FakeLLM:
        def __init__(self):
            self.invoked = False

        def invoke(self, _messages):
            self.invoked = True
            return SimpleNamespace(
                content=(
                    '{"answer_mode":"procedure","most_likely_fault":"拆卸气缸头","risk_level":"中风险",'
                    '"confidence":86,"main_symptoms":["需要拆卸气缸头","按手册执行操作"],'
                    '"preliminary_conclusion":"这是拆卸气缸头步骤，已按最新召回依据重新整理。",'
                    '"next_steps":[{"step_no":1,"title":"排放机油","summary":"先完成放油","sections":[],"meta":[],"raw_text":"1. 排放机油"},'
                    '{"step_no":2,"title":"拆下相关固定件","summary":"按顺序拆卸","sections":[],"meta":[],"raw_text":"2. 拆下相关固定件"}],'
                    '"root_causes":[],"evidence_items":[{"document_title":"摩托车发动机维修手册","chunk_id":101,'
                    '"citation_label":"C1","section":"3.2 拆卸发动机","excerpt":"1. 排放机油。","source_name":"manual.pdf","relevance_score":88},'
                    '{"document_title":"摩托车发动机维修手册","chunk_id":102,"citation_label":"C2","section":"3.2 拆卸发动机",'
                    '"excerpt":"2. 拆下相关固定件。","source_name":"manual.pdf","relevance_score":84}],"evidence_count":2,'
                    '"top_similarity":88,"work_order_ready":false}'
                )
            )

    fake_llm = FakeLLM()
    service = AgentOrchestrationService(session=SimpleNamespace())

    with patch("app.services.agent_orchestration_service.create_llm", return_value=fake_llm):
        payload, report = await service._build_diagnosis_report(
            AgentAssistRequest(
                query="拆卸气缸头步骤",
                equipment_type="摩托车发动机",
                maintenance_level="standard",
            ),
            query_type="procedural",
            retrieval_results=[
                {
                    "chunk_id": 101,
                    "citation_label": "C1",
                    "title": "摩托车发动机维修手册",
                    "section_reference": "3.2 拆卸发动机",
                    "section_path": "三、发动机 > 3.2 拆卸发动机",
                    "excerpt": "1. 排放机油。",
                    "source_name": "manual.pdf",
                },
                {
                    "chunk_id": 102,
                    "citation_label": "C2",
                    "title": "摩托车发动机维修手册",
                    "section_reference": "3.2 拆卸发动机",
                    "section_path": "三、发动机 > 3.2 拆卸发动机",
                    "excerpt": "2. 拆下相关固定件。",
                    "source_name": "manual.pdf",
                },
            ],
            task_preview=[
                {"title": "排放机油"},
                {"title": "拆下相关固定件"},
            ],
            related_cases=[],
            risk_findings=[],
            execution_brief={"status": "ready", "decision": "可按标准步骤执行", "next_actions": ["按步骤执行"]},
            emit=None,
        )

    assert fake_llm.invoked is True
    assert payload["answer_mode"] == "procedure"
    assert payload["next_steps"][0]["title"] == "排放机油"
    assert "拆卸气缸头" in report
