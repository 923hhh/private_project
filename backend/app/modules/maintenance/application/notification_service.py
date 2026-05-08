"""Notification center service for maintenance console."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import UserNotification, WorkOrder
from app.models.knowledge import MaintenanceCase
from app.models.tasks import MaintenanceTask
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

SLA_HOURS_BY_LEVEL: dict[str, int] = {
    "emergency": 2,
    "紧急检修": 2,
    "standard": 8,
    "标准检修": 8,
    "计划定修": 8,
    "routine": 24,
    "例行检修": 24,
}


def _resolve_sla_hours(maintenance_level: str | None) -> int:
    level = (maintenance_level or "").strip()
    return SLA_HOURS_BY_LEVEL.get(level, 72)


def _format_work_order_code(work_order_id: int) -> str:
    return f"WO-{work_order_id:06d}"


def _format_task_code(task_id: int) -> str:
    return f"TASK-{task_id:06d}"


def _format_case_code(case_id: int) -> str:
    return f"CASE-{case_id:03d}"


class MaintenanceNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _build_candidates(self, ctx: CurrentUserCtx) -> list[dict[str, Any]]:
        now = utc_now_naive()
        warning_cutoff = now + timedelta(minutes=30)
        candidates: list[dict[str, Any]] = []

        work_order_stmt = select(WorkOrder).where(WorkOrder.status.not_in(["S10", "SX"]))
        if not ctx.has_any("admin", "expert", "safety"):
            work_order_stmt = work_order_stmt.where(
                or_(
                    WorkOrder.created_by_user_id == ctx.user_id,
                    WorkOrder.assigned_worker_user_id == ctx.user_id,
                    WorkOrder.assigned_expert_user_id == ctx.user_id,
                    WorkOrder.assigned_safety_user_id == ctx.user_id,
                    WorkOrder.current_owner_user_id == ctx.user_id,
                )
            )
        work_orders = (await self.session.execute(work_order_stmt.order_by(WorkOrder.updated_at.desc()).limit(20))).scalars().all()
        for work_order in work_orders:
            deadline = work_order.created_at + timedelta(hours=_resolve_sla_hours(work_order.maintenance_level))
            if deadline > warning_cutoff:
                continue
            if deadline <= now:
                minutes = max(1, int((now - deadline).total_seconds() // 60))
                stage = "overdue"
                detail = f"{_format_work_order_code(work_order.id)} 已超时 {minutes} 分钟"
            else:
                minutes = max(1, int((deadline - now).total_seconds() // 60))
                stage = "warning"
                detail = f"{_format_work_order_code(work_order.id)} 还有 {minutes} 分钟超时"
            candidates.append(
                {
                    "kind": "work_order_sla",
                    "source_key": f"work_order_sla:{work_order.id}:{stage}",
                    "title": "工单超时预警",
                    "detail": detail,
                    "link_url": f"/tickets/{work_order.id}",
                }
            )

        task_rows = (
            await self.session.execute(
                select(MaintenanceTask)
                .where(MaintenanceTask.status == "completed")
                .order_by(MaintenanceTask.updated_at.desc())
                .limit(8)
            )
        ).scalars().all()
        for task in task_rows:
            candidates.append(
                {
                    "kind": "task_completed",
                    "source_key": f"task_completed:{task.id}",
                    "title": "诊断任务完成",
                    "detail": f"{_format_task_code(task.id)} 已生成诊断结论",
                    "link_url": f"/tasks/{task.id}",
                }
            )

        if ctx.has_any("admin", "expert"):
            case_rows = (
                await self.session.execute(
                    select(MaintenanceCase)
                    .where(MaintenanceCase.status == "pending_review")
                    .order_by(MaintenanceCase.updated_at.desc())
                    .limit(8)
                )
            ).scalars().all()
            for case in case_rows:
                candidates.append(
                    {
                        "kind": "case_pending_review",
                        "source_key": f"case_pending_review:{case.id}",
                        "title": "新案例待审核",
                        "detail": f"{_format_case_code(case.id)} 已提交待审核",
                        "link_url": f"/cases/CASE-{case.id}",
                    }
                )

        return candidates

    async def _sync_notifications(self, ctx: CurrentUserCtx) -> None:
        candidates = await self._build_candidates(ctx)
        if not candidates:
            return

        source_keys = [item["source_key"] for item in candidates]
        existing_rows = (
            await self.session.execute(
                select(UserNotification).where(
                    UserNotification.user_id == ctx.user_id,
                    UserNotification.source_key.in_(source_keys),
                )
            )
        ).scalars().all()
        existing_by_key = {row.source_key: row for row in existing_rows}
        now = utc_now_naive()

        for item in candidates:
            row = existing_by_key.get(item["source_key"])
            if row is None:
                self.session.add(
                    UserNotification(
                        user_id=ctx.user_id,
                        kind=item["kind"],
                        source_key=item["source_key"],
                        title=item["title"],
                        detail=item["detail"],
                        link_url=item.get("link_url"),
                        is_read=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
                continue
            if row.title != item["title"] or row.detail != item["detail"] or row.link_url != item.get("link_url"):
                row.title = item["title"]
                row.detail = item["detail"]
                row.link_url = item.get("link_url")
                row.is_read = False
                row.read_at = None
                row.updated_at = now

        await self.session.commit()

    @staticmethod
    def _serialize(row: UserNotification) -> dict[str, Any]:
        return {
            "id": row.id,
            "kind": row.kind,
            "title": row.title,
            "detail": row.detail,
            "link_url": row.link_url,
            "read": row.is_read,
            "created_at": to_iso_cn(row.created_at),
            "updated_at": to_iso_cn(row.updated_at),
        }

    async def list_notifications(self, ctx: CurrentUserCtx, *, limit: int = 20) -> dict[str, Any]:
        await self._sync_notifications(ctx)
        rows = (
            await self.session.execute(
                select(UserNotification)
                .where(UserNotification.user_id == ctx.user_id)
                .order_by(UserNotification.is_read.asc(), UserNotification.updated_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        items = [self._serialize(row) for row in rows]
        unread_count = sum(1 for item in items if not item["read"])
        return {"items": items, "unread_count": unread_count}

    async def mark_read(self, notification_id: int, ctx: CurrentUserCtx) -> dict[str, Any]:
        row = await self.session.get(UserNotification, notification_id)
        if row is None or row.user_id != ctx.user_id:
            raise MaintenanceAPIError(404, "NOT_FOUND", "通知不存在")
        row.is_read = True
        row.read_at = utc_now_naive()
        row.updated_at = utc_now_naive()
        await self.session.commit()
        await self.session.refresh(row)
        return self._serialize(row)

    async def mark_all_read(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        now = utc_now_naive()
        await self.session.execute(
            update(UserNotification)
            .where(UserNotification.user_id == ctx.user_id, UserNotification.is_read.is_(False))
            .values(is_read=True, read_at=now, updated_at=now)
        )
        await self.session.commit()
        return {"success": True}
