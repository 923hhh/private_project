"""Assistant module public surface."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "router",
    "AgentOrchestrationService",
    "AgentAssistRequest",
    "AgentAssistResponse",
    "AgentTaskPreviewStep",
    "AgentRunStep",
    "AgentToolCall",
]

_EXPORTS = {
    "router": ("app.modules.assistant.router", "router"),
    "AgentOrchestrationService": (
        "app.modules.assistant.application.orchestration_service",
        "AgentOrchestrationService",
    ),
    "AgentAssistRequest": ("app.modules.assistant.schemas", "AgentAssistRequest"),
    "AgentAssistResponse": ("app.modules.assistant.schemas", "AgentAssistResponse"),
    "AgentTaskPreviewStep": ("app.modules.assistant.schemas", "AgentTaskPreviewStep"),
    "AgentRunStep": ("app.modules.assistant.schemas", "AgentRunStep"),
    "AgentToolCall": ("app.modules.assistant.schemas", "AgentToolCall"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
