"""Maintenance task workflow APIs."""
import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.modules.tasks.application.task_service import MaintenanceTaskService
from app.modules.tasks.schemas import (
    KnowledgeReference,
    MaintenanceTaskCreate,
    MaintenanceTaskExportResponse,
    MaintenanceTaskHistoryItem,
    MaintenanceTaskHistoryResponse,
    MaintenanceTaskResponse,
    MaintenanceTaskStepResponse,
    MaintenanceTaskStepUpdate,
    MaintenanceTaskTimelineUpsert,
)
from app.schemas.diagnosis import DiagnosisStructuredPayload

router = APIRouter(prefix="/api/v1", tags=["检修任务"])
logger = logging.getLogger(__name__)


def _build_task_response(payload: dict) -> MaintenanceTaskResponse:
    return MaintenanceTaskResponse(
        id=payload["id"],
        title=payload["title"],
        work_order_id=payload.get("work_order_id"),
        asset_code=payload.get("asset_code"),
        report_source=payload.get("report_source"),
        priority=payload.get("priority") or "medium",
        equipment_type=payload["equipment_type"],
        equipment_model=payload.get("equipment_model"),
        maintenance_level=payload["maintenance_level"],
        fault_type=payload.get("fault_type"),
        symptom_description=payload.get("symptom_description"),
        status=payload["status"],
        advice_card=payload.get("advice_card"),
        diagnosis_report=payload.get("diagnosis_report"),
        diagnosis_structured=(
            DiagnosisStructuredPayload(**payload["diagnosis_structured"])
            if payload.get("diagnosis_structured") is not None
            else None
        ),
        execution_timeline=payload.get("execution_timeline") or [],
        total_steps=payload["total_steps"],
        completed_steps=payload["completed_steps"],
        source_refs=[KnowledgeReference(**item) for item in payload.get("source_refs", [])],
        steps=[
            MaintenanceTaskStepResponse(
                **{
                    **item,
                    "knowledge_refs": [KnowledgeReference(**ref) for ref in item.get("knowledge_refs", [])],
                }
            )
            for item in payload.get("steps", [])
        ],
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
        run_started_at=payload.get("run_started_at"),
        run_finished_at=payload.get("run_finished_at"),
    )


@router.post(
    "/tasks",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建检修任务",
    description="根据设备信息、故障现象和已选知识条目，生成标准化检修任务与步骤。",
)
async def create_maintenance_task(
    request: MaintenanceTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskResponse:
    logger.info(
        "maintenance_task_create equipment_type=%s equipment_model=%s maintenance_level=%s refs=%s",
        request.equipment_type,
        request.equipment_model or "",
        request.maintenance_level,
        len(request.source_chunk_ids),
    )
    service = MaintenanceTaskService(session)
    payload = await service.create_task(request)
    return _build_task_response(payload)


@router.get(
    "/tasks/{task_id}",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="获取检修任务详情",
)
async def get_maintenance_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskResponse:
    service = MaintenanceTaskService(session)
    try:
        payload = await service.get_task_detail(task_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_not_found",
            message=str(exc),
        ) from exc
    return _build_task_response(payload)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除检修任务",
    description="删除指定检修任务及其关联引用关系。",
)
async def delete_maintenance_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = MaintenanceTaskService(session)
    try:
        await service.delete_task(task_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_not_found",
            message=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tasks/{task_id}/retry",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="重新运行检修任务",
    description="清空既有诊断报告、执行时间线和步骤完成态，使任务重新进入可诊断状态。",
)
async def retry_maintenance_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskResponse:
    service = MaintenanceTaskService(session)
    try:
        payload = await service.reset_task_for_retry(task_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_not_found",
            message=str(exc),
        ) from exc
    return _build_task_response(payload)


@router.patch(
    "/tasks/{task_id}/execution-timeline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="保存任务执行时间线",
    description="将前端采集的 SSE 执行事件写入任务 execution_timeline 字段。",
)
async def upsert_maintenance_task_execution_timeline(
    task_id: int,
    request: MaintenanceTaskTimelineUpsert,
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = MaintenanceTaskService(session)
    try:
        await service.upsert_execution_timeline(
            task_id,
            [e.model_dump() for e in request.events],
            diagnosis_report=request.diagnosis_report,
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_not_found",
            message=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/tasks/{task_id}/steps/{step_id}",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="更新检修步骤状态",
    description="对任务步骤进行完成、跳过或进行中的状态更新。",
)
async def update_maintenance_task_step(
    task_id: int,
    step_id: int,
    request: MaintenanceTaskStepUpdate,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskResponse:
    logger.info(
        "maintenance_task_step_update task_id=%s step_id=%s status=%s",
        task_id,
        step_id,
        request.status,
    )
    service = MaintenanceTaskService(session)
    try:
        payload = await service.update_task_step(task_id, step_id, request)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_step_not_found",
            message=str(exc),
        ) from exc
    return _build_task_response(payload)


@router.get(
    "/history",
    response_model=MaintenanceTaskHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="检修任务历史",
)
async def list_maintenance_history(
    limit: int = Query(default=10, ge=1, le=50, description="历史记录返回上限"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="按任务状态过滤：pending / in_progress / completed / skipped",
    ),
    priority_filter: str | None = Query(
        default=None,
        alias="priority",
        description="按优先级过滤：low / medium / high / urgent",
    ),
    work_order_id: str | None = Query(default=None, description="按工单编号模糊过滤"),
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskHistoryResponse:
    service = MaintenanceTaskService(session)
    tasks = await service.list_history(
        limit=limit,
        status_filter=status_filter,
        priority_filter=priority_filter,
        work_order_id=work_order_id,
    )
    return MaintenanceTaskHistoryResponse(
        total=len(tasks),
        tasks=[MaintenanceTaskHistoryItem(**item) for item in tasks],
    )


@router.get(
    "/export/{task_id}",
    response_model=MaintenanceTaskExportResponse,
    status_code=status.HTTP_200_OK,
    summary="导出检修任务",
    description="导出任务、步骤、知识引用和总结，便于归档、复盘或共享。",
)
async def export_maintenance_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceTaskExportResponse:
    service = MaintenanceTaskService(session)
    try:
        payload = await service.export_task(task_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_task_not_found",
            message=str(exc),
        ) from exc

    return MaintenanceTaskExportResponse(
        task=_build_task_response(payload["task"]),
        exported_at=payload["exported_at"],
        export_summary=payload["export_summary"],
    )


__all__ = ["router", "MaintenanceTaskService"]
