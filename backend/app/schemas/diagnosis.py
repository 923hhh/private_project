"""Diagnosis schemas for legacy diagnose APIs and structured outputs."""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DiagnosisRequest(BaseModel):
    """Legacy synchronous diagnosis request payload."""

    start_time: str = Field(..., description="起始时间，格式 YYYY-MM-DD HH:MM:SS")
    end_time: str = Field(..., description="结束时间，格式 YYYY-MM-DD HH:MM:SS")
    symptom_description: str | None = Field(default=None, description="症状描述")
    model_provider: str = Field(default="openai", description="模型提供商")
    model_name: str | None = Field(default=None, description="模型名称")
    maintenance_task_id: int | None = Field(default=None, description="关联检修任务 ID")

    @field_validator("start_time", "end_time", "symptom_description", "model_provider", "model_name", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class DiagnosisResponse(BaseModel):
    """Legacy synchronous diagnosis response payload."""

    code: int = 200
    message: str = "诊断完成"
    data: Any = None


class DiagnosisRootCause(BaseModel):
    """Candidate root cause with confidence and evidence note."""

    name: str
    confidence: int = Field(ge=0, le=100)
    evidence: str


class DiagnosisEvidenceItem(BaseModel):
    """Structured evidence reference for diagnosis."""

    document_title: str
    chunk_id: int | None = None
    citation_label: str | None = None
    section: str | None = None
    excerpt: str | None = None
    source_name: str | None = None
    relevance_score: int | None = Field(default=None, ge=0, le=100)


class DiagnosisStepSection(BaseModel):
    """Structured sub-section inside one action/procedure step."""

    label: str
    items: list[str] = Field(default_factory=list)


class DiagnosisStep(BaseModel):
    """Structured step/action returned for diagnosis and procedure answers."""

    step_no: int | None = None
    title: str
    summary: str = ""
    sections: list[DiagnosisStepSection] = Field(default_factory=list)
    meta: list[str] = Field(default_factory=list)
    raw_text: str | None = None

    @field_validator("title", "summary", "raw_text", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("meta", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class DiagnosisStructuredPayload(BaseModel):
    """Structured diagnosis payload returned by backend services."""

    answer_mode: Literal["diagnosis", "procedure"] = "diagnosis"
    most_likely_fault: str
    risk_level: str
    confidence: int = Field(ge=0, le=100)
    main_symptoms: list[str] = Field(default_factory=list)
    preliminary_conclusion: str
    next_steps: list[DiagnosisStep] = Field(default_factory=list)
    root_causes: list[DiagnosisRootCause] = Field(default_factory=list)
    evidence_items: list[DiagnosisEvidenceItem] = Field(default_factory=list)
    evidence_count: int = 0
    top_similarity: int | None = Field(default=None, ge=0, le=100)
    work_order_ready: bool = False

    @field_validator("next_steps", mode="before")
    @classmethod
    def coerce_next_steps(cls, value: object) -> list[DiagnosisStep | dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            normalized: list[DiagnosisStep | dict[str, Any]] = []
            for index, item in enumerate(value, start=1):
                if isinstance(item, str):
                    normalized.append(
                        {
                            "step_no": index,
                            "title": item.strip() or f"步骤 {index}",
                            "summary": "",
                            "sections": [],
                            "meta": [],
                            "raw_text": item.strip() or None,
                        }
                    )
                else:
                    normalized.append(item)
            return normalized
        return []
