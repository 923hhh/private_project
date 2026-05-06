"""LLM-based query rewriting for improved retrieval coverage.

Generates multiple query variants from a single user query, preserving
temporal constraints and domain-specific terms.
"""
from __future__ import annotations

import logging
import re

from app.core.config import Settings

logger = logging.getLogger(__name__)

_TEMPORAL_PATTERN = re.compile(r"(最新|当前|目前|今年|本年|最近|\d{4}年|\d{4}-\d{2})")

_MULTI_QUERY_SYSTEM = (
    "你是工业检修知识系统的检索查询规划器。"
    "围绕同一个检修问题，生成若干条适合检索的短查询。"
    "必须保留设备型号、故障类型、部件名称等专有名词。"
    "如果原问题包含时间约束（最新/当前/今年等），每条查询都必须保留这些词。"
    "不要回答问题，不要解释，不要编号，每行只输出一条查询。"
)

_MULTI_QUERY_HUMAN = "当前问题：\n{query}\n\n请输出 {n} 条不同角度的检索查询："


def _should_skip_rewrite(query: str) -> bool:
    """Skip rewrite for very short queries or pure code/number queries."""
    stripped = query.strip()
    if len(stripped) <= 4:
        return True
    if re.fullmatch(r"[A-Z0-9\-_/]+", stripped):
        return True
    return False


async def generate_multi_queries(
    query: str,
    settings: Settings,
    n: int = 3,
) -> list[str]:
    """Generate n query variants via LLM. Returns [original] on failure."""
    if _should_skip_rewrite(query):
        return [query]
    try:
        from app.agents.diagnosis_agent import create_llm

        llm = create_llm("openai")
        if llm is None:
            return [query]

        prompt = _MULTI_QUERY_HUMAN.format(query=query, n=n)
        response = await llm.ainvoke([
            ("system", _MULTI_QUERY_SYSTEM),
            ("human", prompt),
        ])
        text = response.content if hasattr(response, "content") else str(response)
        variants = [line.strip() for line in text.strip().splitlines() if line.strip()]

        # Ensure temporal terms are preserved in all variants
        temporal_matches = _TEMPORAL_PATTERN.findall(query)
        if temporal_matches:
            filtered = []
            for v in variants:
                if all(t in v for t in temporal_matches):
                    filtered.append(v)
                else:
                    filtered.append(f"{v} {' '.join(temporal_matches)}")
            variants = filtered

        # Always include original query
        all_queries = [query] + [v for v in variants if v != query]
        return all_queries[:n + 1]
    except Exception:
        logger.debug("query_rewrite_failed, using original", exc_info=True)
        return [query]
