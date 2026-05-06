"""Helpers for maintaining knowledge-related device model records."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import DeviceModel
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate


async def ensure_device_model(
    session: AsyncSession,
    data: KnowledgeDocumentCreate,
) -> None:
    """Create a device model record when a new model code appears."""
    stmt = select(DeviceModel).where(
        DeviceModel.equipment_type == data.equipment_type,
        DeviceModel.model_code == data.equipment_model,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return

    session.add(
        DeviceModel(
            equipment_type=data.equipment_type,
            model_code=data.equipment_model or "",
            display_name=data.equipment_model,
        )
    )
    await session.flush()
