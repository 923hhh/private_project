"""Formatting helpers for knowledge search results."""
from __future__ import annotations

from typing import Any

from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.services.knowledge_query_rewrite import extract_search_tokens


def serialize_search_row(
    *,
    request: KnowledgeSearchRequest,
    query: str,
    chunk: KnowledgeChunk,
    document: KnowledgeDocument,
    retrieval_score: float | None,
) -> dict[str, Any]:
    retrieval_score_value = float(retrieval_score) if retrieval_score is not None else 0.0
    return {
        "chunk_id": chunk.id,
        "document_id": document.id,
        "title": document.title,
        "source_name": document.source_name,
        "source_type": document.source_type,
        "equipment_type": chunk.equipment_type,
        "equipment_model": chunk.equipment_model,
        "fault_type": chunk.fault_type,
        "excerpt": build_excerpt(chunk.content, query),
        "section_reference": chunk.section_reference or document.section_reference,
        "section_path": getattr(chunk, "section_path", None),
        "step_anchor": getattr(chunk, "step_anchor", None),
        "page_reference": chunk.page_reference or document.page_reference,
        "image_anchor": getattr(chunk, "image_anchor", None),
        "source_modality": getattr(chunk, "source_modality", None),
        "ocr_text": getattr(chunk, "ocr_text", None),
        "image_caption": getattr(chunk, "image_caption", None),
        "evidence_summary": getattr(chunk, "evidence_summary", None),
        "expanded_content": None,
        "recommendation_reason": build_reason(request, document, chunk),
        "score": retrieval_score_value,
        "retrieval_score": retrieval_score_value,
        "rerank_score": retrieval_score_value,
        "_content": chunk.content,
        "_heading": getattr(chunk, "heading", None),
        "_document_updated_at": getattr(document, "updated_at", None),
    }


def build_excerpt(content: str, query: str) -> str:
    """Create a short result excerpt around the matched text."""
    condensed = " ".join(content.split())
    if not condensed:
        return ""

    if not query:
        return condensed[:180] + ("..." if len(condensed) > 180 else "")

    lower_content = condensed.lower()
    lower_query = query.lower()
    index = lower_content.find(lower_query)
    if index < 0:
        for token in extract_search_tokens(query):
            index = lower_content.find(token.lower())
            if index >= 0:
                break
        else:
            return condensed[:180] + ("..." if len(condensed) > 180 else "")

    start = max(0, index - 60)
    end = min(len(condensed), index + len(query) + 80)
    excerpt = condensed[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(condensed):
        excerpt += "..."
    return excerpt


def build_reason(
    request: KnowledgeSearchRequest,
    document: KnowledgeDocument,
    chunk: KnowledgeChunk,
) -> str:
    """Generate a deterministic recommendation reason for UI display."""
    reasons = []
    if request.query:
        reasons.append(f"命中了检索关键词“{request.query}”")
    if request.equipment_model and chunk.equipment_model == request.equipment_model:
        reasons.append("设备型号过滤匹配")
    elif request.equipment_model and not chunk.equipment_model:
        reasons.append("命中了当前型号可复用的通用手册")
    if request.fault_type and chunk.fault_type == request.fault_type:
        reasons.append("故障类型过滤匹配")
    if not reasons:
        reasons.append("满足当前元数据过滤条件")
    reasons.append(f"来源于 {document.source_name}")
    return "，".join(reasons)
