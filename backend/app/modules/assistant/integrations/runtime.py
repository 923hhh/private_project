"""Compatibility export for assistant runtime integration."""
from app.integrations.agent_runtime import get_sensor_data_by_time_range, run_multi_agent_diagnosis

__all__ = ["get_sensor_data_by_time_range", "run_multi_agent_diagnosis"]
