"""Corrective RAG: retrieval quality scoring and answer completeness guard."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Minimum cosine-like score threshold for a retrieval result to be "relevant"
_RELEVANCE_THRESHOLD = 0.25
# Minimum number of results to consider retrieval "sufficient"
_MIN_SUFFICIENT_RESULTS = 2


# ---------------------------------------------------------------------------
# Retrieval quality scoring
# ---------------------------------------------------------------------------

def score_retrieval_quality(
    query: str,
    results: list[dict[str, Any]],
) -> str:
    """Return 'relevant' | 'partial' | 'insufficient' based on result quality."""
    if not results:
        return "insufficient"

    high_quality = [r for r in results if (r.get("score") or 0) >= _RELEVANCE_THRESHOLD]

    if len(high_quality) >= _MIN_SUFFICIENT_RESULTS:
        return "relevant"
    if high_quality:
        return "partial"
    return "insufficient"


def should_trigger_corrective_retrieval(quality: str) -> bool:
    return quality in ("partial", "insufficient")


# ---------------------------------------------------------------------------
# Query expansion for corrective retrieval
# ---------------------------------------------------------------------------

_SYNONYM_EXPANSIONS: dict[str, list[str]] = {
    "异响": ["噪音", "杂音", "声音异常"],
    "发动机": ["引擎", "动力总成"],
    "动力下降": ["功率不足", "加速无力", "提速慢"],
    "启动困难": ["打不着火", "冷启动失败", "起动困难"],
    "渗漏": ["漏油", "漏液", "泄漏"],
    "高温": ["过热", "温度偏高", "散热不良"],
    "故障灯": ["报警灯", "警示灯", "MIL灯"],
    "怠速不稳": ["抖动", "怠速抖", "空转不稳"],
}


def expand_query_for_corrective(query: str) -> list[str]:
    """Generate synonym-expanded query variants for a second retrieval pass."""
    variants: list[str] = [query]
    for term, synonyms in _SYNONYM_EXPANSIONS.items():
        if term in query:
            for syn in synonyms:
                variant = query.replace(term, syn)
                if variant not in variants:
                    variants.append(variant)
    # Also try stripping common noise prefixes
    stripped = re.sub(r"^(请问|帮我|我想知道|如何|怎么|为什么)\s*", "", query).strip()
    if stripped and stripped != query and stripped not in variants:
        variants.append(stripped)
    return variants[:4]  # cap at 4 variants


# ---------------------------------------------------------------------------
# Answer completeness check (lightweight, no LLM required)
# ---------------------------------------------------------------------------

_COMPLETENESS_MARKERS = [
    "原因",
    "步骤",
    "方法",
    "建议",
    "注意",
    "检查",
    "处理",
    "解决",
]


def check_answer_completeness(query: str, answer: str) -> bool:
    """Heuristic: answer is complete if it contains at least one action marker."""
    if not answer or len(answer.strip()) < 30:
        return False
    return any(marker in answer for marker in _COMPLETENESS_MARKERS)


# ---------------------------------------------------------------------------
# LLM-based answer revision (optional, graceful degradation)
# ---------------------------------------------------------------------------

async def maybe_revise_answer(
    query: str,
    answer: str,
    knowledge_refs: list[dict[str, Any]],
    settings: Any,
) -> str:
    """
    Ask the LLM to revise an incomplete answer using the provided knowledge refs.
    Returns the original answer if LLM is unavailable or revision fails.
    """
    if not answer or not knowledge_refs:
        return answer

    if check_answer_completeness(query, answer):
        return answer

    context_text = "\n\n".join(
        f"[{i+1}] {ref.get('title', '')}: {ref.get('content', '')[:300]}"
        for i, ref in enumerate(knowledge_refs[:5])
    )

    prompt = (
        f"以下是一个维修知识问答的初步回答，请根据提供的知识参考资料对其进行补充和完善。\n\n"
        f"问题：{query}\n\n"
        f"初步回答：{answer}\n\n"
        f"知识参考资料：\n{context_text}\n\n"
        f"请输出JSON格式：{{\"status\": \"revise\", \"revised_answer\": \"...\"}}\n"
        f"如果初步回答已经足够完整，输出：{{\"status\": \"ok\"}}"
    )

    try:
        from app.agents.diagnosis_agent import create_llm
        llm = create_llm(settings)
        raw = await llm.ainvoke(prompt)
        content = raw.content if hasattr(raw, "content") else str(raw)
        payload = _extract_json(content)
        if payload and payload.get("status") == "revise":
            revised = payload.get("revised_answer", "").strip()
            if revised and len(revised) > len(answer) * 0.5:
                return revised
    except Exception:
        logger.debug("Answer revision LLM call failed, using original answer")

    return answer


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from LLM output, stripping markdown fences."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Answer cleanup
# ---------------------------------------------------------------------------

_TRUNCATED_TAIL_PHRASES = [
    "综上所述，",
    "总的来说，",
    "因此，建议",
    "请注意，",
    "如需进一步",
]


def cleanup_answer(text: str) -> str:
    """Strip known truncated tail phrases and normalize whitespace."""
    if not text:
        return text
    text = text.strip()
    for phrase in _TRUNCATED_TAIL_PHRASES:
        if text.endswith(phrase):
            text = text[: -len(phrase)].rstrip("，,。 ")
    return text
