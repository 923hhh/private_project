"""Compatibility router export for legacy workbench imports."""
from app.modules.workbench.router import WorkbenchOverviewService, router

__all__ = ["router", "WorkbenchOverviewService"]
