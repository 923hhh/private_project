"""Per-request context helpers for logs and structured error responses."""
from __future__ import annotations

from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> Token[str]:
    """Bind the current request id to the async context."""
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request id after a request finishes."""
    _request_id_ctx.reset(token)


def get_request_id() -> str:
    """Return the current request id or a fallback placeholder."""
    return _request_id_ctx.get("-")
