"""Device operations for maintenance."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import Device
from app.modules.maintenance.datetime_util import to_iso_cn, utc_now_naive
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError

AuditCallback = Callable[[str, str, str, int | None, dict | None, str | None], Awaitable[None]]


class MaintenanceDeviceService:
    """Device list/detail/update/create operations."""

    def __init__(self, session: AsyncSession, audit: AuditCallback) -> None:
        self.session = session
        self._audit = audit

    async def list_devices(
        self,
        *,
        page: int,
        page_size: int,
        device_type: str | None,
        model: str | None,
        q: str | None,
    ) -> dict[str, Any]:
        stmt = select(Device)
        if device_type:
            stmt = stmt.where(Device.device_type == device_type)
        if model:
            stmt = stmt.where(Device.model.contains(model))
        if q:
            stmt = stmt.where(
                (Device.asset_code.contains(q)) | (Device.model.contains(q)) | (Device.location.contains(q))
            )
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            await self.session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
        ).scalars().all()
        items = [self._serialize_device(device) for device in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_device(self, device_id: int) -> Device:
        device = await self.session.get(Device, device_id)
        if device is None:
            raise MaintenanceAPIError(404, "DEVICE_NOT_FOUND", "设备不存在")
        return device

    async def patch_device(self, device_id: int, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        device = await self.get_device(device_id)
        if "location" in body and body["location"] is not None:
            device.location = body["location"]
        if "responsibility_expert_user_id" in body:
            device.responsibility_expert_user_id = body["responsibility_expert_user_id"]
        device.updated_at = utc_now_naive()
        await self._audit("DEVICE_UPDATED", "device", str(device_id), ctx.user_id, {"fields": list(body.keys())}, None)
        await self.session.commit()
        return self._serialize_device(device)

    async def create_device(self, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        device = Device(
            device_type=body["device_type"],
            model=body["model"],
            asset_code=body.get("asset_code"),
            location=body.get("location"),
            responsibility_expert_user_id=body.get("responsibility_expert_user_id"),
            extra=body.get("extra"),
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.session.add(device)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise MaintenanceAPIError(409, "DUPLICATE_ASSET", "资产编号冲突") from exc
        await self._audit("DEVICE_CREATED", "device", str(device.id), ctx.user_id, None, None)
        await self.session.commit()
        await self.session.refresh(device)
        return self._serialize_device(device)

    def _serialize_device(self, device: Device) -> dict[str, Any]:
        return {
            "id": device.id,
            "device_type": device.device_type,
            "model": device.model,
            "asset_code": device.asset_code,
            "location": device.location,
            "responsibility_expert_user_id": device.responsibility_expert_user_id,
            "created_at": to_iso_cn(device.created_at),
            "updated_at": to_iso_cn(device.updated_at),
        }
