"""BM25 lexical index for hybrid retrieval (keyword + vector + BM25)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

CJK_PATTERN = re.compile(r"[一-鿿]+")
ASCII_PATTERN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_MISSING_DEPENDENCY_WARNED = False


def tokenize_chinese(text: str) -> list[str]:
    """Simple bigram tokenizer for Chinese + ASCII tokens."""
    tokens: list[str] = []
    for seq in CJK_PATTERN.findall(text):
        for i in range(len(seq) - 1):
            tokens.append(seq[i : i + 2])
        if len(seq) == 1:
            tokens.append(seq)
    for match in ASCII_PATTERN.findall(text.lower()):
        tokens.append(match)
    return tokens


class BM25Service:
    """Manages a BM25 index over knowledge chunks for lexical retrieval."""

    def __init__(self, settings: Settings) -> None:
        self._index_path = Path(settings.faiss_index_path) / "bm25_index.json"
        self._bm25 = None
        self._chunk_ids: list[int] = []
        self._corpus: list[list[str]] = []
        self._enabled = True

    def _load_bm25_class(self):
        global _MISSING_DEPENDENCY_WARNED
        try:
            from rank_bm25 import BM25Okapi

            return BM25Okapi
        except ModuleNotFoundError:
            self._enabled = False
            if not _MISSING_DEPENDENCY_WARNED:
                logger.warning("rank_bm25_not_installed; BM25 retrieval disabled")
                _MISSING_DEPENDENCY_WARNED = True
            return None

    def _load_or_build(self) -> None:
        if not self._enabled:
            return
        if self._index_path.exists():
            self._load_from_disk()
        else:
            logger.info("BM25 index not found, will be empty until build")

    def _load_from_disk(self) -> None:
        try:
            BM25Okapi = self._load_bm25_class()
            if BM25Okapi is None:
                return

            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._chunk_ids = data["chunk_ids"]
            self._corpus = data["corpus"]
            if self._corpus:
                self._bm25 = BM25Okapi(self._corpus)
            logger.info("BM25 index loaded: %d documents", len(self._chunk_ids))
        except Exception:
            logger.warning("BM25 index load failed", exc_info=True)

    def _save_to_disk(self) -> None:
        if not self._enabled:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"chunk_ids": self._chunk_ids, "corpus": self._corpus}
        self._index_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    async def build_index(self, session: Any) -> int:
        BM25Okapi = self._load_bm25_class()
        if BM25Okapi is None:
            return 0
        from sqlalchemy import select
        from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument

        stmt = (
            select(KnowledgeChunk.id, KnowledgeChunk.heading, KnowledgeChunk.content)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == "published")
            .order_by(KnowledgeChunk.id)
        )
        rows = (await session.execute(stmt)).all()
        self._chunk_ids = [r.id for r in rows]
        self._corpus = [tokenize_chinese(f"{r.heading or ''} {r.content or ''}") for r in rows]
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        self._save_to_disk()
        logger.info("BM25 index built: %d documents", len(self._chunk_ids))
        return len(self._chunk_ids)

    async def add_chunks(self, chunk_ids: list[int], texts: list[str]) -> None:
        BM25Okapi = self._load_bm25_class()
        if BM25Okapi is None:
            return

        if not chunk_ids:
            return
        new_tokens = [tokenize_chinese(t) for t in texts]
        self._chunk_ids.extend(chunk_ids)
        self._corpus.extend(new_tokens)
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        self._save_to_disk()

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        if not self._enabled or self._bm25 is None or not self._chunk_ids:
            return []
        tokens = tokenize_chinese(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[tuple[int, float]] = []
        for idx, score in ranked[:top_k]:
            if score <= 0:
                break
            results.append((self._chunk_ids[idx], float(score)))
        return results

    def ensure_loaded(self) -> None:
        if self._enabled and self._bm25 is None:
            self._load_or_build()


_bm25_instance: BM25Service | None = None


def init_bm25_service(settings: Settings) -> BM25Service:
    global _bm25_instance
    _bm25_instance = BM25Service(settings)
    _bm25_instance.ensure_loaded()
    return _bm25_instance


def get_bm25_service() -> BM25Service | None:
    return _bm25_instance
