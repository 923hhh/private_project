"""Build FAISS index from all published knowledge chunks.

Usage:
    cd backend && python -m scripts.build_faiss_index
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.session import get_session_context
from app.services.embedding_service import EmbeddingService


async def main() -> None:
    settings = get_settings()
    from app.services.bm25_service import BM25Service

    async with get_session_context() as session:
        faiss_svc = EmbeddingService(settings)
        faiss_count = await faiss_svc.build_index(session)
        bm25_svc = BM25Service(settings)
        bm25_count = await bm25_svc.build_index(session)

    print(f"Done. FAISS: {faiss_count} chunks, BM25: {bm25_count} chunks → {settings.faiss_index_path}")


if __name__ == "__main__":
    asyncio.run(main())
