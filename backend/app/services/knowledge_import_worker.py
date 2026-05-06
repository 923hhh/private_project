"""In-process background worker for persisted knowledge import jobs."""
from __future__ import annotations

import asyncio
import logging

from app.db.session import get_session_context


logger = logging.getLogger("app.knowledge_import_worker")


class KnowledgeImportWorker:
    """Run queued knowledge imports in the background within the current process."""

    _active_tasks: dict[int, asyncio.Task[None]] = {}

    @classmethod
    def schedule_job(cls, job_id: int) -> None:
        """Schedule one job if it is not already running in this process."""
        existing = cls._active_tasks.get(job_id)
        if existing is not None and not existing.done():
            return

        task = asyncio.create_task(cls._run_job(job_id))
        cls._active_tasks[job_id] = task
        task.add_done_callback(lambda _: cls._active_tasks.pop(job_id, None))

    @classmethod
    async def resume_pending_jobs(cls, limit: int = 20) -> list[int]:
        """Recover pending jobs on startup and schedule them again."""
        from app.modules.knowledge.application.import_service import KnowledgeImportService

        async with get_session_context() as session:
            job_ids = await KnowledgeImportService(session).list_restartable_job_ids(limit=limit)

        for job_id in job_ids:
            cls.schedule_job(job_id)
        return job_ids

    @classmethod
    async def _run_job(cls, job_id: int) -> None:
        """Process one persisted import job with a worker-owned session."""
        from app.modules.knowledge.application.import_service import KnowledgeImportService

        logger.info("knowledge_import_worker_started job_id=%s", job_id)
        try:
            async with get_session_context() as session:
                await KnowledgeImportService(session).process_job(job_id)
        except Exception:
            logger.exception("knowledge_import_worker_failed job_id=%s", job_id)
        else:
            logger.info("knowledge_import_worker_finished job_id=%s", job_id)
