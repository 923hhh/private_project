"""Diagnosis module public surface."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "router",
    "DiagnosisAgent",
    "run_diagnosis",
    "run_multi_agent_diagnosis",
    "get_sensor_data_by_time_range",
    "DiagnosisRequest",
    "DiagnosisResponse",
]

_EXPORTS = {
    "router": ("app.modules.diagnosis.router", "router"),
    "DiagnosisAgent": ("app.modules.diagnosis.llm.diagnosis_agent", "DiagnosisAgent"),
    "run_diagnosis": ("app.modules.diagnosis.llm.diagnosis_agent", "run_diagnosis"),
    "run_multi_agent_diagnosis": ("app.modules.diagnosis.workflow.graph", "run_multi_agent_diagnosis"),
    "get_sensor_data_by_time_range": ("app.modules.diagnosis.workflow.tools", "get_sensor_data_by_time_range"),
    "DiagnosisRequest": ("app.modules.diagnosis.schemas", "DiagnosisRequest"),
    "DiagnosisResponse": ("app.modules.diagnosis.schemas", "DiagnosisResponse"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
