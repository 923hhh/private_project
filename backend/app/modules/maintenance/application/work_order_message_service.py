"""Work-order message operations for maintenance."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import WorkOrderMessage
from app.modules.maintenance.application.work_order_service import MaintenanceWorkOrderService
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError


class MaintenanceWorkOrderMessageService:
    """User/assistant message read-write operations bound to a work order."""

    def __init__(
        self,
        session: AsyncSession,
        work_order_service: MaintenanceWorkOrderService,
    ) -> None:
        self.session = session
        self.work_order_service = work_order_service

    async def post_user_message(
        self,
        work_order_id: int,
        body: dict[str, Any],
        ctx: CurrentUserCtx,
    ) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        content = (body.get("content") or "").strip()
        if not content:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "content 必填")
        message = WorkOrderMessage(
            work_order_id=work_order.id,
            role="user",
            content=content,
            retrieval_snapshot_id=None,
            created_at=utc_now_naive(),
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return {"id": message.id, "created_at": to_iso_cn(message.created_at)}

    async def list_messages(
        self,
        work_order_id: int,
        ctx: CurrentUserCtx,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        stmt = select(WorkOrderMessage).where(WorkOrderMessage.work_order_id == work_order_id)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(
                stmt.order_by(WorkOrderMessage.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        items = [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "retrieval_snapshot_id": message.retrieval_snapshot_id,
                "created_at": to_iso_cn(message.created_at),
            }
            for message in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
