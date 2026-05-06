"""Compatibility router export for legacy task imports."""
from app.modules.tasks.router import MaintenanceTaskService, router

__all__ = ["router", "MaintenanceTaskService"]
