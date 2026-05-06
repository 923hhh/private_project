"""Agent orchestration APIs for the formal workbench."""
from datetime import datetime, timezone
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session, get_session_context
from app.modules.tasks.application.task_service import MaintenanceTaskService
from app.modules.assistant.application.orchestration_service import AgentOrchestrationService
from app.modules.assistant.schemas import (
    AgentAssistRequest,
    AgentAssistResponse,
    AgentExecutionBrief,
    AgentRelatedCase,
    AgentRequestContext,
    AgentRunStep,
    AgentTaskPreviewStep,
    AgentToolCall,
)
from app.modules.diagnosis.schemas import DiagnosisStructuredPayload
from app.modules.knowledge.schemas.search import KnowledgeImageAnalysis, KnowledgeSearchHit

router = APIRouter(prefix="/api/v1/agents", tags=["Agent 协作"])
logger = logging.getLogger(__name__)


def _build_agent_response(payload: dict) -> AgentAssistResponse:
    return AgentAssistResponse(
        run_id=payload["run_id"],
        status=payload["status"],
        summary=payload["summary"],
        diagnosis_report=payload.get("diagnosis_report"),
        diagnosis_structured=(
            DiagnosisStructuredPayload(**payload["diagnosis_structured"])
            if payload.get("diagnosis_structured") is not None
            else None
        ),
        request_context=(
            AgentRequestContext(**payload["request_context"])
            if payload.get("request_context") is not None
            else None
        ),
        execution_brief=(
            AgentExecutionBrief(**payload["execution_brief"])
            if payload.get("execution_brief") is not None
            else None
        ),
        effective_query=payload.get("effective_query"),
        effective_keywords=payload.get("effective_keywords") or [],
        image_analysis=(
            KnowledgeImageAnalysis(**payload["image_analysis"])
            if payload.get("image_analysis") is not None
            else None
        ),
        knowledge_results=[KnowledgeSearchHit(**item) for item in payload.get("knowledge_results", [])],
        related_cases=[AgentRelatedCase(**item) for item in payload.get("related_cases", [])],
        task_plan_preview=[AgentTaskPreviewStep(**item) for item in payload.get("task_plan_preview", [])],
        risk_findings=payload.get("risk_findings", []),
        case_suggestions=payload.get("case_suggestions", []),
        agents=[AgentRunStep(**item) for item in payload.get("agents", [])],
        tool_calls=[AgentToolCall(**item) for item in payload.get("tool_calls", [])],
        created_at=payload["created_at"],
    )


@router.post(
    "/assist",
    response_model=AgentAssistResponse,
    status_code=status.HTTP_200_OK,
    summary="Agent 协作辅助",
    description="统一触发知识召回、作业规划、风险校验和案例沉淀建议的多智能体协作入口。",
)
async def assist_with_agents(
    request: AgentAssistRequest,
) -> AgentAssistResponse:
    logger.info(
        "agent_assist_request equipment_type=%s equipment_model=%s fault_type=%s query_present=%s image_present=%s",
        request.equipment_type or "",
        request.equipment_model or "",
        request.fault_type or "",
        bool(request.query),
        bool(request.image_base64),
    )
    async with get_session_context() as session:
        payload = await AgentOrchestrationService(session).assist(request)
        return _build_agent_response(payload)


@router.get(
    "/assist/stream",
    status_code=status.HTTP_200_OK,
    summary="Agent 协作流式执行",
    description="通过 SSE 按阶段推送知识召回、步骤规划、工具执行和最终协作结果。",
)
async def assist_with_agents_stream(
    work_order_id: str | None = Query(default=None, description="工单编号"),
    asset_code: str | None = Query(default=None, description="设备编号"),
    report_source: str | None = Query(default=None, description="报修来源"),
    priority: str = Query(default="medium", description="工单优先级"),
    query: str | None = Query(default=None, description="故障描述"),
    equipment_type: str | None = Query(default=None, description="设备类型"),
    equipment_model: str | None = Query(default=None, description="设备型号"),
    fault_type: str | None = Query(default=None, description="故障类型"),
    maintenance_level: str = Query(default="standard", description="检修等级"),
    limit: int = Query(default=5, ge=1, le=10, description="知识召回上限"),
    selected_chunk_ids: list[int] | None = Query(default=None, description="已锁定知识条目"),
    model_provider: str = Query(default="openai", description="模型提供商"),
    model_name: str | None = Query(default=None, description="模型名称"),
    maintenance_task_id: int | None = Query(default=None, description="关联检修任务 ID"),
):
    try:
        request = AgentAssistRequest(
            work_order_id=work_order_id,
            asset_code=asset_code,
            report_source=report_source,
            priority=priority,
            query=query,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_type=fault_type,
            maintenance_level=maintenance_level,
            limit=limit,
            selected_chunk_ids=selected_chunk_ids or [],
            model_provider=model_provider,
            model_name=model_name,
            maintenance_task_id=maintenance_task_id,
        )
    except ValidationError as exc:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="agent_stream_invalid_request",
            message="流式协作请求参数不合法。",
            details={"errors": exc.errors()},
        ) from exc

    logger.info(
        "agent_assist_stream_request equipment_type=%s equipment_model=%s fault_type=%s query_present=%s",
        request.equipment_type or "",
        request.equipment_model or "",
        request.fault_type or "",
        bool(request.query),
    )
    async def sse_generator() -> AsyncGenerator[bytes, None]:
        import asyncio

        queue: asyncio.Queue[dict] = asyncio.Queue()
        client_connected = True

        async def emit(event: dict) -> None:
            if client_connected:
                await queue.put(event)

        async def run_in_background() -> None:
            try:
                async with get_session_context() as session:
                    service = AgentOrchestrationService(session)
                    await service.assist_stream(request, emit)
            except Exception as exc:
                logger.exception("agent_assist_stream_failed")
                if request.maintenance_task_id is not None:
                    try:
                        async with get_session_context() as session:
                            await MaintenanceTaskService(session).append_execution_timeline_event(
                                request.maintenance_task_id,
                                {
                                    "id": f"error-{request.maintenance_task_id}",
                                    "type": "error",
                                    "title": "诊断失败",
                                    "description": str(exc) or "流式执行失败",
                                    "time": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                    except Exception:
                        logger.exception(
                            "agent_assist_stream_error_event_persist_failed task_id=%s",
                            request.maintenance_task_id,
                        )
                if client_connected:
                    await queue.put(
                        {
                            "event": "stream_error",
                            "data": {"error": str(exc) or "流式执行失败"},
                        }
                    )

        runner = asyncio.create_task(run_in_background())
        yield b"event: connected\ndata: {\"status\": \"stream_started\"}\n\n"

        try:
            while True:
                if runner.done() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=4)
                except asyncio.TimeoutError:
                    yield b": heartbeat\n\n"
                    continue
                yield (
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                ).encode()
            await runner
        except Exception as exc:
            yield f"event: stream_error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n".encode()
        finally:
            client_connected = False

        yield b"event: done\ndata: {\"status\": \"stream_finished\"}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentAssistResponse,
    status_code=status.HTTP_200_OK,
    summary="获取 Agent 协作记录",
    description="返回最近一次协作的聚合结果。",
)
async def get_agent_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentAssistResponse:
    service = AgentOrchestrationService(session)
    payload = await service.get_run(run_id)
    if payload is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="agent_run_not_found",
            message="指定的 Agent 协作记录不存在。",
        )
    return _build_agent_response(payload)


__all__ = ["router", "assist_with_agents", "assist_with_agents_stream", "get_agent_run", "AgentOrchestrationService"]
