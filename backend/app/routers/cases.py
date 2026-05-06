"""Compatibility router export for maintenance cases."""
from app.modules.cases.router import (
    MaintenanceCaseService,
    add_maintenance_case_correction,
    create_maintenance_case,
    get_maintenance_case,
    list_maintenance_cases,
    review_maintenance_case,
    router,
)

__all__ = [
    "router",
    "MaintenanceCaseService",
    "create_maintenance_case",
    "list_maintenance_cases",
    "get_maintenance_case",
    "add_maintenance_case_correction",
    "review_maintenance_case",
]
