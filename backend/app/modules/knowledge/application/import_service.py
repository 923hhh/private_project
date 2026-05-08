"""Formal knowledge import management service for the Next.js knowledge center."""
from __future__ import annotations

import asyncio
import mimetypes
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import increment_counter, observe_duration
from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeImportJob, KnowledgeRelation
from app.integrations.pdf_import import PdfKnowledgeImportService
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate
from app.services.knowledge_chunking import build_anchored_chunk_payloads
from app.services.knowledge_index_sync import rebuild_all_knowledge_indices
from app.services.ocr_service import ImageOcrResult, KnowledgeOcrService

IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SCANNED_PDF_MAX_OCR_PAGES = 15
_SOURCE_IMPORT_LOCKS: dict[str, asyncio.Lock] = {}
SUMMARY_SENTENCE_SPLIT = re.compile(r"[。！？；\n]+")
TOP_LEVEL_SECTION_PATTERN = re.compile(r"^[一二三四五六七八九十]+、\s*(.+)$")
OPERATION_KEYWORDS = ("拆卸", "检查", "安装", "测量", "调整", "装配")


def _utc_naive_now() -> datetime:
    """Return naive UTC datetime for columns declared as TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def render_pdf_pages_as_png_bytes(
    file_bytes: bytes,
    *,
    max_pages: int = SCANNED_PDF_MAX_OCR_PAGES,
) -> list[bytes]:
    """将 PDF 各页渲染为 PNG 字节序列；用于文本层为空时的扫描件 OCR 回退。"""
    try:
        import fitz  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return []
    doc = None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = min(len(doc), max_pages)
        out: list[bytes] = []
        for index in range(page_count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            out.append(pix.tobytes("png"))
        return out
    except Exception:
        return []
    finally:
        if doc is not None:
            doc.close()


class KnowledgeImportService:
    """Manage PDF knowledge import jobs, document list and chunk preview."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.importer = PdfKnowledgeImportService()
        self.knowledge_service = KnowledgeService(session)
        self.ocr_service = KnowledgeOcrService()

    async def import_pdf_upload(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        content_type: str | None,
        title: str | None,
        equipment_type: str,
        equipment_model: str | None,
        fault_type: str | None,
        section_reference: str | None,
        source_type: str = "manual",
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Accept an uploaded file and enqueue a persisted import job."""
        normalized_title = (title or "").strip() or self._derive_title(filename)
        source_name = filename.strip()
        import_type, processing_note = self._classify_import_file(
            filename=filename,
            content_type=content_type,
        )

        job = KnowledgeImportJob(
            import_type=import_type,
            title=normalized_title,
            source_name=source_name,
            source_type=source_type,
            content_type=(content_type or "").strip() or None,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_type=fault_type,
            section_reference=section_reference,
            replace_existing=replace_existing,
            status="pending",
            file_bytes=file_bytes,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        await increment_counter("knowledge_import_jobs_accepted_total", import_type=import_type)
        return self._serialize_job(job, processing_note=processing_note)

    async def retry_job(self, job_id: int) -> dict[str, Any]:
        """Requeue a failed job for another background attempt."""
        job = await self._load_job(job_id)
        if job.status != "failed":
            raise ValueError("只有失败的知识导入任务才能重试。")
        if not job.file_bytes:
            raise ValueError("当前导入任务缺少源文件载荷，无法重试。")

        job.status = "pending"
        job.error_message = None
        job.page_count = None
        job.chunk_count = None
        job.document_id = None
        job.preview_excerpt = None
        job.started_at = None
        job.finished_at = None
        job.updated_at = _utc_naive_now()
        await self.session.commit()
        await self.session.refresh(job)
        await increment_counter("knowledge_import_jobs_retried_total", import_type=job.import_type)
        return self._serialize_job(job)

    async def process_job(self, job_id: int) -> dict[str, Any]:
        """Process one queued job inside a worker-owned session."""
        started_at = perf_counter()
        processing_note: str | None = None
        job = await self._load_job(job_id)
        if job.status == "completed":
            return self._serialize_job(job)

        async with self._get_source_import_lock(job.source_name):
            job = await self._load_job(job_id)
            if job.status == "completed":
                return self._serialize_job(job)

            claimed = await self._mark_job_processing(job_id)
            if not claimed:
                job = await self._load_job(job_id)
                return self._serialize_job(job)

            job = await self._load_job(job_id)
            processing_note = self._build_processing_note(job.import_type)
            normalized_title = (job.title or "").strip() or self._derive_title(job.source_name)

            try:
                if not job.file_bytes:
                    raise ValueError("当前导入任务缺少源文件载荷，无法继续处理。")

                existing_documents = await self._list_existing_documents(job.source_name)
                if existing_documents and not job.replace_existing:
                    raise ValueError("已存在同名知识文档，请勾选覆盖导入后重试。")

                prepared = await self._prepare_upload_content(
                    import_type=job.import_type,
                    filename=job.source_name,
                    file_bytes=job.file_bytes or b"",
                    content_type=job.content_type,
                    title=normalized_title,
                    equipment_type=job.equipment_type,
                    equipment_model=job.equipment_model,
                    fault_type=job.fault_type,
                    section_reference=job.section_reference,
                )
                processing_note = prepared.get("processing_note") or processing_note
                content = prepared["content"]
                chunk_payloads = prepared["chunk_payloads"]
                document_request = KnowledgeDocumentCreate(
                    title=normalized_title,
                    source_name=job.source_name,
                    source_type=job.source_type,
                    equipment_type=job.equipment_type,
                    equipment_model=job.equipment_model,
                    fault_type=job.fault_type,
                    section_reference=job.section_reference,
                    page_reference=prepared["page_reference"],
                    content=content,
                )

                replaced_existing = False
                if existing_documents and job.replace_existing:
                    await self._delete_existing_documents(job.source_name)
                    replaced_existing = True

                document, chunk_count = await self.knowledge_service.create_document(
                    document_request,
                    chunk_payloads=chunk_payloads,
                )
                if replaced_existing:
                    await rebuild_all_knowledge_indices(self.session)

                job = await self._load_job(job.id)
                job.import_type = prepared.get("final_import_type", job.import_type)
                job.status = "completed"
                job.page_count = prepared["page_count"]
                job.chunk_count = chunk_count
                job.document_id = document.id
                job.preview_excerpt = chunk_payloads[0]["content"][:220] if chunk_payloads else None
                job.error_message = None
                job.file_bytes = None
                job.finished_at = _utc_naive_now()
                job.updated_at = job.finished_at
                await self.session.commit()
                await self.session.refresh(job)
                await increment_counter(
                    "knowledge_import_jobs_completed_total",
                    import_type=job.import_type,
                )
                await observe_duration(
                    "knowledge_import_processing_ms",
                    (perf_counter() - started_at) * 1000,
                    import_type=job.import_type,
                    status="completed",
                )
                return self._serialize_job(job, processing_note=processing_note)
            except Exception as exc:
                await self.session.rollback()
                job = await self._load_job(job_id)
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = _utc_naive_now()
                job.updated_at = job.finished_at
                await self.session.commit()
                await self.session.refresh(job)
                await increment_counter(
                    "knowledge_import_jobs_failed_total",
                    import_type=job.import_type,
                )
                await observe_duration(
                    "knowledge_import_processing_ms",
                    (perf_counter() - started_at) * 1000,
                    import_type=job.import_type,
                    status="failed",
                )
                return self._serialize_job(job, processing_note=processing_note)

    async def list_restartable_job_ids(self, limit: int = 20) -> list[int]:
        """Return queued job ids and recover stale processing jobs after restart."""
        now = _utc_naive_now()
        await self.session.execute(
            update(KnowledgeImportJob)
            .where(KnowledgeImportJob.status == "processing")
            .values(status="pending", updated_at=now)
        )
        await self.session.commit()

        stmt = (
            select(KnowledgeImportJob.id)
            .where(KnowledgeImportJob.status == "pending")
            .order_by(KnowledgeImportJob.created_at.asc(), KnowledgeImportJob.id.asc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [int(job_id) for job_id in rows]

    async def preview_pdf_upload(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        content_type: str | None,
        title: str | None,
        equipment_type: str,
        equipment_model: str | None,
        fault_type: str | None,
        section_reference: str | None,
        source_type: str = "manual",
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Preview a PDF or image import without persisting it into the knowledge base."""
        normalized_title = (title or "").strip() or self._derive_title(filename)
        source_name = filename.strip()
        import_type, processing_note = self._classify_import_file(
            filename=filename,
            content_type=content_type,
        )
        prepared = await self._prepare_upload_content(
            import_type=import_type,
            filename=filename,
            file_bytes=file_bytes,
            content_type=content_type,
            title=normalized_title,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_type=fault_type,
            section_reference=section_reference,
        )
        chunk_payloads = prepared["chunk_payloads"]
        existing = await self._find_existing_document(source_name)
        existing_document_detected = existing is not None
        warning_message = None

        if existing_document_detected and not replace_existing:
            warning_message = "已存在同名知识文档，确认导入前请勾选覆盖导入或调整文件名。"
        elif prepared.get("processing_warning"):
            warning_message = prepared["processing_warning"]

        return {
            "import_type": prepared.get("final_import_type", import_type),
            "processing_note": prepared.get("processing_note") or processing_note,
            "normalized_title": normalized_title,
            "source_name": source_name,
            "source_type": source_type,
            "equipment_type": equipment_type,
            "equipment_model": equipment_model,
            "fault_type": fault_type,
            "section_reference": section_reference,
            "replace_existing": replace_existing,
            "page_count": prepared["page_count"],
            "chunk_count": len(chunk_payloads),
            "preview_excerpt": chunk_payloads[0]["content"][:220] if chunk_payloads else None,
            "existing_document_detected": existing_document_detected,
            "warning_message": warning_message,
        }

    async def get_import_job(self, job_id: int) -> dict[str, Any]:
        """Return one import job detail."""
        job = await self._load_job(job_id)
        return self._serialize_job(job)

    async def delete_import_job(self, job_id: int) -> None:
        """Delete one failed import job record."""
        job = await self._load_job(job_id)
        if job.status != "failed":
            raise ValueError("仅解析失败的导入记录允许删除。")
        await self.session.delete(job)
        await self.session.commit()

    async def list_import_jobs(
        self,
        *,
        limit: int = 10,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent import jobs for the knowledge management center."""
        stmt = (
            select(KnowledgeImportJob)
            .order_by(KnowledgeImportJob.updated_at.desc(), KnowledgeImportJob.id.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(KnowledgeImportJob.status == status)

        jobs = (await self.session.execute(stmt)).scalars().all()
        return [self._serialize_job(job) for job in jobs]

    async def list_documents(
        self,
        *,
        limit: int = 20,
        equipment_type: str | None = None,
        equipment_model: str | None = None,
        source_type: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List imported knowledge documents with chunk counts."""
        stmt = (
            select(
                KnowledgeDocument,
                func.count(KnowledgeChunk.id).label("chunk_count"),
            )
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
            .limit(limit)
        )
        if equipment_type:
            stmt = stmt.where(KnowledgeDocument.equipment_type == equipment_type)
        if equipment_model:
            stmt = stmt.where(
                (KnowledgeDocument.equipment_model == equipment_model)
                | (KnowledgeDocument.equipment_model.is_(None))
            )
        if source_type:
            stmt = stmt.where(KnowledgeDocument.source_type == source_type)
        if query:
            normalized_query = f"%{query.strip()}%"
            stmt = stmt.where(
                KnowledgeDocument.title.ilike(normalized_query)
                | KnowledgeDocument.source_name.ilike(normalized_query)
                | KnowledgeDocument.content.ilike(normalized_query)
            )

        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "id": document.id,
                "title": document.title,
                "source_name": document.source_name,
                "source_type": document.source_type,
                "equipment_type": document.equipment_type,
                "equipment_model": document.equipment_model,
                "fault_type": document.fault_type,
                "status": document.status,
                "chunk_count": int(chunk_count or 0),
                "created_at": self._as_utc_aware(document.created_at),
                "updated_at": self._as_utc_aware(document.updated_at),
            }
            for document, chunk_count in rows
        ]

    async def get_document_detail(self, document_id: int) -> dict[str, Any]:
        """Return detailed metadata for a single knowledge document."""
        document = await self._ensure_document(document_id)
        chunk_count_stmt = select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.document_id == document_id
        )
        chunk_count = (await self.session.execute(chunk_count_stmt)).scalar_one()
        preview_chunks = (
            await self.session.execute(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document_id)
                .order_by(KnowledgeChunk.chunk_index.asc())
                .limit(6)
            )
        ).scalars().all()
        return {
            "id": document.id,
            "title": document.title,
            "source_name": document.source_name,
            "source_type": document.source_type,
            "equipment_type": document.equipment_type,
            "equipment_model": document.equipment_model,
            "fault_type": document.fault_type,
            "status": document.status,
            "chunk_count": int(chunk_count or 0),
            "section_reference": document.section_reference,
            "page_reference": document.page_reference,
            "content_excerpt": self._build_document_summary(document, list(preview_chunks)),
            "created_at": self._as_utc_aware(document.created_at),
            "updated_at": self._as_utc_aware(document.updated_at),
        }

    async def delete_document(self, document_id: int) -> None:
        """Delete a knowledge document and remove all graph relations that reference it."""
        document = await self._ensure_document(document_id)
        await self.session.execute(
            delete(KnowledgeRelation).where(
                (KnowledgeRelation.source_kind == "knowledge_document")
                & (KnowledgeRelation.source_id == document_id)
            )
        )
        await self.session.execute(
            delete(KnowledgeRelation).where(
                (KnowledgeRelation.target_kind == "knowledge_document")
                & (KnowledgeRelation.target_id == document_id)
            )
        )
        await self.session.delete(document)
        await self.session.commit()

    def _build_document_summary(
        self,
        document: KnowledgeDocument,
        chunks: list[KnowledgeChunk],
    ) -> str | None:
        """Generate a fixed three-part document summary."""
        sections = self._extract_document_sections(document.content, chunks)
        operations = self._extract_document_operations(document.content, chunks)

        scope_parts = [part for part in [document.equipment_type, document.equipment_model, document.fault_type] if part]
        scope_text = "、".join(scope_parts)
        lead = document.title.strip() if document.title else "该文档"

        sentences: list[str] = []
        if scope_text:
            sentences.append(f"文档用途：{lead}是一份面向{scope_text}的检修指导资料。")
        else:
            sentences.append(f"文档用途：{lead}是一份面向发动机检修场景的检修指导资料。")

        if sections:
            section_text = "、".join(sections[:6])
            if len(sections) > 6:
                section_text += "等"
            sentences.append(f"主要覆盖模块：文档主要覆盖{section_text}等系统或部件的维修内容。")
        else:
            sentences.append("主要覆盖模块：当前未提取到稳定章节标题，可结合下方分段预览查看具体覆盖内容。")

        if operations:
            operation_text = "、".join(operations[:5])
            sentences.append(
                f"可用于哪些检修/诊断场景：可用于{operation_text}等检修流程，也可支持部件清单核对、工具与扭矩要求确认、间隙或压力标准复核以及故障判断。"
            )
        elif document.content:
            fallback = self._extract_summary_sentence(document.content, max_length=110)
            if fallback:
                sentences.append(f"可用于哪些检修/诊断场景：可用于现场复核和维修准备，核心内容包括{fallback}。")
            else:
                sentences.append("可用于哪些检修/诊断场景：可用于现场检修准备、步骤确认和关键参数复核。")
        else:
            sentences.append("可用于哪些检修/诊断场景：可用于现场检修准备、步骤确认和关键参数复核。")

        return "\n".join(sentence.strip() for sentence in sentences if sentence.strip()) or None

    def _extract_document_sections(
        self,
        content: str | None,
        chunks: list[KnowledgeChunk],
    ) -> list[str]:
        sections: list[str] = []
        seen: set[str] = set()

        for line in (content or "").splitlines():
            normalized = " ".join(line.split()).strip()
            match = TOP_LEVEL_SECTION_PATTERN.match(normalized)
            if not match:
                continue
            title = match.group(1).strip(" ：:")
            if len(title) < 2 or title in seen:
                continue
            seen.add(title)
            sections.append(title)
            if len(sections) >= 8:
                return sections

        for chunk in chunks:
            candidate = (chunk.heading or chunk.section_reference or "").strip()
            if not candidate:
                continue
            candidate = re.sub(r"^\d+(?:\.\d+)*\s*", "", candidate).strip(" ：:")
            if len(candidate) < 2 or candidate in seen:
                continue
            seen.add(candidate)
            sections.append(candidate)
            if len(sections) >= 8:
                break
        return sections

    def _extract_document_operations(
        self,
        content: str | None,
        chunks: list[KnowledgeChunk],
    ) -> list[str]:
        corpus = "\n".join(
            part for part in [content or "", *(chunk.heading or "" for chunk in chunks)] if part
        )
        operations = [keyword for keyword in OPERATION_KEYWORDS if keyword in corpus]
        return operations

    def _extract_summary_sentence(self, content: str | None, *, max_length: int = 72) -> str:
        condensed = " ".join((content or "").split()).strip()
        if not condensed:
            return ""

        for part in SUMMARY_SENTENCE_SPLIT.split(condensed):
            sentence = part.strip(" 0123456789.、:：()-")
            if len(sentence) >= 8:
                return sentence[:max_length].rstrip("，,;；:： ") + ("..." if len(sentence) > max_length else "")
        return condensed[:max_length].rstrip("，,;；:： ") + ("..." if len(condensed) > max_length else "")

    async def list_document_chunks(
        self,
        document_id: int,
        *,
        limit: int = 8,
        focus_chunk_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return ordered preview chunks for one document."""
        await self._ensure_document(document_id)
        base_stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        if focus_chunk_id is None:
            chunks = (await self.session.execute(base_stmt.limit(limit))).scalars().all()
        else:
            ordered_chunks = (await self.session.execute(base_stmt)).scalars().all()
            focus_index = next(
                (index for index, chunk in enumerate(ordered_chunks) if chunk.id == focus_chunk_id),
                None,
            )
            if focus_index is None:
                chunks = ordered_chunks[:limit]
            else:
                start = max(focus_index - (limit // 2), 0)
                end = min(start + limit, len(ordered_chunks))
                start = max(end - limit, 0)
                chunks = ordered_chunks[start:end]
        return [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "heading": chunk.heading,
                "content": chunk.content,
                "page_reference": chunk.page_reference,
                "section_reference": chunk.section_reference,
                "section_path": chunk.section_path,
                "step_anchor": chunk.step_anchor,
                "image_anchor": chunk.image_anchor,
            }
            for chunk in chunks
        ]

    async def _find_existing_document(self, source_name: str) -> KnowledgeDocument | None:
        existing = await self._list_existing_documents(source_name)
        return existing[0] if existing else None

    async def _list_existing_documents(self, source_name: str) -> list[KnowledgeDocument]:
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.source_name == source_name)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def _delete_existing_documents(self, source_name: str) -> None:
        existing = await self._list_existing_documents(source_name)
        for document in existing:
            await self.session.delete(document)
        if existing:
            await self.session.commit()

    async def _load_job(self, job_id: int) -> KnowledgeImportJob:
        stmt = select(KnowledgeImportJob).where(KnowledgeImportJob.id == job_id)
        job = (await self.session.execute(stmt)).scalar_one_or_none()
        if job is None:
            raise ValueError("指定的知识导入任务不存在。")
        return job

    async def _mark_job_processing(self, job_id: int) -> bool:
        now = _utc_naive_now()
        result = await self.session.execute(
            update(KnowledgeImportJob)
            .where(KnowledgeImportJob.id == job_id)
            .where(KnowledgeImportJob.status == "pending")
            .values(
                status="processing",
                attempt_count=KnowledgeImportJob.attempt_count + 1,
                started_at=now,
                finished_at=None,
                updated_at=now,
                error_message=None,
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def _ensure_document(self, document_id: int) -> KnowledgeDocument:
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        document = (await self.session.execute(stmt)).scalar_one_or_none()
        if document is None:
            raise ValueError("指定的知识文档不存在。")
        return document

    def _serialize_job(
        self,
        job: KnowledgeImportJob,
        *,
        processing_note: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": job.id,
            "import_type": job.import_type,
            "processing_note": processing_note or self._build_processing_note(job.import_type),
            "title": job.title,
            "source_name": job.source_name,
            "source_type": job.source_type,
            "equipment_type": job.equipment_type,
            "equipment_model": job.equipment_model,
            "fault_type": job.fault_type,
            "section_reference": job.section_reference,
            "replace_existing": job.replace_existing,
            "status": job.status,
            "page_count": job.page_count,
            "chunk_count": job.chunk_count,
            "document_id": job.document_id,
            "preview_excerpt": job.preview_excerpt,
            "error_message": job.error_message,
            "created_at": self._as_utc_aware(job.created_at),
            "updated_at": self._as_utc_aware(job.updated_at),
        }

    @staticmethod
    def _as_utc_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _derive_title(self, filename: str) -> str:
        stem = filename.rsplit(".", maxsplit=1)[0]
        return stem.strip() or "未命名知识文档"

    @staticmethod
    def _get_source_import_lock(source_name: str) -> asyncio.Lock:
        lock = _SOURCE_IMPORT_LOCKS.get(source_name)
        if lock is None:
            lock = asyncio.Lock()
            _SOURCE_IMPORT_LOCKS[source_name] = lock
        return lock

    def _classify_import_file(self, *, filename: str, content_type: str | None) -> tuple[str, str | None]:
        extension = ""
        if "." in filename:
            extension = f".{filename.rsplit('.', maxsplit=1)[-1].lower()}"
        normalized_content_type = (content_type or "").lower().strip()

        if extension == ".pdf" or normalized_content_type == "application/pdf":
            return "pdf", None

        guessed_content_type, _ = mimetypes.guess_type(filename)
        effective_content_type = normalized_content_type or (guessed_content_type or "").lower()
        if extension in IMAGE_EXTENSIONS or effective_content_type in IMAGE_MIME_TYPES:
            return (
                "image_ocr",
                "当前文件将按图片 OCR 流程导入知识库，建议导入后抽查来源回溯和分段预览。",
            )

        raise ValueError("当前仅支持 PDF、PNG、JPG/JPEG 或 WEBP 文件导入。")

    async def _prepare_upload_content(
        self,
        *,
        import_type: str,
        filename: str,
        file_bytes: bytes,
        content_type: str | None,
        title: str,
        equipment_type: str,
        equipment_model: str | None,
        fault_type: str | None,
        section_reference: str | None,
    ) -> dict[str, Any]:
        if import_type == "pdf":
            try:
                pages = self.importer.extract_pages_from_bytes(file_bytes)
            except ValueError as pdf_exc:
                png_pages = render_pdf_pages_as_png_bytes(file_bytes)
                if not png_pages:
                    raise ValueError(
                        f"{pdf_exc} 若为扫描件，请确认已安装 PyMuPDF（`requirements.txt` 中 `pymupdf`）后重试，"
                        "或将手册逐页导出为 PNG/JPEG 后使用图片导入。"
                    ) from pdf_exc
                return await self._build_pdf_from_scanned_page_pngs(
                    png_pages=png_pages,
                    title=title,
                    filename=filename,
                    equipment_type=equipment_type,
                    equipment_model=equipment_model,
                    section_reference=section_reference,
                )
            return {
                "content": self.importer.build_document_content(pages),
                "chunk_payloads": self.importer.build_chunk_payloads(title=title, pages=pages),
                "page_reference": f"P1-P{pages[-1].page_number}",
                "page_count": len(pages),
                "final_import_type": "pdf",
                "processing_note": None,
                "processing_warning": None,
            }

        ocr_result = await self.ocr_service.extract_text(
            image_bytes=file_bytes,
            image_mime_type=(content_type or "").strip() or "image/jpeg",
            image_filename=filename,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            title=title,
            section_reference=section_reference,
        )
        chunk_payloads = self._build_image_chunk_payloads(
            title=title,
            recognized_text=ocr_result.recognized_text,
            section_reference=section_reference,
            image_caption=ocr_result.summary,
        )
        return {
            "content": ocr_result.recognized_text,
            "chunk_payloads": chunk_payloads,
            "page_reference": "IMG1",
            "page_count": 1,
            "final_import_type": "image_ocr" if ocr_result.source == "vision_model" else "image_fallback",
            "processing_note": (
                "图片已通过视觉 OCR 提取为知识文本。"
                if ocr_result.source == "vision_model"
                else "图片已按回退模式生成可导入文本，请在导入后人工校对。"
            ),
            "processing_warning": ocr_result.warning,
        }

    def _build_image_chunk_payloads(
        self,
        *,
        title: str,
        recognized_text: str,
        section_reference: str | None,
        image_caption: str | None,
    ) -> list[dict[str, str | None]]:
        payloads = build_anchored_chunk_payloads(
            recognized_text,
            title=title,
            max_chars=420,
            section_reference=section_reference,
            page_reference="IMG1",
            image_anchor_prefix="IMG1#OCR",
        )
        for index, payload in enumerate(payloads, start=1):
            payload["heading"] = (
                f"{payload['section_path']} - OCR 第 {index} 段"
                if payload.get("section_path")
                else f"{title} - OCR 导入 - 第 {index} 段"
            )
            if not payload.get("image_anchor"):
                payload["image_anchor"] = f"IMG1#OCR-{index}"
            payload["source_modality"] = "ocr"
            payload["ocr_text"] = payload.get("content")
            payload["image_caption"] = image_caption
            payload["evidence_summary"] = image_caption or "图片已通过 OCR 转为可检索知识。"
        return payloads

    def _build_processing_note(self, import_type: str) -> str | None:
        if import_type == "image_ocr":
            return "图片已通过视觉 OCR 导入知识库，建议结合来源回溯进行人工校对。"
        if import_type == "image_fallback":
            return "图片按回退模式生成导入文本，建议后续补充人工转写或重新 OCR。"
        if import_type == "pdf_scanned_ocr":
            return "扫描件 PDF 已逐页渲染并进行视觉识别，导入后请务必结合原稿人工校对。"
        return None

    async def _build_pdf_from_scanned_page_pngs(
        self,
        *,
        png_pages: list[bytes],
        title: str,
        filename: str,
        equipment_type: str,
        equipment_model: str | None,
        section_reference: str | None,
    ) -> dict[str, Any]:
        """将扫描件 PDF 各页 PNG 走视觉 OCR，拼成可入库文档与分段。"""
        parts: list[str] = []
        warnings: list[str] = []
        for index, png in enumerate(png_pages, start=1):
            ocr_result: ImageOcrResult = await self.ocr_service.extract_text(
                image_bytes=png,
                image_mime_type="image/png",
                image_filename=f"{filename}#第{index}页",
                equipment_type=equipment_type,
                equipment_model=equipment_model,
                title=title,
                section_reference=section_reference,
            )
            parts.append(f"[第 {index} 页 OCR]\n{ocr_result.recognized_text}")
            if ocr_result.warning:
                warnings.append(f"第{index}页：{ocr_result.warning}")

        content = "\n\n".join(parts)
        chunk_payloads = build_anchored_chunk_payloads(
            content,
            title=title,
            max_chars=420,
            section_reference=section_reference,
            page_reference=f"P1-P{len(png_pages)}",
            image_anchor_prefix="PDFSCAN#OCR",
        )
        for idx, payload in enumerate(chunk_payloads, start=1):
            payload["heading"] = (
                f"{payload['section_path']} - 扫描 PDF OCR 第 {idx} 段"
                if payload.get("section_path")
                else f"{title} - 扫描 PDF OCR - 第 {idx} 段"
            )
            if not payload.get("image_anchor"):
                payload["image_anchor"] = f"PDFSCAN#OCR-{idx}"
            payload["source_modality"] = "ocr"
            payload["ocr_text"] = payload.get("content")
            payload["image_caption"] = "扫描件页 OCR 导入"
            payload["evidence_summary"] = "扫描件 PDF 经逐页 OCR 转换为检修知识片段。"

        processing_warning = "；".join(warnings) if warnings else None
        return {
            "content": content,
            "chunk_payloads": chunk_payloads,
            "page_reference": f"P1-P{len(png_pages)}",
            "page_count": len(png_pages),
            "final_import_type": "pdf_scanned_ocr",
            "processing_note": (
                "扫描件 PDF 已逐页渲染并进行视觉识别，请在预览确认后再导入，导入后建议人工校对。"
            ),
            "processing_warning": processing_warning,
        }


__all__ = ["KnowledgeImportService", "render_pdf_pages_as_png_bytes"]
