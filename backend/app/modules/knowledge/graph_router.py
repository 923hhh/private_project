"""Knowledge graph query endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.knowledge.application.graph_service import KnowledgeGraphService
from app.modules.knowledge.schemas.graph import GraphResponse, GraphStatsResponse

router = APIRouter(prefix="/api/v1/knowledge/graph", tags=["knowledge-graph"])


def _svc(session: AsyncSession) -> KnowledgeGraphService:
    return KnowledgeGraphService(session)


@router.get("", response_model=GraphResponse)
async def get_graph(
    session: Annotated[AsyncSession, Depends(get_session)],
    relation_type: str | None = Query(None, description="Filter by relation type"),
    kind: str | None = Query(None, description="Filter by entity kind"),
    limit: int = Query(200, ge=1, le=1000),
):
    return await _svc(session).get_full_graph(relation_type, kind, limit)


@router.get("/neighbors", response_model=GraphResponse)
async def get_neighbors(
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: str = Query(..., description="Entity kind"),
    entity_id: int = Query(..., description="Entity ID"),
    depth: int = Query(1, ge=1, le=3),
):
    return await _svc(session).get_neighbors(kind, entity_id, depth)


@router.get("/stats", response_model=GraphStatsResponse)
async def get_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await _svc(session).get_stats()


__all__ = ["router"]
