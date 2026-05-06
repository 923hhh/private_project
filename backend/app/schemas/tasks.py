"""Schemas for maintenance task workflow."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.diagnosis import DiagnosisStructuredPayload

class KnowledgeReference(BaseModel):
    """Knowledge citation attached to a task or step."""

    chunk_id: int
    document_id: int
    title: str
    source_name: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    section_reference: str | None = None
    section_path: str | None = None
    step_anchor: str | None = None
    page_reference: str | None = None
    image_anchor: str | None = None
    citation_label: str | None = None
    excerpt: str
    retrieval_score: float | None = None
    rerank_score: float | None = None


class MaintenanceTaskCreate(BaseModel):
    """Create a maintenance task from selected knowledge results."""

    title: str | None = Field(default=None, description="检修任务标题")
    work_order_id: str | None = Field(default=None, description="工单编号")
    asset_code: str | None = Field(default=None, description="设备编号")
    report_source: str | None = Field(default=None, description="报修来源")
    priority: str | None = Field(default=None, description="工单优先级")
    equipment_type: str = Field(..., min_length=1, description="设备类型")
    equipment_model: str | None = Field(default=None, description="设备型号")
    maintenance_level: str = Field(default="standard", description="检修等级")
    fault_type: str | None = Field(default=None, description="故障类型")
    symptom_description: str | None = Field(default=None, description="故障现象描述")
    source_chunk_ids: list[int] = Field(default_factory=list, description="关联知识分段 ID 列表")

    @field_validator(
        "title",
        "work_order_id",
        "asset_code",
        "report_source",
        "equipment_type",
        "equipment_model",
        "maintenance_level",
        "fault_type",
        "symptom_description",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("maintenance_level")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        normalized = (value or "standard").lower()
        allowed = {"routine", "standard", "emergency"}
        if normalized not in allowed:
            raise ValueError("maintenance_level 仅支持 routine、standard、emergency。")
        return normalized

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        allowed = {"low", "medium", "high", "urgent"}
        if normalized not in allowed:
            raise ValueError("priority 仅支持 low、medium、high、urgent。")
        return normalized

    @model_validator(mode="after")
    def validate_source(self) -> "MaintenanceTaskCreate":
        if not self.symptom_description and not self.source_chunk_ids:
            raise ValueError("至少需要提供故障现象描述或选中的知识条目。")
        return self


class MaintenanceTaskStepUpdate(BaseModel):
    """Update the runtime status of a task step."""

    status: str = Field(..., description="步骤状态")
    completion_note: str | None = Field(default=None, description="执行备注")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"pending", "in_progress", "completed", "skipped"}
        if normalized not in allowed:
            raise ValueError("status 仅支持 pending、in_progress、completed、skipped。")
        return normalized

    @field_validator("completion_note", mode="before")
    @classmethod
    def strip_note(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MaintenanceTaskStepResponse(BaseModel):
    """Response schema for a task step."""

    id: int
    step_order: int
    title: str
    instruction: str
    risk_warning: str | None = None
    caution: str | None = None
    confirmation_text: str | None = None
    required_tools: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = None
    status: str
    started_at: datetime | None = None
    completion_note: str | None = None
    completed_at: datetime | None = None
    runtime_events: list["MaintenanceTaskTimelineEvent"] = Field(default_factory=list)
    knowledge_refs: list[KnowledgeReference] = Field(default_factory=list)
    safety_preconditions: list[str] = Field(default_factory=list)
    requires_manual_authorization: bool = False
    authorization_hint: str | None = None


class MaintenanceTaskTimelineEvent(BaseModel):
    """Persisted execution timeline event for a maintenance task."""

    id: str
    type: str
    title: str
    description: str
    time: str


class MaintenanceTaskTimelineUpsert(BaseModel):
    """Upsert task execution timeline events."""

    events: list[MaintenanceTaskTimelineEvent] = Field(default_factory=list)
    diagnosis_report: str | None = Field(default=None, description="RAG/协作诊断生成的最终结论")


class MaintenanceTaskResponse(BaseModel):
    """Detailed maintenance task response."""

    id: int
    title: str
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    equipment_type: str
    equipment_model: str | None = None
    maintenance_level: str
    fault_type: str | None = None
    symptom_description: str | None = None
    status: str
    advice_card: str | None = None
    diagnosis_report: str | None = None
    diagnosis_structured: DiagnosisStructuredPayload | None = None
    execution_timeline: list[MaintenanceTaskTimelineEvent] = Field(default_factory=list)
    total_steps: int
    completed_steps: int
    source_refs: list[KnowledgeReference] = Field(default_factory=list)
    steps: list[MaintenanceTaskStepResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    run_started_at: datetime | None = None
    run_finished_at: datetime | None = None


class MaintenanceTaskHistoryItem(BaseModel):
    """History summary item."""

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
    run_started_at: datetime | None = None
    run_finished_at: datetime | None = None


class MaintenanceTaskHistoryResponse(BaseModel):
    """Task history response."""

    total: int
    tasks: list[MaintenanceTaskHistoryItem]


class MaintenanceTaskExportResponse(BaseModel):
    """Export payload for presentation or document generation."""

    task: MaintenanceTaskResponse
    exported_at: datetime
    export_summary: str
