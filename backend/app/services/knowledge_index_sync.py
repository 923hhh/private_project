"""Shared helpers for keeping vector and BM25 indices in sync with knowledge docs."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)


def _build_index_text(row: Any) -> str:
    return " ".join(
        part.strip()
        for part in [
            row.heading or "",
            row.content or "",
            getattr(row, "section_reference", None) or "",
            getattr(row, "section_path", None) or "",
            getattr(row, "step_anchor", None) or "",
            getattr(row, "page_reference", None) or "",
            getattr(row, "image_anchor", None) or "",
            getattr(row, "ocr_text", None) or "",
            getattr(row, "image_caption", None) or "",
            getattr(row, "evidence_summary", None) or "",
        ]
        if part
    ).strip()


async def refresh_document_indices(
    session: Any,
    *,
    document_id: int,
) -> None:
    """Incrementally append one document's chunks to the active indices."""
    from app.services.bm25_service import get_bm25_service
    from app.services.embedding_service import get_embedding_service

    stmt = (
        select(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.document_id == document_id)
        .where(KnowledgeDocument.status == "published")
        .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
    )
    chunks = list((await session.execute(stmt)).scalars().all())
    if not chunks:
        return

    chunk_ids = [item.id for item in chunks]
    texts = [_build_index_text(item) for item in chunks]

    emb_svc = get_embedding_service()
    if emb_svc is not None:
        await emb_svc.add_chunks(chunk_ids, texts)

    bm25_svc = get_bm25_service()
    if bm25_svc is not None:
        await bm25_svc.add_chunks(chunk_ids, texts)


async def rebuild_all_knowledge_indices(session: Any) -> None:
    """Full rebuild fallback used when chunks were deleted or replaced."""
    from app.services.bm25_service import get_bm25_service
    from app.services.embedding_service import get_embedding_service

    emb_svc = get_embedding_service()
    if emb_svc is not None:
        await emb_svc.build_index(session)

    bm25_svc = get_bm25_service()
    if bm25_svc is not None:
        await bm25_svc.build_index(session)

    logger.info("knowledge_indices_rebuilt_full")
