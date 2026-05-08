"""Work-order message operations for maintenance."""
from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import observe_duration
from app.db.session import get_session_factory
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
        started = perf_counter()
        work_order = await self.work_order_service.get_work_order(work_order_id)
        await self.work_order_service.assert_work_order_readable(ctx, work_order)
        stmt = select(WorkOrderMessage).where(WorkOrderMessage.work_order_id == work_order_id)
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        rows_stmt = (
            stmt.order_by(WorkOrderMessage.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        session_factory = get_session_factory()
        async with session_factory() as count_session, session_factory() as rows_session:
            total_result, rows_result = await asyncio.gather(
                count_session.execute(count_stmt),
                rows_session.execute(rows_stmt),
            )
        total = total_result.scalar_one()
        rows = rows_result.scalars().all()
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
        await observe_duration(
            "maintenance_work_order_query_duration_ms",
            (perf_counter() - started) * 1000,
            endpoint="list_messages",
            phase="count_and_rows",
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}
