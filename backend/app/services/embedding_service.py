"""Embedding service: Ollama bge-m3 + vector index for semantic search.

Supports two backends:
- pgvector (default): stores embeddings in knowledge_chunks.embedding column
- faiss: local file index (fallback for SQLite / offline environments)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from app.core.config import Settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 64


class EmbeddingService:
    """Manages embedding generation via Ollama and vector index for semantic search."""

    def __init__(self, settings: Settings, session_factory=None) -> None:
        self._settings = settings
        self._embeddings = None
        backend = getattr(settings, "vector_store_backend", "faiss")
        if backend == "pgvector" and session_factory is not None:
            from app.services.vector_store_adapter import PgvectorAdapter
            self._adapter = PgvectorAdapter(session_factory, settings.embedding_dim)
            self._use_pgvector = True
        else:
            from app.services.vector_store_adapter import FaissAdapter
            self._adapter = FaissAdapter(settings.faiss_index_path, settings.embedding_dim)
            self._use_pgvector = False
        self._lock = asyncio.Lock()

    def _get_embeddings(self):
        if self._embeddings is None:
            from langchain_openai import OpenAIEmbeddings

            self._embeddings = OpenAIEmbeddings(
                model=self._settings.embedding_model,
                openai_api_base=f"{self._settings.ollama_base_url}/v1",
                openai_api_key="ollama",
                check_embedding_ctx_length=False,
            )
        return self._embeddings

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        emb = self._get_embeddings()
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            vecs = emb.embed_documents(batch)
            all_vecs.extend(vecs)
        arr = np.array(all_vecs, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms

    async def build_index(self, session: Any) -> int:
        """Full rebuild: embed all published chunks and save index."""
        from sqlalchemy import select
        from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument

        stmt = (
            select(KnowledgeChunk.id, KnowledgeChunk.heading, KnowledgeChunk.content)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == "published")
            .order_by(KnowledgeChunk.id)
        )
        rows = (await session.execute(stmt)).all()
        if not rows:
            logger.warning("No published chunks found, skipping index build")
            if not self._use_pgvector:
                # FAISS: create empty index on disk
                import faiss
                self._adapter._index = faiss.IndexFlatIP(self._settings.embedding_dim)
                self._adapter._chunk_ids = []
                self._adapter.save()
            return 0

        texts = [f"{r.heading or ''} {r.content or ''}".strip() for r in rows]
        chunk_ids = [r.id for r in rows]
        logger.info("Embedding %d chunks...", len(texts))
        vectors = self._embed_texts(texts)

        if not self._use_pgvector:
            # FAISS: reset and rebuild in-memory index
            import faiss
            self._adapter._index = faiss.IndexFlatIP(self._settings.embedding_dim)
            self._adapter._chunk_ids = []

        await self._adapter.add(chunk_ids, vectors.tolist())
        return len(chunk_ids)

    async def add_chunks(self, chunk_ids: list[int], texts: list[str]) -> None:
        """Incrementally add new chunks to the index."""
        if not chunk_ids or not texts:
            return
        async with self._lock:
            vectors = self._embed_texts(texts)
            await self._adapter.add(chunk_ids, vectors.tolist())

    async def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Vector search, returns [(chunk_id, similarity_score), ...]."""
        if not self._use_pgvector:
            # FAISS: ensure index is loaded from disk
            if self._adapter._index is None:
                self._adapter.load()
            if self._adapter.size == 0:
                return []
        emb = self._get_embeddings()
        q_vec = emb.embed_query(query)
        return await self._adapter.search(q_vec, top_k)

    def ensure_loaded(self) -> None:
        """Load index from disk if not already loaded (FAISS only)."""
        if not self._use_pgvector and self._adapter._index is None:
            self._adapter.load()


_instance: EmbeddingService | None = None


def init_embedding_service(settings: Settings, session_factory=None) -> EmbeddingService:
    """Create and cache the global EmbeddingService singleton."""
    global _instance
    _instance = EmbeddingService(settings, session_factory=session_factory)
    if not _instance._use_pgvector:
        _instance.ensure_loaded()
    return _instance


def get_embedding_service() -> EmbeddingService | None:
    """Return the cached singleton, or None if not initialized."""
    return _instance
