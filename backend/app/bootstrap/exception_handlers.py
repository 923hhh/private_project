"""Global exception handlers for structured API errors."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import AppError, ErrorResponse
from app.core.request_context import get_request_id
from app.modules.maintenance.errors import MaintenanceAPIError

logger = logging.getLogger("app.errors")


def _default_error_code(status_code: int) -> str:
    mapping = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        422: "validation_error",
        status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_server_error",
    }
    return mapping.get(status_code, f"http_{status_code}")


def _build_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        request_id=request_id,
        details=details,
    ).model_dump(exclude_none=True)
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers=response_headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for structured errors."""

    @app.exception_handler(MaintenanceAPIError)
    async def handle_maintenance_error(
        request: Request,
        exc: MaintenanceAPIError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        logger.warning(
            "maintenance_error method=%s path=%s status=%s business_code=%s message=%s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.business_code,
            exc.message,
        )
        payload: dict[str, Any] = {
            "success": False,
            "business_code": exc.business_code,
            "message": exc.message,
        }
        if exc.errors is not None:
            payload["errors"] = exc.errors
        if exc.data is not None:
            payload["data"] = exc.data
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(payload),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        logger.warning(
            "app_error method=%s path=%s status=%s error_code=%s message=%s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.error_code,
            exc.message,
        )
        return _build_response(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            request_id=request_id,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        logger.warning(
            "validation_error method=%s path=%s error_count=%s",
            request.method,
            request.url.path,
            len(exc.errors()),
        )
        return _build_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code="validation_error",
            message="请求参数校验失败。",
            request_id=request_id,
            details=exc.errors(),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        error_code = _default_error_code(exc.status_code)
        message = "请求处理失败。"
        details: dict[str, Any] | list[Any] | None = None

        if isinstance(exc.detail, dict):
            error_code = exc.detail.get("error_code") or error_code
            message = exc.detail.get("message") or exc.detail.get("detail") or message
            details = exc.detail.get("details")
        elif isinstance(exc.detail, str):
            message = exc.detail
        elif exc.detail is not None:
            details = exc.detail

        logger.warning(
            "http_error method=%s path=%s status=%s error_code=%s",
            request.method,
            request.url.path,
            exc.status_code,
            error_code,
        )
        return _build_response(
            status_code=exc.status_code,
            error_code=error_code,
            message=message,
            request_id=request_id,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        logger.exception(
            "unhandled_exception method=%s path=%s exception=%s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
        )
        return _build_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_server_error",
            message="服务内部处理失败，请稍后重试。",
            request_id=request_id,
        )
