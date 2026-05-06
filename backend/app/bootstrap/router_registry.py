"""Router registration for the application factory."""
from fastapi import FastAPI

from app.modules.assistant.router import router as agents_router
from app.modules.diagnosis.router import router as diagnosis_router
from app.modules.cases.router import router as cases_router
from app.modules.knowledge.graph_router import router as knowledge_graph_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.maintenance import router as maintenance_router
from app.modules.tasks.router import router as tasks_router
from app.modules.workbench.router import router as workbench_router
from app.routers.health import router as health_router
from app.routers.observability import router as observability_router


def register_routers(app: FastAPI) -> None:
    """Register all public API routers."""
    app.include_router(health_router)
    # 检修域契约 API；legacy：tasks / agents / knowledge / cases 等路由仍保留给现有工作台使用
    app.include_router(maintenance_router)
    app.include_router(observability_router)
    app.include_router(workbench_router)
    app.include_router(agents_router)
    app.include_router(diagnosis_router)
    app.include_router(knowledge_router)
    app.include_router(knowledge_graph_router)
    app.include_router(tasks_router)
    app.include_router(cases_router)
