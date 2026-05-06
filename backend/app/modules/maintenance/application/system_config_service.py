"""System configuration and health operations for maintenance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import SystemConfig
from app.modules.maintenance.datetime_util import to_iso_cn
from app.modules.maintenance.deps import CurrentUserCtx
from app.modules.maintenance.errors import MaintenanceAPIError


class MaintenanceSystemConfigService:
    """System config read/write plus subsystem health."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_system_configs(self, ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅管理员")
        rows = (await self.session.execute(select(SystemConfig))).scalars().all()
        items = []
        for config in rows:
            entry: dict[str, Any] = {
                "key": config.key,
                "value_type": config.value_type,
                "reload_policy": config.reload_policy,
                "is_sensitive": config.is_sensitive,
                "updated_at": to_iso_cn(config.updated_at),
            }
            if config.is_sensitive:
                entry["value_masked"] = "****"
            else:
                entry["value"] = config.value
            items.append(entry)
        total = len(items)
        return {"items": items, "total": total, "page": 1, "page_size": max(total, 1)}

    async def patch_system_config(self, key: str, body: dict[str, Any], ctx: CurrentUserCtx) -> dict[str, Any]:
        if not ctx.has_any("admin"):
            raise MaintenanceAPIError(403, "FORBIDDEN", "仅管理员")
        config = await self.session.get(SystemConfig, key)
        if config is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "配置不存在")
        if config.is_sensitive:
            raise MaintenanceAPIError(400, "VALIDATION_ERROR", "敏感配置不可通过接口写入")
        config.value = body.get("value", config.value)
        config.updated_at = datetime.now(timezone.utc)
        config.updated_by_user_id = ctx.user_id
        await self.session.commit()
        return {
            "key": config.key,
            "value": config.value,
            "value_type": config.value_type,
            "reload_policy": config.reload_policy,
            "is_sensitive": config.is_sensitive,
            "updated_at": to_iso_cn(config.updated_at),
        }

    async def health_sub(self) -> dict[str, Any]:
        try:
            await self.session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"
        return {
            "app": "ok",
            "database": db_status,
            "vector": "skipped",
            "llm": "config_only",
        }
