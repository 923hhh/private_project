"""Knowledge ingestion and retrieval service."""
from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import increment_counter, observe_duration
from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate, KnowledgeSearchRequest
from app.services.image_analysis_service import FaultImageAnalysisService
from app.services.knowledge_answer_guard import build_grounding_assessment
from app.services.knowledge_chunking import split_text_into_chunks
from app.services.knowledge_device_models import ensure_device_model
from app.services.knowledge_document_ingest import prepare_chunk_payloads
from app.services.knowledge_index_sync import refresh_document_indices
from app.services.knowledge_query_profile import (
    build_query_bundle,
    infer_query_profile,
)
from app.services.knowledge_query_rewrite import (
    analyze_procedural_query,
    apply_query_rewrite_rules,
    build_effective_keywords,
    expand_tokens_with_synonyms,
    extract_search_tokens,
)
from app.services.knowledge_rerank import (
    compute_equipment_model_bonus,
    compute_fault_type_bonus,
    compute_recency_bonus,
    compute_source_type_bonus,
    compute_token_coverage_bonus,
    contains_safety_terms,
    merge_candidates,
    rerank_results,
    resolve_candidate_limit,
)
from app.services.knowledge_result_formatting import (
    build_excerpt,
    build_reason,
    serialize_search_row,
)
from app.services.knowledge_retrieval_sql import (
    build_equipment_model_filter,
    build_token_search_expressions,
)


