"""Application middleware registration."""
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.metrics import increment_counter, observe_duration
from app.core.request_context import reset_request_id, set_request_id


def _resolve_request_id(request: Request) -> str:
    incoming = (request.headers.get("X-Request-ID") or "").strip()
    if incoming:
        return incoming[:128]
    return f"req-{uuid4().hex[:12]}"


def _resolve_route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def register_middlewares(app: FastAPI, cors_origins: list[str]) -> None:
    """Register CORS and request logging middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log each request with status code and elapsed time."""
        logger = logging.getLogger("app.http")
        started_at = perf_counter()
        request_id = _resolve_request_id(request)
        request.state.request_id = request_id
        context_token = set_request_id(request_id)

        logger.info(
            "request_started method=%s path=%s client=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else "",
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((perf_counter() - started_at) * 1000)
            route_path = _resolve_route_path(request)
            await increment_counter(
                "http_requests_total",
                method=request.method,
                path=route_path,
                status_code="500",
            )
            await observe_duration(
                "http_request_duration_ms",
                duration_ms,
                method=request.method,
                path=route_path,
                status_code="500",
            )
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%s",
                request.method,
                route_path,
                duration_ms,
            )
            raise
        else:
            duration_ms = int((perf_counter() - started_at) * 1000)
            route_path = _resolve_route_path(request)
            await increment_counter(
                "http_requests_total",
                method=request.method,
                path=route_path,
                status_code=response.status_code,
            )
            await observe_duration(
                "http_request_duration_ms",
                duration_ms,
                method=request.method,
                path=route_path,
                status_code=response.status_code,
            )
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed method=%s path=%s status=%s duration_ms=%s",
                request.method,
                route_path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            reset_request_id(context_token)
