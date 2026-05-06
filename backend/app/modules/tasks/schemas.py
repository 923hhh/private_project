"""Task schema compatibility exports."""
from app.schemas.tasks import (
    KnowledgeReference,
    MaintenanceTaskCreate,
    MaintenanceTaskExportResponse,
    MaintenanceTaskHistoryItem,
    MaintenanceTaskHistoryResponse,
    MaintenanceTaskResponse,
    MaintenanceTaskStepResponse,
    MaintenanceTaskStepUpdate,
    MaintenanceTaskTimelineEvent,
    MaintenanceTaskTimelineUpsert,
)

__all__ = [
    "KnowledgeReference",
    "MaintenanceTaskCreate",
    "MaintenanceTaskExportResponse",
    "MaintenanceTaskHistoryItem",
    "MaintenanceTaskHistoryResponse",
    "MaintenanceTaskResponse",
    "MaintenanceTaskStepResponse",
    "MaintenanceTaskStepUpdate",
    "MaintenanceTaskTimelineEvent",
    "MaintenanceTaskTimelineUpsert",
]
