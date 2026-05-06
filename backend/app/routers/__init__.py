# File: app/routers/__init__.py
"""API 路由处理器"""
from app.modules.assistant.router import router as agents_router
from app.modules.cases.router import router as cases_router
from app.modules.diagnosis.router import router as diagnosis_router
from app.modules.knowledge.graph_router import router as knowledge_graph_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.tasks.router import router as tasks_router
from app.modules.workbench.router import router as workbench_router
from app.routers.health import router as health_router

__all__ = [
    "health_router",
    "workbench_router",
    "agents_router",
    "diagnosis_router",
    "knowledge_router",
    "knowledge_graph_router",
    "tasks_router",
    "cases_router",
]
