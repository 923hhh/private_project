"""Approval-task operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import ApprovalTask
from app.modules.maintenance.application.work_order_service import (
    MaintenanceWorkOrderService,
    _wo_public,
)
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


class MaintenanceApprovalService:
    """Approval-task list and resolution operations."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditCallback,
        work_order_service: MaintenanceWorkOrderService,
    ) -> None:
        self.session = session
        self._audit = audit
        self.work_order_service = work_order_service

    async def list_approval_tasks(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("safety", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅审批人可查看")
        rows = (
            await self.session.execute(
                select(ApprovalTask)
                .where(ApprovalTask.status == "pending")
                .order_by(ApprovalTask.id.desc())
            )
        ).scalars().all()
        items = [
            {
                "id": task.id,
                "work_order_id": task.work_order_id,
                "step_no": task.step_no,
                "status": task.status,
                "created_at": to_iso_cn(task.created_at),
            }
            for task in rows
        ]
        total = len(items)
        return {"items": items, "total": total, "page": 1, "page_size": max(total, 1)}

    async def resolve_approval(
        self,
        approval_task_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        if not ctx.has_any("safety", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅审批人可操作")
        task = await self.session.get(ApprovalTask, approval_task_id)
        if task is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "审批任务不存在")
        new_status = body["status"]
        if new_status not in ("approved", "rejected", "need_more_info"):
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "status 非法")
        work_order = await self.work_order_service.get_work_order(task.work_order_id)

        if task.status != "pending":
            if task.status == new_status:
                await self._audit(
                    "approval.idempotent",
                    "approval_task",
                    str(task.id),
                    ctx.user_id,
                    {"note": "duplicate"},
                    "ALREADY_PROCESSED",
                )
                await self.session.commit()
                return {
                    "id": task.id,
                    "work_order_id": task.work_order_id,
                    "status": task.status,
                    "resolved_at": to_iso_cn(task.resolved_at),
                    "work_order": _wo_public(work_order),
                    "business_code": "ALREADY_PROCESSED",
                }
            raise MaintenanceAPIError(409, "CONFLICT", "审批已终态且结论不一致")

        if work_order.status != "S6":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "工单不在待审批状态")

        task.status = new_status
        task.resolution = new_status
        task.comment = body.get("comment")
        task.material_attachment_ids = body.get("material_attachment_ids")
        task.approver_user_id = ctx.user_id
        task.resolved_at = utc_now_naive()
        task.updated_at = utc_now_naive()

        if new_status == "approved":
            await self.work_order_service.transition(
                work_order,
                "S7",
                event_type="approval_approved",
                actor_user_id=ctx.user_id,
            )
        elif new_status == "rejected":
            await self.work_order_service.transition(
                work_order,
                "SX",
                event_type="approval_rejected",
                actor_user_id=ctx.user_id,
            )
        else:
            await self.work_order_service.transition(
                work_order,
                "S6",
                event_type="approval_need_info",
                actor_user_id=ctx.user_id,
            )

        await self._audit(
            "approval.resolve",
            "approval_task",
            str(task.id),
            ctx.user_id,
            {"status": new_status},
            None,
        )
        await self.session.commit()
        await self.session.refresh(work_order)
        return {
            "id": task.id,
            "work_order_id": task.work_order_id,
            "status": task.status,
            "resolved_at": to_iso_cn(task.resolved_at),
            "work_order": _wo_public(work_order),
        }
