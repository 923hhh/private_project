"""Lightweight in-memory TTL cache for knowledge search results.

Uses ``cachetools.TTLCache`` (LRU eviction + time-to-live).  The cache is
process-local and intentionally simple — no Redis, no persistence.  It is
designed for the demo / development scenario where the same query is repeated
several times within a short window.

Configuration (via environment variables / Settings):
    ENABLE_SEARCH_CACHE   bool   default True
    SEARCH_CACHE_TTL      int    seconds, default 300 (5 min)
    SEARCH_CACHE_MAXSIZE  int    max entries, default 1000
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

try:
    from cachetools import TTLCache as CachetoolsTTLCache
except ModuleNotFoundError:  # pragma: no cover - runtime fallback
    CachetoolsTTLCache = None

logger = logging.getLogger(__name__)


class FallbackTTLCache:
    """Minimal TTL cache fallback used when cachetools is unavailable."""

    def __init__(self, *, maxsize: int, ttl: int):
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired_keys = [key for key, (expires_at, _) in self._data.items() if expires_at <= now]
        for key in expired_keys:
            self._data.pop(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        self._purge_expired()
        item = self._data.get(key)
        if item is None:
            return default
        expires_at, value = item
        if expires_at <= time.monotonic():
            self._data.pop(key, None)
            return default
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._purge_expired()
        if key not in self._data and len(self._data) >= self.maxsize:
            oldest_key = next(iter(self._data))
            self._data.pop(oldest_key, None)
        self._data[key] = (time.monotonic() + self.ttl, value)

    def pop(self, key: str, default: Any = None) -> Any:
        self._purge_expired()
        item = self._data.pop(key, None)
        if item is None:
            return default
        return item[1]

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._data)


# ── 单例缓存实例（模块级，进程内共享）────────────────────────────────────────
_cache: Any | None = None


def _get_cache() -> Any:
    global _cache
    if _cache is None:
        try:
            from app.core.config import get_settings

            s = get_settings()
            maxsize = getattr(s, "search_cache_maxsize", 1000)
            ttl = getattr(s, "search_cache_ttl", 300)
        except Exception:
            maxsize, ttl = 1000, 300
        if CachetoolsTTLCache is not None:
            _cache = CachetoolsTTLCache(maxsize=maxsize, ttl=ttl)
            logger.info("SearchCache 初始化: backend=cachetools maxsize=%d ttl=%ds", maxsize, ttl)
        else:
            _cache = FallbackTTLCache(maxsize=maxsize, ttl=ttl)
            logger.warning("SearchCache 初始化降级: backend=fallback maxsize=%d ttl=%ds", maxsize, ttl)
    return _cache


# ── 公开接口 ─────────────────────────────────────────────────────────────────

def make_cache_key(
    query: str | None,
    equipment_type: str | None = None,
    equipment_model: str | None = None,
    fault_type: str | None = None,
    limit: int = 10,
) -> str:
    """Deterministic cache key from search parameters."""
    raw = json.dumps(
        {
            "q": (query or "").strip().lower(),
            "et": equipment_type or "",
            "em": equipment_model or "",
            "ft": fault_type or "",
            "lim": limit,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "search:" + hashlib.md5(raw.encode()).hexdigest()


def get(key: str) -> Any | None:
    """Return cached value or *None* on miss / disabled."""
    try:
        from app.core.config import get_settings

        if not getattr(get_settings(), "enable_search_cache", True):
            return None
    except Exception:
        pass
    cache = _get_cache()
    value = cache.get(key)
    if value is not None:
        logger.debug("cache_hit key=%s", key)
    return value


def set(key: str, value: Any) -> None:  # noqa: A001
    """Store *value* under *key*.  Silently skips if cache is disabled."""
    try:
        from app.core.config import get_settings

        if not getattr(get_settings(), "enable_search_cache", True):
            return
    except Exception:
        pass
    _get_cache()[key] = value
    logger.debug("cache_set key=%s", key)


def invalidate(key: str) -> None:
    """Remove a single key (no-op if absent)."""
    cache = _get_cache()
    cache.pop(key, None)


def clear() -> None:
    """Flush the entire cache (e.g. after bulk document import)."""
    _get_cache().clear()
    logger.info("SearchCache cleared")


def stats() -> dict[str, int]:
    """Return current cache occupancy for monitoring."""
    cache = _get_cache()
    return {"size": len(cache), "maxsize": cache.maxsize}
