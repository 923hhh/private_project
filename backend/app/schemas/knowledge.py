"""Knowledge base request and response schemas."""
from pydantic import BaseModel, Field, field_validator, model_validator


class KnowledgeDocumentCreate(BaseModel):
    """Create a knowledge document and automatically split it into chunks."""

    title: str = Field(..., min_length=1, description="知识文档标题")
    source_name: str = Field(..., min_length=1, description="原始来源文件名或资源名")
    source_type: str = Field(default="manual", description="知识来源类型，例如 manual/case/procedure")
    equipment_type: str = Field(..., min_length=1, description="设备类型")
    equipment_model: str | None = Field(default=None, description="设备型号")
    fault_type: str | None = Field(default=None, description="故障类型")
    section_reference: str | None = Field(default=None, description="章节标识")
    page_reference: str | None = Field(default=None, description="页码标识")
    content: str = Field(..., min_length=20, description="原始知识文本内容")


class KnowledgeDocumentResponse(BaseModel):
    """Document import response."""

    id: int
    title: str
    source_name: str
    source_type: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    status: str
    chunk_count: int


class KnowledgeSearchRequest(BaseModel):
    """Knowledge search request."""

    work_order_id: str | None = Field(default=None, description="工单编号")
    report_source: str | None = Field(default=None, description="报修来源")
    priority: str = Field(default="medium", description="工单优先级")
    maintenance_level: str = Field(default="standard", description="检修等级")
    query: str | None = Field(default=None, description="检修问题或关键词")
    equipment_type: str | None = Field(default=None, description="设备类型")
    equipment_model: str | None = Field(default=None, description="设备型号")
    fault_type: str | None = Field(default=None, description="故障类型")
    image_base64: str | None = Field(default=None, description="单张故障图片的 Base64 编码")
    image_mime_type: str | None = Field(default=None, description="故障图片 MIME 类型，例如 image/png")
    image_filename: str | None = Field(default=None, description="故障图片原始文件名")
    model_provider: str = Field(default="openai", description="图片识别模型提供商")
    model_name: str | None = Field(default=None, description="图片识别模型名称")
    limit: int = Field(default=5, ge=1, le=20, description="返回结果上限")

    @field_validator(
        "query",
        "work_order_id",
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
    def validate_search_inputs(self) -> "KnowledgeSearchRequest":
        if not any(
            [
                (self.query or "").strip(),
                (self.equipment_type or "").strip(),
                (self.equipment_model or "").strip(),
                (self.fault_type or "").strip(),
                (self.image_base64 or "").strip(),
            ]
        ):
            raise ValueError(
                "至少需要提供检索关键词、设备类型、设备型号、故障类型或故障图片中的一项。"
            )
        if self.image_base64 and not (self.image_mime_type or "").startswith("image/"):
            raise ValueError("上传故障图片时，image_mime_type 必须是 image/ 开头的有效类型。")
        return self


class KnowledgeImageAnalysis(BaseModel):
    """Fault image analysis summary used to enrich retrieval."""

    summary: str
    keywords: list[str] = Field(default_factory=list)
    source: str = Field(description="识别来源：vision_model / fallback")
    warning: str | None = None


class KnowledgeSearchHit(BaseModel):
    """Single knowledge search result."""

    chunk_id: int
    document_id: int
    title: str
    source_name: str
    source_type: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    excerpt: str
    section_reference: str | None = None
    section_path: str | None = None
    step_anchor: str | None = None
    page_reference: str | None = None
    image_anchor: str | None = None
    citation_label: str | None = None
    source_modality: str | None = None
    ocr_text: str | None = None
    image_caption: str | None = None
    evidence_summary: str | None = None
    expanded_content: str | None = None
    recommendation_reason: str
    score: float | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None


class KnowledgeSearchResponse(BaseModel):
    """Knowledge search response."""

    query: str | None = None
    effective_query: str | None = None
    effective_keywords: list[str] = Field(default_factory=list)
    query_type: str = Field(default="text_related")
    image_analysis_used: bool = False
    retrieval_path: list[str] = Field(default_factory=list)
    answer_confidence: float = 0.0
    coverage_warnings: list[str] = Field(default_factory=list)
    grounded: bool = True
    image_analysis: KnowledgeImageAnalysis | None = None
    total: int
    results: list[KnowledgeSearchHit]
