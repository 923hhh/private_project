"""检修域 HTTP 路由：`/api/v1/maintenance`。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.modules.maintenance.deps import CurrentUserCtx, get_current_user_ctx, require_roles
from app.modules.maintenance.errors import MaintenanceAPIError
from app.modules.maintenance.service import ATTACHMENT_UPLOAD_MAX_BYTES, MaintenanceService

PREFIX = "/api/v1/maintenance"

router = APIRouter(prefix=PREFIX, tags=["检修域"])


def _svc(session: AsyncSession, settings: Settings) -> MaintenanceService:
    return MaintenanceService(session, settings)


def _ok(data: Any, message: str | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "business_code": None, "message": message}


def _err(
    *,
    status_code: int,
    business_code: str,
    message: str,
    errors: list | None = None,
    data: Any = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "success": False,
        "data": data,
        "business_code": business_code,
        "message": message,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


@router.post("/auth/login")
async def auth_login(
    body: dict[str, Any],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        data = await _svc(session, settings).login(body.get("username", ""), body.get("password", ""))
        return _ok(data)
    except MaintenanceAPIError as e:
        return _err(
            status_code=e.status_code,
            business_code=e.business_code,
            message=e.message,
            errors=e.errors,
            data=e.data,
        )


@router.post("/auth/logout")
async def auth_logout():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me")
async def auth_me(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    data = await _svc(session, settings).get_me(ctx)
    return _ok(data)


@router.get("/notifications")
async def notifications_list(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(20, ge=1, le=50),
):
    try:
        return _ok(await _svc(session, settings).list_notifications(ctx, limit))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.patch("/notifications/{notification_id}/read")
async def notifications_mark_read(
    notification_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).mark_notification_read(notification_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/notifications/read-all")
async def notifications_mark_all_read(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).mark_all_notifications_read(ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/health")
async def maintenance_health(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    data = await _svc(session, settings).health_sub()
    return _ok(data)


# ---------- 管理员用户 ----------
@router.get("/admin/users")
async def admin_users(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    data = await _svc(session, settings).admin_list_users(page, page_size)
    return _ok(data)


@router.post("/admin/users")
async def admin_users_create(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        data = await _svc(session, settings).admin_create_user(body)
        return _ok(data)
    except MaintenanceAPIError as e:
        return _err(
            status_code=e.status_code,
            business_code=e.business_code,
            message=e.message,
        )


@router.post("/admin/users/{user_id}/roles")
async def admin_users_roles(
    user_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    await _svc(session, settings).admin_assign_roles(user_id, body)
    return _ok({})


@router.get("/admin/roles")
async def admin_roles(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from sqlalchemy import select

    from app.db.models.maintenance import Role

    rows = (await session.execute(select(Role))).scalars().all()
    return _ok([{"id": r.id, "code": r.code, "name": r.name} for r in rows])


@router.get("/admin/audit-logs")
async def admin_audit(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resource_type: str | None = None,
    resource_id: str | None = None,
):
    try:
        data = await _svc(session, settings).list_audit_logs(
            ctx, page=page, page_size=page_size, resource_type=resource_type, resource_id=resource_id
        )
        return _ok(data)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/admin/system-configs")
async def admin_cfgs(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).list_system_configs(ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.patch("/admin/system-configs/{key}")
async def admin_cfg_patch(
    key: str,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).patch_system_config(key, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 设备 ----------
@router.get("/devices")
async def devices_list(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_type: str | None = None,
    model: str | None = None,
    q: str | None = None,
):
    data = await _svc(session, settings).list_devices(
        page=page, page_size=page_size, device_type=device_type, model=model, q=q
    )
    return _ok(data)


@router.post("/devices")
async def devices_create(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).create_device(body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/devices/{device_id}")
async def devices_get(
    device_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        d = await _svc(session, settings).get_device(device_id)
        return _ok(
            {
                "id": d.id,
                "device_type": d.device_type,
                "model": d.model,
                "asset_code": d.asset_code,
                "location": d.location,
                "responsibility_expert_user_id": d.responsibility_expert_user_id,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
        )
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.patch("/devices/{device_id}")
async def devices_patch(
    device_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).patch_device(device_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 附件 ----------
@router.post("/attachments")
async def attachments_upload(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
    biz_type: str = Form(...),
    work_order_id: int | None = Form(default=None),
):
    raw = await file.read()
    if len(raw) > ATTACHMENT_UPLOAD_MAX_BYTES:
        return _err(
            status_code=413,
            business_code="PAYLOAD_TOO_LARGE",
            message="单文件超过 10MB 限制",
        )
    try:
        data = await _svc(session, settings).save_attachment(
            file_bytes=raw,
            filename=file.filename or "upload.bin",
            mime=file.content_type or "application/octet-stream",
            biz_type=biz_type,
            work_order_id=work_order_id,
            ctx=ctx,
        )
        return _ok(data)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/attachments/{attachment_id}/content")
async def attachments_redirect(
    attachment_id: int,
    request: Request,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        svc = _svc(session, settings)
        await svc.get_attachment_for_download(attachment_id, ctx)
        exp = int((datetime.now(timezone.utc) + timedelta(seconds=300)).timestamp())
        token = svc._sign_attachment_token(attachment_id, exp)
        base = str(request.base_url).rstrip("/")
        url = f"{base}{PREFIX}/attachments/{attachment_id}/file?token={token}"
        return RedirectResponse(url=url, status_code=302)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/attachments/{attachment_id}/file", name="maintenance_attachment_file")
async def attachments_file(
    attachment_id: int,
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        aid, _ = _svc(session, settings)._verify_attachment_token(token)
        if aid != attachment_id:
            raise MaintenanceAPIError(403, "FORBIDDEN", "令牌不匹配")
        _, path = await _svc(session, settings).attachment_file_path(attachment_id)
        return FileResponse(path)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 工单 ----------
@router.post("/work-orders")
async def wo_create(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).create_work_order(body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message, errors=e.errors)


@router.get("/work-orders")
async def wo_list(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    device_id: int | None = None,
    mine: bool | None = None,
    assignment_role: str | None = Query(None, pattern="^(worker|expert|safety)$"),
    assignment_state: str | None = Query(None, pattern="^(assigned|unassigned|mine)$"),
):
    try:
        return _ok(
            await _svc(session, settings).list_work_orders(
                ctx,
                page=page,
                page_size=page_size,
                status=status,
                device_id=device_id,
                mine=mine,
                assignment_role=assignment_role,
                assignment_state=assignment_state,
            )
        )
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message, errors=e.errors)


@router.get("/work-orders/assignment-candidates")
async def wo_assignment_candidates(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    role: str | None = Query(None, pattern="^(worker|expert|safety)$"),
):
    try:
        return _ok(await _svc(session, settings).list_assignment_candidates(ctx, role))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message, errors=e.errors)


@router.get("/work-orders/{work_order_id}")
async def wo_get(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).get_work_order_detail(work_order_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.patch("/work-orders/{work_order_id}/assignment")
async def wo_update_assignment(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).update_work_order_assignment(work_order_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message, errors=e.errors)


@router.delete("/work-orders/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def wo_delete(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        await _svc(session, settings).delete_work_order(work_order_id, ctx)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/work-orders/{work_order_id}/events")
async def wo_events(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).list_events(work_order_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/retrieval")
async def wo_retrieval(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        out = await _svc(session, settings).post_retrieval(work_order_id, body, ctx)
        if out.get("success"):
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": out["data"],
                    "business_code": out.get("business_code"),
                    "message": out.get("message"),
                },
            )
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "data": out.get("data"),
                "business_code": out.get("business_code"),
                "message": out.get("message"),
            },
        )
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/work-orders/{work_order_id}/retrieval/stream")
async def wo_retrieval_stream(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    query_text: str = Query(default="", description="检索关键词"),
    maintenance_level: str | None = Query(default=None, description="检修等级"),
):
    """SSE 流式知识检索：搜索 → 结果 → LLM 综合回答 → 快照持久化。"""
    import asyncio

    try:
        await _svc(session, settings).get_work_order_detail(work_order_id, ctx)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)

    async def event_gen():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def emit(event: dict) -> None:
            await queue.put(event)

        svc = _svc(session, settings)
        runner = asyncio.create_task(
            svc.retrieval_stream(work_order_id, query_text, maintenance_level, ctx, emit)
        )
        yield f"event: connected\ndata: {json.dumps({'work_order_id': work_order_id}, ensure_ascii=False)}\n\n"

        try:
            while True:
                if runner.done() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=4)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            await runner
        except Exception as exc:
            yield f"event: stream_error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            if not runner.done():
                runner.cancel()

        yield f"event: done\ndata: {json.dumps({'status': 'finished'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/asr/transcribe")
async def asr_transcribe_placeholder(
    _ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
):
    """P1 占位：未接入语音识别引擎。"""
    return _err(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        business_code="ASR_NOT_IMPLEMENTED",
        message="语音识别为 P1 能力，当前版本未实现",
    )


@router.post("/work-orders/{work_order_id}/messages")
async def wo_msg_post(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).post_user_message(work_order_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/work-orders/{work_order_id}/messages")
async def wo_msg_list(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return _ok(await _svc(session, settings).list_messages(work_order_id, ctx, page, page_size))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/actions/enter-maintenance")
async def wo_enter_maint(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).action_enter_maintenance(work_order_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/actions/complete-maintenance")
async def wo_complete_maint(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).action_complete_maintenance(work_order_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/actions/accept-fill-review")
async def wo_accept_fill(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).action_accept_fill_review(work_order_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/fillings")
async def wo_fillings(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).post_filling(work_order_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message, errors=e.errors)


@router.post("/work-orders/{work_order_id}/escalations")
async def wo_esc_create(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).create_escalation(work_order_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/actions/request-escalation")
async def wo_esc_alias(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).create_escalation(work_order_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/steps/confirm")
async def wo_step_confirm(
    work_order_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("worker", "admin", "expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        out = await _svc(session, settings).confirm_step(work_order_id, body, ctx)
        if out.get("business_code") == "ALREADY_PROCESSED":
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": out,
                    "business_code": "ALREADY_PROCESSED",
                    "message": None,
                },
            )
        return _ok(out)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/work-orders/{work_order_id}/messages/{message_id}/annotations")
async def wo_ann(
    work_order_id: int,
    message_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).create_annotation(work_order_id, message_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 审批 ----------
@router.get("/approval-tasks/{approval_task_id}")
async def appr_get(
    approval_task_id: int,
    _ctx: Annotated[CurrentUserCtx, Depends(require_roles("safety", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from sqlalchemy import select

    from app.db.models.maintenance import ApprovalTask

    t = await session.get(ApprovalTask, approval_task_id)
    if t is None:
        return _err(status_code=404, business_code="NOT_FOUND", message="审批任务不存在")
    return _ok(
        {
            "id": t.id,
            "work_order_id": t.work_order_id,
            "step_no": t.step_no,
            "status": t.status,
            "comment": t.comment,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        }
    )


@router.get("/approval-tasks")
async def appr_list(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("safety", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).list_approval_tasks(ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/approval-tasks/{approval_task_id}/resolve")
async def appr_resolve(
    approval_task_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("safety", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        out = await _svc(session, settings).resolve_approval(approval_task_id, body, ctx)
        bc = out.pop("business_code", None)
        if bc == "ALREADY_PROCESSED":
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": out, "business_code": "ALREADY_PROCESSED", "message": None},
            )
        return _ok(out)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 升级 ----------
@router.get("/escalations/{escalation_id}")
async def esc_get(
    escalation_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).get_escalation(escalation_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/escalations/{escalation_id}/resolve")
async def esc_resolve(
    escalation_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).resolve_escalation(escalation_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 模板 ----------
@router.get("/flow-templates")
async def ft_list(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    device_type: str | None = None,
    maintenance_level: str | None = None,
):
    return _ok(await _svc(session, settings).list_flow_templates(device_type, maintenance_level))


@router.get("/flow-templates/{template_id}")
async def ft_get(
    template_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).get_flow_template(template_id))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


# ---------- 知识 ----------
@router.post("/knowledge-articles/from-work-order")
async def kb_from_wo(
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).kb_from_work_order(body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/knowledge-articles")
async def kb_list(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    series_id: int | None = Query(default=None, ge=1),
):
    try:
        return _ok(await _svc(session, settings).list_kb_articles(ctx, status, page, page_size, series_id))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/knowledge-articles/publish-console")
async def kb_publish_console(
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).get_kb_publish_console(ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.get("/knowledge-articles/{article_id}/versions")
async def kb_versions(
    article_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(get_current_user_ctx)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).get_kb_article_versions(article_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/knowledge-articles/{article_id}/review")
async def kb_review(
    article_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any],
):
    try:
        return _ok(await _svc(session, settings).review_kb(article_id, body, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/knowledge-articles/{article_id}/publish")
async def kb_publish(
    article_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any] | None = None,
):
    try:
        return _ok(await _svc(session, settings).publish_kb(article_id, body or {}, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/knowledge-articles/{article_id}/withdraw")
async def kb_withdraw(
    article_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return _ok(await _svc(session, settings).withdraw_kb(article_id, ctx))
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)


@router.post("/annotations/{annotation_id}/spawn-kb-draft")
async def ann_spawn(
    annotation_id: int,
    ctx: Annotated[CurrentUserCtx, Depends(require_roles("expert", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: dict[str, Any] | None = None,
):
    try:
        out = await _svc(session, settings).spawn_kb_draft(annotation_id, body or {}, ctx)
        if out.get("business_code") == "ALREADY_PROCESSED":
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": {k: v for k, v in out.items() if k != "business_code"},
                    "business_code": "ALREADY_PROCESSED",
                    "message": None,
                },
            )
        return _ok(out)
    except MaintenanceAPIError as e:
        return _err(status_code=e.status_code, business_code=e.business_code, message=e.message)
