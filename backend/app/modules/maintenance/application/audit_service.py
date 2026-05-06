"""Audit-log queries for maintenance."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import AuditLog
from app.modules.maintenance.datetime_util import to_iso_cn
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError


class MaintenanceAuditService:
    """Administrative audit-log listing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_audit_logs(
        self,
        ctx: CurrentUserCtx,
        *,
        page: int,
        page_size: int,
        resource_type: str | None,
        resource_id: str | None,
    ) -> dict[str, Any]:
        if not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅管理员可查审计")
        stmt = select(AuditLog)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [
            {
                "id": row.id,
                "action": row.action,
                "actor_user_id": row.actor_user_id,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "payload": row.payload,
                "created_at": to_iso_cn(row.created_at),
            }
            for row in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
