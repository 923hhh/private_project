"""Application lifespan handlers."""
from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI

from app.agents.graph import get_diagnosis_graph
from app.db.session import get_engine
from app.services.knowledge_import_worker import KnowledgeImportWorker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown resources."""
    engine = get_engine()
    logger = logging.getLogger("app.lifecycle")
    logger.info("application_started")
    try:
        resumed_job_ids = await KnowledgeImportWorker.resume_pending_jobs()
    except Exception:
        logger.exception("knowledge_import_jobs_resume_failed")
        resumed_job_ids = []
    if resumed_job_ids:
        logger.info("knowledge_import_jobs_resumed count=%s", len(resumed_job_ids))
    try:
        get_diagnosis_graph()
        logger.info("diagnosis_graph_prewarmed")
    except Exception:
        logger.exception("diagnosis_graph_prewarm_failed")

    try:
        from app.core.config import get_settings
        from app.core.database import _get_session_factory
        from app.services.embedding_service import init_embedding_service
        from app.services.bm25_service import init_bm25_service

        settings = get_settings()
        emb_svc = init_embedding_service(settings, session_factory=_get_session_factory())
        if emb_svc._use_pgvector:
            logger.info("embedding_service_loaded backend=pgvector")
        else:
            vec_count = emb_svc._adapter._index.ntotal if emb_svc._adapter._index else 0
            logger.info("embedding_index_loaded backend=faiss vectors=%d", vec_count)
        init_bm25_service(settings)
        logger.info("bm25_index_loaded")
    except Exception:
        logger.warning("search_index_load_skipped (run build_faiss_index to create)")

    yield

    await engine.dispose()
    logger.info("application_stopped")
