"""Business logic layer."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "SensorService",
    "MaintenanceCaseService",
    "AgentOrchestrationService",
    "KnowledgeService",
    "KnowledgeImportService",
    "FaultImageAnalysisService",
    "KnowledgeOcrService",
    "ImageOcrResult",
    "MaintenanceTaskService",
    "WorkbenchOverviewService",
    "split_text_into_chunks",
]

_EXPORTS = {
    "SensorService": ("app.services.sensor_service", "SensorService"),
    "MaintenanceCaseService": ("app.services.case_service", "MaintenanceCaseService"),
    "AgentOrchestrationService": ("app.services.agent_orchestration_service", "AgentOrchestrationService"),
    "KnowledgeService": ("app.services.knowledge_service", "KnowledgeService"),
    "KnowledgeImportService": ("app.services.knowledge_import_service", "KnowledgeImportService"),
    "FaultImageAnalysisService": ("app.services.image_analysis_service", "FaultImageAnalysisService"),
    "KnowledgeOcrService": ("app.services.ocr_service", "KnowledgeOcrService"),
    "ImageOcrResult": ("app.services.ocr_service", "ImageOcrResult"),
    "MaintenanceTaskService": ("app.services.maintenance_task_service", "MaintenanceTaskService"),
    "WorkbenchOverviewService": ("app.services.workbench_service", "WorkbenchOverviewService"),
    "split_text_into_chunks": ("app.services.knowledge_chunking", "split_text_into_chunks"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
