"""Schemas for formal knowledge import management."""
from datetime import datetime

from pydantic import BaseModel


class KnowledgeImportJobResponse(BaseModel):
    """Single knowledge import job summary."""

    id: int
    import_type: str
    processing_note: str | None = None
    title: str | None = None
    source_name: str
    source_type: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    section_reference: str | None = None
    replace_existing: bool
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    document_id: int | None = None
    preview_excerpt: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeImportJobListResponse(BaseModel):
    """Knowledge import job list response."""

    total: int
    jobs: list[KnowledgeImportJobResponse]


class KnowledgeImportPreviewResponse(BaseModel):
    """Preview payload returned before a PDF import is confirmed."""

    import_type: str
    processing_note: str | None = None
    normalized_title: str
    source_name: str
    source_type: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    section_reference: str | None = None
    replace_existing: bool
    page_count: int
    chunk_count: int
    preview_excerpt: str | None = None
    existing_document_detected: bool = False
    warning_message: str | None = None


class KnowledgeDocumentListItem(BaseModel):
    """Knowledge document row for the management center."""

    id: int
    title: str
    source_name: str
    source_type: str
    equipment_type: str
    equipment_model: str | None = None
    fault_type: str | None = None
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentDetailResponse(KnowledgeDocumentListItem):
    """Detailed knowledge document payload used for source trace-back."""

    section_reference: str | None = None
    page_reference: str | None = None
    content_excerpt: str | None = None


class KnowledgeDocumentListResponse(BaseModel):
    """Knowledge document list response."""

    total: int
    documents: list[KnowledgeDocumentListItem]


class KnowledgeChunkPreview(BaseModel):
    """Knowledge chunk preview used by the management center."""

    chunk_id: int
    chunk_index: int
    heading: str | None = None
    content: str
    page_reference: str | None = None
    section_reference: str | None = None
    section_path: str | None = None
    step_anchor: str | None = None
    image_anchor: str | None = None


class KnowledgeChunkPreviewResponse(BaseModel):
    """Document chunk preview response."""

    document_id: int
    total: int
    chunks: list[KnowledgeChunkPreview]
