"""Lightweight in-process metrics for debugging and maintenance observability."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

_lock = asyncio.Lock()
_counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}
_durations: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = {}


def _normalize_labels(labels: dict[str, object]) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    for key, value in labels.items():
        if value is None:
            continue
        normalized.append((str(key), str(value)))
    normalized.sort(key=lambda item: item[0])
    return tuple(normalized)


async def increment_counter(name: str, amount: int = 1, **labels: object) -> None:
    """Increase a named counter with optional labels."""
    key = (name, _normalize_labels(labels))
    async with _lock:
        _counters[key] = _counters.get(key, 0) + amount


async def observe_duration(name: str, value_ms: float | int, **labels: object) -> None:
    """Record a duration sample in milliseconds."""
    duration_ms = float(value_ms)
    key = (name, _normalize_labels(labels))
    async with _lock:
        bucket = _durations.setdefault(
            key,
            {
                "count": 0.0,
                "total_ms": 0.0,
                "max_ms": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["total_ms"] += duration_ms
        bucket["max_ms"] = max(bucket["max_ms"], duration_ms)


async def build_metrics_snapshot() -> dict[str, Any]:
    """Return a JSON-serializable metrics snapshot."""
    async with _lock:
        counters = [
            {
                "name": name,
                "labels": dict(labels),
                "value": value,
            }
            for (name, labels), value in sorted(_counters.items(), key=lambda item: item[0][0])
        ]
        durations = [
            {
                "name": name,
                "labels": dict(labels),
                "count": int(bucket["count"]),
                "total_ms": round(bucket["total_ms"], 2),
                "avg_ms": round(bucket["total_ms"] / bucket["count"], 2) if bucket["count"] else 0.0,
                "max_ms": round(bucket["max_ms"], 2),
            }
            for (name, labels), bucket in sorted(_durations.items(), key=lambda item: item[0][0])
        ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counters": counters,
        "durations": durations,
    }


async def reset_metrics() -> None:
    """Clear all in-memory metrics, mainly for tests."""
    async with _lock:
        _counters.clear()
        _durations.clear()
