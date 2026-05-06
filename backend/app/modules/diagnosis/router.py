"""Diagnosis API router."""
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.modules.diagnosis.schemas import DiagnosisRequest, DiagnosisResponse
from app.modules.diagnosis.workflow.graph import get_diagnosis_graph
from app.modules.diagnosis.workflow.state import DiagnosisState
from app.modules.tasks.application.task_service import (
    MaintenanceTaskService,
    finalize_maintenance_task_after_pipeline,
)
from app.agents import run_multi_agent_diagnosis

router = APIRouter(prefix="/api/v1", tags=["诊断"])
logger = logging.getLogger(__name__)


@router.post(
    "/diagnose",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_200_OK,
    summary="AI 故障诊断（多智能体）",
    description="基于传感器数据的时间范围，调用多智能体协作进行故障诊断分析。",
)
async def diagnose(
    request: DiagnosisRequest,
    session: AsyncSession = Depends(get_session),
) -> DiagnosisResponse:
    logger.info(
        "diagnose_request provider=%s model=%s start_time=%s end_time=%s symptom_present=%s",
        request.model_provider,
        request.model_name or "",
        request.start_time,
        request.end_time,
        bool(request.symptom_description),
    )
    try:
        result = await run_multi_agent_diagnosis(
            start_time=request.start_time,
            end_time=request.end_time,
            symptom_description=request.symptom_description,
            model_provider=request.model_provider,
            model_name=request.model_name,
        )

        if request.maintenance_task_id is not None:
            try:
                await MaintenanceTaskService(session).complete_task_after_pipeline_success(
                    request.maintenance_task_id,
                )
            except Exception:
                logger.exception(
                    "检修任务在同步诊断结束后自动完结失败 task_id=%s",
                    request.maintenance_task_id,
                )

        return DiagnosisResponse(code=200, message="诊断完成", data=result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "diagnose_request_failed provider=%s model=%s start_time=%s end_time=%s",
            request.model_provider,
            request.model_name or "",
            request.start_time,
            request.end_time,
        )
        raise AppError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="diagnosis_execution_failed",
            message="诊断执行失败，请稍后重试。",
            details={"exception": exc.__class__.__name__},
        ) from exc


@router.get(
    "/diagnose/stream",
    summary="AI 故障诊断（流式响应 - SSE）",
    description="通过 Server-Sent Events (SSE) 实时推送多智能体工作流进度。",
)
async def diagnose_stream_get(
    start_time: str = Query(description="起始时间，格式 YYYY-MM-DD HH:MM:SS"),
    end_time: str = Query(description="结束时间，格式 YYYY-MM-DD HH:MM:SS"),
    symptom_description: str | None = Query(default=None, description="症状描述"),
    model_provider: str = Query(default="openai", description="模型提供商"),
    model_name: str | None = Query(default=None, description="模型名称"),
    maintenance_task_id: int | None = Query(
        default=None,
        description="关联检修任务 ID；流式诊断正常结束后将该任务标为已完成",
    ),
):
    logger.info(
        "diagnose_stream_request provider=%s model=%s start_time=%s end_time=%s symptom_present=%s",
        model_provider,
        model_name or "",
        start_time,
        end_time,
        bool(symptom_description),
    )
    graph = get_diagnosis_graph()

    initial_state: DiagnosisState = {
        "start_time": start_time,
        "end_time": end_time,
        "symptom_description": symptom_description,
        "model_provider": model_provider,
        "model_name": model_name,
        "sensor_stats": None,
        "diagnosis_report": None,
        "next_node": "supervisor",
        "messages": [],
    }

    async def sse_generator() -> AsyncGenerator[bytes, None]:
        import asyncio

        node_labels = {
            "supervisor": "任务调度中",
            "data_analyst": "正在查询传感器数据",
            "diagnosis_expert": "正在生成诊断报告",
        }

        astream_aiter = graph.astream(initial_state)
        astream_task = asyncio.create_task(astream_aiter.__anext__())

        async def heartbeat_aiter():
            while True:
                await asyncio.sleep(4)
                yield b": heartbeat\n\n"

        heartbeat_task = asyncio.create_task(heartbeat_aiter().__anext__())
        pending = {astream_task, heartbeat_task}

        try:
            yield b"event: connected\ndata: {\"status\": \"stream_started\"}\n\n"

            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    result = task.result()
                    if task is astream_task:
                        chunk = result
                        if isinstance(chunk, dict):
                            for node_name, node_output in chunk.items():
                                if node_name.startswith("__") or node_output is None:
                                    continue
                                if node_name in node_labels:
                                    yield (
                                        f"event: node_start\ndata: "
                                        f"{json.dumps({'node': node_name, 'message': node_labels[node_name]}, ensure_ascii=False)}\n\n"
                                    ).encode()
                                if node_name == "diagnosis_expert":
                                    report = node_output.get("diagnosis_report", "")
                                    logger.info(
                                        "diagnose_stream_report_generated model=%s report_length=%s",
                                        model_name or "",
                                        len(report),
                                    )
                                    yield f"event: report\ndata: {json.dumps({'report': report}, ensure_ascii=False)}\n\n".encode()
                                elif node_name == "data_analyst":
                                    stats = node_output.get("sensor_stats", "")
                                    summary = (stats[:200] + "...") if len(stats) > 200 else stats
                                    yield (
                                        f"event: node_finish\ndata: "
                                        f"{json.dumps({'node': node_name, 'status': 'done', 'preview': summary}, ensure_ascii=False)}\n\n"
                                    ).encode()
                                elif node_name == "supervisor":
                                    next_node = node_output.get("next_node", "")
                                    yield (
                                        f"event: node_finish\ndata: "
                                        f"{json.dumps({'node': node_name, 'status': 'done', 'next': next_node}, ensure_ascii=False)}\n\n"
                                    ).encode()

                        astream_task = asyncio.create_task(astream_aiter.__anext__())
                        pending.add(astream_task)
                    elif task is heartbeat_task:
                        yield result
                        heartbeat_task = asyncio.create_task(heartbeat_aiter().__anext__())
                        pending.add(heartbeat_task)
        except StopAsyncIteration:
            logger.info("diagnose_stream_completed model=%s", model_name or "")
            if maintenance_task_id is not None:
                try:
                    await finalize_maintenance_task_after_pipeline(maintenance_task_id)
                except Exception:
                    logger.exception(
                        "检修任务在流式诊断结束后自动完结失败 task_id=%s",
                        maintenance_task_id,
                    )
        except Exception as exc:
            logger.exception("diagnose_stream_failed model=%s", model_name or "")
            yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n".encode()
        finally:
            for task in pending:
                if not task.done():
                    task.cancel()

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


__all__ = ["router", "diagnose", "diagnose_stream_get"]
