"""时间序列化（接口文档 ISO8601，东八区展示）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_CN = timezone(timedelta(hours=8))

def utc_now_naive() -> datetime:
    """数据库列为 TIMESTAMP WITHOUT TIME ZONE 时统一写入 naive UTC。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso_cn(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_CN).isoformat()
