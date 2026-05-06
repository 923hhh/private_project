"""Maintenance case upload, review and correction APIs for TODO-SB-5."""
import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.modules.cases.application.case_service import MaintenanceCaseService
from app.modules.cases.schemas import (
    MaintenanceCaseCorrectionCreate,
    MaintenanceCaseCorrectionResponse,
    MaintenanceCaseCreate,
    MaintenanceCaseListItem,
    MaintenanceCaseListResponse,
    MaintenanceCaseResponse,
    MaintenanceCaseReviewRequest,
)
from app.modules.tasks.schemas import KnowledgeReference

router = APIRouter(prefix="/api/v1", tags=["案例沉淀"])
logger = logging.getLogger(__name__)


def _build_case_response(payload: dict) -> MaintenanceCaseResponse:
    return MaintenanceCaseResponse(
        id=payload["id"],
        title=payload["title"],
        work_order_id=payload.get("work_order_id"),
        asset_code=payload.get("asset_code"),
        report_source=payload.get("report_source"),
        priority=payload.get("priority") or "medium",
        equipment_type=payload["equipment_type"],
        equipment_model=payload.get("equipment_model"),
        fault_type=payload.get("fault_type"),
        task_id=payload.get("task_id"),
        symptom_description=payload["symptom_description"],
        processing_steps=payload.get("processing_steps", []),
        resolution_summary=payload.get("resolution_summary"),
        attachment_name=payload.get("attachment_name"),
        attachment_url=payload.get("attachment_url"),
        knowledge_refs=[KnowledgeReference(**item) for item in payload.get("knowledge_refs", [])],
        status=payload["status"],
        reviewer_name=payload.get("reviewer_name"),
        review_note=payload.get("review_note"),
        reviewed_at=payload.get("reviewed_at"),
        source_document_id=payload.get("source_document_id"),
        corrections=[
            MaintenanceCaseCorrectionResponse(**item) for item in payload.get("corrections", [])
        ],
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
    )


@router.post(
    "/cases",
    response_model=MaintenanceCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上传检修案例",
    description="将检修任务结果或人工整理经验沉淀为待审核案例。",
)
async def create_maintenance_case(
    request: MaintenanceCaseCreate,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceCaseResponse:
    logger.info(
        "maintenance_case_create title=%s equipment_type=%s task_id=%s refs=%s",
        request.title,
        request.equipment_type,
        request.task_id or "",
        len(request.knowledge_refs),
    )
    service = MaintenanceCaseService(session)
    try:
        payload = await service.create_case(request)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_case_dependency_not_found",
            message=str(exc),
        ) from exc
    return _build_case_response(payload)


@router.get(
    "/cases",
    response_model=MaintenanceCaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="检修案例列表",
)
async def list_maintenance_cases(
    limit: int = Query(default=10, ge=1, le=50, description="案例列表返回上限"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="按案例状态过滤：pending_review / approved / rejected",
    ),
    priority_filter: str | None = Query(
        default=None,
        alias="priority",
        description="按优先级过滤：low / medium / high / urgent",
    ),
    work_order_id: str | None = Query(default=None, description="按工单编号模糊过滤"),
    session: AsyncSession = Depends(get_session),
) -> MaintenanceCaseListResponse:
    service = MaintenanceCaseService(session)
    cases = await service.list_cases(
        limit=limit,
        status_filter=status_filter,
        priority_filter=priority_filter,
        work_order_id=work_order_id,
    )
    return MaintenanceCaseListResponse(
        total=len(cases),
        cases=[MaintenanceCaseListItem(**item) for item in cases],
    )


@router.get(
    "/cases/{case_id}",
    response_model=MaintenanceCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="获取案例详情",
)
async def get_maintenance_case(
    case_id: int,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceCaseResponse:
    service = MaintenanceCaseService(session)
    try:
        payload = await service.get_case_detail(case_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_case_not_found",
            message=str(exc),
        ) from exc
    return _build_case_response(payload)


@router.delete(
    "/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除检修案例",
)
async def delete_maintenance_case(
    case_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    logger.info("maintenance_case_delete case_id=%s", case_id)
    service = MaintenanceCaseService(session)
    try:
        await service.delete_case(case_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_case_not_found",
            message=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/cases/{case_id}/corrections",
    response_model=MaintenanceCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="新增人工修正",
    description="对检索结果、模型输出、总结或步骤进行人工勘误与补充。",
)
async def add_maintenance_case_correction(
    case_id: int,
    request: MaintenanceCaseCorrectionCreate,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceCaseResponse:
    logger.info(
        "maintenance_case_correction case_id=%s target=%s",
        case_id,
        request.correction_target,
    )
    service = MaintenanceCaseService(session)
    try:
        payload = await service.add_correction(case_id, request)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_case_not_found",
            message=str(exc),
        ) from exc
    return _build_case_response(payload)


@router.post(
    "/cases/{case_id}/review",
    response_model=MaintenanceCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="审核检修案例",
    description="审核通过后，案例会自动沉淀为知识文档并参与后续检索。",
)
async def review_maintenance_case(
    case_id: int,
    request: MaintenanceCaseReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> MaintenanceCaseResponse:
    logger.info(
        "maintenance_case_review case_id=%s action=%s reviewer=%s",
        case_id,
        request.action,
        request.reviewer_name or "",
    )
    service = MaintenanceCaseService(session)
    try:
        payload = await service.review_case(case_id, request)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="maintenance_case_not_found",
            message=str(exc),
        ) from exc
    return _build_case_response(payload)


__all__ = ["router", "MaintenanceCaseService"]
