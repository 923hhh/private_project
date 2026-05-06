"""Unified application error primitives."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response body returned by the backend."""

    error_code: str
    message: str
    request_id: str
    details: dict[str, Any] | list[Any] | None = None


class AppError(Exception):
    """Business-facing exception with stable error code and status."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details
        self.headers = headers or {}
