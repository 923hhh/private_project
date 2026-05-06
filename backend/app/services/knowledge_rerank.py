"""Deterministic candidate merge and rerank helpers for knowledge retrieval."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.services.knowledge_query_rewrite import analyze_procedural_query, extract_search_tokens

logger = logging.getLogger(__name__)

SAFETY_PRIORITY_TERMS = {
    "安全",
    "隔离",
    "停机",
    "断电",
    "风险",
    "高温",
    "防护",
    "急停",
}
SOURCE_TYPE_RERANK_BONUS = {
    "manual": 0.8,
    "procedure": 0.9,
    "case": 0.4,
}


def merge_candidates(
    keyword_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """RRF (Reciprocal Rank Fusion) merge of keyword and vector results."""
    rrf_k = 60
    rrf: dict[int, float] = {}
    sources: dict[int, list[str]] = {}

    for rank, item in enumerate(keyword_results):
        chunk_id = item["chunk_id"]
        rrf[chunk_id] = rrf.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources.setdefault(chunk_id, []).append("keyword")

    for rank, item in enumerate(vector_results):
        chunk_id = item["chunk_id"]
        rrf[chunk_id] = rrf.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources.setdefault(chunk_id, []).append("vector")

    by_id: dict[int, dict[str, Any]] = {}
    for item in keyword_results:
        by_id[item["chunk_id"]] = item
    for item in vector_results:
        chunk_id = item["chunk_id"]
        if chunk_id not in by_id:
            by_id[chunk_id] = item

    for chunk_id, score in rrf.items():
        if chunk_id not in by_id:
            continue
        by_id[chunk_id]["retrieval_score"] = score
        source_labels = sources.get(chunk_id, [])
        if len(source_labels) > 1:
            by_id[chunk_id]["recommendation_reason"] = "语义检索 + 关键词匹配"
        elif "vector" in source_labels:
            by_id[chunk_id]["recommendation_reason"] = "语义检索命中"

    return sorted(
        by_id.values(),
        key=lambda item: item.get("retrieval_score", 0.0),
        reverse=True,
    )


def rerank_results(
    request: KnowledgeSearchRequest,
    candidates: list[dict[str, Any]],
    *,
    query_profile: Any | None = None,
) -> list[dict[str, Any]]:
    """Apply deterministic rerank + optional neural rerank.

    流程：
    1. 启发式重排（设备型号 / 故障类型 / 来源类型 / token 覆盖 / 时效性）
    2. 若 ENABLE_RERANKER=true 且 FlagEmbedding 可用，再做神经精排
    """
    reranked: list[dict[str, Any]] = []
    for item in candidates:
        final_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
        rerank_reasons: list[str] = []

        model_bonus = compute_equipment_model_bonus(request, item)
        if model_bonus > 0:
            final_score += model_bonus
            if item.get("equipment_model"):
                rerank_reasons.append(f"同型号 {item['equipment_model']}")
            else:
                rerank_reasons.append("当前型号可复用的通用手册")

        fault_bonus = compute_fault_type_bonus(request, item)
        if fault_bonus > 0:
            final_score += fault_bonus
            if request.fault_type and item.get("fault_type") == request.fault_type:
                rerank_reasons.append(f"同故障类型 {request.fault_type}")
            elif item.get("fault_type"):
                rerank_reasons.append(f"故障相近：{item['fault_type']}")

        source_bonus = compute_source_type_bonus(request, item)
        if source_bonus > 0:
            final_score += source_bonus
            if request.maintenance_level == "emergency" and item.get("source_type") in {"manual", "procedure"}:
                rerank_reasons.append("应急场景优先标准作业依据")
            elif request.priority in {"high", "urgent"} and item.get("source_type") in {"manual", "procedure"}:
                rerank_reasons.append("高优工单优先标准手册")

        coverage_bonus, matched_tokens = compute_token_coverage_bonus(request, item)
        if coverage_bonus > 0:
            final_score += coverage_bonus
            rerank_reasons.append(f"覆盖关键词 {', '.join(matched_tokens[:3])}")

        procedural_bonus = compute_procedural_bonus(request, item, query_profile=query_profile)
        if procedural_bonus > 0:
            final_score += procedural_bonus
            if item.get("step_anchor"):
                rerank_reasons.append("命中步骤锚点")
            elif item.get("section_path"):
                rerank_reasons.append("命中步骤章节")

        procedural_penalty = compute_procedural_conflict_penalty(request, item, query_profile=query_profile)
        if procedural_penalty < 0:
            final_score += procedural_penalty
            rerank_reasons.append("与当前操作意图不一致")

        recency_bonus = compute_recency_bonus(item.get("_document_updated_at"))
        if recency_bonus > 0:
            final_score += recency_bonus
            rerank_reasons.append("近期更新")

        item["rerank_score"] = round(final_score, 4)
        item["score"] = item["rerank_score"]
        if rerank_reasons:
            item["recommendation_reason"] = (
                f"{item['recommendation_reason']}，rerank 优先：{'、'.join(rerank_reasons)}"
            )

        item.pop("_content", None)
        item.pop("_heading", None)
        item.pop("_document_updated_at", None)
        reranked.append(item)

    reranked.sort(
        key=lambda entry: (
            float(entry.get("rerank_score") or 0.0),
            float(entry.get("retrieval_score") or 0.0),
            entry["chunk_id"],
        ),
        reverse=True,
    )
    top = reranked[: request.limit]

    # 神经重排：在启发式排序基础上用 FlagReranker 精排
    query = request.query or ""
    if query:
        try:
            from app.core.config import get_settings
            from app.services.rerank_service import rerank as neural_rerank

            settings = get_settings()
            if settings.enable_reranker:
                # 把 _content/_heading 暂时还原供 reranker 使用（已在上面 pop 掉，从 excerpt 补充）
                for item in top:
                    if "_content" not in item:
                        item["_content"] = item.get("excerpt", "")
                    if "_heading" not in item:
                        item["_heading"] = item.get("title", "")
                top = neural_rerank(
                    query,
                    top,
                    model_name=settings.reranker_model,
                    top_k=settings.reranker_top_k,
                    batch_size=settings.reranker_batch_size,
                )
                logger.debug(
                    "neural rerank done: %d results, top score=%.4f",
                    len(top),
                    top[0].get("rerank_score", 0) if top else 0,
                )
        except Exception:
            logger.warning("神经重排失败，保留启发式排序结果", exc_info=True)

    return top


def resolve_candidate_limit(limit: int) -> int:
    """Fetch more candidates than the final limit so rerank has room to work."""
    return min(max(limit * 4, 12), 80)


def compute_equipment_model_bonus(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
) -> float:
    candidate_model = (item.get("equipment_model") or "").strip()
    if not request.equipment_model:
        return 0.0
    if candidate_model and candidate_model.lower() == request.equipment_model.lower():
        return 4.0
    if not candidate_model:
        return 1.2
    return 0.0


def compute_fault_type_bonus(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
) -> float:
    candidate_fault = (item.get("fault_type") or "").strip()
    requested_fault = (request.fault_type or "").strip()
    if not requested_fault or not candidate_fault:
        return 0.0
    if candidate_fault == requested_fault:
        return 3.0
    if requested_fault in candidate_fault or candidate_fault in requested_fault:
        return 1.5
    return 0.0


def compute_source_type_bonus(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
) -> float:
    source_type = item.get("source_type") or ""
    bonus = SOURCE_TYPE_RERANK_BONUS.get(source_type, 0.0)
    if request.maintenance_level == "emergency" and source_type in {"manual", "procedure"}:
        bonus += 1.4
    if request.priority in {"high", "urgent"} and source_type in {"manual", "procedure"}:
        bonus += 0.7
    if contains_safety_terms(item) and request.maintenance_level == "emergency":
        bonus += 1.2
    return bonus


def compute_token_coverage_bonus(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
) -> tuple[float, list[str]]:
    if not request.query:
        return 0.0, []
    tokens = extract_search_tokens(request.query)[:6]
    if not tokens:
        return 0.0, []
    haystack = " ".join(
        part
        for part in [
            item.get("title") or "",
            item.get("_heading") or "",
            item.get("_content") or "",
            item.get("section_reference") or "",
            item.get("section_path") or "",
            item.get("step_anchor") or "",
            item.get("page_reference") or "",
            item.get("image_anchor") or "",
        ]
        if part
    ).lower()
    matched = [token for token in tokens if token.lower() in haystack]
    if not matched:
        return 0.0, []
    return min(len(matched), 4) * 0.45, matched


def compute_recency_bonus(updated_at: datetime | None) -> float:
    if updated_at is None:
        return 0.0
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_days = max((datetime.now(timezone.utc) - updated_at).total_seconds() / 86400.0, 0.0)
    if age_days <= 7:
        return 0.4
    if age_days <= 30:
        return 0.2
    return 0.0


def contains_safety_terms(item: dict[str, Any]) -> bool:
    haystack = " ".join(
        part
        for part in [
            item.get("title") or "",
            item.get("_heading") or "",
            item.get("_content") or "",
            item.get("excerpt") or "",
        ]
        if part
    )
    return any(term in haystack for term in SAFETY_PRIORITY_TERMS)


def compute_procedural_bonus(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
    *,
    query_profile: Any | None = None,
) -> float:
    query = (request.query or "").strip()
    query_type = getattr(query_profile, "query_type", None)
    if not query and query_type != "procedural":
        return 0.0

    procedural_analysis = analyze_procedural_query(query)
    procedural_query = query_type == "procedural" or procedural_analysis.is_procedural
    if not procedural_query:
        return 0.0

    bonus = 0.0
    section_heading_text = " ".join(
        str(part or "")
        for part in (
            item.get("section_reference"),
            item.get("section_path"),
        )
    )
    step_anchor_text = str(item.get("step_anchor") or "")
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
    focus_terms = [
        token for token in extract_search_tokens(query)
        if token not in {"步骤", "流程", "顺序", "操作", "怎么", "如何", "标准"}
    ][:4]
    if item.get("step_anchor"):
        bonus += 1.6
    if item.get("section_path"):
        bonus += 0.7
    if item.get("source_type") == "procedure":
        bonus += 0.8
    if item.get("expanded_content") and any(marker in str(item.get("expanded_content")) for marker in ("1.", "2.", "步骤")):
        bonus += 0.5
    if focus_terms:
        matched_terms = sum(1 for term in focus_terms if term in structural_text)
        bonus += matched_terms * 0.55
    if procedural_analysis.action and procedural_analysis.action in structural_text:
        bonus += 1.2
    if procedural_analysis.action and procedural_analysis.action in narrative_text and procedural_analysis.action not in structural_text:
        bonus += 0.35
    if procedural_analysis.object_terms:
        heading_object_hits = sum(1 for term in procedural_analysis.object_terms if term in section_heading_text)
        step_object_hits = sum(
            1 for term in procedural_analysis.object_terms if term in step_anchor_text and term not in section_heading_text
        )
        narrative_object_hits = sum(
            1 for term in procedural_analysis.object_terms if term in narrative_text and term not in structural_text
        )
        bonus += heading_object_hits * 1.7
        bonus += step_object_hits * 0.7
        bonus += narrative_object_hits * 0.3
    if procedural_analysis.action and procedural_analysis.object_text:
        exact_phrase = f"{procedural_analysis.action}{procedural_analysis.object_text}"
        if exact_phrase in section_heading_text:
            bonus += 4.2
        elif exact_phrase in structural_text:
            bonus += 1.2
    if procedural_analysis.scope == "single_step" and item.get("step_anchor"):
        bonus += 0.9
    return bonus


def compute_procedural_conflict_penalty(
    request: KnowledgeSearchRequest,
    item: dict[str, Any],
    *,
    query_profile: Any | None = None,
) -> float:
    query = (request.query or "").strip()
    query_type = getattr(query_profile, "query_type", None)
    procedural_analysis = analyze_procedural_query(query)
    procedural_query = query_type == "procedural" or procedural_analysis.is_procedural
    if not procedural_query:
        return 0.0

    haystack = " ".join(
        str(part or "")
        for part in (
            item.get("title"),
            item.get("section_reference"),
            item.get("section_path"),
            item.get("step_anchor"),
            item.get("excerpt"),
        )
    )

    penalty = 0.0
    structural_text = " ".join(
        str(part or "")
        for part in (
            item.get("section_reference"),
            item.get("section_path"),
            item.get("step_anchor"),
        )
    )
    section_heading_text = " ".join(
        str(part or "")
        for part in (
            item.get("section_reference"),
            item.get("section_path"),
        )
    )
    if any(term in query for term in ("拆卸", "拆下")) and "安装" in haystack:
        penalty -= 2.8
    if "安装" in query and any(term in haystack for term in ("拆卸", "拆下")):
        penalty -= 2.8
    if any(term in query for term in ("发动机",)) and any(term in haystack for term in ("压缩压力", "火花塞")):
        penalty -= 1.6
    if "发动机" in query and "起动电机" in haystack:
        penalty -= 2.2
    focus_terms = list(procedural_analysis.object_terms) or [
        token for token in extract_search_tokens(query)
        if token not in {"步骤", "流程", "顺序", "操作", "怎么", "如何", "标准"}
    ][:4]
    if focus_terms and not any(term in structural_text for term in focus_terms):
        penalty -= 1.8
    if procedural_analysis.object_text and procedural_analysis.scope == "whole_section":
        if procedural_analysis.object_text not in section_heading_text and procedural_analysis.object_text in structural_text:
            penalty -= 1.6
    if procedural_analysis.action:
        if procedural_analysis.action in {"检查", "安装", "拆卸", "拆下", "更换"}:
            lifecycle_conflicts = {
                "检查": ("安装", "拆卸", "拆下"),
                "安装": ("拆卸", "拆下"),
                "拆卸": ("安装",),
                "拆下": ("安装",),
                "更换": ("安装",),
            }
            for conflict in lifecycle_conflicts.get(procedural_analysis.action, ()):
                if conflict in structural_text and procedural_analysis.action not in structural_text:
                    penalty -= 2.2
                    break
        elif procedural_analysis.scope == "single_step" and item.get("step_anchor") is None:
            penalty -= 0.8
    return penalty
