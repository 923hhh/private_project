"""Agent orchestration service for the formal workbench."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import increment_counter, observe_duration
from app.agents.diagnosis_agent import create_llm
from app.db.models.knowledge import AgentRun
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.modules.tasks.application.task_service import MaintenanceTaskService
from app.modules.tasks.schemas import MaintenanceTaskCreate
from app.modules.assistant.schemas import AgentAssistRequest
from app.modules.assistant.application.tooling_service import AgentToolingService
from app.modules.diagnosis.application.report_formatter import (
    build_structured_diagnosis,
    parse_llm_structured_json,
    render_structured_diagnosis_report,
)
from app.modules.cases.application.case_service import MaintenanceCaseService
from app.services.maintenance_safety_service import MaintenanceSafetyService
from app.services.answer_guard_service import (
    cleanup_answer,
    expand_query_for_corrective,
    maybe_revise_answer,
    score_retrieval_quality,
    should_trigger_corrective_retrieval,
)

logger = logging.getLogger(__name__)


def _stringify_step_items(steps: list[Any]) -> str:
    lines: list[str] = []
    for item in steps or []:
        raw_text = getattr(item, "raw_text", None)
        title = getattr(item, "title", None)
        candidate = raw_text or title
        if isinstance(candidate, str) and candidate.strip():
            lines.append(candidate.strip())
    return "\n".join(lines)


class AgentOrchestrationService:
    """Coordinate the new multi-agent workbench assistance flow."""

    EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.knowledge_service = KnowledgeService(session)
        self.task_service = MaintenanceTaskService(session)
        self.case_service = MaintenanceCaseService(session)
        self.tooling_service = AgentToolingService(session)
        self._active_task_id: int | None = None

    async def assist(self, request: AgentAssistRequest) -> dict[str, Any]:
        """Run the agent collaboration pipeline and persist a run snapshot."""
        return await self._run_pipeline(request)

    async def assist_stream(
        self,
        request: AgentAssistRequest,
        emit: EventCallback,
    ) -> dict[str, Any]:
        """Run the same pipeline but surface stage events for SSE clients."""
        return await self._run_pipeline(request, emit=emit)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch a stored agent run snapshot."""
        stmt = select(AgentRun).where(AgentRun.run_id == run_id)
        record = (await self.session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return None
        return dict(record.payload)

    async def _run_pipeline(
        self,
        request: AgentAssistRequest,
        emit: EventCallback | None = None,
    ) -> dict[str, Any]:
        """Execute the full Agent pipeline with optional stage-level events."""
        self._active_task_id = request.maintenance_task_id
        started_at = datetime.now(timezone.utc)
        await increment_counter(
            "agent_assist_requests_total",
            maintenance_level=request.maintenance_level,
            has_image=bool(request.image_base64),
        )
        retrieval_payload = {
            "query": request.query,
            "effective_query": request.query,
            "effective_keywords": [],
            "image_analysis": None,
            "results": [],
        }

        await self._emit_event(
            emit,
            "stage_start",
            {
                "stage": "retrieval",
                "title": "知识召回与引用整理",
                "message": "正在检索知识依据并整理有效查询词。",
            },
        )
        if any(
            [
                request.query,
                request.equipment_type,
                request.equipment_model,
                request.fault_type,
                request.image_base64,
            ]
        ):
            knowledge_request = KnowledgeSearchRequest(
                work_order_id=request.work_order_id,
                report_source=request.report_source,
                priority=request.priority,
                maintenance_level=request.maintenance_level,
                query=request.query,
                equipment_type=request.equipment_type,
                equipment_model=request.equipment_model,
                fault_type=request.fault_type,
                image_base64=request.image_base64,
                image_mime_type=request.image_mime_type,
                image_filename=request.image_filename,
                model_provider=request.model_provider,
                model_name=request.model_name,
                limit=request.limit,
            )
            retrieval_payload = await self.knowledge_service.search_multimodal(knowledge_request)
        retrieval_results = retrieval_payload["results"]

        # Corrective RAG: if retrieval quality is insufficient, do a second pass
        retrieval_quality = score_retrieval_quality(request.query or "", retrieval_results)
        if should_trigger_corrective_retrieval(retrieval_quality) and request.query:
            corrective_queries = expand_query_for_corrective(request.query)
            for cq in corrective_queries[1:]:  # skip original query
                corrective_request = KnowledgeSearchRequest(
                    query=cq,
                    equipment_type=request.equipment_type,
                    equipment_model=request.equipment_model,
                    fault_type=request.fault_type,
                    limit=request.limit,
                )
                try:
                    corrective_payload = await self.knowledge_service.search_multimodal(corrective_request)
                    new_results = corrective_payload.get("results", [])
                    existing_ids = {r["chunk_id"] for r in retrieval_results}
                    for r in new_results:
                        if r["chunk_id"] not in existing_ids:
                            retrieval_results.append(r)
                            existing_ids.add(r["chunk_id"])
                    if score_retrieval_quality(cq, retrieval_results) == "relevant":
                        break
                except Exception:
                    logger.debug("Corrective retrieval pass failed for query: %s", cq)
            retrieval_payload["results"] = retrieval_results
            logger.info(
                "Corrective RAG: quality=%s → %d total results after expansion",
                retrieval_quality,
                len(retrieval_results),
            )

        selected_chunk_ids = request.selected_chunk_ids or [
            item["chunk_id"] for item in retrieval_results[: min(3, len(retrieval_results))]
        ]
        await self._emit_event(
            emit,
            "stage_finish",
            {
                "stage": "retrieval",
                "title": "知识召回与引用整理",
                "summary": self._build_retrieval_summary(retrieval_payload["effective_query"], retrieval_results),
                "knowledge_count": len(retrieval_results),
                "selected_chunk_ids": selected_chunk_ids,
            },
        )

        await self._emit_event(
            emit,
            "stage_start",
            {
                "stage": "planning",
                "title": "作业步骤规划",
                "message": "正在根据知识依据生成标准化检修步骤。",
            },
        )
        knowledge_refs = await self.task_service._load_knowledge_refs(selected_chunk_ids)
        task_preview = await self._build_task_preview(request, knowledge_refs)
        await self._emit_event(
            emit,
            "stage_finish",
            {
                "stage": "planning",
                "title": "作业步骤规划",
                "summary": f"已生成 {len(task_preview)} 个标准化检修步骤预案。",
                "step_count": len(task_preview),
            },
        )

        await self._emit_event(
            emit,
            "stage_start",
            {
                "stage": "cases",
                "title": "案例沉淀建议",
                "message": "正在查询相似案例并准备沉淀建议。",
            },
        )
        related_cases = await self.case_service.recommend_cases(
            equipment_type=request.equipment_type,
            equipment_model=request.equipment_model,
            fault_type=request.fault_type or retrieval_payload.get("effective_query"),
            limit=3,
        )
        await self._emit_event(
            emit,
            "stage_finish",
            {
                "stage": "cases",
                "title": "案例沉淀建议",
                "summary": f"已命中 {len(related_cases)} 条相似案例。",
                "case_count": len(related_cases),
            },
        )

        await self._emit_event(
            emit,
            "stage_start",
            {
                "stage": "tools",
                "title": "工具执行与合规校验",
                "message": "正在执行遥测、案例、前置条件和人工授权工具。",
            },
        )
        tool_chain = await self.tooling_service.run_tool_chain(
            request=request,
            knowledge_refs=knowledge_refs,
            task_preview=task_preview,
            related_cases=related_cases,
        )
        tool_calls = tool_chain["tool_calls"]
        for tool_call in tool_calls:
            await self._emit_event(
                emit,
                "tool_call",
                {
                    "tool_name": tool_call["tool_name"],
                    "title": tool_call["title"],
                    "status": tool_call["status"],
                    "summary": tool_call["summary"],
                    "blocking": tool_call["blocking"],
                    "requires_human_authorization": tool_call["requires_human_authorization"],
                    "details": tool_call.get("details") or [],
                },
            )

        case_suggestions = self._build_case_suggestions(request, knowledge_refs, related_cases)
        risk_findings = self._build_risk_findings(
            request,
            task_preview,
            knowledge_refs,
            tool_calls,
        )
        execution_brief = self._build_execution_brief(
            request,
            retrieval_results,
            selected_chunk_ids,
            task_preview,
            related_cases,
            tool_calls,
            risk_findings,
        )
        diagnosis_structured, diagnosis_report = await self._build_diagnosis_report(
            request,
            retrieval_payload.get("query_type") or "text_related",
            retrieval_results,
            task_preview,
            related_cases,
            risk_findings,
            execution_brief,
            emit=emit,
        )
        await self._emit_event(
            emit,
            "stage_finish",
            {
                "stage": "tools",
                "title": "工具执行与合规校验",
                "summary": execution_brief["decision"],
                "authorization_required": execution_brief["authorization_required"],
                "blocking_issues": execution_brief["blocking_issues"],
            },
        )
        await self._emit_event(
            emit,
            "report",
            {
                "report": diagnosis_report,
                "structured_report": diagnosis_structured,
            },
        )

        agents = [
            {
                "agent_name": "KnowledgeRetrieverAgent",
                "title": "知识召回与引用整理",
                "status": "completed",
                "summary": self._build_retrieval_summary(retrieval_payload["effective_query"], retrieval_results),
                "citations": [f"{item['title']}#{item['page_reference'] or 'N/A'}" for item in retrieval_results[:3]],
            },
            {
                "agent_name": "WorkOrderPlannerAgent",
                "title": "作业步骤规划",
                "status": "completed",
                "summary": f"已生成 {len(task_preview)} 个标准化检修步骤预案。",
                "citations": [item["title"] for item in knowledge_refs[:2]],
            },
            {
                "agent_name": "RiskControlAgent",
                "title": "风险与缺项校验",
                "status": "completed",
                "summary": f"识别出 {len(risk_findings)} 条重点风险或现场提醒。",
                "citations": [step["title"] for step in task_preview[:2]],
            },
            {
                "agent_name": "CaseCuratorAgent",
                "title": "案例沉淀建议",
                "status": "completed",
                "summary": (
                    f"已输出 {len(case_suggestions)} 条案例沉淀建议，"
                    f"并推荐 {len(related_cases)} 条相似案例。"
                ),
                "citations": [item["title"] for item in knowledge_refs[:1]]
                + [item["title"] for item in related_cases[:1]],
            },
        ]

        run_payload = {
            "run_id": f"agent-run-{uuid4().hex[:12]}",
            "status": "completed",
            "summary": self._build_run_summary(retrieval_results, task_preview, risk_findings, related_cases),
            "diagnosis_report": diagnosis_report,
            "diagnosis_structured": diagnosis_structured,
            "request_context": self._build_request_context(
                request,
                retrieval_payload.get("effective_query"),
                selected_chunk_ids,
            ),
            "execution_brief": execution_brief,
            "effective_query": retrieval_payload["effective_query"],
            "effective_keywords": retrieval_payload.get("effective_keywords") or [],
            "image_analysis": retrieval_payload["image_analysis"],
            "knowledge_results": retrieval_results,
            "related_cases": related_cases,
            "task_plan_preview": task_preview,
            "risk_findings": risk_findings,
            "case_suggestions": case_suggestions,
            "agents": agents,
            "tool_calls": tool_calls,
            "created_at": datetime.now(timezone.utc),
        }
        await self._emit_event(
            emit,
            "result",
            {
                "run_id": run_payload["run_id"],
                "status": run_payload["status"],
                "summary": run_payload["summary"],
                "execution_status": execution_brief["status"],
            },
        )
        try:
            await self._store_run(run_payload)
        except Exception:
            logger.exception("agent_run_persist_failed run_id=%s", run_payload["run_id"])
        if request.maintenance_task_id is not None:
            try:
                await self.task_service.update_diagnosis_context(
                    request.maintenance_task_id,
                    diagnosis_report=diagnosis_report,
                    source_chunk_ids=[item["chunk_id"] for item in retrieval_results[: min(len(retrieval_results), 8)]],
                    source_refs=retrieval_results[:8],
                )
                await self.task_service.complete_task_after_pipeline_success(
                    request.maintenance_task_id,
                )
            except Exception:
                logger.exception(
                    "检修任务在协作流水线结束后自动完结失败 task_id=%s",
                    request.maintenance_task_id,
                )
        duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        await observe_duration(
            "agent_assist_duration_ms",
            duration_ms,
            maintenance_level=request.maintenance_level,
            result_status=run_payload["status"],
        )
        await self._emit_event(
            emit,
            "payload",
            jsonable_encoder(run_payload),
        )
        if request.maintenance_task_id is not None:
            try:
                await self.task_service.append_execution_timeline_event(
                    request.maintenance_task_id,
                    {
                        "id": f"done-{uuid4().hex[:8]}",
                        "type": "done",
                        "title": "诊断任务完成",
                        "description": "已结束并回写任务状态",
                        "time": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                logger.exception("persist_done_event_failed task_id=%s", request.maintenance_task_id)
        return run_payload

    async def _build_diagnosis_report(
        self,
        request: AgentAssistRequest,
        query_type: str,
        retrieval_results: list[dict[str, Any]],
        task_preview: list[dict[str, Any]],
        related_cases: list[dict[str, Any]],
        risk_findings: list[str],
        execution_brief: dict[str, Any],
        emit: EventCallback | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Generate structured diagnosis payload and a legacy user-facing text report.

        When *emit* is provided (SSE stream mode), the LLM response is streamed
        token-by-token and forwarded as ``diagnosis_chunk`` events every 50 tokens.
        Falls back to ``llm.invoke()`` when streaming is unavailable or *emit* is None.
        """
        llm = create_llm(request.model_provider, request.model_name)

        knowledge_lines = [
            (
                f"- [{item.get('citation_label') or f'C{idx + 1}'}|chunk_id={item.get('chunk_id') or '--'}] "
                f"{item['title']}（定位：{item.get('section_path') or item.get('section_reference') or item.get('page_reference') or '未提供'}，"
                f"摘录：{(item.get('excerpt') or item.get('content') or '无摘录')[:120]}）"
            )
            for idx, item in enumerate(retrieval_results[:3])
        ] or ["- 当前未命中稳定知识条目。"]
        step_lines = [f"- 步骤{idx + 1}：{item['title']}" for idx, item in enumerate(task_preview[:4])] or ["- 暂未生成标准步骤。"]
        case_lines = [f"- {item['title']}（{item.get('match_reason') or '相似案例'}）" for item in related_cases[:2]] or ["- 暂无相似案例。"]
        risk_lines = [f"- {item}" for item in risk_findings[:4]] or ["- 当前未识别出额外风险提醒。"]
        next_action_lines = [f"- {item}" for item in execution_brief.get("next_actions", [])[:4]] or ["- 暂无下一步建议。"]

        procedure_requirements = ""
        if query_type == "procedural":
            procedure_requirements = """
额外要求（当前是步骤/操作类问题）：
8. answer_mode 必须输出 procedure。
9. 这是操作步骤问题，不要把答案写成故障诊断，不要套用根因分析模板。
10. most_likely_fault 填当前操作主题或操作对象，不得写“待进一步定位”。
11. next_steps 必须覆盖完整、连续、可执行的步骤，不得只给前两步，不得省略中间步骤。
12. root_causes 输出空数组。
13. preliminary_conclusion 用一句话说明“这是哪项操作、依据哪些手册片段整理得到”。"""

        prompt = f"""请基于以下 RAG 检索与协作规划结果，输出严格合法的 JSON，对应工业检修诊断报告。必须全部使用中文，不要输出 Markdown，不要输出代码块，不要输出解释文字。

JSON 结构必须包含以下字段：
answer_mode: string
most_likely_fault: string
risk_level: string
confidence: integer(0-100)
main_symptoms: string[]
preliminary_conclusion: string
next_steps: [{{step_no: integer|null, title: string, summary: string, sections: [{{label: string, items: string[]}}], meta: string[], raw_text: string|null}}]
root_causes: [{{name: string, confidence: integer(0-100), evidence: string}}]
evidence_items: [{{document_title: string, chunk_id: integer, citation_label: string, section: string, excerpt: string, source_name: string, relevance_score: integer(0-100)}}]
evidence_count: integer
top_similarity: integer(0-100)
work_order_ready: boolean

要求：
1. risk_level 仅输出：低风险 / 中风险 / 高风险。
2. main_symptoms 输出 2-4 条。
3. next_steps 必须是结构化可执行动作；title 写动作名称，summary 写补充说明，sections 仅在存在子步骤时输出。若当前是步骤/操作类问题，则应尽量输出完整连续步骤，不限制为 6 条以内。
4. root_causes 输出 3-4 条候选根因，按置信度降序。
5. evidence_items 至少输出 2 条；每条都必须带 citation_label 和 chunk_id；若知识不足要明确写出证据不足。
6. work_order_ready 在结论可执行且具备生成工单基础时输出 true，否则 false。
7. evidence_items 中的 citation_label 只允许使用已提供的 [C1] / [C2] 等标签，chunk_id 必须与对应知识依据一致。
{procedure_requirements}

【任务信息】
- 设备类型：{request.equipment_type or '未提供'}
- 设备型号：{request.equipment_model or '未提供'}
- 故障现象：{request.query or request.fault_type or '未提供'}

【知识依据】
{chr(10).join(knowledge_lines)}

【规划步骤】
{chr(10).join(step_lines)}

【风险提醒】
{chr(10).join(risk_lines)}

【相似案例】
{chr(10).join(case_lines)}

【执行结论摘要】
- 状态：{execution_brief.get('status') or 'unknown'}
- 结论：{execution_brief.get('decision') or '未生成'}

【下一步建议】
{chr(10).join(next_action_lines)}
"""

        if llm is not None:
            try:
                messages = [
                    (
                        "system",
                        "你是工业设备检修诊断专家。请把 RAG 检索、风险判断和步骤规划整合成最终诊断结论，全部使用中文，并严格按指定分段输出。",
                    ),
                    ("human", prompt),
                ]
                # ── 流式路径（SSE 场景）──────────────────────────────────────
                if emit is not None and hasattr(llm, "astream"):
                    content_parts: list[str] = []
                    pending_chars: list[str] = []
                    async for chunk in llm.astream(messages):
                        delta = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if not delta:
                            continue
                        content_parts.append(delta)
                        pending_chars.append(delta)
                        # 每累积 50 个字符发一次 diagnosis_chunk 事件
                        if sum(len(c) for c in pending_chars) >= 50:
                            await self._emit_event(
                                emit,
                                "diagnosis_chunk",
                                {"delta": "".join(pending_chars)},
                            )
                            pending_chars.clear()
                    # 发送剩余不足 50 字符的尾部
                    if pending_chars:
                        await self._emit_event(
                            emit,
                            "diagnosis_chunk",
                            {"delta": "".join(pending_chars)},
                        )
                    content = "".join(content_parts)
                # ── 非流式路径（非 SSE 或 LLM 不支持 astream）──────────────
                else:
                    response = llm.invoke(messages)
                    content = response.content if hasattr(response, "content") else str(response)
                content = cleanup_answer(content)
                if isinstance(content, str) and content.strip():
                    structured = parse_llm_structured_json(content)
                    if structured is not None:
                        if query_type == "procedural" and structured.answer_mode != "procedure":
                            structured = structured.model_copy(update={"answer_mode": "procedure"})
                        structured = self._hydrate_diagnosis_evidence_items(structured, retrieval_results)
                        return structured.model_dump(), render_structured_diagnosis_report(structured)
            except Exception:
                logger.exception("agent_assist_build_diagnosis_report_failed")
        structured = build_structured_diagnosis(
            diagnosis_report=(
                "■ 诊断结论\n"
                f"{execution_brief.get('decision') or '当前尚未形成稳定诊断结论。'}\n\n"
                "■ 原因判断\n"
                f"{'；'.join(risk_findings[:3]) or '当前知识依据不足，尚不能进一步缩小故障范围。'}\n\n"
                "■ 知识依据\n"
                f"{chr(10).join(knowledge_lines[:3])}\n\n"
                "■ 建议措施\n"
                f"{chr(10).join(next_action_lines)}"
            ),
            advice_card="\n".join(execution_brief.get("next_actions", [])[:6]),
            retrieval_results=retrieval_results,
            maintenance_level=request.maintenance_level,
            symptom_description=request.query or request.fault_type,
            work_order_ready=bool(request.asset_code),
            answer_mode="procedure" if query_type == "procedural" else "diagnosis",
        )
        return structured.model_dump(), render_structured_diagnosis_report(structured)

    def _hydrate_diagnosis_evidence_items(
        self,
        structured,
        retrieval_results: list[dict[str, Any]],
    ):
        if not retrieval_results:
            return structured

        evidence_items = list(structured.evidence_items or [])
        if not evidence_items:
            return build_structured_diagnosis(
                diagnosis_report=render_structured_diagnosis_report(structured),
                advice_card=_stringify_step_items(structured.next_steps or []),
                retrieval_results=retrieval_results,
                work_order_ready=structured.work_order_ready,
            )

        normalized_items = []
        for index, item in enumerate(evidence_items):
            source = retrieval_results[min(index, len(retrieval_results) - 1)]
            payload = item.model_dump()
            payload["chunk_id"] = payload.get("chunk_id") or source.get("chunk_id")
            payload["citation_label"] = payload.get("citation_label") or source.get("citation_label") or f"C{index + 1}"
            if not payload.get("section"):
                payload["section"] = source.get("section_reference") or source.get("page_reference") or "命中片段"
            if not payload.get("excerpt"):
                payload["excerpt"] = (source.get("excerpt") or source.get("content") or "")[:240] or None
            if not payload.get("source_name"):
                payload["source_name"] = source.get("source_name")
            normalized_items.append(payload)

        payload = structured.model_dump()
        payload["evidence_items"] = normalized_items
        payload["evidence_count"] = max(structured.evidence_count, len(retrieval_results))
        payload["top_similarity"] = structured.top_similarity or min(
            100,
            int(
                round(
                    max(
                        [
                            float(item.get("rerank_score") or item.get("score") or item.get("retrieval_score") or 0.0)
                            for item in retrieval_results
                        ],
                        default=0.0,
                    )
                    * 100
                )
            ),
        )
        return type(structured).model_validate(payload)

    async def _emit_event(
        self,
        emit: EventCallback | None,
        event: str,
        data: dict[str, Any],
    ) -> None:
        """Send one stage event when a stream callback is present."""
        if self._active_task_id is not None:
            persisted = self._build_persisted_timeline_event(event, data)
            if persisted is not None:
                try:
                    await self.task_service.append_execution_timeline_event(
                        self._active_task_id,
                        persisted,
                        diagnosis_report=data.get("report") if event == "report" else None,
                    )
                except Exception:
                    logger.exception(
                        "persist_timeline_event_failed task_id=%s event=%s",
                        self._active_task_id,
                        event,
                    )
        if emit is None:
            return
        result = emit({"event": event, "data": data})
        if result is not None:
            await result

    def _build_persisted_timeline_event(self, event: str, data: dict[str, Any]) -> dict[str, Any] | None:
        timestamp = datetime.now(timezone.utc).isoformat()
        if event == "connected":
            return {
                "id": f"connected-{uuid4().hex[:8]}",
                "type": "connected",
                "title": "SSE 连接建立",
                "description": "已连接协作诊断流",
                "time": timestamp,
            }
        if event == "stage_start":
            return {
                "id": f"node-start-{uuid4().hex[:8]}",
                "type": "node_start",
                "title": data.get("title") or "阶段开始",
                "description": data.get("message") or "正在执行",
                "time": timestamp,
            }
        if event == "stage_finish":
            return {
                "id": f"node-finish-{uuid4().hex[:8]}",
                "type": "node_finish",
                "title": data.get("title") or "阶段完成",
                "description": data.get("summary") or "执行完成",
                "time": timestamp,
            }
        if event == "report":
            report_text = str(data.get("report") or "").strip()
            return {
                "id": f"report-{uuid4().hex[:8]}",
                "type": "report",
                "title": "RAG 诊断报告生成",
                "description": report_text or "已生成诊断摘要",
                "time": timestamp,
            }
        return None

    async def _store_run(self, payload: dict[str, Any]) -> None:
        """Persist a JSON-safe playback snapshot."""
        created_at = payload.get("created_at")
        if isinstance(created_at, datetime):
            stored_created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            stored_created_at = datetime.now(timezone.utc).replace(tzinfo=None)

        for attempt in range(3):
            try:
                record = AgentRun(
                    run_id=payload["run_id"],
                    status=payload["status"],
                    payload=jsonable_encoder(payload),
                    created_at=stored_created_at,
                )
                self.session.add(record)
                await self.session.commit()
                break
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower() or attempt >= 2:
                    raise
                await self.session.rollback()
                await asyncio.sleep(0.2 * (attempt + 1))
        await increment_counter("agent_runs_persisted_total", status=payload["status"])

    async def _build_task_preview(
        self,
        request: AgentAssistRequest,
        knowledge_refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        equipment_type = request.equipment_type or "摩托车发动机"
        template = await self.task_service._ensure_template(equipment_type, request.maintenance_level)
        preview_data = MaintenanceTaskCreate(
            work_order_id=request.work_order_id,
            asset_code=request.asset_code,
            report_source=request.report_source,
            priority=request.priority,
            equipment_type=equipment_type,
            equipment_model=request.equipment_model,
            maintenance_level=request.maintenance_level,
            fault_type=request.fault_type,
            symptom_description=request.query or request.fault_type or "现场异常待进一步确认",
            source_chunk_ids=[ref["chunk_id"] for ref in knowledge_refs],
        )
        preview_steps: list[dict[str, Any]] = []
        for index, template_step in enumerate(template.steps, start=1):
            guardrails = MaintenanceSafetyService.build_step_guardrails(
                step_title=template_step.title,
                step_order=index,
                maintenance_level=request.maintenance_level,
                priority=request.priority,
                symptom_description=request.query or request.fault_type,
                has_image=bool(request.image_base64),
                knowledge_locked=bool(knowledge_refs),
                risk_warning=template_step.risk_warning,
            )
            preview_steps.append(
                {
                    "step_order": index,
                    "title": template_step.title,
                    "instruction": self.task_service._render_instruction(
                        template_step.instruction_template,
                        preview_data,
                        knowledge_refs,
                    ),
                    "risk_warning": template_step.risk_warning,
                    "caution": template_step.caution,
                    "confirmation_text": template_step.confirmation_text,
                    "required_tools": self.task_service._normalize_step_items(
                        getattr(template_step, "required_tools", None)
                    ),
                    "required_materials": self.task_service._normalize_step_items(
                        getattr(template_step, "required_materials", None)
                    ),
                    "estimated_minutes": getattr(template_step, "estimated_minutes", None),
                    "safety_preconditions": guardrails["safety_preconditions"],
                    "requires_manual_authorization": guardrails["requires_manual_authorization"],
                    "authorization_hint": guardrails["authorization_hint"],
                }
            )
        return preview_steps

    def _build_risk_findings(
        self,
        request: AgentAssistRequest,
        task_preview: list[dict[str, Any]],
        knowledge_refs: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
    ) -> list[str]:
        findings = []
        if knowledge_refs:
            findings.append("先核对知识引用与现场现象是否一致，避免直接照搬手册结论。")
        if request.maintenance_level == "emergency":
            findings.append("当前为应急检修模式，仅执行知识库已覆盖且风险可控的动作。")
        if "高温" in (request.query or "") or "温度偏高" in (request.query or ""):
            findings.append("温度相关故障应先完成停机与冷却确认，再进行拆检。")
        if request.image_base64:
            findings.append("图片识别结果仅作为辅助线索，最终仍需人工复核关键部件。")
        if task_preview:
            warnings = [step["risk_warning"] for step in task_preview[:2] if step.get("risk_warning")]
            findings.extend(warnings)
        for tool_call in tool_calls:
            if tool_call.get("blocking"):
                findings.extend(tool_call.get("details") or [])
        return list(dict.fromkeys(findings))[:5]

    def _build_case_suggestions(
        self,
        request: AgentAssistRequest,
        knowledge_refs: list[dict[str, Any]],
        related_cases: list[dict[str, Any]],
    ) -> list[str]:
        suggestions = [
            "完成检修后立即沉淀案例，保留处理步骤、结论和差异项。",
            "若知识条目与现场现象存在偏差，应新增人工修正并提交审核。",
        ]
        if knowledge_refs:
            suggestions.append(
                f"建议优先保留 {knowledge_refs[0]['title']} 的引用截图与页码，便于后续复盘与核对。"
            )
        if related_cases:
            suggestions.append(f"可先对照案例《{related_cases[0]['title']}》检查是否存在相同处理路径。")
        if request.equipment_model:
            suggestions.append(f"案例标题中保留型号 {request.equipment_model}，提升后续精准命中率。")
        return suggestions[:4]

    def _build_request_context(
        self,
        request: AgentAssistRequest,
        effective_query: str | None,
        selected_chunk_ids: list[int],
    ) -> dict[str, Any]:
        return {
            "work_order_id": request.work_order_id,
            "asset_code": request.asset_code,
            "report_source": request.report_source,
            "priority": request.priority,
            "maintenance_level": request.maintenance_level,
            "equipment_type": request.equipment_type,
            "equipment_model": request.equipment_model,
            "fault_type": request.fault_type,
            "symptom_description": effective_query or request.query,
            "selected_chunk_ids": list(selected_chunk_ids),
            "has_image": bool(request.image_base64),
            "maintenance_task_id": request.maintenance_task_id,
        }

    def _build_execution_brief(
        self,
        request: AgentAssistRequest,
        knowledge_results: list[dict[str, Any]],
        selected_chunk_ids: list[int],
        task_preview: list[dict[str, Any]],
        related_cases: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        risk_findings: list[str],
    ) -> dict[str, Any]:
        recommended_path = {
            "routine": "例行检修流程",
            "standard": "标准检修流程",
            "emergency": "应急检修流程",
        }.get(request.maintenance_level, "标准检修流程")
        blocking_issues = list(
            dict.fromkeys(
                issue
                for tool_call in tool_calls
                for issue in tool_call.get("details", [])
                if tool_call.get("blocking")
            )
        )
        authorization_required = any(tool_call.get("requires_human_authorization") for tool_call in tool_calls)

        if not knowledge_results and not selected_chunk_ids:
            status = "need_more_input"
            decision = "当前知识依据不足，需补充更明确的故障描述、设备型号或故障图片后再下发预案。"
        elif blocking_issues:
            status = "review_required"
            decision = "当前仍有前置安全条件未满足，建议先完成合规校验与人工复核，再进入现场执行。"
        elif authorization_required:
            status = "review_required"
            decision = "当前工单包含高风险或高优先级操作，需人工授权后再推进关键步骤。"
        elif request.maintenance_level == "emergency":
            status = "review_required" if risk_findings else "ready"
            decision = "当前工单进入应急处置模式，建议先隔离风险源，再执行最小闭环排查。"
        elif len(risk_findings) >= 4:
            status = "review_required"
            decision = "风险提醒较多，建议由班组长先复核知识引用和现场现象，再执行标准步骤。"
        else:
            status = "ready"
            decision = "知识依据、步骤预案和风险提示已形成，可进入标准检修执行准备。"

        next_actions: list[str] = []
        if knowledge_results:
            next_actions.append(f"先锁定 {max(1, len(selected_chunk_ids))} 条知识依据，并记录章节或页码。")
        else:
            next_actions.append("补充设备型号、故障部位或现场图片，重新触发协作。")
        if task_preview:
            next_actions.append(f"优先执行“{task_preview[0]['title']}”，再进入现场现象核对。")
        if related_cases:
            next_actions.append(f"对照案例《{related_cases[0]['title']}》检查是否存在相同处理分支。")
        next_actions.append("完成检修后沉淀案例并提交审核回流。")
        if blocking_issues:
            next_actions.insert(0, "先关闭未满足的前置安全条件，再重新触发执行评估。")
        elif authorization_required:
            next_actions.insert(0, "先由班组长或专家完成高风险步骤授权。")

        return {
            "status": status,
            "decision": decision,
            "recommended_path": recommended_path,
            "next_actions": next_actions[:4],
            "blocking_issues": blocking_issues[:4],
            "authorization_required": authorization_required,
        }

    def _build_retrieval_summary(self, effective_query: str | None, results: list[dict[str, Any]]) -> str:
        if not results:
            return "未命中稳定知识条目，建议补充更明确的故障描述、设备型号或图片。"
        top = results[0]
        return (
            f"已围绕“{effective_query or top['title']}”召回 {len(results)} 条知识，"
            f"首条来源为 {top['title']}（{top['page_reference'] or '页码待补充'}）。"
        )

    def _build_run_summary(
        self,
        knowledge_results: list[dict[str, Any]],
        task_preview: list[dict[str, Any]],
        risk_findings: list[str],
        related_cases: list[dict[str, Any]],
    ) -> str:
        return (
            f"本次协作已完成知识召回、作业步骤规划、风险校验和案例沉淀建议。"
            f"当前共命中 {len(knowledge_results)} 条知识，生成 {len(task_preview)} 个步骤，"
            f"识别 {len(risk_findings)} 条风险提醒，并推荐 {len(related_cases)} 条相似案例。"
        )
