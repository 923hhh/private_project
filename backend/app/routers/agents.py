"""Compatibility export for assistant router."""
from app.modules.assistant.router import (
    AgentOrchestrationService,
    assist_with_agents,
    assist_with_agents_stream,
    get_agent_run,
    router,
)

__all__ = [
    "router",
    "AgentOrchestrationService",
    "assist_with_agents",
    "assist_with_agents_stream",
    "get_agent_run",
]
