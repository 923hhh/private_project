"""Document-to-chunk normalization helpers for knowledge ingestion."""
from __future__ import annotations

from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate
from app.services.knowledge_chunking import build_anchored_chunk_payloads


def prepare_chunk_payloads(
    data: KnowledgeDocumentCreate,
    chunk_payloads: list[dict[str, str | None]] | None = None,
) -> list[dict[str, str | None]]:
    """Normalize explicit chunk payloads or derive chunks from document content."""
    prepared_payloads: list[dict[str, str | None]] = []
    if chunk_payloads:
        for payload in chunk_payloads:
            content = (payload.get("content") or "").strip()
            if not content:
                continue
            normalized_heading = (payload.get("heading") or data.title).strip()
            normalized_section_reference = payload.get("section_reference") or data.section_reference
            normalized_page_reference = payload.get("page_reference") or data.page_reference
            inferred_anchors = build_anchored_chunk_payloads(
                content,
                title=normalized_heading,
                max_chars=max(len(content) + 8, 64),
                section_reference=normalized_section_reference,
                page_reference=normalized_page_reference,
                image_anchor_prefix=(
                    normalized_page_reference
                    if (normalized_page_reference or "").startswith("IMG")
                    else None
                ),
            )
            inferred = inferred_anchors[0] if inferred_anchors else {}
            prepared_payloads.append(
                {
                    "heading": normalized_heading,
                    "content": content,
                    "equipment_type": payload.get("equipment_type") or data.equipment_type,
                    "equipment_model": payload.get("equipment_model") or data.equipment_model,
                    "fault_type": payload.get("fault_type") or data.fault_type,
                    "section_reference": normalized_section_reference
                    or inferred.get("section_reference"),
                    "section_path": payload.get("section_path") or inferred.get("section_path"),
                    "step_anchor": payload.get("step_anchor") or inferred.get("step_anchor"),
                    "page_reference": normalized_page_reference,
                    "image_anchor": payload.get("image_anchor") or inferred.get("image_anchor"),
                    "source_modality": payload.get("source_modality") or "text",
                    "ocr_text": payload.get("ocr_text"),
                    "image_caption": payload.get("image_caption"),
                    "evidence_summary": payload.get("evidence_summary"),
                }
            )

    if prepared_payloads:
        return prepared_payloads

    return [
        {
            "heading": payload["heading"],
            "content": payload["content"],
            "equipment_type": data.equipment_type,
            "equipment_model": data.equipment_model,
            "fault_type": data.fault_type,
            "section_reference": payload.get("section_reference"),
            "section_path": payload.get("section_path"),
            "step_anchor": payload.get("step_anchor"),
            "page_reference": payload.get("page_reference"),
            "image_anchor": payload.get("image_anchor"),
            "source_modality": payload.get("source_modality") or "text",
            "ocr_text": payload.get("ocr_text"),
            "image_caption": payload.get("image_caption"),
            "evidence_summary": payload.get("evidence_summary"),
        }
        for payload in build_anchored_chunk_payloads(
            data.content,
            title=data.title,
            section_reference=data.section_reference,
            page_reference=data.page_reference,
            image_anchor_prefix=(
                data.page_reference if (data.page_reference or "").startswith("IMG") else None
            ),
        )
    ]
