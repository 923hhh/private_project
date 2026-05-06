"""Maintenance module public surface."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "router",
    "CurrentUserCtx",
    "get_current_user_ctx",
    "require_roles",
    "MaintenanceAPIError",
    "MaintenanceService",
    "ATTACHMENT_UPLOAD_MAX_BYTES",
    "to_iso_cn",
    "create_access_token",
    "decode_token",
    "hash_password",
    "verify_password",
]

_EXPORTS = {
    "router": ("app.modules.maintenance.router", "router"),
    "CurrentUserCtx": ("app.modules.maintenance.deps", "CurrentUserCtx"),
    "get_current_user_ctx": ("app.modules.maintenance.deps", "get_current_user_ctx"),
    "require_roles": ("app.modules.maintenance.deps", "require_roles"),
    "MaintenanceAPIError": ("app.modules.maintenance.errors", "MaintenanceAPIError"),
    "MaintenanceService": ("app.modules.maintenance.service", "MaintenanceService"),
    "ATTACHMENT_UPLOAD_MAX_BYTES": ("app.modules.maintenance.service", "ATTACHMENT_UPLOAD_MAX_BYTES"),
    "to_iso_cn": ("app.modules.maintenance.datetime_util", "to_iso_cn"),
    "create_access_token": ("app.modules.maintenance.security", "create_access_token"),
    "decode_token": ("app.modules.maintenance.security", "decode_token"),
    "hash_password": ("app.modules.maintenance.security", "hash_password"),
    "verify_password": ("app.modules.maintenance.security", "verify_password"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
