"""Reranker service: FlagEmbedding bge-reranker-v2-m3 精排封装。

首次调用时懒加载模型（~2s），后续推理约 100ms/20条。
FlagEmbedding 不可用时自动降级，返回原始候选顺序。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_reranker = None
_reranker_model_name: str | None = None
_reranker_disabled_models: dict[str, str] = {}


def _validate_reranker_compatibility(reranker: Any, model_name: str) -> None:
    """Fail fast on known-incompatible tokenizer/runtime combinations."""
    tokenizer = getattr(reranker, "tokenizer", None)
    if tokenizer is None:
        return
    if hasattr(tokenizer, "prepare_for_model"):
        return

    try:
        import transformers  # type: ignore

        transformers_version = transformers.__version__
    except Exception:
        transformers_version = "unknown"

    raise RuntimeError(
        "Incompatible reranker runtime: "
        f"model={model_name}, tokenizer={tokenizer.__class__.__name__}, "
        f"transformers={transformers_version}. "
        "Tokenizer is missing prepare_for_model()."
    )


def _get_reranker(model_name: str):
    """懒加载 FlagReranker 单例，模型名变化时重新加载。"""
    global _reranker, _reranker_model_name
    disabled_reason = _reranker_disabled_models.get(model_name)
    if disabled_reason is not None:
        logger.debug("reranker already disabled for %s: %s", model_name, disabled_reason)
        return None
    if _reranker is not None and _reranker_model_name == model_name:
        return _reranker
    try:
        from FlagEmbedding import FlagReranker
        _reranker = FlagReranker(model_name, use_fp16=True)
        _validate_reranker_compatibility(_reranker, model_name)
        _reranker_model_name = model_name
        logger.info("FlagReranker loaded: %s", model_name)
    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        _reranker_disabled_models[model_name] = reason
        logger.warning(
            "FlagReranker 加载失败，reranker 将降级为 passthrough: %s",
            reason,
            exc_info=True,
        )
        _reranker = None
        _reranker_model_name = None
    return _reranker


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    model_name: str = "BAAI/bge-reranker-v2-m3",
    top_k: int = 20,
    batch_size: int = 32,
) -> list[dict[str, Any]]:
    """
    对候选结果精排，返回按 rerank_score 降序的列表。

    - 取前 top_k 条送入 reranker（超出部分直接截断）
    - FlagEmbedding 不可用时原样返回 candidates[:top_k]
    - rerank_score 写回每条结果的 "rerank_score" 字段
    """
    if not candidates or not query:
        return candidates

    pool = candidates[:top_k]
    reranker = _get_reranker(model_name)

    if reranker is None:
        return pool

    try:
        texts = [
            f"{item.get('_heading') or item.get('title') or ''} {item.get('_content') or item.get('excerpt') or ''}".strip()
            for item in pool
        ]
        pairs = [[query, t] for t in texts]

        scores: list[float] = []
        for i in range(0, len(pairs), batch_size):
            batch_scores = reranker.compute_score(pairs[i : i + batch_size], normalize=True)
            if isinstance(batch_scores, float):
                scores.append(batch_scores)
            else:
                scores.extend(batch_scores)

        for item, score in zip(pool, scores):
            item["neural_score"] = float(score)
            # 在启发式 rerank_score 基础上叠加神经精排分数（scale=3.0 使量纲对齐）
            heuristic = float(item.get("rerank_score") or item.get("retrieval_score") or 0.0)
            item["rerank_score"] = round(heuristic + float(score) * 3.0, 4)

        pool.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        logger.debug("rerank done: query=%r top1_score=%.4f", query[:30], pool[0].get("rerank_score", 0))
        return pool

    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        _reranker_disabled_models[model_name] = reason
        logger.warning("rerank 推理失败，降级返回原始顺序: %s", reason, exc_info=True)
        return pool
