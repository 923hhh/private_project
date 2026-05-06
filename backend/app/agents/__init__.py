# File: app/agents/__init__.py
"""AI Agent 模块（LangChain 智能体集成）"""
from __future__ import annotations

from typing import Any

__all__ = ["get_sensor_data_by_time_range", "DiagnosisAgent", "run_diagnosis", "run_multi_agent_diagnosis"]


def __getattr__(name: str) -> Any:
    # 延迟导入避免 app.agents 子模块在应用启动预热阶段产生循环依赖。
    if name == "get_sensor_data_by_time_range":
        from app.agents.tools import get_sensor_data_by_time_range as symbol

        return symbol
    if name in {"DiagnosisAgent", "run_diagnosis"}:
        from app.agents.diagnosis_agent import DiagnosisAgent, run_diagnosis

        return {"DiagnosisAgent": DiagnosisAgent, "run_diagnosis": run_diagnosis}[name]
    if name == "run_multi_agent_diagnosis":
        from app.agents.graph import run_multi_agent_diagnosis as symbol

        return symbol
    raise AttributeError(f"module 'app.agents' has no attribute {name!r}")
