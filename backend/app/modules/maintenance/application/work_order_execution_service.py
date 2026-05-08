"""Work-order execution actions and filling operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import FlowTemplate, WorkOrderFilling, WorkOrderFillingAttachment
from app.modules.maintenance.application.device_service import MaintenanceDeviceService
from app.modules.maintenance.application.work_order_service import (
    MaintenanceWorkOrderService,
    _wo_public,
)
from app.modules.maintenance.datetime_util import utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]

MAINTENANCE_LEVEL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "standard": ("计划定修", "标准检修"),
    "routine": ("例行检修",),
    "emergency": ("紧急检修",),
}


class MaintenanceWorkOrderExecutionService:
    """Execution entry, completion, expert review acceptance, and filling submission."""

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

    async def action_enter_maintenance(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if work_order.status not in ("S1", "S3", "S5"):
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "当前状态不允许进入检修")
        device = await self.device_service.get_device(work_order.device_id)
        template = await self._resolve_flow_template(
            device_type=device.device_type,
            maintenance_level=work_order.maintenance_level,
        )
        if template:
            work_order.flow_template_id = template.id
            work_order.current_step_no = 1
        await self.work_order_service.transition(
            work_order,
            "S7",
            event_type="enter_maintenance",
            actor_user_id=ctx.user_id,
        )
        await self.session.commit()
        return {"work_order": _wo_public(work_order)}

    async def action_complete_maintenance(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if work_order.status != "S7":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "仅检修中可完成检修")
        await self.work_order_service.transition(
            work_order,
            "S8",
            event_type="complete_maintenance",
            actor_user_id=ctx.user_id,
        )
        await self.session.commit()
        return {"work_order": _wo_public(work_order)}

    async def action_accept_fill_review(self, work_order_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("expert", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅专家或管理员可复核")
        work_order = await self.work_order_service.get_work_order(work_order_id)
        if work_order.status != "S9":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "工单不在待验收状态")
        await self.work_order_service.transition(
            work_order,
            "S10",
            event_type="expert_accept_fill",
            actor_user_id=ctx.user_id,
        )
        await self.session.commit()
        return {"work_order": _wo_public(work_order)}

    def validate_filling(self, body: dict[str, Any]) -> None:
        resolution_status = body.get("resolution_status")
        closure_code = body.get("closure_code")
        attachment_ids = body.get("attachment_ids") or []
        if resolution_status not in ("resolved", "unresolved"):
            raise MaintenanceAPIError(
                400,
                "VALIDATION_ERROR",
                "resolution_status 非法",
                errors=[{"field": "resolution_status", "code": "INVALID_ENUM", "message": ""}],
            )
        if not isinstance(attachment_ids, list) or len(attachment_ids) < 1:
            raise MaintenanceAPIError(
                400,
                "VALIDATION_ERROR",
                "attachment_ids 至少 1 个",
                errors=[{"field": "attachment_ids", "code": "REQUIRED", "message": ""}],
            )
        if resolution_status == "resolved":
            allowed = {"NORMAL", "PART_REPLACED", "ADJUSTED", "OTHER"}
            if closure_code not in allowed:
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "closure_code 非法")
            if closure_code == "OTHER" and not (body.get("detail_notes") or "").strip():
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "OTHER 须填写 detail_notes")
        else:
            if closure_code != "UNRESOLVED":
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "unresolved 时 closure_code 须为 UNRESOLVED")
            post_action = body.get("post_unresolved_action")
            if post_action not in ("REOPEN_ESCALATION", "RETRY_RETRIEVAL", "CLOSE_UNRESOLVED"):
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "post_unresolved_action 必填且枚举合法")
            unresolved_reason = body.get("unresolved_reason_code")
            allowed_reasons = {"EQUIPMENT_LIMIT", "INFO_INSUFFICIENT", "EXPERT_REQUIRED", "USER_ABORT", "OTHER"}
            if unresolved_reason not in allowed_reasons:
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "unresolved_reason_code 非法")
            if unresolved_reason == "OTHER" and not (body.get("detail_notes") or "").strip():
                raise MaintenanceAPIError(400, "VALIDATION_ERROR", "OTHER 原因须填写 detail_notes")

    async def post_filling(self, work_order_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        if work_order.status != "S8":
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "仅待回填状态可提交")
        self.validate_filling(body)
        await self.session.execute(
            update(WorkOrderFilling)
            .where(
                WorkOrderFilling.work_order_id == work_order.id,
                WorkOrderFilling.is_latest.is_(True),
            )
            .values(is_latest=False)
        )
        filling = WorkOrderFilling(
            work_order_id=work_order.id,
            is_latest=True,
            resolution_status=body["resolution_status"],
            closure_code=body["closure_code"],
            post_unresolved_action=body.get("post_unresolved_action"),
            unresolved_reason_code=body.get("unresolved_reason_code"),
            detail_notes=body.get("detail_notes"),
            submitted_by_user_id=ctx.user_id,
            submitted_at=utc_now_naive(),
        )
        self.session.add(filling)
        await self.session.flush()
        for attachment_id in body["attachment_ids"]:
            self.session.add(
                WorkOrderFillingAttachment(
                    filling_id=filling.id,
                    attachment_id=int(attachment_id),
                )
            )
        await self.work_order_service.transition(
            work_order,
            "S9",
            event_type="fill_submitted",
            actor_user_id=ctx.user_id,
        )
        await self._audit(
            "filling.submitted",
            "work_order",
            str(work_order.id),
            ctx.user_id,
            {"filling_id": filling.id},
            None,
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "INVALID_STATE_TRANSITION", "并发回填冲突，请重试") from None
        return {"work_order": _wo_public(work_order), "filling_id": filling.id}
