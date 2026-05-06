"""Work-order core operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import (
    Annotation,
    ApprovalTask,
    Device,
    Escalation,
    FlowTemplate,
    KnowledgeArticle,
    Attachment,
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
    }


def _can_read_wo(ctx: CurrentUserCtx, wo: WorkOrder) -> bool:
    if ctx.has_any("admin", "expert", "safety"):
        return True
    return wo.created_by_user_id == ctx.user_id


class MaintenanceWorkOrderService:
    """Core work-order lifecycle, detail, event, and step-confirm actions."""

    def __init__(self, session: AsyncSession, audit: AuditCallback) -> None:
        self.session = session
        self._audit = audit

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
        return _wo_public(work_order)

    async def list_work_orders(
        self,
        ctx: CurrentUserCtx,
        *,
        page: int,
        page_size: int,
        status: str | None,
        device_id: int | None,
        mine: bool | None,
    ) -> dict[str, Any]:
        stmt = select(WorkOrder)
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if device_id:
            stmt = stmt.where(WorkOrder.device_id == device_id)
        if mine or (not ctx.has_any("admin", "expert", "safety")):
            stmt = stmt.where(WorkOrder.created_by_user_id == ctx.user_id)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(
                stmt.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        return {
            "items": [_wo_public(work_order) for work_order in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

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
        work_order = await self.get_work_order(work_order_id)
        await self.assert_work_order_readable(ctx, work_order)
        detail = dict(_wo_public(work_order))
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
        if work_order.flow_template_id is not None:
            template = await self.session.get(FlowTemplate, work_order.flow_template_id)
            if template is not None:
                detail["flow_template"] = {
                    "id": template.id,
                    "name": template.name,
                    "steps_json": template.steps_json,
                }
        return detail

    async def list_events(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
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
                raise MaintenanceAPIError(409, "STEP_NOT_ALLOWED", "高危工步未审批通过")
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
