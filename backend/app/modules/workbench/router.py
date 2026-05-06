"""Workbench overview APIs for the formal Next.js front-end."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.workbench.application.overview_service import WorkbenchOverviewService
from app.modules.workbench.schemas import (
    WorkbenchCaseSummary,
    WorkbenchMetricHighlight,
    WorkbenchOverviewResponse,
    WorkbenchStatCard,
    WorkbenchTaskSummary,
)

router = APIRouter(prefix="/api/v1/workbench", tags=["正式工作台"])
logger = logging.getLogger(__name__)


@router.get(
    "/overview",
    response_model=WorkbenchOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="正式工作台概览",
    description="聚合知识库、检修任务、案例审核和 Agent 能力摘要，供正式前端首页加载。",
)
async def get_workbench_overview(
    session: AsyncSession = Depends(get_session),
) -> WorkbenchOverviewResponse:
    logger.info("workbench_overview_request")
    payload = await WorkbenchOverviewService(session).build_overview()
    return WorkbenchOverviewResponse(
        generated_at=payload["generated_at"],
        stats=[WorkbenchStatCard(**item) for item in payload["stats"]],
        featured_queries=payload["featured_queries"],
        agent_capabilities=payload["agent_capabilities"],
        quality_highlights=[
            WorkbenchMetricHighlight(**item) for item in payload.get("quality_highlights", [])
        ],
        runtime_highlights=[
            WorkbenchMetricHighlight(**item) for item in payload.get("runtime_highlights", [])
        ],
        recent_tasks=[WorkbenchTaskSummary(**item) for item in payload["recent_tasks"]],
        recent_cases=[WorkbenchCaseSummary(**item) for item in payload["recent_cases"]],
    )


__all__ = ["router", "WorkbenchOverviewService"]
