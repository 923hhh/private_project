"""Schemas for workbench overview APIs."""
from datetime import datetime

from pydantic import BaseModel, Field


class WorkbenchStatCard(BaseModel):
    """Summary card shown on the new workbench home page."""

    key: str
    label: str
    value: int
    accent: str = "neutral"


class WorkbenchTaskSummary(BaseModel):
    """Recent maintenance task summary."""

    id: int
    title: str
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    equipment_type: str
    equipment_model: str | None = None
    maintenance_level: str
    status: str
    total_steps: int
    completed_steps: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkbenchCaseSummary(BaseModel):
    """Recent case review summary."""

    id: int
    title: str
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    equipment_type: str
    equipment_model: str | None = None
    status: str
    task_id: int | None = None
    updated_at: datetime | None = None


class WorkbenchMetricHighlight(BaseModel):
    """Compact metric highlight for evaluation and runtime snapshots."""

    key: str
    label: str
    value: str
    description: str | None = None
    accent: str = "neutral"


class WorkbenchOverviewResponse(BaseModel):
    """Aggregated workbench overview for the formal front-end."""

    generated_at: datetime
    stats: list[WorkbenchStatCard] = Field(default_factory=list)
    featured_queries: list[str] = Field(default_factory=list)
    agent_capabilities: list[str] = Field(default_factory=list)
    quality_highlights: list[WorkbenchMetricHighlight] = Field(default_factory=list)
    runtime_highlights: list[WorkbenchMetricHighlight] = Field(default_factory=list)
    recent_tasks: list[WorkbenchTaskSummary] = Field(default_factory=list)
    recent_cases: list[WorkbenchCaseSummary] = Field(default_factory=list)
