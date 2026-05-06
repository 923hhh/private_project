"""Compatibility export for the knowledge import service."""
from app.modules.knowledge.application.import_service import (
    KnowledgeImportService,
    render_pdf_pages_as_png_bytes,
)

__all__ = ["KnowledgeImportService", "render_pdf_pages_as_png_bytes"]
