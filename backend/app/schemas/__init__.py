"""Pydantic V2 schemas for request/response validation."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "SensorDataBase",
    "SensorDataCreate",
    "SensorDataUpdate",
    "SensorDataResponse",
    "KnowledgeDocumentCreate",
    "KnowledgeDocumentResponse",
    "KnowledgeImageAnalysis",
    "KnowledgeSearchRequest",
    "KnowledgeSearchHit",
    "KnowledgeSearchResponse",
    "KnowledgeImportJobResponse",
    "KnowledgeDocumentListItem",
    "KnowledgeDocumentListResponse",
    "KnowledgeChunkPreview",
    "KnowledgeChunkPreviewResponse",
    "KnowledgeReference",
    "MaintenanceTaskCreate",
    "MaintenanceTaskStepUpdate",
    "MaintenanceTaskStepResponse",
    "MaintenanceTaskResponse",
    "MaintenanceTaskHistoryItem",
    "MaintenanceTaskHistoryResponse",
    "MaintenanceTaskExportResponse",
    "MaintenanceCaseCreate",
    "MaintenanceCaseCorrectionCreate",
    "MaintenanceCaseReviewRequest",
    "MaintenanceCaseCorrectionResponse",
    "MaintenanceCaseResponse",
    "MaintenanceCaseListItem",
    "MaintenanceCaseListResponse",
    "AgentAssistRequest",
    "AgentAssistResponse",
    "AgentRunStep",
    "AgentTaskPreviewStep",
    "AgentToolCall",
    "WorkbenchOverviewResponse",
    "WorkbenchStatCard",
    "WorkbenchTaskSummary",
    "WorkbenchCaseSummary",
    "WorkbenchMetricHighlight",
]

_EXPORTS = {
    "SensorDataBase": ("app.schemas.sensor_data", "SensorDataBase"),
    "SensorDataCreate": ("app.schemas.sensor_data", "SensorDataCreate"),
    "SensorDataUpdate": ("app.schemas.sensor_data", "SensorDataUpdate"),
    "SensorDataResponse": ("app.schemas.sensor_data", "SensorDataResponse"),
    "KnowledgeDocumentCreate": ("app.schemas.knowledge", "KnowledgeDocumentCreate"),
    "KnowledgeDocumentResponse": ("app.schemas.knowledge", "KnowledgeDocumentResponse"),
    "KnowledgeImageAnalysis": ("app.schemas.knowledge", "KnowledgeImageAnalysis"),
    "KnowledgeSearchRequest": ("app.schemas.knowledge", "KnowledgeSearchRequest"),
    "KnowledgeSearchHit": ("app.schemas.knowledge", "KnowledgeSearchHit"),
    "KnowledgeSearchResponse": ("app.schemas.knowledge", "KnowledgeSearchResponse"),
    "KnowledgeChunkPreview": ("app.schemas.knowledge_imports", "KnowledgeChunkPreview"),
    "KnowledgeChunkPreviewResponse": ("app.schemas.knowledge_imports", "KnowledgeChunkPreviewResponse"),
    "KnowledgeDocumentListItem": ("app.schemas.knowledge_imports", "KnowledgeDocumentListItem"),
    "KnowledgeDocumentListResponse": ("app.schemas.knowledge_imports", "KnowledgeDocumentListResponse"),
    "KnowledgeImportJobResponse": ("app.schemas.knowledge_imports", "KnowledgeImportJobResponse"),
    "KnowledgeReference": ("app.schemas.tasks", "KnowledgeReference"),
    "MaintenanceTaskCreate": ("app.schemas.tasks", "MaintenanceTaskCreate"),
    "MaintenanceTaskStepUpdate": ("app.schemas.tasks", "MaintenanceTaskStepUpdate"),
    "MaintenanceTaskStepResponse": ("app.schemas.tasks", "MaintenanceTaskStepResponse"),
    "MaintenanceTaskResponse": ("app.schemas.tasks", "MaintenanceTaskResponse"),
    "MaintenanceTaskHistoryItem": ("app.schemas.tasks", "MaintenanceTaskHistoryItem"),
    "MaintenanceTaskHistoryResponse": ("app.schemas.tasks", "MaintenanceTaskHistoryResponse"),
    "MaintenanceTaskExportResponse": ("app.schemas.tasks", "MaintenanceTaskExportResponse"),
    "MaintenanceCaseCreate": ("app.schemas.cases", "MaintenanceCaseCreate"),
    "MaintenanceCaseCorrectionCreate": ("app.schemas.cases", "MaintenanceCaseCorrectionCreate"),
    "MaintenanceCaseReviewRequest": ("app.schemas.cases", "MaintenanceCaseReviewRequest"),
    "MaintenanceCaseCorrectionResponse": ("app.schemas.cases", "MaintenanceCaseCorrectionResponse"),
    "MaintenanceCaseResponse": ("app.schemas.cases", "MaintenanceCaseResponse"),
    "MaintenanceCaseListItem": ("app.schemas.cases", "MaintenanceCaseListItem"),
    "MaintenanceCaseListResponse": ("app.schemas.cases", "MaintenanceCaseListResponse"),
    "AgentAssistRequest": ("app.schemas.agents", "AgentAssistRequest"),
    "AgentAssistResponse": ("app.schemas.agents", "AgentAssistResponse"),
    "AgentRunStep": ("app.schemas.agents", "AgentRunStep"),
    "AgentTaskPreviewStep": ("app.schemas.agents", "AgentTaskPreviewStep"),
    "AgentToolCall": ("app.schemas.agents", "AgentToolCall"),
    "WorkbenchOverviewResponse": ("app.schemas.workbench", "WorkbenchOverviewResponse"),
    "WorkbenchStatCard": ("app.schemas.workbench", "WorkbenchStatCard"),
    "WorkbenchTaskSummary": ("app.schemas.workbench", "WorkbenchTaskSummary"),
    "WorkbenchCaseSummary": ("app.schemas.workbench", "WorkbenchCaseSummary"),
    "WorkbenchMetricHighlight": ("app.schemas.workbench", "WorkbenchMetricHighlight"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
