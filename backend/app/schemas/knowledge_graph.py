"""Knowledge graph query schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(description="Unique node ID in '{kind}:{numeric_id}' format")
    kind: str
    label: str
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: int
    source: str
    target: str
    relation_type: str
    notes: str | None = None
    created_at: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    nodes_by_kind: dict[str, int]
    edges_by_type: dict[str, int]
