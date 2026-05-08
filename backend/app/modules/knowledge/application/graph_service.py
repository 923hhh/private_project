"""Knowledge graph query service — reads KnowledgeRelation rows and resolves
referenced entities into a {nodes, edges} structure for visualisation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRelation,
    MaintenanceCase,
)
from app.db.models.tasks import MaintenanceTask
from app.modules.knowledge.schemas.graph import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStatsResponse,
)

_KIND_TABLE: dict[str, Any] = {
    "maintenance_case": MaintenanceCase,
    "maintenance_task": MaintenanceTask,
    "knowledge_chunk": KnowledgeChunk,
    "knowledge_document": KnowledgeDocument,
}

_KIND_LABEL_ATTR: dict[str, str] = {
    "maintenance_case": "title",
    "maintenance_task": "title",
    "knowledge_chunk": "heading",
    "knowledge_document": "title",
}


def _node_id(kind: str, entity_id: int) -> str:
    return f"{kind}:{entity_id}"


async def _resolve_entities(
    session: AsyncSession,
    refs: set[tuple[str, int]],
) -> dict[str, GraphNode]:
    by_kind: dict[str, list[int]] = defaultdict(list)
    for kind, entity_id in refs:
        by_kind[kind].append(entity_id)

    nodes: dict[str, GraphNode] = {}
    for kind, ids in by_kind.items():
        model = _KIND_TABLE.get(kind)
        if model is None:
            continue

        rows = (await session.execute(select(model).where(model.id.in_(ids)))).scalars().all()
        for row in rows:
            node_id = _node_id(kind, row.id)
            label_attr = _KIND_LABEL_ATTR.get(kind, "id")
            label = getattr(row, label_attr, None) or f"{kind}#{row.id}"
            props: dict[str, Any] = {}
            for attr in ("equipment_type", "equipment_model", "fault_type", "status", "source_type"):
                val = getattr(row, attr, None)
                if val is not None:
                    props[attr] = val
            nodes[node_id] = GraphNode(id=node_id, kind=kind, label=label, properties=props)

    return nodes


def _edge_from_row(row: KnowledgeRelation) -> GraphEdge:
    return GraphEdge(
        id=row.id,
        source=_node_id(row.source_kind, row.source_id),
        target=_node_id(row.target_kind, row.target_id),
        relation_type=row.relation_type,
        notes=row.notes,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_full_graph(
        self,
        relation_type: str | None = None,
        kind: str | None = None,
        limit: int = 200,
    ) -> GraphResponse:
        stmt = select(KnowledgeRelation)
        if relation_type:
            stmt = stmt.where(KnowledgeRelation.relation_type == relation_type)
        if kind:
            stmt = stmt.where(
                (KnowledgeRelation.source_kind == kind)
                | (KnowledgeRelation.target_kind == kind)
            )
        stmt = stmt.order_by(KnowledgeRelation.id.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()

        refs: set[tuple[str, int]] = set()
        edges: list[GraphEdge] = []
        for row in rows:
            refs.add((row.source_kind, row.source_id))
            refs.add((row.target_kind, row.target_id))
            edges.append(_edge_from_row(row))

        nodes = await _resolve_entities(self._session, refs)
        valid_node_ids = set(nodes.keys())
        filtered_edges = [
            edge for edge in edges if edge.source in valid_node_ids and edge.target in valid_node_ids
        ]
        return GraphResponse(nodes=list(nodes.values()), edges=filtered_edges)

    async def get_neighbors(
        self,
        kind: str,
        entity_id: int,
        depth: int = 1,
    ) -> GraphResponse:
        depth = min(depth, 3)
        visited_edges: dict[int, GraphEdge] = {}
        visited_refs: set[tuple[str, int]] = {(kind, entity_id)}
        frontier: set[tuple[str, int]] = {(kind, entity_id)}

        for _ in range(depth):
            if not frontier:
                break
            conditions = []
            for frontier_kind, frontier_id in frontier:
                conditions.append(
                    (KnowledgeRelation.source_kind == frontier_kind)
                    & (KnowledgeRelation.source_id == frontier_id)
                )
                conditions.append(
                    (KnowledgeRelation.target_kind == frontier_kind)
                    & (KnowledgeRelation.target_id == frontier_id)
                )
            from sqlalchemy import or_

            stmt = select(KnowledgeRelation).where(or_(*conditions))
            rows = (await self._session.execute(stmt)).scalars().all()

            next_frontier: set[tuple[str, int]] = set()
            for row in rows:
                if row.id not in visited_edges:
                    visited_edges[row.id] = _edge_from_row(row)
                for ref in ((row.source_kind, row.source_id), (row.target_kind, row.target_id)):
                    if ref not in visited_refs:
                        visited_refs.add(ref)
                        next_frontier.add(ref)
            frontier = next_frontier

        nodes = await _resolve_entities(self._session, visited_refs)
        valid_node_ids = set(nodes.keys())
        filtered_edges = [
            edge
            for edge in visited_edges.values()
            if edge.source in valid_node_ids and edge.target in valid_node_ids
        ]
        return GraphResponse(nodes=list(nodes.values()), edges=filtered_edges)

    async def get_stats(self) -> GraphStatsResponse:
        edge_counts = (
            await self._session.execute(
                select(
                    KnowledgeRelation.relation_type,
                    func.count(KnowledgeRelation.id),
                ).group_by(KnowledgeRelation.relation_type)
            )
        ).all()
        edges_by_type = {relation_type: count for relation_type, count in edge_counts}
        total_edges = sum(edges_by_type.values())

        source_counts = (
            await self._session.execute(
                select(
                    KnowledgeRelation.source_kind,
                    KnowledgeRelation.source_id,
                ).distinct()
            )
        ).all()
        target_counts = (
            await self._session.execute(
                select(
                    KnowledgeRelation.target_kind,
                    KnowledgeRelation.target_id,
                ).distinct()
            )
        ).all()
        all_refs: set[tuple[str, int]] = set()
        for kind_val, id_val in source_counts:
            all_refs.add((kind_val, id_val))
        for kind_val, id_val in target_counts:
            all_refs.add((kind_val, id_val))

        nodes_by_kind: dict[str, int] = defaultdict(int)
        for kind_val, _ in all_refs:
            nodes_by_kind[kind_val] += 1

        return GraphStatsResponse(
            total_nodes=len(all_refs),
            total_edges=total_edges,
            nodes_by_kind=dict(nodes_by_kind),
            edges_by_type=edges_by_type,
        )


__all__ = ["KnowledgeGraphService"]
