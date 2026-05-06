"""Schemas for case upload, review and manual correction."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.tasks.schemas import KnowledgeReference


class MaintenanceCaseCreate(BaseModel):
    """Create a maintenance case from task execution or manual input."""

    title: str = Field(..., min_length=1, description="案例标题")
    work_order_id: str | None = Field(default=None, description="工单编号")
    asset_code: str | None = Field(default=None, description="设备编号")
    report_source: str | None = Field(default=None, description="报修来源")
    priority: str | None = Field(default=None, description="工单优先级")
    equipment_type: str = Field(..., min_length=1, description="设备类型")
    equipment_model: str | None = Field(default=None, description="设备型号")
    fault_type: str | None = Field(default=None, description="故障类型")
    task_id: int | None = Field(default=None, description="关联检修任务 ID")
    symptom_description: str = Field(..., min_length=1, description="故障现象描述")
    processing_steps: list[str] = Field(default_factory=list, description="处理步骤列表")
    resolution_summary: str | None = Field(default=None, description="处理结果总结")
    attachment_name: str | None = Field(default=None, description="附件名称")
    attachment_url: str | None = Field(default=None, description="附件地址")
    knowledge_refs: list[KnowledgeReference] = Field(default_factory=list, description="关联知识引用")

    @field_validator(
        "title",
        "work_order_id",
        "asset_code",
        "report_source",
        "equipment_type",
        "equipment_model",
        "fault_type",
        "symptom_description",
        "resolution_summary",
        "attachment_name",
        "attachment_url",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("processing_steps", mode="before")
    @classmethod
    def normalize_steps(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.splitlines() if part.strip()]
            return parts
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("processing_steps 必须是字符串列表或多行文本。")

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
    def validate_case(self) -> "MaintenanceCaseCreate":
        if not self.processing_steps and not self.resolution_summary:
            raise ValueError("至少需要提供处理步骤或处理结果总结中的一项。")
        return self


class MaintenanceCaseCorrectionCreate(BaseModel):
    """Create a manual correction for case-related outputs."""

    correction_target: str = Field(..., description="修正目标")
    original_content: str | None = Field(default=None, description="原始内容")
    corrected_content: str = Field(..., min_length=1, description="修正后内容")
    note: str | None = Field(default=None, description="修正说明")

    @field_validator("correction_target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"retrieval_result", "model_output", "summary", "procedure"}
        if normalized not in allowed:
            raise ValueError("correction_target 仅支持 retrieval_result、model_output、summary、procedure。")
        return normalized

    @field_validator("original_content", "corrected_content", "note", mode="before")
    @classmethod
    def strip_correction_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MaintenanceCaseReviewRequest(BaseModel):
    """Approve or reject a maintenance case."""

    action: str = Field(..., description="审核动作")
    reviewer_name: str | None = Field(default=None, description="审核人")
    review_note: str | None = Field(default=None, description="审核意见")

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"approve", "reject"}
        if normalized not in allowed:
            raise ValueError("action 仅支持 approve 或 reject。")
        return normalized

    @field_validator("reviewer_name", "review_note", mode="before")
    @classmethod
    def strip_review_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MaintenanceCaseCorrectionResponse(BaseModel):
    """Correction response item."""

    id: int
    correction_target: str
    original_content: str | None = None
    corrected_content: str
    note: str | None = None
    status: str
    created_at: datetime | None = None


class MaintenanceCaseResponse(BaseModel):
    """Detailed maintenance case response."""

    id: int
    title: str
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    task_id: int | None = None
    symptom_description: str
    processing_steps: list[str] = Field(default_factory=list)
    resolution_summary: str | None = None
    attachment_name: str | None = None
    attachment_url: str | None = None
    knowledge_refs: list[KnowledgeReference] = Field(default_factory=list)
    status: str
    reviewer_name: str | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    source_document_id: int | None = None
    corrections: list[MaintenanceCaseCorrectionResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaintenanceCaseListItem(BaseModel):
    """Case list summary item."""

    id: int
    title: str
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    status: str
    task_id: int | None = None
    source_document_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaintenanceCaseListResponse(BaseModel):
    """Case list response."""

    total: int
    cases: list[MaintenanceCaseListItem]
