"""Flow-template queries for maintenance."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.maintenance import FlowTemplate
from app.modules.maintenance.errors import MaintenanceAPIError


class MaintenanceFlowTemplateService:
    """Read-only flow-template access."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_flow_templates(
        self,
        device_type: str | None,
        maintenance_level: str | None,
    ) -> dict[str, Any]:
        stmt = select(FlowTemplate).where(FlowTemplate.status == "published")
        if device_type:
            stmt = stmt.where(FlowTemplate.device_type == device_type)
        if maintenance_level:
            stmt = stmt.where(FlowTemplate.maintenance_level == maintenance_level)
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [
            {
                "id": template.id,
                "name": template.name,
                "device_type": template.device_type,
                "maintenance_level": template.maintenance_level,
                "version": template.version,
            }
            for template in rows
        ]
        total = len(items)
        return {"items": items, "total": total, "page": 1, "page_size": max(total, 1)}

    async def get_flow_template(self, template_id: int) -> dict[str, Any]:
        template = await self.session.get(FlowTemplate, template_id)
        if template is None:
            raise MaintenanceAPIError(404, "NOT_FOUND", "模板不存在")
        return {
            "id": template.id,
            "name": template.name,
            "device_type": template.device_type,
            "maintenance_level": template.maintenance_level,
            "steps_json": template.steps_json,
            "version": template.version,
            "status": template.status,
        }
