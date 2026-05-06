"""Compatibility export for diagnosis router."""
from app.modules.diagnosis.router import diagnose, diagnose_stream_get, router

__all__ = ["router", "diagnose", "diagnose_stream_get"]
