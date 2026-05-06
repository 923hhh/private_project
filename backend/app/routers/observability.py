"""Observability endpoints for backend diagnostics."""
from fastapi import APIRouter, status

from app.core.metrics import build_metrics_snapshot

router = APIRouter(prefix="/api/v1/system", tags=["可观测性"])


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="获取基础运行指标",
    description="返回应用进程内累计的请求计数、业务计数和耗时统计，供排障与演示环境验收使用。",
)
async def get_metrics() -> dict:
    """Return an in-process metrics snapshot."""
    return await build_metrics_snapshot()
