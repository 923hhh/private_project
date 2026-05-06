"""LLM-facing integration exports.

当前 LLM 调用仍主要封装在诊断智能体内部。本层先作为未来独立 LLM client
的稳定出口，避免业务模块继续直接依赖旧路径。
"""
from app.agents.diagnosis_agent import DiagnosisAgent, run_diagnosis

__all__ = ["DiagnosisAgent", "run_diagnosis"]
