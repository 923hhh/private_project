"""Vector store adapter: ABC + FAISS implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseVectorStoreAdapter(ABC):
    """Abstract interface for vector store backends."""

    @abstractmethod
    async def add(self, chunk_ids: list[int], vectors: list[list[float]]) -> None:
        """Add pre-computed vectors for the given chunk IDs."""

    @abstractmethod
    async def search(self, vector: list[float], top_k: int) -> list[tuple[int, float]]:
        """Return [(chunk_id, score), ...] for the nearest top_k vectors."""

    @abstractmethod
    def load(self) -> None:
        """Load index from persistent storage."""

    @abstractmethod
    def save(self) -> None:
        """Persist index to storage."""

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of vectors currently indexed."""


class FaissAdapter(BaseVectorStoreAdapter):
    """FAISS IndexFlatIP adapter (inner-product / cosine on normalised vectors)."""

    def __init__(self, index_dir: str, dim: int) -> None:
        import json
        from pathlib import Path

        self._dir = Path(index_dir)
        self._dim = dim
        self._index: Any = None
        self._chunk_ids: list[int] = []
        self._meta_path = self._dir / "meta.json"
        self._index_path = self._dir / "index.faiss"
        self._json = json

    # ------------------------------------------------------------------
    def load(self) -> None:
        import faiss

        if self._index_path.exists() and self._meta_path.exists():
            self._index = faiss.read_index(str(self._index_path))
            self._chunk_ids = self._json.loads(self._meta_path.read_text(encoding="utf-8"))
        else:
            self._index = faiss.IndexFlatIP(self._dim)
            self._chunk_ids = []

    def save(self) -> None:
        import faiss

        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        self._meta_path.write_text(
            self._json.dumps(self._chunk_ids), encoding="utf-8"
        )

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index is not None else 0

    # ------------------------------------------------------------------
    async def add(self, chunk_ids: list[int], vectors: list[list[float]]) -> None:
        import numpy as np

        if self._index is None:
            self.load()
        arr = np.array(vectors, dtype=np.float32)
        self._index.add(arr)  # caller is responsible for normalisation
        self._chunk_ids.extend(chunk_ids)
        self.save()

    async def search(self, vector: list[float], top_k: int) -> list[tuple[int, float]]:
        import numpy as np

        if self._index is None:
            self.load()
        if self._index.ntotal == 0:
            return []
        q = np.array([vector], dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q /= norm
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(q, k)
        results: list[tuple[int, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._chunk_ids):
                results.append((self._chunk_ids[idx], float(score)))
        return results


class PgvectorAdapter(BaseVectorStoreAdapter):
    """pgvector adapter — stores embeddings in knowledge_chunks.embedding column.

    Uses raw SQL via text() to avoid pgvector SQLAlchemy type dependency at import time.
    Requires PostgreSQL with the pgvector extension enabled.
    """

    def __init__(self, session_factory: Any, dim: int) -> None:
        self._session_factory = session_factory  # async_sessionmaker
        self._dim = dim

    def load(self) -> None:
        pass  # no-op: data lives in DB

    def save(self) -> None:
        pass  # no-op: DB handles persistence

    @property
    def size(self) -> int:
        return -1  # unknown without a COUNT query

    async def add(self, chunk_ids: list[int], vectors: list[list[float]]) -> None:
        """Write embeddings back to knowledge_chunks rows via UPDATE."""
        from sqlalchemy import text

        async with self._session_factory() as session:
            for chunk_id, vec in zip(chunk_ids, vectors):
                # pgvector accepts '[x,y,...]' string cast to vector
                await session.execute(
                    text(
                        "UPDATE knowledge_chunks "
                        "SET embedding = CAST(:vec AS vector) "
                        "WHERE id = :id"
                    ),
                    {"vec": str(vec), "id": chunk_id},
                )
            await session.commit()

    async def search(self, vector: list[float], top_k: int) -> list[tuple[int, float]]:
        """Cosine similarity search via pgvector <=> operator."""
        from sqlalchemy import text

        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, "
                        "1 - (embedding <=> CAST(:vec AS vector)) AS score "
                        "FROM knowledge_chunks "
                        "WHERE embedding IS NOT NULL "
                        "ORDER BY embedding <=> CAST(:vec AS vector) "
                        "LIMIT :k"
                    ),
                    {"vec": str(vector), "k": top_k},
                )
            ).all()
        return [(row.id, float(row.score)) for row in rows]
