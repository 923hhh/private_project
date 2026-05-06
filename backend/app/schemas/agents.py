"""Schemas for agent orchestration APIs."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.diagnosis import DiagnosisStructuredPayload
from app.schemas.knowledge import KnowledgeImageAnalysis, KnowledgeSearchHit


class AgentAssistRequest(BaseModel):
    """Unified request payload for agent-based assistance."""

    work_order_id: str | None = Field(default=None, description="工单编号")
    asset_code: str | None = Field(default=None, description="设备编号")
    report_source: str | None = Field(default=None, description="报修来源")
    priority: str = Field(default="medium", description="工单优先级")
    query: str | None = Field(default=None, description="用户当前检修问题或故障描述")
    equipment_type: str | None = Field(default=None, description="设备类型")
    equipment_model: str | None = Field(default=None, description="设备型号")
    fault_type: str | None = Field(default=None, description="故障类型")
    maintenance_level: str = Field(default="standard", description="检修等级")
    limit: int = Field(default=5, ge=1, le=10, description="知识召回上限")
    selected_chunk_ids: list[int] = Field(default_factory=list, description="已选知识条目")
    image_base64: str | None = Field(default=None, description="故障图片 Base64")
    image_mime_type: str | None = Field(default=None, description="故障图片 MIME 类型")
    image_filename: str | None = Field(default=None, description="故障图片文件名")
    model_provider: str = Field(default="openai", description="多模态模型提供商")
    model_name: str | None = Field(default=None, description="多模态模型名称")
    maintenance_task_id: int | None = Field(
        default=None,
        description="关联检修任务 ID；流水线成功结束后将该任务及步骤标为已完成",
    )

    @field_validator("maintenance_task_id", mode="before")
    @classmethod
    def coerce_maintenance_task_id(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

    @field_validator(
        "query",
        "work_order_id",
        "asset_code",
        "report_source",
        "equipment_type",
        "equipment_model",
        "fault_type",
        "image_base64",
        "image_mime_type",
        "image_filename",
        "model_provider",
        "model_name",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("maintenance_level")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        normalized = (value or "standard").strip().lower()
        allowed = {"routine", "standard", "emergency"}
        if normalized not in allowed:
            raise ValueError("maintenance_level 仅支持 routine、standard、emergency。")
        return normalized

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: str) -> str:
        normalized = (value or "medium").strip().lower()
        allowed = {"low", "medium", "high", "urgent"}
        if normalized not in allowed:
            raise ValueError("priority 仅支持 low、medium、high、urgent。")
        return normalized

    @model_validator(mode="after")
    def validate_agent_inputs(self) -> "AgentAssistRequest":
        tid = self.maintenance_task_id
        if tid is not None and tid < 1:
            raise ValueError("maintenance_task_id 必须为正整数。")
        if not any(
            [
                self.query,
                self.equipment_type,
                self.equipment_model,
                self.fault_type,
                self.image_base64,
                self.selected_chunk_ids,
            ]
        ):
            raise ValueError("至少需要提供检修问题、设备信息、故障图片或已选知识条目中的一项。")
        if self.image_base64 and not (self.image_mime_type or "").startswith("image/"):
            raise ValueError("上传故障图片时，image_mime_type 必须是 image/ 开头的有效类型。")
        return self


class AgentRequestContext(BaseModel):
    """Business intake summary echoed back to the workbench."""

    maintenance_task_id: int | None = None
    work_order_id: str | None = None
    asset_code: str | None = None
    report_source: str | None = None
    priority: str = "medium"
    maintenance_level: str = "standard"
    equipment_type: str | None = None
    equipment_model: str | None = None
    fault_type: str | None = None
    symptom_description: str | None = None
    selected_chunk_ids: list[int] = Field(default_factory=list)
    has_image: bool = False


class AgentExecutionBrief(BaseModel):
    """Decision summary for whether the plan can move into execution."""

    status: str
    decision: str
    recommended_path: str
    next_actions: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    authorization_required: bool = False


class AgentTaskPreviewStep(BaseModel):
    """Preview of a planned maintenance step."""

    step_order: int
    title: str
    instruction: str
    risk_warning: str | None = None
    caution: str | None = None
    confirmation_text: str | None = None
    required_tools: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = None
    safety_preconditions: list[str] = Field(default_factory=list)
    requires_manual_authorization: bool = False
    authorization_hint: str | None = None


class AgentRunStep(BaseModel):
    """Single agent contribution within a run."""

    agent_name: str
    title: str
    status: str
    summary: str
    citations: list[str] = Field(default_factory=list)


class AgentToolCall(BaseModel):
    """Structured business tool execution inside one Agent run."""

    tool_name: str
    title: str
    status: str
    summary: str
    risk_level: str = "low"
    blocking: bool = False
    requires_human_authorization: bool = False
    input_summary: str | None = None
    details: list[str] = Field(default_factory=list)
    output_payload: dict = Field(default_factory=dict)


class AgentRelatedCase(BaseModel):
    """Recommended similar maintenance case."""

    id: int
    title: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    status: str
    task_id: int | None = None
    updated_at: datetime | None = None
    match_reason: str


class AgentAssistResponse(BaseModel):
    """Unified response payload for agent collaboration."""

    run_id: str
    status: str
    summary: str
    diagnosis_report: str | None = None
    diagnosis_structured: DiagnosisStructuredPayload | None = None
    request_context: AgentRequestContext | None = None
    execution_brief: AgentExecutionBrief | None = None
    effective_query: str | None = None
    effective_keywords: list[str] = Field(default_factory=list)
    image_analysis: KnowledgeImageAnalysis | None = None
    knowledge_results: list[KnowledgeSearchHit] = Field(default_factory=list)
    related_cases: list[AgentRelatedCase] = Field(default_factory=list)
    task_plan_preview: list[AgentTaskPreviewStep] = Field(default_factory=list)
    risk_findings: list[str] = Field(default_factory=list)
    case_suggestions: list[str] = Field(default_factory=list)
    agents: list[AgentRunStep] = Field(default_factory=list)
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    created_at: datetime
