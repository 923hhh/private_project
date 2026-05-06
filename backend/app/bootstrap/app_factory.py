"""Central FastAPI application factory."""
from fastapi import FastAPI

from app.bootstrap.exception_handlers import register_exception_handlers
from app.bootstrap.lifespan import lifespan
from app.bootstrap.middleware import register_middlewares
from app.bootstrap.router_registry import register_routers
from app.core.config import get_settings
from app.shared.logging import configure_logging


def create_app() -> FastAPI:
    """Create and assemble the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    register_exception_handlers(app)
    register_middlewares(app, cors_origins=settings.cors_origins)
    register_routers(app)
    return app
