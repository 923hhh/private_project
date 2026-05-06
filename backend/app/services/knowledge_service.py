"""Compatibility export for the knowledge search service."""
from app.modules.knowledge.application.search_service import KnowledgeService, split_text_into_chunks

__all__ = ["KnowledgeService", "split_text_into_chunks"]
