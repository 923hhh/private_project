"""Case upload, review and knowledge feedback service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRelation,
    MaintenanceCase,
    MaintenanceCaseCorrection,
)
from app.db.models.tasks import MaintenanceTask
from app.modules.cases.schemas import (
    MaintenanceCaseCorrectionCreate,
    MaintenanceCaseCreate,
    MaintenanceCaseReviewRequest,
)
from app.services.knowledge_index_sync import rebuild_all_knowledge_indices, refresh_document_indices
from app.services.knowledge_chunking import build_anchored_chunk_payloads, split_text_into_chunks


def utc_now_naive() -> datetime:
    """Store UTC timestamps in naive DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MaintenanceCaseService:
    """Service layer for case upload, review and knowledge feedback."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_case(self, data: MaintenanceCaseCreate) -> dict[str, Any]:
        task = await self._load_task(data.task_id) if data.task_id else None
        knowledge_refs = self._normalize_knowledge_refs(data.knowledge_refs, task)
        work_order_id = data.work_order_id or getattr(task, "work_order_id", None)
        asset_code = data.asset_code or getattr(task, "asset_code", None)
        report_source = data.report_source or getattr(task, "report_source", None)
        priority = data.priority or getattr(task, "priority", None) or "medium"

        case = MaintenanceCase(
            title=data.title,
            work_order_id=work_order_id,
            asset_code=asset_code,
            report_source=report_source,
            priority=priority,
            equipment_type=data.equipment_type,
            equipment_model=data.equipment_model,
            fault_type=data.fault_type,
            task_id=data.task_id,
            symptom_description=data.symptom_description,
            processing_steps=list(data.processing_steps),
            resolution_summary=data.resolution_summary,
            attachment_name=data.attachment_name,
            attachment_url=data.attachment_url,
            knowledge_refs=knowledge_refs,
            status="pending_review",
        )
        self.session.add(case)
        await self.session.flush()

        if task is not None:
            await self._ensure_relation(
                source_kind="maintenance_case",
                source_id=case.id,
                target_kind="maintenance_task",
                target_id=task.id,
                relation_type="derived_from",
                notes="案例由标准化检修任务沉淀生成",
            )

        for ref in knowledge_refs:
            chunk_id = ref.get("chunk_id")
            if chunk_id is None:
                continue
            await self._ensure_relation(
                source_kind="maintenance_case",
                source_id=case.id,
                target_kind="knowledge_chunk",
                target_id=chunk_id,
                relation_type="references",
                notes="案例保留原始知识引用",
            )

        await self.session.commit()
        return await self.get_case_detail(case.id)

    async def list_cases(
        self,
        *,
        limit: int = 20,
        status_filter: str | None = None,
        priority_filter: str | None = None,
        work_order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(MaintenanceCase).order_by(MaintenanceCase.updated_at.desc()).limit(limit)
        if status_filter:
            stmt = stmt.where(MaintenanceCase.status == status_filter)
        if priority_filter:
            stmt = stmt.where(MaintenanceCase.priority == priority_filter)
        if work_order_id:
            stmt = stmt.where(MaintenanceCase.work_order_id.ilike(f"%{work_order_id.strip()}%"))

        cases = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "id": item.id,
                "title": item.title,
                "work_order_id": item.work_order_id,
                "asset_code": item.asset_code,
                "report_source": item.report_source,
                "priority": item.priority,
                "equipment_type": item.equipment_type,
                "equipment_model": item.equipment_model,
                "fault_type": item.fault_type,
                "status": item.status,
                "task_id": item.task_id,
                "source_document_id": item.source_document_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in cases
        ]

    async def recommend_cases(
        self,
        *,
        equipment_type: str | None = None,
        equipment_model: str | None = None,
        fault_type: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(MaintenanceCase)
            .where(MaintenanceCase.status.in_(["approved", "pending_review"]))
            .order_by(MaintenanceCase.updated_at.desc())
            .limit(max(limit * 4, 8))
        )
        if equipment_type:
            stmt = stmt.where(MaintenanceCase.equipment_type == equipment_type)

        cases = list((await self.session.execute(stmt)).scalars().all())
        if not cases:
            return []

        ranked: list[tuple[int, float, dict[str, Any]]] = []
        for item in cases:
            score = 0
            reasons: list[str] = []
            if equipment_type and item.equipment_type == equipment_type:
                score += 2
                reasons.append("同设备类型")
            if equipment_model and item.equipment_model == equipment_model:
                score += 3
                reasons.append(f"同型号 {equipment_model}")
            if fault_type and item.fault_type:
                if fault_type == item.fault_type:
                    score += 3
                    reasons.append(f"同故障类型 {fault_type}")
                elif fault_type in item.fault_type or item.fault_type in fault_type:
                    score += 2
                    reasons.append(f"故障相近：{item.fault_type}")
            if item.status == "approved":
                score += 1
                reasons.append("已审核入库")

            ranked.append(
                (
                    score,
                    item.updated_at.timestamp() if item.updated_at else 0.0,
                    {
                        "id": item.id,
                        "title": item.title,
                        "equipment_type": item.equipment_type,
                        "equipment_model": item.equipment_model,
                        "fault_type": item.fault_type,
                        "status": item.status,
                        "task_id": item.task_id,
                        "updated_at": item.updated_at,
                        "match_reason": "、".join(reasons) if reasons else "最近可参考案例",
                    },
                )
            )

        ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
        recommendations = [payload for score, _, payload in ranked if score > 0][:limit]
        if recommendations:
            return recommendations

        return [payload for _, _, payload in ranked[:limit]]

    async def get_case_detail(self, case_id: int) -> dict[str, Any]:
        case = await self._load_case(case_id)
        corrections = await self._load_corrections(case_id)

        return {
            "id": case.id,
            "title": case.title,
            "work_order_id": case.work_order_id,
            "asset_code": case.asset_code,
            "report_source": case.report_source,
            "priority": case.priority,
            "equipment_type": case.equipment_type,
            "equipment_model": case.equipment_model,
            "fault_type": case.fault_type,
            "task_id": case.task_id,
            "symptom_description": case.symptom_description,
            "processing_steps": case.processing_steps or [],
            "resolution_summary": case.resolution_summary,
            "attachment_name": case.attachment_name,
            "attachment_url": case.attachment_url,
            "knowledge_refs": case.knowledge_refs or [],
            "status": case.status,
            "reviewer_name": case.reviewer_name,
            "review_note": case.review_note,
            "reviewed_at": case.reviewed_at,
            "source_document_id": case.source_document_id,
            "corrections": [
                {
                    "id": item.id,
                    "correction_target": item.correction_target,
                    "original_content": item.original_content,
                    "corrected_content": item.corrected_content,
                    "note": item.note,
                    "status": item.status,
                    "created_at": item.created_at,
                }
                for item in corrections
            ],
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }

    async def add_correction(
        self,
        case_id: int,
        data: MaintenanceCaseCorrectionCreate,
    ) -> dict[str, Any]:
        case = await self._load_case(case_id)
        correction = MaintenanceCaseCorrection(
            case_id=case.id,
            correction_target=data.correction_target,
            original_content=data.original_content,
            corrected_content=data.corrected_content,
            note=data.note,
            status="accepted",
        )
        self.session.add(correction)
        case.updated_at = utc_now_naive()

        await self._ensure_relation(
            source_kind="maintenance_case",
            source_id=case.id,
            target_kind="maintenance_case",
            target_id=case.id,
            relation_type="corrected",
            notes=f"人工修正 {data.correction_target}: {(data.note or '')[:100]}".strip(),
        )

        await self.session.commit()
        return await self.get_case_detail(case_id)

    async def review_case(
        self,
        case_id: int,
        data: MaintenanceCaseReviewRequest,
    ) -> dict[str, Any]:
        case = await self._load_case(case_id)
        case.reviewer_name = data.reviewer_name
        case.review_note = data.review_note
        case.reviewed_at = utc_now_naive()

        if data.action == "approve":
            corrections = await self._load_corrections(case.id)
            replacing_existing = bool(case.source_document_id)
            document = await self._publish_case_document(case, corrections)
            case.status = "approved"
            case.source_document_id = document.id

            await self._ensure_relation(
                source_kind="maintenance_case",
                source_id=case.id,
                target_kind="knowledge_document",
                target_id=document.id,
                relation_type="approved_into",
                notes="审核通过后自动沉淀为知识文档",
            )
        else:
            case.status = "rejected"
            if case.source_document_id:
                document_stmt = select(KnowledgeDocument).where(
                    KnowledgeDocument.id == case.source_document_id
                )
                document = (await self.session.execute(document_stmt)).scalar_one_or_none()
                if document is not None:
                    document.status = "archived"

        await self.session.commit()
        if data.action == "approve":
            if replacing_existing:
                await rebuild_all_knowledge_indices(self.session)
            else:
                await refresh_document_indices(self.session, document_id=document.id)
        elif case.source_document_id:
            await rebuild_all_knowledge_indices(self.session)
        return await self.get_case_detail(case_id)

    async def delete_case(self, case_id: int) -> None:
        case = await self._load_case(case_id)
        source_document_id = case.source_document_id
        deleted_document = False

        await self.session.execute(
            delete(KnowledgeRelation).where(
                (KnowledgeRelation.source_kind == "maintenance_case")
                & (KnowledgeRelation.source_id == case.id)
            )
        )
        await self.session.execute(
            delete(KnowledgeRelation).where(
                (KnowledgeRelation.target_kind == "maintenance_case")
                & (KnowledgeRelation.target_id == case.id)
            )
        )

        if source_document_id:
            document_stmt = select(KnowledgeDocument).where(
                KnowledgeDocument.id == source_document_id
            )
            document = (await self.session.execute(document_stmt)).scalar_one_or_none()
            if (
                document is not None
                and document.source_type == "case"
                and document.source_name == f"case-{case.id}"
            ):
                await self.session.execute(
                    delete(KnowledgeRelation).where(
                        (KnowledgeRelation.source_kind == "knowledge_document")
                        & (KnowledgeRelation.source_id == document.id)
                    )
                )
                await self.session.execute(
                    delete(KnowledgeRelation).where(
                        (KnowledgeRelation.target_kind == "knowledge_document")
                        & (KnowledgeRelation.target_id == document.id)
                    )
                )
                await self.session.delete(document)
                deleted_document = True

        await self.session.delete(case)
        await self.session.commit()

        if deleted_document:
            await rebuild_all_knowledge_indices(self.session)

    async def _publish_case_document(
        self,
        case: MaintenanceCase,
        corrections: list[MaintenanceCaseCorrection] | None = None,
    ) -> KnowledgeDocument:
        document_content = await self._build_case_document_content(case, corrections)
        chunks = split_text_into_chunks(document_content)

        document: KnowledgeDocument | None = None
        if case.source_document_id:
            stmt = (
                select(KnowledgeDocument)
                .options(selectinload(KnowledgeDocument.chunks))
                .where(KnowledgeDocument.id == case.source_document_id)
            )
            document = (await self.session.execute(stmt)).scalar_one_or_none()

        if document is None:
            document = KnowledgeDocument(
                title=case.title,
                source_name=f"case-{case.id}",
                source_type="case",
                equipment_type=case.equipment_type,
                equipment_model=case.equipment_model,
                fault_type=case.fault_type,
                section_reference="案例审核入库",
                page_reference=None,
                content=document_content,
                status="published",
            )
            self.session.add(document)
            await self.session.flush()
        else:
            document.title = case.title
            document.source_name = f"case-{case.id}"
            document.source_type = "case"
            document.equipment_type = case.equipment_type
            document.equipment_model = case.equipment_model
            document.fault_type = case.fault_type
            document.section_reference = "案例审核入库"
            document.page_reference = None
            document.content = document_content
            document.status = "published"
            await self.session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
            )
            await self.session.flush()

        chunk_payloads = build_anchored_chunk_payloads(
            document_content,
            title=case.title,
            section_reference="案例审核入库",
        )
        if not chunk_payloads:
            chunk_payloads = [
                {
                    "heading": case.title,
                    "content": chunk_text,
                    "section_reference": "案例审核入库",
                    "section_path": "案例审核入库",
                    "step_anchor": None,
                    "page_reference": None,
                    "image_anchor": None,
                }
                for chunk_text in chunks
            ]

        self.session.add_all(
            [
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    heading=payload.get("heading") or case.title,
                    content=payload.get("content") or "",
                    equipment_type=case.equipment_type,
                    equipment_model=case.equipment_model,
                    fault_type=case.fault_type,
                    section_reference=payload.get("section_reference") or "案例审核入库",
                    section_path=payload.get("section_path") or "案例审核入库",
                    step_anchor=payload.get("step_anchor"),
                    page_reference=payload.get("page_reference"),
                    image_anchor=payload.get("image_anchor"),
                    source_modality="text",
                    ocr_text=None,
                    image_caption=None,
                    evidence_summary="经专家审核发布的检修案例知识。",
                )
                for index, payload in enumerate(chunk_payloads, start=1)
            ]
        )
        await self.session.flush()
        return document

    async def _build_case_document_content(
        self,
        case: MaintenanceCase,
        corrections: list[MaintenanceCaseCorrection] | None = None,
    ) -> str:
        correction_rows = (
            corrections if corrections is not None else await self._load_corrections(case.id)
        )
        lines = [
            f"案例标题：{case.title}",
            f"工单编号：{case.work_order_id or '未标注'}",
            f"设备编号：{case.asset_code or '未标注'}",
            f"报修来源：{case.report_source or '未标注'}",
            f"优先级：{self._format_priority(case.priority)}",
            f"设备类型：{case.equipment_type}",
            f"设备型号：{case.equipment_model or '未标注'}",
            f"故障类型：{case.fault_type or '未标注'}",
            "",
            "故障现象：",
            case.symptom_description,
            "",
            "处理步骤：",
        ]

        steps = case.processing_steps or []
        if steps:
            lines.extend([f"{index}. {step}" for index, step in enumerate(steps, start=1)])
        else:
            lines.append("暂无标准步骤记录。")

        lines.extend(["", "处理结果：", case.resolution_summary or "暂无处理结果总结。"])

        refs = case.knowledge_refs or []
        if refs:
            lines.extend(["", "原始知识引用："])
            for ref in refs:
                title = ref.get("title", "未命名知识条目")
                source_name = ref.get("source_name", "未知来源")
                excerpt = ref.get("excerpt", "")
                lines.append(f"- {title} / {source_name}：{excerpt}")

        if correction_rows:
            lines.extend(["", "人工修正记录："])
            for item in correction_rows:
                note = f"（说明：{item.note}）" if item.note else ""
                lines.append(f"- 目标 {item.correction_target}：{item.corrected_content}{note}")

        return "\n".join(lines).strip()

    async def _load_case(self, case_id: int) -> MaintenanceCase:
        stmt = select(MaintenanceCase).where(MaintenanceCase.id == case_id)
        case = (await self.session.execute(stmt)).scalar_one_or_none()
        if case is None:
            raise ValueError("指定的检修案例不存在。")
        return case

    async def _load_task(self, task_id: int) -> MaintenanceTask:
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise ValueError("指定的检修任务不存在，无法生成案例。")
        return task

    async def _load_corrections(self, case_id: int) -> list[MaintenanceCaseCorrection]:
        stmt = (
            select(MaintenanceCaseCorrection)
            .where(MaintenanceCaseCorrection.case_id == case_id)
            .order_by(MaintenanceCaseCorrection.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    def _normalize_knowledge_refs(
        self,
        raw_refs: list[Any],
        task: MaintenanceTask | None,
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for item in raw_refs:
            if hasattr(item, "model_dump"):
                refs.append(item.model_dump())
            elif isinstance(item, dict):
                refs.append(dict(item))

        if refs:
            return refs

        if task is not None and task.source_snapshot:
            return [dict(item) for item in task.source_snapshot]

        return []

    async def _ensure_relation(
        self,
        *,
        source_kind: str,
        source_id: int,
        target_kind: str,
        target_id: int,
        relation_type: str,
        notes: str | None = None,
    ) -> None:
        stmt = select(KnowledgeRelation).where(
            KnowledgeRelation.source_kind == source_kind,
            KnowledgeRelation.source_id == source_id,
            KnowledgeRelation.target_kind == target_kind,
            KnowledgeRelation.target_id == target_id,
            KnowledgeRelation.relation_type == relation_type,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            if notes:
                existing.notes = notes
            return

        self.session.add(
            KnowledgeRelation(
                source_kind=source_kind,
                source_id=source_id,
                target_kind=target_kind,
                target_id=target_id,
                relation_type=relation_type,
                notes=notes,
            )
        )
        await self.session.flush()

    def _format_priority(self, priority: str | None) -> str:
        return {
            "low": "低",
            "medium": "中",
            "high": "高",
            "urgent": "紧急",
        }.get(priority or "medium", priority or "medium")


__all__ = ["MaintenanceCaseService"]
