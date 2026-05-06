"""Escalation operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import ApprovalTask, Escalation, WorkOrderMessage
from app.modules.maintenance.application.device_service import MaintenanceDeviceService
from app.modules.maintenance.application.work_order_service import (
    MaintenanceWorkOrderService,
    _wo_public,
)
from app.modules.maintenance.datetime_util import utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


class MaintenanceEscalationService:
    """Escalation create/read/resolve operations."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditCallback,
        work_order_service: MaintenanceWorkOrderService,
        device_service: MaintenanceDeviceService,
    ) -> None:
        self.session = session
        self._audit = audit
        self.work_order_service = work_order_service
        self.device_service = device_service

    async def create_escalation(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        note = (body.get("escalation_note") or "").strip()
        if len(note) < 10:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "escalation_note 至少 10 字")
        device = await self.device_service.get_device(work_order.device_id)
        if device.responsibility_expert_user_id is None:
            raise MaintenanceAPIError(400, "EXPERT_NOT_CONFIGURED", "设备未配置责任专家")
        active_escalation = (
            await self.session.execute(
                select(Escalation).where(
                    Escalation.work_order_id == work_order.id,
                    Escalation.status.in_(["open", "in_progress"]),
                )
            )
        ).scalars().first()
        if active_escalation is not None:
            raise MaintenanceAPIError(409, "ESCALATION_IN_PROGRESS", "已存在进行中的升级单")
        if work_order.status not in ("S2", "S3"):
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "当前状态不可发起升级")
        related_message_id = body.get("related_message_id")
        if related_message_id is not None:
            message = await self.session.get(WorkOrderMessage, int(related_message_id))
            if message is None or message.work_order_id != work_order.id or message.role != "assistant":
                raise MaintenanceAPIError(400, "INVALID_MESSAGE_REF", "related_message_id 非法")
        escalation = Escalation(
            work_order_id=work_order.id,
            status="open",
            assigned_expert_user_id=device.responsibility_expert_user_id,
            escalation_note=note,
            attachment_ids=body.get("attachment_ids"),
            related_message_id=related_message_id,
            created_by_user_id=ctx.user_id,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.session.add(escalation)
        try:
            await self.work_order_service.transition(
                work_order,
                "S4",
                event_type="escalation_created",
                actor_user_id=ctx.user_id,
            )
            await self.session.flush()
            await self._audit(
                "escalation.created",
                "work_order",
                str(work_order.id),
                ctx.user_id,
                {"escalation_id": escalation.id},
                None,
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "ESCALATION_IN_PROGRESS", "已存在进行中的升级单") from None
        await self.session.refresh(escalation)
        return {
            "id": escalation.id,
            "work_order_id": work_order.id,
            "status": escalation.status,
            "work_order": _wo_public(work_order),
        }

    async def get_escalation(self, escalation_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        escalation = await self.session.get(Escalation, escalation_id)
        if escalation is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "升级单不存在")
        work_order = await self.work_order_service.get_work_order(escalation.work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if ctx.has_any("expert") and escalation.assigned_expert_user_id != ctx.user_id and not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "非指派专家不可查看")
        return {
            "id": escalation.id,
            "work_order_id": escalation.work_order_id,
            "status": escalation.status,
            "assigned_expert_user_id": escalation.assigned_expert_user_id,
            "escalation_note": escalation.escalation_note,
            "conclusion_text": escalation.conclusion_text,
        }

    async def resolve_escalation(
        self,
        escalation_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        escalation = await self.session.get(Escalation, escalation_id)
        if escalation is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "升级单不存在")
        if escalation.assigned_expert_user_id != ctx.user_id and not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "非指派专家不可处理")
        work_order = await self.work_order_service.get_work_order(escalation.work_order_id)
        if work_order.status not in ("S4", "S5"):
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "工单状态不允许会诊结论")
        conclusion = (body.get("conclusion_text") or "").strip()
        if not conclusion:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "conclusion_text 必填")
        high_risk = bool(body.get("requires_high_risk_work"))
        escalation.status = "resolved"
        escalation.conclusion_text = conclusion
        escalation.resolved_at = utc_now_naive()
        escalation.updated_at = utc_now_naive()
        if high_risk:
            await self.work_order_service.transition(
                work_order,
                "S6",
                event_type="escalation_high_risk",
                actor_user_id=ctx.user_id,
            )
            step_no = work_order.current_step_no or 2
            self.session.add(
                ApprovalTask(
                    work_order_id=work_order.id,
                    step_no=step_no,
                    status="pending",
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive(),
                )
            )
        else:
            await self.work_order_service.transition(
                work_order,
                "S7",
                event_type="escalation_resolved",
                actor_user_id=ctx.user_id,
            )
        await self._audit(
            "escalation.resolved",
            "escalation",
            str(escalation.id),
            ctx.user_id,
            {"high_risk": high_risk, "work_order_id": work_order.id},
            None,
        )
        await self.session.commit()
        await self.session.refresh(work_order)
        return {"id": escalation.id, "status": escalation.status, "work_order": _wo_public(work_order)}
