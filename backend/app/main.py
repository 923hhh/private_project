"""ASGI entrypoint for the FastAPI application.

本文件保留为唯一对外入口，内部装配逻辑已经迁移到 `app.bootstrap`。
"""
from app.bootstrap import create_app


app = create_app()
