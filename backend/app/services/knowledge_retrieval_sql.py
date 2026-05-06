"""SQL expression helpers for knowledge retrieval."""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, literal, or_

from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument


def build_equipment_model_filter(equipment_model: str) -> Any:
    """Allow generic manual chunks to remain visible when a specific model is selected."""
    return or_(
        KnowledgeChunk.equipment_model == equipment_model,
        KnowledgeChunk.equipment_model.is_(None),
        KnowledgeChunk.equipment_model == "",
    )


def build_token_search_expressions(tokens: list[str]) -> tuple[Any, Any]:
    """Build score and match expressions for token-based retrieval."""
    if not tokens:
        return literal(0.0), literal(False)

    title_matches = [
        case((KnowledgeDocument.title.ilike(f"%{token}%"), 3.0), else_=0.0)
        for token in tokens
    ]
    content_matches = [
        case((KnowledgeChunk.content.ilike(f"%{token}%"), 2.0), else_=0.0)
        for token in tokens
    ]
    model_matches = [
        case((KnowledgeChunk.equipment_model.ilike(f"%{token}%"), 1.0), else_=0.0)
        for token in tokens
    ]
    fault_matches = [
        case((KnowledgeChunk.fault_type.ilike(f"%{token}%"), 1.0), else_=0.0)
        for token in tokens
    ]
    anchor_matches = [
        case(
            (
                KnowledgeChunk.section_path.ilike(f"%{token}%")
                | KnowledgeChunk.step_anchor.ilike(f"%{token}%")
                | KnowledgeChunk.section_reference.ilike(f"%{token}%")
                | KnowledgeChunk.page_reference.ilike(f"%{token}%")
                | KnowledgeChunk.image_anchor.ilike(f"%{token}%"),
                1.4,
            ),
            else_=0.0,
        )
        for token in tokens
    ]
    score_expr = (
        sum(title_matches, literal(0.0))
        + sum(content_matches, literal(0.0))
        + sum(model_matches, literal(0.0))
        + sum(fault_matches, literal(0.0))
        + sum(anchor_matches, literal(0.0))
    )
    match_expr = or_(
        *[KnowledgeDocument.title.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.content.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.equipment_model.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.fault_type.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.section_path.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.step_anchor.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.section_reference.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.page_reference.ilike(f"%{token}%") for token in tokens],
        *[KnowledgeChunk.image_anchor.ilike(f"%{token}%") for token in tokens],
    )
    return score_expr, match_expr
