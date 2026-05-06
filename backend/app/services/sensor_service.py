# File: app/services/sensor_service.py
"""业务逻辑层 - 传感器数据操作

提供 API 路由层与数据库访问之间的抽象隔离，
为未来 LangChain Agent 集成保持模块化纯粹性。
"""
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sensor_data import SensorData
from app.schemas.sensor_data import SensorDataCreate


class SensorService:
    """传感器数据 CRUD 操作服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: SensorDataCreate) -> SensorData:
        """创建单条传感器数据记录

        Args:
            data: Pydantic 创建schema

        Returns:
            创建的 SensorData ORM 对象

        Raises:
            Exception: 数据库操作失败时自动回滚
        """
        try:
            record = SensorData(**data.model_dump())
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)
            return record
        except Exception:
            await self.session.rollback()
            raise

    async def create_batch(self, data_list: list[SensorDataCreate]) -> int:
        """批量创建传感器数据记录

        Args:
            data_list: Pydantic 创建schema列表

        Returns:
            成功插入的记录数

        Raises:
            Exception: 数据库操作失败时自动回滚
        """
        try:
            records = [SensorData(**data.model_dump()) for data in data_list]
            self.session.add_all(records)
            await self.session.commit()
            return len(records)
        except Exception:
            await self.session.rollback()
            raise

    async def create_batch_dict(self, record_dicts: list[dict[str, Any]]) -> int:
        """批量创建传感器数据记录（字典形式）

        Args:
            record_dicts: 字典列表，每条包含传感器数据

        Returns:
            成功插入的记录数

        Raises:
            Exception: 数据库操作失败时自动回滚
        """
        try:
            records = [SensorData(**d) for d in record_dicts]
            self.session.add_all(records)
            await self.session.commit()
            return len(records)
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_id(self, record_id: int) -> SensorData | None:
        """根据 ID 获取传感器记录"""
        result = await self.session.execute(
            select(SensorData).where(SensorData.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_sensor_data_by_time_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> list[SensorData]:
        """按时间范围查询传感器记录（供 LangChain Tool 调用）

        Args:
            start: 起始时间
            end: 结束时间
            limit: 最大返回条数

        Returns:
            时间范围内的传感器记录列表
        """
        result = await self.session.execute(
            select(SensorData)
            .where(SensorData.timestamp >= start, SensorData.timestamp <= end)
            .order_by(SensorData.timestamp)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest(self, limit: int = 100) -> list[SensorData]:
        """获取最新的传感器记录"""
        result = await self.session.execute(
            select(SensorData)
            .order_by(SensorData.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """返回传感器记录总数"""
        result = await self.session.execute(
            select(func.count()).select_from(SensorData)
        )
        return result.scalar_one() or 0