class KnowledgeService:
    """Service layer for knowledge documents and search."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.image_analysis_service = FaultImageAnalysisService()

    async def create_document(
        self,
        data: KnowledgeDocumentCreate,
        chunk_payloads: list[dict[str, str | None]] | None = None,
    ) -> tuple[KnowledgeDocument, int]:
        """Persist a source document and its searchable chunks."""
        document = KnowledgeDocument(
            title=data.title,
            source_name=data.source_name,
            source_type=data.source_type,
            equipment_type=data.equipment_type,
            equipment_model=data.equipment_model,
            fault_type=data.fault_type,
            section_reference=data.section_reference,
            page_reference=data.page_reference,
            content=data.content,
            status="published",
        )
        self.session.add(document)
        await self.session.flush()

        if data.equipment_model:
            await self._ensure_device_model(data)

        chunk_payloads = self._prepare_chunk_payloads(data, chunk_payloads)
        self.session.add_all(
            [
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    heading=chunk_payload["heading"],
                    content=chunk_payload["content"] or "",
                    equipment_type=chunk_payload["equipment_type"] or data.equipment_type,
                    equipment_model=chunk_payload["equipment_model"] or data.equipment_model,
                    fault_type=chunk_payload["fault_type"] or data.fault_type,
                    section_reference=chunk_payload["section_reference"] or data.section_reference,
                    section_path=chunk_payload.get("section_path"),
                    step_anchor=chunk_payload.get("step_anchor"),
                    page_reference=chunk_payload["page_reference"] or data.page_reference,
                    image_anchor=chunk_payload.get("image_anchor"),
                    source_modality=chunk_payload.get("source_modality"),
                    ocr_text=chunk_payload.get("ocr_text"),
                    image_caption=chunk_payload.get("image_caption"),
                    evidence_summary=chunk_payload.get("evidence_summary"),
                )
                for index, chunk_payload in enumerate(chunk_payloads, start=1)
            ]
        )

        await self.session.commit()
        await self.session.refresh(document)

        try:
            if chunk_payloads:
                await refresh_document_indices(self.session, document_id=document.id)
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "index_update_failed doc_id=%s — run build_faiss_index to reconcile",
                document.id,
            )

        return document, len(chunk_payloads)

    async def search_multimodal(self, request: KnowledgeSearchRequest) -> dict[str, Any]:
        """Search knowledge with optional image-derived retrieval hints."""
        started_at = perf_counter()
        image_analysis = None

        # ── 缓存检查（仅对无图片请求缓存，图片 base64 体积大且每次可能不同）──
        from app.services import cache_service as _cache

        _cache_key: str | None = None
        if not request.image_base64:
            _cache_key = _cache.make_cache_key(
                query=request.query,
                equipment_type=request.equipment_type,
                equipment_model=request.equipment_model,
                fault_type=request.fault_type,
                limit=request.limit or 10,
            )
            cached = _cache.get(_cache_key)
            if cached is not None:
                return cached

        if request.image_base64:
            image_analysis = await self.image_analysis_service.analyze(
                image_base64=request.image_base64,
                image_mime_type=request.image_mime_type,
                image_filename=request.image_filename,
                query=request.query,
                equipment_type=request.equipment_type,
                equipment_model=request.equipment_model,
                model_provider=request.model_provider,
                model_name=request.model_name,
            )
        effective_keywords = self._build_effective_keywords(
            query=request.query,
            equipment_model=request.equipment_model,
            fault_type=request.fault_type,
            image_keywords=image_analysis.keywords if image_analysis is not None else None,
        )
        effective_query = " ".join(effective_keywords) if effective_keywords else request.query
        if request.image_base64 and image_analysis is not None and not effective_query:
            effective_query = self.image_analysis_service.merge_query(
                query=request.query,
                analysis=image_analysis,
                equipment_model=request.equipment_model,
            )
        query_bundle = build_query_bundle(
            query=request.query,
            effective_keywords=effective_keywords,
            image_summary=(image_analysis.summary if image_analysis is not None else None),
            equipment_model=request.equipment_model,
        )
        query_profile = infer_query_profile(
            query_bundle=query_bundle,
            has_image=bool(request.image_base64),
        )

        search_request = request.model_copy(update={"query": effective_query})

        try:
            from app.core.config import get_settings
            from app.services.query_rewrite_service import generate_multi_queries

            query_variants = await generate_multi_queries(
                effective_query or request.query or "",
                get_settings(),
            )
        except Exception:
            query_variants = [effective_query or request.query or ""]

        variant_result_sets: list[list[dict[str, Any]]] = []
        retrieval_path = [query_profile.retrieval_path_tag]
        for variant in query_variants:
            variant_req = search_request.model_copy(update={"query": variant})
            variant_results = await self.search(variant_req, query_profile=query_profile)
            if variant_results:
                variant_result_sets.append(variant_results)
        if variant_result_sets:
            results = self._fuse_variant_results(variant_result_sets)
        else:
            results = await self.search(search_request, query_profile=query_profile)
        if results:
            retrieval_path.extend(self._collect_retrieval_channels(results))

        # ── Graph RAG 扩展（1-hop 关联文档）──────────────────────────────────
        try:
            from app.services.graph_rag_service import graph_expand

            seed_ids = [r["chunk_id"] for r in results if "chunk_id" in r]
            graph_extra = await graph_expand(
                self.session,
                seed_ids,
                max_hops=1,
                max_extra_chunks=5,
            )
            if graph_extra:
                existing_ids = {r["chunk_id"] for r in results}
                for extra in graph_extra:
                    if extra["chunk_id"] not in existing_ids:
                        existing_ids.add(extra["chunk_id"])
                        results.append(extra)
                retrieval_path.append("graph_expand")
        except Exception:
            pass  # graph expansion is best-effort

        results = await self._attach_expanded_context(results)
        results = self._assign_citation_labels(results)
        assessment = build_grounding_assessment(
            request_query=request.query,
            query_type=query_profile.query_type,
            results=results,
            image_analysis_used=image_analysis is not None,
        )

        result_status = "hit" if results else "miss"
        await increment_counter(
            "knowledge_search_requests_total",
            has_image=bool(request.image_base64),
            result_status=result_status,
        )
        await observe_duration(
            "knowledge_search_duration_ms",
            (perf_counter() - started_at) * 1000,
            has_image=bool(request.image_base64),
            result_status=result_status,
        )

        payload = {
            "query": request.query,
            "effective_query": effective_query,
            "effective_keywords": effective_keywords,
            "query_type": query_profile.query_type,
            "image_analysis_used": image_analysis is not None,
            "retrieval_path": retrieval_path,
            "answer_confidence": assessment["answer_confidence"],
            "coverage_warnings": assessment["coverage_warnings"],
            "grounded": assessment["grounded"],
            "image_analysis": (
                {
                    "summary": image_analysis.summary,
                    "keywords": image_analysis.keywords,
                    "source": image_analysis.source,
                    "warning": image_analysis.warning,
                }
                if image_analysis is not None
                else None
            ),
            "results": results,
        }
        # ── 写入缓存（仅无图片请求）──────────────────────────────────────────
        if _cache_key is not None:
            _cache.set(_cache_key, payload)
        return payload

    async def search(
        self,
        request: KnowledgeSearchRequest,
        query_profile=None,
    ) -> list[dict[str, Any]]:
        """Search knowledge chunks with metadata filters."""
        query_profile = query_profile or infer_query_profile(
            query_bundle=[request.query or ""],
            has_image=bool(request.image_base64),
        )
        query = (request.query or "").strip()
        if not query and not any([request.equipment_type, request.equipment_model, request.fault_type]):
            return []

        sql_hits = await self._sql_search(request, query)
        vector_hits = await self._vector_search(request, query=query)
        bm25_hits = await self._bm25_search(request, query=query)
        merged = self._fuse_ranked_candidates(
            channels={
                "sql": sql_hits,
                "vector": vector_hits,
                "bm25": bm25_hits,
            },
            query_profile=query_profile,
        )
        reranked = self._rerank_results(request, merged, query_profile=query_profile)
        return await self._refine_procedural_results(
            request,
            reranked,
            query_profile=query_profile,
        )

    async def _sql_search(self, request: KnowledgeSearchRequest, query: str) -> list[dict[str, Any]]:
        dialect_name = self.session.get_bind().dialect.name
        tokens = self._extract_search_tokens(query) if query else []
        candidate_limit = self._resolve_candidate_limit(request.limit)

        if query and dialect_name == "postgresql":
            chunk_search_text = func.concat_ws(
                " ",
                func.coalesce(KnowledgeChunk.heading, ""),
                func.coalesce(KnowledgeChunk.content, ""),
                func.coalesce(KnowledgeChunk.equipment_model, ""),
                func.coalesce(KnowledgeChunk.fault_type, ""),
                func.coalesce(KnowledgeChunk.section_reference, ""),
                func.coalesce(KnowledgeChunk.section_path, ""),
                func.coalesce(KnowledgeChunk.step_anchor, ""),
                func.coalesce(KnowledgeChunk.page_reference, ""),
                func.coalesce(KnowledgeChunk.image_anchor, ""),
                func.coalesce(KnowledgeChunk.ocr_text, ""),
                func.coalesce(KnowledgeChunk.image_caption, ""),
                func.coalesce(KnowledgeChunk.evidence_summary, ""),
            )
            document_search_text = func.concat_ws(
                " ",
                func.coalesce(KnowledgeDocument.title, ""),
                func.coalesce(KnowledgeDocument.source_name, ""),
                func.coalesce(KnowledgeDocument.equipment_model, ""),
                func.coalesce(KnowledgeDocument.fault_type, ""),
            )
            chunk_tsv = func.to_tsvector("simple", chunk_search_text)
            document_tsv = func.to_tsvector("simple", document_search_text)
            ts_query_text = " ".join(tokens) if tokens else query
            ts_query = func.plainto_tsquery("simple", ts_query_text)
            chunk_match = chunk_tsv.bool_op("@@")(ts_query)
            document_match = document_tsv.bool_op("@@")(ts_query)
            token_score_expr, token_match_expr = self._build_token_search_expressions(tokens)
            score_expr = (
                case((chunk_match, func.ts_rank_cd(chunk_tsv, ts_query) * 8.0), else_=0.0)
                + case((document_match, func.ts_rank_cd(document_tsv, ts_query) * 5.0), else_=0.0)
                + token_score_expr
            )
            stmt = (
                select(KnowledgeChunk, KnowledgeDocument, score_expr.label("score"))
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(KnowledgeDocument.status == "published")
                .where(or_(chunk_match, document_match, token_match_expr))
            )
        else:
            score_expr = literal(0.0)
            stmt = (
                select(KnowledgeChunk, KnowledgeDocument, score_expr.label("score"))
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(KnowledgeDocument.status == "published")
            )
            if query:
                score_expr, token_match_expr = self._build_token_search_expressions(tokens)
                stmt = stmt.where(token_match_expr)

        stmt = self._apply_metadata_filters(stmt, request)
        stmt = stmt.order_by(
            score_expr.desc() if query else KnowledgeDocument.updated_at.desc(),
            KnowledgeChunk.chunk_index.asc(),
        )
        rows = (await self.session.execute(stmt.limit(candidate_limit))).all()
        results: list[dict[str, Any]] = []
        for chunk, document, score in rows:
            row = self._serialize_search_row(
                request=request,
                query=query,
                chunk=chunk,
                document=document,
                retrieval_score=score,
            )
            row["_retrieval_channel"] = "sql"
            row["_retrieval_path"] = ["sql"]
            results.append(row)
        return results

    def _serialize_search_row(
        self,
        *,
        request: KnowledgeSearchRequest,
        query: str,
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        retrieval_score: float | None,
    ) -> dict[str, Any]:
        return serialize_search_row(
            request=request,
            query=query,
            chunk=chunk,
            document=document,
            retrieval_score=retrieval_score,
        )

    async def _expand_chunk_context(
        self,
        chunk_id: int,
        document_id: int,
        *,
        section_path: str | None = None,
        section_reference: str | None = None,
        window: int = 1,
    ) -> str:
        """Small-to-big: fetch adjacent chunks from the same section and merge content."""
        stmt = select(
            KnowledgeChunk.id,
            KnowledgeChunk.content,
            KnowledgeChunk.chunk_index,
            KnowledgeChunk.section_path,
            KnowledgeChunk.section_reference,
        ).where(KnowledgeChunk.document_id == document_id)

        normalized_section_path = str(section_path or "").strip()
        normalized_section_reference = str(section_reference or "").strip()
        if normalized_section_path:
            stmt = stmt.where(KnowledgeChunk.section_path == normalized_section_path)
        elif normalized_section_reference:
            stmt = stmt.where(KnowledgeChunk.section_reference == normalized_section_reference)

        stmt = stmt.order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
        rows = (await self.session.execute(stmt)).all()
        ids = [row.id for row in rows]
        contents = {row.id: row.content or "" for row in rows}
        if chunk_id not in ids:
            return contents.get(chunk_id, "")
        idx = ids.index(chunk_id)
        start = max(0, idx - window)
        end = min(len(ids), idx + window + 1)
        return "\n\n".join(contents[ids[i]] for i in range(start, end) if contents.get(ids[i]))

    async def _vector_search(
        self,
        request: KnowledgeSearchRequest,
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        if not query:
            return []
        try:
            from app.services.embedding_service import get_embedding_service

            svc = get_embedding_service()
            if svc is None:
                return []
            hits = await svc.search(query, top_k=request.limit * 3)
            if not hits:
                return []
            chunk_ids = [chunk_id for chunk_id, _ in hits]
            score_map = {chunk_id: score for chunk_id, score in hits}
            stmt = (
                select(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(KnowledgeChunk.id.in_(chunk_ids))
            )
            stmt = self._apply_metadata_filters(stmt, request)
            rows = (await self.session.execute(stmt)).all()
            results: list[dict[str, Any]] = []
            for chunk, document in rows:
                mapped_score = score_map.get(chunk.id, 0.0)
                row = self._serialize_search_row(
                    request=request,
                    query=query,
                    chunk=chunk,
                    document=document,
                    retrieval_score=mapped_score,
                )
                row["_retrieval_channel"] = "vector"
                results.append(row)
            results.sort(
                key=lambda item: (
                    float(item.get("retrieval_score") or 0.0),
                    item["chunk_id"],
                ),
                reverse=True,
            )
            return results
        except Exception:
            import logging

            logging.getLogger(__name__).debug("vector_search failed, falling back", exc_info=True)
            return []

    async def _bm25_search(
        self,
        request: KnowledgeSearchRequest,
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        """BM25 lexical search as a third retrieval channel."""
        if not query:
            return []
        try:
            from app.services.bm25_service import get_bm25_service

            svc = get_bm25_service()
            if svc is None:
                return []
            hits = svc.search(query, top_k=request.limit * 3)
            if not hits:
                return []
            chunk_ids = [chunk_id for chunk_id, _ in hits]
            score_map = {chunk_id: score for chunk_id, score in hits}
            stmt = (
                select(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(KnowledgeChunk.id.in_(chunk_ids))
            )
            stmt = self._apply_metadata_filters(stmt, request)
            rows = (await self.session.execute(stmt)).all()
            results: list[dict[str, Any]] = []
            for chunk, document in rows:
                row = self._serialize_search_row(
                    request=request,
                    query=query,
                    chunk=chunk,
                    document=document,
                    retrieval_score=score_map.get(chunk.id, 0.0),
                )
                row["_retrieval_channel"] = "bm25"
                results.append(row)
            results.sort(
                key=lambda item: (
                    float(item.get("retrieval_score") or 0.0),
                    item["chunk_id"],
                ),
                reverse=True,
            )
            return results
        except Exception:
            return []

    def _apply_metadata_filters(self, stmt: Any, request: KnowledgeSearchRequest) -> Any:
        if request.equipment_type:
            stmt = stmt.where(self._build_equipment_type_filter(request.equipment_type))
        if request.equipment_model:
            stmt = stmt.where(self._build_equipment_model_filter(request.equipment_model))
        if request.fault_type:
            stmt = stmt.where(KnowledgeChunk.fault_type == request.fault_type)
        return stmt

    async def _refine_procedural_results(
        self,
        request: KnowledgeSearchRequest,
        results: list[dict[str, Any]],
        *,
        query_profile: Any | None = None,
    ) -> list[dict[str, Any]]:
        if not results:
            return results
        query_text = (request.query or "").strip()
        procedural_query = (
            getattr(query_profile, "query_type", None) == "procedural"
            or any(marker in query_text for marker in ("步骤", "流程", "顺序", "拆卸", "拆下", "安装", "更换"))
        )
        if not procedural_query:
            return results
        procedural_analysis = analyze_procedural_query(query_text)

        if procedural_analysis.scope == "single_step":
            step_ranked = sorted(
                results,
                key=lambda item: (
                    self._score_procedural_item_match(item, procedural_analysis),
                    float(item.get("rerank_score") or item.get("retrieval_score") or 0.0),
                    item["chunk_id"],
                ),
                reverse=True,
            )
            top_step_score = self._score_procedural_item_match(step_ranked[0], procedural_analysis)
            if top_step_score > 0:
                filtered = [
                    item
                    for item in step_ranked
                    if self._score_procedural_item_match(item, procedural_analysis) >= max(top_step_score - 1.2, 1.0)
                ]
                return filtered[: request.limit]

        ranked_sections = self._rank_procedural_sections(query_text, results)
        if not ranked_sections:
            return results

        best_key, best_items, best_score = ranked_sections[0]
        if not best_key or best_score <= 0:
            return results

        second_score = ranked_sections[1][2] if len(ranked_sections) > 1 else None
        if second_score is not None and best_score < second_score + 2:
            return results

        expanded_section = await self._load_section_siblings(
            request=request,
            section_key=best_key,
            anchor_items=best_items,
        )
        if not expanded_section:
            return results

        if len(expanded_section) >= min(request.limit, 4):
            return expanded_section[: request.limit]

        expanded_ids = {item["chunk_id"] for item in expanded_section}
        remainder = [item for item in results if item["chunk_id"] not in expanded_ids]
        combined = expanded_section + remainder
        return combined[: request.limit]

    def _rank_procedural_sections(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> list[tuple[tuple[int, str, str], list[dict[str, Any]], float]]:
        focus_terms = self._extract_procedural_focus_terms(query)
        procedural_analysis = analyze_procedural_query(query)
        buckets: dict[tuple[int, str, str], list[dict[str, Any]]] = {}

        for item in results[: max(12, len(results))]:
            section_path = str(item.get("section_path") or "").strip()
            section_reference = str(item.get("section_reference") or "").strip()
            section_value = section_path or section_reference
            if not section_value:
                continue
            key = (
                int(item.get("document_id") or 0),
                "section_path" if section_path else "section_reference",
                section_value,
            )
            buckets.setdefault(key, []).append(item)

        ranked: list[tuple[tuple[int, str, str], list[dict[str, Any]], float]] = []
        for key, items in buckets.items():
            score = 0.0
            section_text = " ".join(
                str(part or "")
                for part in (
                    key[2],
                    items[0].get("title"),
                    items[0].get("excerpt"),
                )
            )
            for term in focus_terms:
                if term and term in section_text:
                    score += 4.0
            if procedural_analysis.action and procedural_analysis.action in key[2]:
                score += 4.5
            if procedural_analysis.object_terms:
                score += sum(2.8 for term in procedural_analysis.object_terms if term in key[2])
            if any(term in query for term in ("拆卸", "拆下")) and "安装" in section_text:
                score -= 6.0
            if procedural_analysis.action == "检查" and "安装" in section_text and "检查" not in key[2]:
                score -= 4.2
            if procedural_analysis.action in {"拆卸", "拆下"} and "检查" in key[2] and not any(
                term in key[2] for term in procedural_analysis.object_terms
            ):
                score -= 2.2
            if "装配部件清单" in section_text:
                score -= 8.0
            if any(term in section_text for term in ("步骤", "流程", "顺序", "拆卸", "拆下")):
                score += 3.5
            if any(term in query for term in ("发动机",)) and "发动机" in section_text:
                score += 3.0
            score += max(float(item.get("rerank_score") or item.get("retrieval_score") or 0.0) for item in items)
            score += max(len(items) - 1, 0) * 0.8
            ranked.append((key, items, score))

        ranked.sort(key=lambda entry: entry[2], reverse=True)
        return ranked

    async def _load_section_siblings(
        self,
        *,
        request: KnowledgeSearchRequest,
        section_key: tuple[int, str, str],
        anchor_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        document_id, field_name, field_value = section_key
        if not document_id or not field_value:
            return []

        field = KnowledgeChunk.section_path if field_name == "section_path" else KnowledgeChunk.section_reference
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeChunk.document_id == document_id)
            .where(field == field_value)
            .where(KnowledgeDocument.status == "published")
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return []

        anchor_by_chunk_id = {int(item["chunk_id"]): item for item in anchor_items if item.get("chunk_id") is not None}
        lead_score = max(float(item.get("rerank_score") or item.get("retrieval_score") or 0.0) for item in anchor_items)

        section_results: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            chunk, document = row[0], row[1]
            serialized = self._serialize_search_row(
                request=request,
                query=(request.query or "").strip(),
                chunk=chunk,
                document=document,
                retrieval_score=max(lead_score - index * 0.01, 0.0),
            )
            existing = anchor_by_chunk_id.get(int(chunk.id))
            if existing is not None:
                serialized["retrieval_score"] = existing.get("retrieval_score")
                serialized["rerank_score"] = existing.get("rerank_score")
                serialized["score"] = existing.get("score") or existing.get("rerank_score")
                serialized["recommendation_reason"] = existing.get("recommendation_reason") or serialized["recommendation_reason"]
            else:
                serialized["rerank_score"] = round(max(lead_score - index * 0.01, 0.0), 4)
                serialized["score"] = serialized["rerank_score"]
                serialized["recommendation_reason"] = f"{serialized['recommendation_reason']}，同章节步骤展开"
            serialized["_retrieval_channel"] = "section_expand"
            serialized["_retrieval_path"] = list(existing.get("_retrieval_path") or []) if existing else ["section_expand"]
            if "section_expand" not in serialized["_retrieval_path"]:
                serialized["_retrieval_path"].append("section_expand")
            section_results.append(serialized)
        return section_results

    def _extract_procedural_focus_terms(self, query: str) -> list[str]:
        procedural_analysis = analyze_procedural_query(query)
        if procedural_analysis.focus_terms:
            return list(procedural_analysis.focus_terms)
        focus_terms = self._extract_search_tokens(query)
        preferred: list[str] = []
        for term in focus_terms:
            if term in {"步骤", "流程", "顺序", "操作"}:
                continue
            preferred.append(term)
        return preferred[:6]

    def _score_procedural_item_match(
        self,
        item: dict[str, Any],
        procedural_analysis,
    ) -> float:
        if not getattr(procedural_analysis, "is_procedural", False):
            return 0.0
        structural_text = " ".join(
            str(part or "")
            for part in (
                item.get("section_reference"),
                item.get("section_path"),
                item.get("step_anchor"),
            )
        )
        narrative_text = " ".join(
            str(part or "")
            for part in (
                item.get("title"),
                item.get("excerpt"),
                item.get("expanded_content"),
            )
        )
        score = 0.0
        if procedural_analysis.action:
            if procedural_analysis.action in structural_text:
                score += 3.4
            elif procedural_analysis.action in narrative_text:
                score += 1.0
        for term in procedural_analysis.object_terms:
            if term in structural_text:
                score += 2.3
            elif term in narrative_text:
                score += 0.7
        if procedural_analysis.scope == "single_step" and item.get("step_anchor"):
            score += 1.4
        return score

    def _build_equipment_type_filter(self, equipment_type: str) -> Any:
        candidates = self._expand_equipment_type_candidates(equipment_type)
        clauses = []
        for candidate in candidates:
            like_value = f"%{candidate}%"
            clauses.extend(
                [
                    KnowledgeChunk.equipment_type == candidate,
                    KnowledgeDocument.equipment_type == candidate,
                    KnowledgeChunk.equipment_type.ilike(like_value),
                    KnowledgeDocument.equipment_type.ilike(like_value),
                    KnowledgeDocument.title.ilike(like_value),
                    KnowledgeDocument.source_name.ilike(like_value),
                ]
            )
        return or_(*clauses)

    def _expand_equipment_type_candidates(self, equipment_type: str) -> list[str]:
        normalized = equipment_type.strip()
        if not normalized:
            return []
        candidates = [normalized]
        for suffix in ("发动机", "设备", "系统", "总成"):
            if normalized.endswith(suffix):
                trimmed = normalized[: -len(suffix)].strip()
                if trimmed:
                    candidates.append(trimmed)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(item)
        return deduped

    def _fuse_ranked_candidates(
        self,
        *,
        channels: dict[str, list[dict[str, Any]]],
        query_profile: Any,
    ) -> list[dict[str, Any]]:
        weights = {"sql": 1.0, "vector": 0.9, "bm25": 0.75}
        fused: dict[int, dict[str, Any]] = {}
        for channel_name, items in channels.items():
            for rank, item in enumerate(items):
                chunk_id = item["chunk_id"]
                fused_score = weights.get(channel_name, 0.7) / (60 + rank + 1)
                candidate = fused.setdefault(chunk_id, dict(item))
                candidate["_raw_scores"] = list(candidate.get("_raw_scores") or [])
                candidate["_raw_scores"].append(float(item.get("retrieval_score") or 0.0))
                candidate["_fusion_score"] = float(candidate.get("_fusion_score") or 0.0) + fused_score
                candidate["retrieval_score"] = candidate["_fusion_score"]
                candidate["score"] = candidate["retrieval_score"]
                candidate["rerank_score"] = candidate["retrieval_score"]
                path = list(candidate.get("_retrieval_path") or [])
                if channel_name not in path:
                    path.append(channel_name)
                candidate["_retrieval_path"] = path
                if "_retrieval_channel" not in candidate:
                    candidate["_retrieval_channel"] = channel_name
                if float(item.get("retrieval_score") or 0.0) > float(candidate.get("_best_raw_score") or float("-inf")):
                    candidate["_best_raw_score"] = float(item.get("retrieval_score") or 0.0)
                    for field in (
                        "excerpt",
                        "expanded_content",
                        "recommendation_reason",
                        "_content",
                        "_heading",
                    ):
                        if item.get(field) is not None:
                            candidate[field] = item.get(field)
        for candidate in fused.values():
            self._apply_query_profile_bonus(candidate, query_profile)
        ranked = sorted(
            fused.values(),
            key=lambda item: (
                float(item.get("retrieval_score") or 0.0),
                float(item.get("_best_raw_score") or 0.0),
                item["chunk_id"],
            ),
            reverse=True,
        )
        return ranked

    def _apply_query_profile_bonus(self, candidate: dict[str, Any], query_profile: Any) -> None:
        modality = candidate.get("source_modality") or "text"
        bonus = 0.0
        modality_bonus = getattr(query_profile, "modality_bonus", {}) or {}
        bonus += float(modality_bonus.get(modality, 0.0))
        if candidate.get("step_anchor"):
            bonus += float(getattr(query_profile, "step_anchor_bonus", 0.0) or 0.0)
        if candidate.get("section_path"):
            bonus += float(getattr(query_profile, "section_path_bonus", 0.0) or 0.0)
        source_type_bonus = getattr(query_profile, "source_type_bonus", {}) or {}
        bonus += float(source_type_bonus.get(candidate.get("source_type") or "", 0.0))
        if bonus:
            candidate["retrieval_score"] = float(candidate.get("retrieval_score") or 0.0) + bonus
            candidate["score"] = candidate["retrieval_score"]
            candidate["rerank_score"] = candidate["retrieval_score"]

    def _fuse_variant_results(
        self,
        variant_result_sets: list[list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        fused: dict[int, dict[str, Any]] = {}
        rrf_k = 20
        for variant_index, items in enumerate(variant_result_sets):
            variant_weight = 1.0 if variant_index == 0 else 0.92
            for rank, item in enumerate(items):
                chunk_id = item["chunk_id"]
                rank_score = variant_weight / (rrf_k + rank + 1)
                candidate = fused.setdefault(chunk_id, dict(item))
                existing_path = list(candidate.get("_retrieval_path") or [])
                candidate["_variant_fusion_score"] = float(candidate.get("_variant_fusion_score") or 0.0) + rank_score
                candidate["_variant_hits"] = int(candidate.get("_variant_hits") or 0) + 1
                if float(item.get("rerank_score") or item.get("score") or 0.0) > float(
                    candidate.get("rerank_score") or candidate.get("score") or 0.0
                ):
                    for key, value in item.items():
                        candidate[key] = value
                path = existing_path or list(candidate.get("_retrieval_path") or [])
                for channel in item.get("_retrieval_path") or []:
                    if channel not in path:
                        path.append(channel)
                candidate["_retrieval_path"] = path

        ranked = sorted(
            fused.values(),
            key=lambda item: (
                float(item.get("_variant_fusion_score") or 0.0),
                int(item.get("_variant_hits") or 0),
                float(item.get("rerank_score") or item.get("score") or 0.0),
                float(item.get("retrieval_score") or 0.0),
                item["chunk_id"],
            ),
            reverse=True,
        )
        return ranked

    async def _attach_expanded_context(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in results:
            expanded = await self._expand_chunk_context(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                section_path=item.get("section_path"),
                section_reference=item.get("section_reference"),
                window=1,
            )
            source_modality = item.get("source_modality") or self._infer_source_modality(item)
            enriched_item = dict(item)
            enriched_item["source_modality"] = source_modality
            enriched_item["expanded_content"] = expanded or item.get("_content")
            if not enriched_item.get("ocr_text") and source_modality in {"ocr", "vision", "image"}:
                enriched_item["ocr_text"] = item.get("_content")
            enriched.append(enriched_item)
        return enriched

    def _assign_citation_labels(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        labeled: list[dict[str, Any]] = []
        for index, item in enumerate(results, start=1):
            labeled_item = dict(item)
            labeled_item["citation_label"] = f"C{index}"
            labeled.append(labeled_item)
        return labeled

    def _infer_source_modality(self, item: dict[str, Any]) -> str:
        image_anchor = (item.get("image_anchor") or "").strip().lower()
        source_name = (item.get("source_name") or "").strip().lower()
        if image_anchor or source_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return "ocr"
        return "text"

    def _collect_retrieval_channels(self, results: list[dict[str, Any]]) -> list[str]:
        channels: list[str] = []
        for item in results:
            for channel in item.get("_retrieval_path") or []:
                if channel not in channels:
                    channels.append(channel)
        return channels

    def _merge_candidates(
        self,
        keyword_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return merge_candidates(keyword_results, vector_results)

    def _rerank_results(
        self,
        request: KnowledgeSearchRequest,
        candidates: list[dict[str, Any]],
        *,
        query_profile: Any | None = None,
    ) -> list[dict[str, Any]]:
        return rerank_results(request, candidates, query_profile=query_profile)

    def _resolve_candidate_limit(self, limit: int) -> int:
        return resolve_candidate_limit(limit)

    def _compute_equipment_model_bonus(
        self,
        request: KnowledgeSearchRequest,
        item: dict[str, Any],
    ) -> float:
        return compute_equipment_model_bonus(request, item)

    def _compute_fault_type_bonus(
        self,
        request: KnowledgeSearchRequest,
        item: dict[str, Any],
    ) -> float:
        return compute_fault_type_bonus(request, item)

    def _compute_source_type_bonus(
        self,
        request: KnowledgeSearchRequest,
        item: dict[str, Any],
    ) -> float:
        return compute_source_type_bonus(request, item)

    def _compute_token_coverage_bonus(
        self,
        request: KnowledgeSearchRequest,
        item: dict[str, Any],
    ) -> tuple[float, list[str]]:
        return compute_token_coverage_bonus(request, item)

    def _compute_recency_bonus(self, updated_at: Any) -> float:
        return compute_recency_bonus(updated_at)

    def _contains_safety_terms(self, item: dict[str, Any]) -> bool:
        return contains_safety_terms(item)

    async def _ensure_device_model(self, data: KnowledgeDocumentCreate) -> None:
        await ensure_device_model(self.session, data)

    def _build_excerpt(self, content: str, query: str) -> str:
        return build_excerpt(content, query)

    def _build_reason(
        self,
        request: KnowledgeSearchRequest,
        document: KnowledgeDocument,
        chunk: KnowledgeChunk,
    ) -> str:
        return build_reason(request, document, chunk)

    def _build_effective_keywords(
        self,
        query: str | None,
        equipment_model: str | None,
        fault_type: str | None,
        image_keywords: list[str] | None = None,
    ) -> list[str]:
        """Build a deterministic rewritten keyword set for retrieval and UI display."""
        return build_effective_keywords(
            query=query,
            equipment_model=equipment_model,
            fault_type=fault_type,
            image_keywords=image_keywords,
        )

    def _extract_search_tokens(self, query: str) -> list[str]:
        """Extract deterministic retrieval tokens for Chinese/English maintenance queries."""
        return extract_search_tokens(query)

    def _expand_tokens_with_synonyms(self, query: str, tokens: list[str]) -> list[str]:
        """Expand extracted tokens with deterministic maintenance-domain synonyms."""
        return expand_tokens_with_synonyms(query, tokens)

    def _apply_query_rewrite_rules(self, query: str, tokens: list[str]) -> list[str]:
        """Inject canonical maintenance terms when a known symptom pattern appears."""
        return apply_query_rewrite_rules(query, tokens)

    def _build_equipment_model_filter(self, equipment_model: str) -> Any:
        return build_equipment_model_filter(equipment_model)

    def _build_token_search_expressions(self, tokens: list[str]) -> tuple[Any, Any]:
        return build_token_search_expressions(tokens)

    def _prepare_chunk_payloads(
        self,
        data: KnowledgeDocumentCreate,
        chunk_payloads: list[dict[str, str | None]] | None = None,
    ) -> list[dict[str, str | None]]:
        return prepare_chunk_payloads(data, chunk_payloads)


__all__ = ["KnowledgeService", "split_text_into_chunks"]
