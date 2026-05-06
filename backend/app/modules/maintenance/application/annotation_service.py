"""Annotation operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import Annotation, WorkOrderMessage
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


class MaintenanceAnnotationService:
    """Expert annotation creation for work-order messages."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditCallback,
        work_order_service: MaintenanceWorkOrderService,
    ) -> None:
        self.session = session
        self._audit = audit
        self.work_order_service = work_order_service

    async def create_annotation(
        self,
        work_order_id: int,
        message_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        if not ctx.has_any("expert", "admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅专家可标注")
        work_order = await self.work_order_service.get_work_order(work_order_id)
        message = await self.session.get(WorkOrderMessage, message_id)
        if message is None or message.work_order_id != work_order.id:
            raise MaintenanceAPIError(404, "NOT_FOUND", "消息不存在")
        annotation = Annotation(
            work_order_id=work_order.id,
            message_id=message.id,
            annotator_user_id=ctx.user_id,
            label=body["label"],
            comment=body.get("comment"),
            created_at=utc_now_naive(),
        )
        self.session.add(annotation)
        await self._audit(
            "annotation.created",
            "work_order_message",
            str(message.id),
            ctx.user_id,
            {"annotation_label": body["label"], "work_order_id": work_order.id},
        )
        await self.session.commit()
        await self.session.refresh(annotation)
        return {"id": annotation.id}
