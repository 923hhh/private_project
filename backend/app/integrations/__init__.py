"""External capability adapters."""
from __future__ import annotations

from typing import Any

__all__ = [
    "DiagnosisAgent",
    "run_diagnosis",
    "run_multi_agent_diagnosis",
    "get_sensor_data_by_time_range",
    "FaultImageAnalysisService",
    "ImageAnalysisResult",
    "PdfKnowledgeImportService",
    "ExtractedPdfPage",
    "normalize_pdf_text",
    "KnowledgeOcrService",
    "ImageOcrResult",
]


def __getattr__(name: str) -> Any:
    if name in {"get_sensor_data_by_time_range", "run_multi_agent_diagnosis"}:
        from app.modules.assistant.integrations.runtime import (
            get_sensor_data_by_time_range,
            run_multi_agent_diagnosis,
        )

        return {
            "get_sensor_data_by_time_range": get_sensor_data_by_time_range,
            "run_multi_agent_diagnosis": run_multi_agent_diagnosis,
        }[name]
    if name in {"FaultImageAnalysisService", "ImageAnalysisResult"}:
        from app.integrations.image_analysis import FaultImageAnalysisService, ImageAnalysisResult

        return {"FaultImageAnalysisService": FaultImageAnalysisService, "ImageAnalysisResult": ImageAnalysisResult}[name]
    if name in {"DiagnosisAgent", "run_diagnosis"}:
        from app.integrations.llm import DiagnosisAgent, run_diagnosis

        return {"DiagnosisAgent": DiagnosisAgent, "run_diagnosis": run_diagnosis}[name]
    if name in {"ExtractedPdfPage", "PdfKnowledgeImportService", "normalize_pdf_text"}:
        from app.integrations.pdf_import import ExtractedPdfPage, PdfKnowledgeImportService, normalize_pdf_text

        return {
            "ExtractedPdfPage": ExtractedPdfPage,
            "PdfKnowledgeImportService": PdfKnowledgeImportService,
            "normalize_pdf_text": normalize_pdf_text,
        }[name]
    if name in {"ImageOcrResult", "KnowledgeOcrService"}:
        from app.services.ocr_service import ImageOcrResult, KnowledgeOcrService

        return {"ImageOcrResult": ImageOcrResult, "KnowledgeOcrService": KnowledgeOcrService}[name]
    raise AttributeError(f"module 'app.integrations' has no attribute {name!r}")
