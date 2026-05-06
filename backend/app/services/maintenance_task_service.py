"""Compatibility export for the maintenance task workflow service."""
from app.modules.tasks.application.task_service import (
    MaintenanceTaskService,
    finalize_maintenance_task_after_pipeline,
)

__all__ = ["MaintenanceTaskService", "finalize_maintenance_task_after_pipeline"]
