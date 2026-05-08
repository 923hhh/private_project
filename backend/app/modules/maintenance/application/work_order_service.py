"""Work-order core operations for maintenance."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.metrics import observe_duration
from app.db.session import get_session_factory
from app.db.models.maintenance import (
    Annotation,
    ApprovalTask,
    Attachment,
    AuthUser,
    Device,
    Escalation,
    FlowTemplate,
    KnowledgeArticle,
    RetrievalSnapshot,
    WorkOrder,
    WorkOrderEvent,
    WorkOrderFilling,
    WorkOrderFillingAttachment,
    WorkOrderMessage,
)
from app.db.models.tasks import MaintenanceTask
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]

MAINTENANCE_LEVEL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "standard": ("计划定修", "标准检修"),
    "routine": ("例行检修",),
    "emergency": ("紧急检修",),
}

SLA_HOURS_BY_LEVEL: dict[str, int] = {
    "emergency": 2,
    "紧急检修": 2,
    "standard": 8,
    "标准检修": 8,
    "计划定修": 8,
    "routine": 24,
    "例行检修": 24,
}

ASSIGNMENT_ROLE_FIELDS: dict[str, str] = {
    "worker": "assigned_worker_user_id",
    "expert": "assigned_expert_user_id",
    "safety": "assigned_safety_user_id",
}


def _resolve_sla_hours(maintenance_level: str | None) -> int:
    level = (maintenance_level or "").strip()
    return SLA_HOURS_BY_LEVEL.get(level, 72)


def _build_sla_payload(wo: WorkOrder) -> dict[str, Any]:
    created_at = wo.created_at
    if created_at is None:
        return {
            "sla_hours": None,
            "sla_deadline": None,
            "is_overdue": False,
        }

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    sla_hours = _resolve_sla_hours(wo.maintenance_level)
    deadline = created_at + timedelta(hours=sla_hours)
    is_closed = wo.status in {"S10", "SX"}
    is_overdue = deadline < datetime.now(timezone.utc) and not is_closed
    return {
        "sla_hours": sla_hours,
        "sla_deadline": to_iso_cn(deadline),
        "is_overdue": is_overdue,
    }


def _serialize_user(user: AuthUser | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "roles": [role.code for role in user.roles],
    }


def _wo_public(wo: WorkOrder) -> dict[str, Any]:
    source_task = None
    if isinstance(wo.step_progress_json, dict):
        source_task = wo.step_progress_json.get("source_task")
    return {
        "id": wo.id,
        "device_id": wo.device_id,
        "status": wo.status,
        "maintenance_level": wo.maintenance_level,
        "flow_template_id": wo.flow_template_id,
        "current_step_no": wo.current_step_no,
        "last_retrieval_snapshot_id": wo.last_retrieval_snapshot_id,
        "created_by_user_id": wo.created_by_user_id,
        "source_task_id": source_task.get("task_id") if isinstance(source_task, dict) else None,
        "created_at": to_iso_cn(wo.created_at),
        "updated_at": to_iso_cn(wo.updated_at),
        **_build_sla_payload(wo),
    }


def _can_read_wo(ctx: CurrentUserCtx, wo: WorkOrder) -> bool:
    if ctx.has_any("admin", "expert", "safety"):
        return True
    return ctx.user_id in {
        wo.created_by_user_id,
        wo.assigned_worker_user_id,
        wo.assigned_expert_user_id,
        wo.assigned_safety_user_id,
        wo.current_owner_user_id,
    }


class MaintenanceWorkOrderService:
    """Core work-order lifecycle, detail, event, and step-confirm actions."""

    def __init__(self, session: AsyncSession, audit: AuditCallback) -> None:
        self.session = session
        self._audit = audit

    async def _load_user_map(self, user_ids: set[int]) -> dict[int, AuthUser]:
        if not user_ids:
            return {}
        started = perf_counter()
        rows = (
            await self.session.execute(
                select(AuthUser)
                .options(selectinload(AuthUser.roles))
                .where(AuthUser.id.in_(user_ids))
            )
        ).scalars().all()
        await observe_duration(
            "maintenance_work_order_query_duration_ms",
            (perf_counter() - started) * 1000,
            endpoint="shared",
            phase="load_user_map",
        )
        return {user.id: user for user in rows}

    def _build_assignment_payload(self, work_order: WorkOrder, user_map: dict[int, AuthUser]) -> dict[str, Any]:
        return {
            "assignees": {
                "worker": _serialize_user(user_map.get(work_order.assigned_worker_user_id or 0)),
                "expert": _serialize_user(user_map.get(work_order.assigned_expert_user_id or 0)),
                "safety": _serialize_user(user_map.get(work_order.assigned_safety_user_id or 0)),
            },
            "current_owner": _serialize_user(user_map.get(work_order.current_owner_user_id or 0)),
        }

    async def _serialize_work_order(self, work_order: WorkOrder) -> dict[str, Any]:
        user_ids = {
            user_id
            for user_id in (
                work_order.assigned_worker_user_id,
                work_order.assigned_expert_user_id,
                work_order.assigned_safety_user_id,
                work_order.current_owner_user_id,
            )
            if user_id is not None
        }
        payload = _wo_public(work_order)
        payload.update(self._build_assignment_payload(work_order, await self._load_user_map(user_ids)))
        return payload

    async def _serialize_work_orders(self, work_orders: list[WorkOrder]) -> list[dict[str, Any]]:
        user_ids = {
            user_id
            for work_order in work_orders
            for user_id in (
                work_order.assigned_worker_user_id,
                work_order.assigned_expert_user_id,
                work_order.assigned_safety_user_id,
                work_order.current_owner_user_id,
            )
            if user_id is not None
        }
        user_map = await self._load_user_map(user_ids)
        items: list[dict[str, Any]] = []
        for work_order in work_orders:
            payload = _wo_public(work_order)
            payload.update(self._build_assignment_payload(work_order, user_map))
            items.append(payload)
        return items

    async def _get_assignment_user(self, user_id: int) -> AuthUser:
        result = await self.session.execute(select(AuthUser).where(AuthUser.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise MaintenanceAPIError(404, "USER_NOT_FOUND", "指定用户不存在或已禁用")
        await self.session.refresh(user, attribute_names=["roles"])
        return user

    async def list_assignment_candidates(self, ctx: CurrentUserCtx, *, role_code: str | None = None) -> dict[str, Any]:
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权查看分配候选人")
        if role_code and role_code not in ASSIGNMENT_ROLE_FIELDS:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "role 无效")
        rows = (
            await self.session.execute(
                select(AuthUser).options(selectinload(AuthUser.roles)).where(AuthUser.is_active.is_(True))
            )
        ).scalars().all()
        items: list[dict[str, Any]] = []
        for user in rows:
            payload = _serialize_user(user)
            if payload is None:
                continue
            if role_code and role_code not in payload["roles"]:
                continue
            items.append(payload)
        items.sort(key=lambda item: (item["display_name"], item["username"]))
        return {"items": items}

    async def _resolve_flow_template(self, *, device_type: str, maintenance_level: str | None) -> FlowTemplate | None:
        requested = (maintenance_level or "计划定修").strip() or "计划定修"
        candidates: list[str] = [requested]
        for alias in MAINTENANCE_LEVEL_FALLBACKS.get(requested, ()):
            if alias not in candidates:
                candidates.append(alias)

        for candidate in candidates:
            template = (
                await self.session.execute(
                    select(FlowTemplate).where(
                        FlowTemplate.device_type == device_type,
                        FlowTemplate.maintenance_level == candidate,
                        FlowTemplate.status == "published",
                    )
                )
            ).scalar_one_or_none()
            if template is not None:
                return template
        return None

    async def _ensure_flow_template_bound(self, work_order: WorkOrder, device: Device | None = None) -> FlowTemplate | None:
        if work_order.flow_template_id is not None:
            return await self.session.get(FlowTemplate, work_order.flow_template_id)

        device = device or await self.session.get(Device, work_order.device_id)
        if device is None:
            return None

        template = await self._resolve_flow_template(
            device_type=device.device_type,
            maintenance_level=work_order.maintenance_level,
        )
        if template is None:
            return None

        work_order.flow_template_id = template.id
        if work_order.current_step_no is None:
            work_order.current_step_no = 1
        work_order.updated_at = utc_now_naive()
        await self.session.commit()
        return template

    async def get_work_order(self, work_order_id: int) -> WorkOrder:
        work_order = await self.session.get(WorkOrder, work_order_id)
        if work_order is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "工单不存在")
        return work_order

    async def assert_work_order_readable(self, ctx: CurrentUserCtx, work_order: WorkOrder) -> None:
        if not _can_read_wo(ctx, work_order):
            raise MaintenanceAPIError(404, "NOT_FOUND", "工单不存在")

    async def transition(
        self,
        work_order: WorkOrder,
        to_status: str,
        *,
        event_type: str,
        actor_user_id: int | None,
        payload: dict | None = None,
    ) -> None:
        event = WorkOrderEvent(
            work_order_id=work_order.id,
            from_status=work_order.status,
            to_status=to_status,
            event_type=event_type,
            payload=payload,
            actor_user_id=actor_user_id,
            created_at=utc_now_naive(),
        )
        work_order.status = to_status
        work_order.updated_at = utc_now_naive()
        self.session.add(event)

    async def create_work_order(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        if "device_id" not in body or body["device_id"] is None:
            raise MaintenanceAPIError(
                400,
                "VALIDATION_ERROR",
                "device_id 必填",
                errors=[{"field": "device_id", "code": "REQUIRED", "message": "必填"}],
            )
        device = await self.session.get(Device, int(body["device_id"]))
        if device is None:
            raise MaintenanceAPIError(404, "DEVICE_NOT_FOUND", "设备不存在")

        source_task_snapshot: dict[str, Any] | None = None
        source_task_id_raw = body.get("source_task_id")
        if source_task_id_raw is not None:
            source_task = await self.session.get(MaintenanceTask, int(source_task_id_raw))
            if source_task is None:
                raise MaintenanceAPIError(404, "TASK_NOT_FOUND", "来源诊断任务不存在")
            source_task_snapshot = {
                "task_id": source_task.id,
                "title": source_task.title,
                "diagnosis_report": source_task.diagnosis_report,
                "advice_card": source_task.advice_card,
                "status": source_task.status,
            }

        work_order = WorkOrder(
            device_id=int(body["device_id"]),
            status="S1",
            maintenance_level=body.get("maintenance_level"),
            assigned_expert_user_id=device.responsibility_expert_user_id,
            created_by_user_id=ctx.user_id,
            step_progress_json={"source_task": source_task_snapshot} if source_task_snapshot else None,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.session.add(work_order)
        await self.session.flush()
        self.session.add(
            WorkOrderEvent(
                work_order_id=work_order.id,
                from_status=None,
                to_status="S1",
                event_type="work_order_created",
                payload=None,
                actor_user_id=ctx.user_id,
                created_at=utc_now_naive(),
            )
        )
        await self.session.commit()
        await self.session.refresh(work_order)
        return await self._serialize_work_order(work_order)

    async def list_work_orders(
        self,
        ctx: CurrentUserCtx,
        *,
        page: int,
        page_size: int,
        status: str | None,
        device_id: int | None,
        mine: bool | None,
        assignment_role: str | None = None,
        assignment_state: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(WorkOrder)
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if device_id:
            stmt = stmt.where(WorkOrder.device_id == device_id)
        if assignment_role:
            field_name = ASSIGNMENT_ROLE_FIELDS.get(assignment_role)
            if field_name is None:
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "assignment_role 无效")
            column = getattr(WorkOrder, field_name)
            if assignment_state == "unassigned":
                stmt = stmt.where(column.is_(None))
            else:
                stmt = stmt.where(column.is_not(None))
        if assignment_state and assignment_state not in {"assigned", "unassigned", "mine"}:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "assignment_state 无效")
        if assignment_state and not assignment_role:
            if assignment_state == "assigned":
                stmt = stmt.where(WorkOrder.current_owner_user_id.is_not(None))
            elif assignment_state == "unassigned":
                stmt = stmt.where(WorkOrder.current_owner_user_id.is_(None))
            else:
                stmt = stmt.where(WorkOrder.current_owner_user_id == ctx.user_id)
        elif assignment_state == "mine":
            stmt = stmt.where(WorkOrder.current_owner_user_id == ctx.user_id)
        if mine:
            stmt = stmt.where(WorkOrder.current_owner_user_id == ctx.user_id)
        elif not ctx.has_any("admin", "expert", "safety"):
            stmt = stmt.where(
                or_(
                    WorkOrder.created_by_user_id == ctx.user_id,
                    WorkOrder.assigned_worker_user_id == ctx.user_id,
                    WorkOrder.assigned_expert_user_id == ctx.user_id,
                    WorkOrder.assigned_safety_user_id == ctx.user_id,
                    WorkOrder.current_owner_user_id == ctx.user_id,
                )
            )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        rows_stmt = stmt.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
        started = perf_counter()
        session_factory = get_session_factory()
        async with session_factory() as count_session, session_factory() as rows_session:
            total_result, rows_result = await asyncio.gather(
                count_session.execute(count_stmt),
                rows_session.execute(rows_stmt),
            )
        total = total_result.scalar_one()
        rows = rows_result.scalars().all()
        await observe_duration(
            "maintenance_work_order_query_duration_ms",
            (perf_counter() - started) * 1000,
            endpoint="list_work_orders",
            phase="count_and_rows",
        )
        return {
            "items": await self._serialize_work_orders(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_assignment(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("admin", "expert"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权修改工单分配")
        work_order = await self.get_work_order(work_order_id)
        await self.assert_work_order_readable(ctx, work_order)
        before = await self._serialize_work_order(work_order)

        for field_name in (*ASSIGNMENT_ROLE_FIELDS.values(), "current_owner_user_id"):
            if field_name not in body:
                continue
            raw_value = body.get(field_name)
            if raw_value in (None, "", 0):
                setattr(work_order, field_name, None)
                continue
            user = await self._get_assignment_user(int(raw_value))
            if field_name in ASSIGNMENT_ROLE_FIELDS.values():
                required_role = next(role for role, target in ASSIGNMENT_ROLE_FIELDS.items() if target == field_name)
                user_roles = [role.code for role in user.roles]
                if required_role not in user_roles:
                    raise MaintenanceAPIError(422, "INVALID_ASSIGNMENT_ROLE", f"所选用户不具备 {required_role} 角色")
            setattr(work_order, field_name, user.id)

        allowed_owner_ids = {
            work_order.assigned_worker_user_id,
            work_order.assigned_expert_user_id,
            work_order.assigned_safety_user_id,
        }
        allowed_owner_ids.discard(None)
        if work_order.current_owner_user_id is not None and work_order.current_owner_user_id not in allowed_owner_ids:
            raise MaintenanceAPIError(422, "INVALID_CURRENT_OWNER", "当前负责人必须从已分配的检修员/专家/安全员中选择")

        work_order.updated_at = utc_now_naive()
        after = await self._serialize_work_order(work_order)
        self.session.add(
            WorkOrderEvent(
                work_order_id=work_order.id,
                from_status=work_order.status,
                to_status=work_order.status,
                event_type="assignment_updated",
                payload={
                    "before": {
                        "assignees": before.get("assignees"),
                        "current_owner": before.get("current_owner"),
                    },
                    "after": {
                        "assignees": after.get("assignees"),
                        "current_owner": after.get("current_owner"),
                    },
                },
                actor_user_id=ctx.user_id,
                created_at=utc_now_naive(),
            )
        )
        await self.session.commit()
        await self.session.refresh(work_order)
        return after

    async def delete_work_order(self, work_order_id: int, ctx: CurrentUserCtx) -> None:
        work_order = await self.get_work_order(work_order_id)
        if not (ctx.has_any("admin") or work_order.created_by_user_id == ctx.user_id):
            raise MaintenanceAPIError(403, "FORBIDDEN", "无权删除该工单")

        filling_ids = (
            await self.session.execute(
                select(WorkOrderFilling.id).where(WorkOrderFilling.work_order_id == work_order_id)
            )
        ).scalars().all()
        if filling_ids:
            await self.session.execute(
                delete(WorkOrderFillingAttachment).where(
                    WorkOrderFillingAttachment.filling_id.in_(filling_ids)
                )
            )
        await self.session.execute(
            update(Attachment).where(Attachment.work_order_id == work_order_id).values(work_order_id=None)
        )
        await self.session.execute(
            update(KnowledgeArticle)
            .where(KnowledgeArticle.source_work_order_id == work_order_id)
            .values(source_work_order_id=None)
        )
        await self.session.execute(delete(Annotation).where(Annotation.work_order_id == work_order_id))
        await self.session.execute(delete(Escalation).where(Escalation.work_order_id == work_order_id))
        await self.session.execute(delete(ApprovalTask).where(ApprovalTask.work_order_id == work_order_id))
        await self.session.execute(delete(WorkOrderMessage).where(WorkOrderMessage.work_order_id == work_order_id))
        await self.session.execute(delete(RetrievalSnapshot).where(RetrievalSnapshot.work_order_id == work_order_id))
        await self.session.execute(delete(WorkOrderEvent).where(WorkOrderEvent.work_order_id == work_order_id))
        await self.session.execute(delete(WorkOrderFilling).where(WorkOrderFilling.work_order_id == work_order_id))
        await self._audit(
            "work_order.deleted",
            "work_order",
            str(work_order_id),
            ctx.user_id,
            {"device_id": work_order.device_id, "status": work_order.status},
            None,
        )
        await self.session.delete(work_order)
        await self.session.commit()

    async def get_work_order_detail(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        started = perf_counter()
        work_order = await self.get_work_order(work_order_id)
        await self.assert_work_order_readable(ctx, work_order)
        detail = await self._serialize_work_order(work_order)
        detail["step_progress_json"] = work_order.step_progress_json
        if isinstance(work_order.step_progress_json, dict):
            detail["source_task"] = work_order.step_progress_json.get("source_task")
        device = await self.session.get(Device, work_order.device_id)
        if device is not None:
            detail["device"] = {
                "id": device.id,
                "asset_code": device.asset_code,
                "model": device.model,
                "device_type": device.device_type,
            }
        template = await self._ensure_flow_template_bound(work_order, device)
        if template is not None:
            detail["flow_template"] = {
                "id": template.id,
                "name": template.name,
                "steps_json": template.steps_json,
            }
            detail["flow_template_id"] = template.id
            detail["current_step_no"] = work_order.current_step_no
        await observe_duration(
            "maintenance_work_order_query_duration_ms",
            (perf_counter() - started) * 1000,
            endpoint="get_work_order_detail",
            phase="total",
        )
        return detail

    async def list_events(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        started = perf_counter()
        work_order = await self.get_work_order(work_order_id)
        await self.assert_work_order_readable(ctx, work_order)
        rows = (
            await self.session.execute(
                select(WorkOrderEvent)
                .where(WorkOrderEvent.work_order_id == work_order_id)
                .order_by(WorkOrderEvent.id.asc())
            )
        ).scalars().all()
        items = [
            {
                "id": event.id,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "event_type": event.event_type,
                "payload": event.payload,
                "actor_user_id": event.actor_user_id,
                "created_at": to_iso_cn(event.created_at),
            }
            for event in rows
        ]
        total = len(items)
        await observe_duration(
            "maintenance_work_order_query_duration_ms",
            (perf_counter() - started) * 1000,
            endpoint="list_events",
            phase="total",
        )
        return {"items": items, "total": total, "page": 1, "page_size": max(total, 1)}

    async def confirm_step(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        work_order = await self.get_work_order(work_order_id)
        await self.assert_work_order_readable(ctx, work_order)
        if work_order.status != "S7":
            raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "工单不在检修中")
        if not body.get("mark_done", True):
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "mark_done 须为 true")
        step_no = int(body["step_no"])
        if work_order.flow_template_id is None:
            await self._ensure_flow_template_bound(work_order)
        if work_order.flow_template_id is None:
            raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "未绑定流程模板")
        template = await self.session.get(FlowTemplate, work_order.flow_template_id)
        if template is None:
            raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "模板不存在")
        steps = template.steps_json if isinstance(template.steps_json, list) else []
        step_def = next((step for step in steps if int(step.get("step_no", -1)) == step_no), None)
        if step_def is None:
            raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "工步不在模板中")
        progress = dict(work_order.step_progress_json or {})
        done_list = list(progress.get("completed_steps", []))
        if step_no in done_list:
            await self._audit(
                "step.confirm.idempotent",
                "work_order",
                str(work_order.id),
                ctx.user_id,
                {"step_no": step_no},
                "ALREADY_PROCESSED",
            )
            await self.session.commit()
            return {
                "work_order_id": work_order.id,
                "current_step_no": work_order.current_step_no,
                "confirmed_step_no": step_no,
                "business_code": "ALREADY_PROCESSED",
            }
        if work_order.current_step_no is None or step_no != work_order.current_step_no:
            raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "工步序号不匹配")
        if step_def.get("requires_approval"):
            approval_task = (
                await self.session.execute(
                    select(ApprovalTask).where(
                        ApprovalTask.work_order_id == work_order.id,
                        ApprovalTask.step_no == step_no,
                    )
                )
            ).scalar_one_or_none()
            approved = (
                await self.session.execute(
                    select(ApprovalTask).where(
                        ApprovalTask.work_order_id == work_order.id,
                        ApprovalTask.step_no == step_no,
                        ApprovalTask.status == "approved",
                    )
                )
            ).scalar_one_or_none()
            if approved is None:
                if approval_task is None:
                    approval_task = ApprovalTask(
                        work_order_id=work_order.id,
                        step_no=step_no,
                        status="pending",
                        created_at=utc_now_naive(),
                        updated_at=utc_now_naive(),
                    )
                    self.session.add(approval_task)
                await self.transition(
                    work_order,
                    "S6",
                    event_type="approval_requested",
                    actor_user_id=ctx.user_id,
                    payload={"step_no": step_no},
                )
                await self._audit(
                    "approval.requested",
                    "work_order",
                    str(work_order.id),
                    ctx.user_id,
                    {"step_no": step_no},
                    None,
                )
                await self.session.commit()
                return {
                    "work_order_id": work_order.id,
                    "current_step_no": work_order.current_step_no,
                    "confirmed_step_no": None,
                    "business_code": "APPROVAL_REQUIRED",
                }
        done_list.append(step_no)
        progress["completed_steps"] = done_list
        work_order.step_progress_json = progress
        next_no = step_no + 1
        if any(int(step.get("step_no", -1)) == next_no for step in steps):
            work_order.current_step_no = next_no
        else:
            work_order.current_step_no = next_no
        work_order.updated_at = utc_now_naive()
        await self._audit(
            "step.confirmed",
            "work_order",
            str(work_order.id),
            ctx.user_id,
            {"step_no": step_no},
            None,
        )
        await self.session.commit()
        return {
            "work_order_id": work_order.id,
            "current_step_no": work_order.current_step_no,
            "confirmed_step_no": step_no,
        }
