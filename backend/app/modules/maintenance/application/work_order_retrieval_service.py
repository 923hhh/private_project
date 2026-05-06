"""Work-order retrieval and streaming suggestion operations for maintenance."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import RetrievalSnapshot, WorkOrder, WorkOrderMessage
from app.db.models.tasks import MaintenanceTask
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.modules.maintenance.application.device_service import MaintenanceDeviceService
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


def _map_maint_for_knowledge(ml: str | None) -> str:
    if not ml:
        return "standard"
    s = ml.strip()
    if any(x in s for x in ("抢修", "应急")):
        return "emergency"
    if any(x in s for x in ("日常", "保养")):
        return "routine"
    return "standard"


def _wo_public(work_order: WorkOrder) -> dict[str, Any]:
    source_task = None
    if isinstance(work_order.step_progress_json, dict):
        source_task = work_order.step_progress_json.get("source_task")
    return {
        "id": work_order.id,
        "device_id": work_order.device_id,
        "status": work_order.status,
        "maintenance_level": work_order.maintenance_level,
        "flow_template_id": work_order.flow_template_id,
        "current_step_no": work_order.current_step_no,
        "last_retrieval_snapshot_id": work_order.last_retrieval_snapshot_id,
        "created_by_user_id": work_order.created_by_user_id,
        "source_task_id": source_task.get("task_id") if isinstance(source_task, dict) else None,
        "created_at": to_iso_cn(work_order.created_at),
        "updated_at": to_iso_cn(work_order.updated_at),
    }


class MaintenanceWorkOrderRetrievalService:
    """Knowledge retrieval and streaming answer generation for a work order."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditCallback,
        work_order_service: MaintenanceWorkOrderService,
        device_service: MaintenanceDeviceService,
    ) -> None:
        self.session = session
        self._audit = audit
        self.work_order_service = work_order_service
        self.device_service = device_service

    def _build_chunk_citations(self, results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
        citations: list[dict[str, Any]] = []
        chunks_json: list[dict[str, Any]] = []
        top_score = None
        for index, result in enumerate(results[:8], start=1):
            chunk_id = int(result["chunk_id"])
            excerpt = (result.get("expanded_content") or result.get("excerpt") or "")[:800]
            source_document = result.get("source_name") or result.get("title") or ""
            citation_label = result.get("citation_label") or f"C{index}"
            citations.append(
                {
                    "citation_label": citation_label,
                    "chunk_id": chunk_id,
                    "source_document": source_document,
                    "section_reference": result.get("section_reference"),
                    "page_reference": result.get("page_reference"),
                    "excerpt": excerpt,
                }
            )
            chunks_json.append(
                {
                    "citation_label": citation_label,
                    "chunk_id": chunk_id,
                    "source_document": source_document,
                    "section_reference": result.get("section_reference"),
                    "page_reference": result.get("page_reference"),
                    "score": result.get("score"),
                    "text_excerpt": excerpt,
                }
            )
            if top_score is None and result.get("score") is not None:
                top_score = float(result["score"])
        return citations, chunks_json, top_score

    def _bind_answer_citations(self, answer_text: str, citations: list[dict[str, Any]]) -> str:
        normalized = (answer_text or "").strip()
        if not normalized:
            return normalized
        labels = [item["citation_label"] for item in citations[:3] if item.get("citation_label")]
        if not labels:
            return normalized
        if any(f"[{label}]" in normalized for label in labels):
            return normalized
        return f"{normalized}\n\n依据：{' '.join(f'[{label}]' for label in labels)}"

    async def _load_source_task(self, work_order: WorkOrder) -> MaintenanceTask | None:
        snapshot = work_order.step_progress_json if isinstance(work_order.step_progress_json, dict) else None
        source_task = snapshot.get("source_task") if isinstance(snapshot, dict) else None
        task_id = source_task.get("task_id") if isinstance(source_task, dict) else None
        if not task_id:
            return None
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == int(task_id))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _build_source_task_citations(
        self,
        source_refs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
        citations: list[dict[str, Any]] = []
        chunks_json: list[dict[str, Any]] = []
        for index, ref in enumerate(source_refs[:8], start=1):
            chunk_id = int(ref.get("chunk_id") or 0)
            source_document = str(ref.get("source_name") or ref.get("title") or "")
            citation_label = str(ref.get("citation_label") or f"C{index}")
            excerpt = str(ref.get("excerpt") or "")[:800]
            citations.append(
                {
                    "citation_label": citation_label,
                    "chunk_id": chunk_id,
                    "source_document": source_document,
                    "section_reference": ref.get("section_reference"),
                    "page_reference": ref.get("page_reference"),
                    "excerpt": excerpt,
                }
            )
            chunks_json.append(
                {
                    "citation_label": citation_label,
                    "chunk_id": chunk_id,
                    "source_document": source_document,
                    "section_reference": ref.get("section_reference"),
                    "page_reference": ref.get("page_reference"),
                    "score": ref.get("retrieval_score") or ref.get("rerank_score"),
                    "text_excerpt": excerpt,
                }
            )
        return citations, chunks_json, None

    def _build_diagnosis_first_reply(
        self,
        source_task: MaintenanceTask,
        citations: list[dict[str, Any]],
    ) -> str:
        advice = (source_task.advice_card or "").strip()
        diagnosis = (source_task.diagnosis_report or "").strip()
        symptom = (source_task.symptom_description or "").strip()
        lines = ["已优先承接来源诊断结果，建议按以下工步执行："]

        step_source = advice or diagnosis or symptom
        raw_steps = [
            re.sub(r"^[\-•●■\d．。、)\s]+", "", item).strip()
            for item in re.split(r"[\n；;。]", step_source)
            if item and item.strip()
        ]
        normalized_steps: list[str] = []
        for item in raw_steps:
            if len(item) < 4:
                continue
            if item.startswith(("优先沿用来源诊断建议", "优先依据诊断结论推进检修")):
                continue
            normalized_steps.append(item)
            if len(normalized_steps) >= 5:
                break

        if not normalized_steps:
            if symptom:
                normalized_steps = [
                    f"先复核当前故障现象：{symptom}",
                    "对照来源诊断结论检查相关部件和连接状态。",
                    "记录现场结果后再进入下一步处理。",
                ]
            else:
                normalized_steps = [
                    "先复核来源诊断结论与现场现象是否一致。",
                    "优先检查诊断建议涉及的关键部件和连接状态。",
                    "记录现场结果后再继续执行后续处理。",
                ]

        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(normalized_steps, start=1)
        )

        if citations:
            refs = "；".join(
                f"[{citation['citation_label']}] {citation['source_document']}（chunk_id={citation['chunk_id']}）"
                for citation in citations[:5]
            )
            lines.append(f"本次优先参考来源诊断已命中的知识依据：{refs}")

        return "\n".join(lines).strip()

    async def post_retrieval(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if work_order.status == "S1":
            await self.work_order_service.transition(
                work_order,
                "S2",
                event_type="retrieval_started",
                actor_user_id=ctx.user_id,
            )
        device = await self.device_service.get_device(work_order.device_id)
        query_text = (body.get("query_text") or "").strip()
        maintenance_level = body.get("maintenance_level") or work_order.maintenance_level
        knowledge_level = _map_maint_for_knowledge(maintenance_level if isinstance(maintenance_level, str) else None)
        source_task = await self._load_source_task(work_order)

        used_source_task = False
        soft_code: str | None = None
        soft_msg: str | None = None
        if source_task is not None and (
            (source_task.advice_card or "").strip()
            or (source_task.diagnosis_report or "").strip()
            or list(source_task.source_snapshot or [])
        ):
            citations, chunks_json, top_score = self._build_source_task_citations(
                list(source_task.source_snapshot or [])
            )
            suggested_reply = self._build_diagnosis_first_reply(source_task, citations)
            used_source_task = True
        else:
            request = KnowledgeSearchRequest(
                query=query_text or "检修",
                equipment_type=device.device_type,
                equipment_model=device.model,
                maintenance_level=knowledge_level,
                limit=8,
            )
            knowledge_service = KnowledgeService(self.session)
            try:
                payload = await knowledge_service.search_multimodal(request)
                results = payload.get("results") or []
            except Exception:
                results = []
                soft_code = "MODEL_UNAVAILABLE"
                soft_msg = "检索或模型链路异常，已降级为片段模式"

            citations, chunks_json, top_score = self._build_chunk_citations(results)

            empty_hit = len(citations) == 0
            if empty_hit and soft_code is None:
                soft_code = "EMPTY_HIT"
                soft_msg = "未命中可用知识片段，请补充描述或发起升级"

            if citations:
                suggested_reply = "建议参考：" + "；".join(
                    f"[{citation['citation_label']}] {citation['source_document']}（chunk_id={citation['chunk_id']}）"
                    for citation in citations[:5]
                )
            else:
                suggested_reply = soft_msg or "暂无检索结果。"
        empty_hit = len(citations) == 0

        device_snapshot = {
            "device_id": device.id,
            "model": device.model,
            "asset_code": device.asset_code,
            "device_type": device.device_type,
        }
        snapshot = RetrievalSnapshot(
            work_order_id=work_order.id,
            query_text=query_text,
            chunks=chunks_json,
            model_name=None,
            knowledge_corpus_version=None,
            confidence_top1=top_score,
            empty_hit=empty_hit,
            degraded_response=not used_source_task,
            prompt_template_version="maintenance-1",
            device_context_snapshot=device_snapshot,
            created_at=utc_now_naive(),
        )
        self.session.add(snapshot)
        await self.session.flush()

        message = WorkOrderMessage(
            work_order_id=work_order.id,
            role="assistant",
            content=suggested_reply,
            retrieval_snapshot_id=snapshot.id,
            created_at=utc_now_naive(),
        )
        self.session.add(message)
        work_order.last_retrieval_snapshot_id = snapshot.id
        if work_order.status == "S2":
            await self.work_order_service.transition(
                work_order,
                "S3",
                event_type="retrieval_done",
                actor_user_id=ctx.user_id,
            )
        await self._audit(
            "retrieval.completed",
            "work_order",
            str(work_order.id),
            ctx.user_id,
            {"retrieval_snapshot_id": snapshot.id, "empty_hit": empty_hit},
            business_code=soft_code,
        )
        await self.session.commit()
        await self.session.refresh(message)
        await self.session.refresh(snapshot)

        base_data = {
            "retrieval_snapshot_id": snapshot.id,
            "message_id": message.id,
            "suggested_reply": suggested_reply,
            "citations": citations,
            "work_order": _wo_public(work_order),
        }
        if soft_code:
            return {
                "http": 200,
                "success": False,
                "business_code": soft_code,
                "message": soft_msg or "",
                "data": {**base_data, "empty_hit": empty_hit},
            }
        return {"http": 200, "success": True, "business_code": None, "message": None, "data": base_data}

    async def retrieval_stream(
        self,
        work_order_id: int,
        query_text: str,
        maintenance_level: str | None,
        ctx: CurrentUserCtx,
        emit: Any,
    ) -> None:
        """Streaming variant of post_retrieval."""
        from app.agents.diagnosis_agent import create_llm

        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if work_order.status == "S1":
            await self.work_order_service.transition(
                work_order,
                "S2",
                event_type="retrieval_started",
                actor_user_id=ctx.user_id,
            )
        device = await self.device_service.get_device(work_order.device_id)
        trimmed_query = (query_text or "").strip()
        effective_level = maintenance_level or work_order.maintenance_level
        knowledge_level = _map_maint_for_knowledge(effective_level if isinstance(effective_level, str) else None)

        await emit(
            {
                "event": "retrieval_start",
                "data": {
                    "query_text": trimmed_query or "检修",
                    "device": {"id": device.id, "model": device.model, "type": device.device_type},
                },
            }
        )

        request = KnowledgeSearchRequest(
            query=trimmed_query or "检修",
            equipment_type=device.device_type,
            equipment_model=device.model,
            maintenance_level=knowledge_level,
            limit=8,
        )
        knowledge_service = KnowledgeService(self.session)
        try:
            payload = await knowledge_service.search_multimodal(request)
            results = payload.get("results") or []
        except Exception:
            results = []

        await emit(
            {
                "event": "search_results",
                "data": {
                    "count": len(results),
                    "results": [
                        {
                            "chunk_id": result["chunk_id"],
                            "title": result.get("title", ""),
                            "excerpt": (result.get("excerpt") or "")[:300],
                            "score": result.get("score"),
                        }
                        for result in results[:8]
                    ],
                },
            }
        )

        citations, chunks_json, top_score = self._build_chunk_citations(results)

        answer_text = ""
        llm = create_llm("openai")
        if llm and citations:
            context = "\n".join(
                f"[{citation['citation_label']}|chunk_id={citation['chunk_id']}] {citation['source_document']} / {citation.get('section_reference') or citation.get('page_reference') or '命中片段'}: {citation['excerpt'][:200]}"
                for citation in citations[:5]
            )
            prompt = (
                f"根据以下检修知识片段，为工单 {work_order.id} 的设备 "
                f"{device.model}（{device.device_type}）生成简洁的检修建议（200字以内）。"
                "回答中的关键结论或步骤后必须引用方括号标签，例如 [C1] [C2]，且只允许使用已提供标签。\n\n"
                f"{context}"
            )
            try:
                async for chunk in llm.astream(
                    [("system", "你是工业检修助手，请用中文回答。"), ("human", prompt)]
                ):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if token:
                        answer_text += token
                        await emit({"event": "answer_chunk", "data": {"token": token}})
            except Exception:
                pass

        if not answer_text:
            if citations:
                answer_text = "建议参考：" + "；".join(
                    f"[{citation['citation_label']}] {citation['source_document']}（chunk_id={citation['chunk_id']}）"
                    for citation in citations[:5]
                )
            else:
                answer_text = "暂无检索结果。"
        else:
            answer_text = self._bind_answer_citations(answer_text, citations)

        device_snapshot = {
            "device_id": device.id,
            "model": device.model,
            "asset_code": device.asset_code,
            "device_type": device.device_type,
        }
        snapshot = RetrievalSnapshot(
            work_order_id=work_order.id,
            query_text=trimmed_query,
            chunks=chunks_json,
            model_name=None,
            knowledge_corpus_version=None,
            confidence_top1=top_score,
            empty_hit=len(citations) == 0,
            degraded_response=False,
            prompt_template_version="maintenance-stream-1",
            device_context_snapshot=device_snapshot,
            created_at=utc_now_naive(),
        )
        self.session.add(snapshot)
        await self.session.flush()

        message = WorkOrderMessage(
            work_order_id=work_order.id,
            role="assistant",
            content=answer_text,
            retrieval_snapshot_id=snapshot.id,
            created_at=utc_now_naive(),
        )
        self.session.add(message)
        work_order.last_retrieval_snapshot_id = snapshot.id
        if work_order.status == "S2":
            await self.work_order_service.transition(
                work_order,
                "S3",
                event_type="retrieval_done",
                actor_user_id=ctx.user_id,
            )
        await self.session.commit()
        await self.session.refresh(message)
        await self.session.refresh(snapshot)

        await emit(
            {
                "event": "snapshot_saved",
                "data": {"retrieval_snapshot_id": snapshot.id, "message_id": message.id},
            }
        )
