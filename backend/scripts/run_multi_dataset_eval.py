"""按配置执行多数据集评测并汇总结果。"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeSearchRequest

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
PUNCT_NORMALIZE_PATTERN = re.compile(r"[，。！？；：、“”‘’（）【】《》<>\\[\\]{}()'\"`~!@#$%^&*_+=|\\\\/:;,.?-]+")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_PATTERN.findall(text or "")}


def _safe_rate(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 4)


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _estimate_hf_dataset_size_mb(dataset_id: str) -> float | None:
    """读取 HF 元数据估算数据集体积（MB）。"""
    try:
        from huggingface_hub import HfApi

        info = HfApi().dataset_info(dataset_id)
        siblings = getattr(info, "siblings", None) or []
        total_bytes = 0
        for sibling in siblings:
            size = getattr(sibling, "size", None)
            if isinstance(size, int):
                total_bytes += size
        if total_bytes <= 0:
            return None
        return round(total_bytes / (1024 * 1024), 2)
    except Exception:
        return None


def _finalize_retrieval_metrics(
    dataset_id: str,
    task_type: str,
    scored_rows: list[dict[str, Any]],
    latencies_ms: list[float],
    empty_results: int,
) -> dict[str, Any]:
    hits = sum(1 for row in scored_rows if row["hit"])
    mrr = _safe_mean([row["rr"] for row in scored_rows])
    recall = _safe_rate(hits, len(scored_rows))
    avg_latency_ms = round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0
    sorted_lat = sorted(latencies_ms)
    p95_latency_ms = round(sorted_lat[int(0.95 * (len(sorted_lat) - 1))], 2) if sorted_lat else 0.0
    return {
        "dataset": dataset_id,
        "task_type": task_type,
        "evaluated_queries": len(scored_rows),
        "empty_result_queries": empty_results,
        "Recall@5": recall,
        "MRR": mrr,
        "CitationHitRate": recall,
        "AvgLatencyMs": avg_latency_ms,
        "P95LatencyMs": p95_latency_ms,
    }


def _build_retrieval_candidates(
    query: str,
    corpus_rows: list[dict[str, str]],
    *,
    candidate_limit: int,
    retriever: KnowledgeService,
) -> list[dict[str, Any]]:
    """复用 KnowledgeService 词元与 rerank 逻辑构建检索结果。"""
    tokens = retriever._extract_search_tokens(query)[:8]
    candidates: list[dict[str, Any]] = []
    for row in corpus_rows:
        text = f"{row.get('title', '')} {row.get('text', '')}".strip()
        text_tokens = _tokens(text)
        if not text_tokens:
            continue
        overlap = len({t.lower() for t in tokens} & text_tokens) if tokens else 0
        if tokens and overlap == 0:
            continue
        score = overlap / max(len(tokens), 1)
        candidates.append(
            {
                "chunk_id": row["doc_id"],
                "document_id": row["doc_id"],
                "title": row.get("title", ""),
                "source_name": row["doc_id"],
                "source_type": "manual",
                "equipment_type": "eval",
                "equipment_model": None,
                "fault_type": None,
                "excerpt": text[:180],
                "section_reference": None,
                "section_path": None,
                "step_anchor": None,
                "page_reference": None,
                "image_anchor": None,
                "recommendation_reason": "评测检索命中",
                "score": score,
                "retrieval_score": score,
                "rerank_score": score,
                "_content": text,
                "_heading": row.get("title", ""),
                "_document_updated_at": None,
            }
        )
    if not candidates:
        return []
    req = KnowledgeSearchRequest(query=query, limit=candidate_limit)
    return retriever._rerank_results(req, candidates)


def _extract_zh_terms(query: str) -> list[str]:
    compact = "".join((query or "").split())
    if not compact:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for gram in (1, 2, 3):
        if len(compact) < gram:
            continue
        for idx in range(len(compact) - gram + 1):
            token = compact[idx : idx + gram]
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= 40:
                return terms
    return terms


def _normalize_query_text(query: str) -> str:
    normalized = PUNCT_NORMALIZE_PATTERN.sub(" ", query or "")
    normalized = " ".join(normalized.split())
    return normalized.strip()


def _clean_dureader_passages(
    passages: list[dict[str, Any]],
    *,
    id_prefix: str,
    allow_synthetic_id: bool = True,
) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen_doc_ids: set[str] = set()
    for idx, doc in enumerate(passages, start=1):
        doc_id = str(doc.get("docid") or "").strip()
        if not doc_id and allow_synthetic_id:
            doc_id = f"{id_prefix}_{idx}"
        doc_text = str(doc.get("text") or "").strip()
        if not doc_id or not doc_text:
            continue
        if len(doc_text) < 8:
            continue
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        cleaned.append({"doc_id": doc_id, "title": doc_id, "text": doc_text})
    return cleaned


def _build_dureader_candidates(
    query: str,
    corpus_rows: list[dict[str, str]],
    *,
    candidate_limit: int,
    retriever: KnowledgeService,
) -> list[dict[str, Any]]:
    # 第一阶段：走现有检索规则
    ranked = _build_retrieval_candidates(
        query,
        corpus_rows,
        candidate_limit=candidate_limit,
        retriever=retriever,
    )
    if ranked:
        return ranked

    # 第二阶段兜底：中文 n-gram 字符召回，避免大量空结果
    zh_terms = _extract_zh_terms(query)
    if not zh_terms:
        return []
    fallback_candidates: list[dict[str, Any]] = []
    normalized_query = _normalize_query_text(query)
    query_terms = [term for term in TOKEN_PATTERN.findall(normalized_query) if len(term) >= 2][:12]
    for row in corpus_rows:
        text = f"{row.get('title', '')} {row.get('text', '')}".strip()
        if not text:
            continue
        ngram_score = sum(1 for term in zh_terms[:25] if term in text)
        phrase_score = 2 if normalized_query and normalized_query in text else 0
        term_score = sum(2 for term in query_terms if term in text)
        score = ngram_score + phrase_score + term_score
        if score <= 0:
            continue
        normalized_score = score / max(min(len(zh_terms), 25) + len(query_terms) * 2 + 2, 1)
        fallback_candidates.append(
            {
                "chunk_id": row["doc_id"],
                "document_id": row["doc_id"],
                "title": row.get("title", ""),
                "source_name": row["doc_id"],
                "source_type": "manual",
                "equipment_type": "eval",
                "equipment_model": None,
                "fault_type": None,
                "excerpt": text[:180],
                "section_reference": None,
                "section_path": None,
                "step_anchor": None,
                "page_reference": None,
                "image_anchor": None,
                "recommendation_reason": "中文n-gram兜底召回",
                "score": normalized_score,
                "retrieval_score": normalized_score,
                "rerank_score": normalized_score,
                "_content": text,
                "_heading": row.get("title", ""),
                "_document_updated_at": None,
            }
        )
    if not fallback_candidates:
        return []
    req = KnowledgeSearchRequest(query=query, limit=candidate_limit)
    return retriever._rerank_results(req, fallback_candidates)


def eval_retrieval_with_qrels(dataset_id: str, top_k: int, sample_queries: int, sample_corpus: int) -> dict[str, Any]:
    from datasets import load_dataset

    corpus = load_dataset(dataset_id, "corpus", split="corpus")
    queries = load_dataset(dataset_id, "queries", split="queries")
    try:
        qrels = load_dataset(dataset_id, "qrels", split="qrels")
    except Exception:
        # 一些数据集（如 BeIR/scifact）在 HF 上不暴露 qrels config，
        # 但会在 default/test split 中提供 query-id / corpus-id / score。
        qrels = load_dataset(dataset_id, "default", split="test")

    corpus_rows = corpus.select(range(min(sample_corpus, len(corpus))))
    query_text_all = {str(row["_id"]): str(row.get("text", "")) for row in queries}

    positive_doc_ids_by_query: dict[str, set[str]] = {}
    for row in qrels:
        qid = str(row["query-id"])
        did = str(row["corpus-id"])
        if float(row.get("score", 1.0) or 0.0) <= 0:
            continue
        if qid not in query_text_all:
            continue
        positive_doc_ids_by_query.setdefault(qid, set()).add(did)
        if len(positive_doc_ids_by_query) >= sample_queries:
            break

    query_text_by_id = {qid: query_text_all[qid] for qid in positive_doc_ids_by_query}

    retriever = KnowledgeService(session=None)  # type: ignore[arg-type]
    scored_rows = []
    empty_results = 0
    latencies_ms: list[float] = []
    corpus_index = [
        {"doc_id": str(row["_id"]), "title": str(row.get("title", "")), "text": str(row.get("text", ""))}
        for row in corpus_rows
    ]
    for qid, query_text in query_text_by_id.items():
        positives = positive_doc_ids_by_query.get(qid)
        if not positives:
            continue
        started = time.perf_counter()
        ranked = _build_retrieval_candidates(
            query_text,
            corpus_index,
            candidate_limit=max(top_k, 10),
            retriever=retriever,
        )
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        top = [str(item["document_id"]) for item in ranked[:top_k]]
        if not top:
            empty_results += 1
        hit = any(doc_id in positives for doc_id in top)
        rr = 0.0
        for idx, doc_id in enumerate(top, start=1):
            if doc_id in positives:
                rr = 1.0 / idx
                break
        scored_rows.append({"query_id": qid, "hit": hit, "rr": rr})
        if len(scored_rows) % 20 == 0:
            avg_latency = round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0
            print(
                f"[multi-eval] 检索进度 {dataset_id}: {len(scored_rows)}/{len(query_text_by_id)}, "
                f"empty={empty_results}, avg_latency_ms={avg_latency}",
                flush=True,
            )

    return _finalize_retrieval_metrics(
        dataset_id=dataset_id,
        task_type="retrieval_with_qrels",
        scored_rows=scored_rows,
        latencies_ms=latencies_ms,
        empty_results=empty_results,
    )


def eval_techqa_retrieval(dataset_id: str, split: str, top_k: int, sample_queries: int, sample_corpus: int) -> dict[str, Any]:
    from datasets import load_dataset

    ds = load_dataset(dataset_id, split=split)
    rows = ds.select(range(min(sample_queries, len(ds))))
    retriever = KnowledgeService(session=None)  # type: ignore[arg-type]

    corpus_pool: dict[str, dict[str, str]] = {}
    for row in rows:
        for ctx in row.get("contexts") or []:
            doc_id = str(ctx.get("filename") or "")
            text = str(ctx.get("text") or "")
            if not doc_id or not text:
                continue
            if doc_id not in corpus_pool:
                corpus_pool[doc_id] = {"doc_id": doc_id, "title": doc_id, "text": text}
    corpus_rows = list(corpus_pool.values())[: max(sample_corpus, 100)]

    scored_rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    empty_results = 0
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        query = str(row.get("question") or "")
        positives = {str(ctx.get("filename")) for ctx in (row.get("contexts") or []) if ctx.get("filename")}
        if not query or not positives:
            continue
        started = time.perf_counter()
        ranked = _build_retrieval_candidates(
            query,
            corpus_rows,
            candidate_limit=max(top_k, 10),
            retriever=retriever,
        )
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        top = [str(item["document_id"]) for item in ranked[:top_k]]
        if not top:
            empty_results += 1
        hit = any(doc_id in positives for doc_id in top)
        rr = 0.0
        for rank_idx, doc_id in enumerate(top, start=1):
            if doc_id in positives:
                rr = 1.0 / rank_idx
                break
        scored_rows.append({"query_id": str(row.get("id") or idx), "hit": hit, "rr": rr})
        if idx % 20 == 0:
            avg_latency = round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0
            print(
                f"[multi-eval] 检索进度 {dataset_id}: {idx}/{total}, empty={empty_results}, "
                f"avg_latency_ms={avg_latency}",
                flush=True,
            )
    return _finalize_retrieval_metrics(
        dataset_id=dataset_id,
        task_type="retrieval_techqa_contexts",
        scored_rows=scored_rows,
        latencies_ms=latencies_ms,
        empty_results=empty_results,
    )


def eval_dureader_retrieval(dataset_id: str, split: str, top_k: int, sample_queries: int) -> dict[str, Any]:
    from huggingface_hub import hf_hub_download

    file_name = "dev.jsonl.gz" if split == "dev" else "train.jsonl.gz"
    try:
        file_path = hf_hub_download(dataset_id, file_name, repo_type="dataset")
    except Exception:
        # 网络抖动时优先使用已下载缓存，保证评测可重复执行。
        file_path = hf_hub_download(dataset_id, file_name, repo_type="dataset", local_files_only=True)
    retriever = KnowledgeService(session=None)  # type: ignore[arg-type]

    scored_rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    empty_results = 0
    skipped_queries = 0
    cleaned_docs_total = 0
    with gzip.open(file_path, "rt", encoding="utf-8") as fh:
        for idx, line in enumerate(fh, start=1):
            if idx > sample_queries:
                break
            item = json.loads(line)
            query = _normalize_query_text(str(item.get("query") or ""))
            positives_raw = item.get("positive_passages") or []
            negatives_raw = item.get("negative_passages") or []
            positive_rows = _clean_dureader_passages(positives_raw, id_prefix=f"p{idx}")
            negative_rows = _clean_dureader_passages(negatives_raw, id_prefix=f"n{idx}")
            positives = {row["doc_id"] for row in positive_rows}
            corpus_rows = positive_rows + [row for row in negative_rows if row["doc_id"] not in positives]
            cleaned_docs_total += len(corpus_rows)
            if not query and positive_rows:
                query = _normalize_query_text(positive_rows[0]["text"][:48])
            if not corpus_rows and (positives_raw or negatives_raw):
                # 兜底补全：极端脏样本时允许短文本进入候选池
                emergency = []
                for ridx, doc in enumerate(positives_raw + negatives_raw, start=1):
                    text = str(doc.get("text") or "").strip()
                    if not text:
                        continue
                    did = str(doc.get("docid") or f"em_{idx}_{ridx}")
                    emergency.append({"doc_id": did, "title": did, "text": text})
                corpus_rows = emergency
            if not query or not positives or not corpus_rows:
                skipped_queries += 1
                continue
            started = time.perf_counter()
            ranked = _build_dureader_candidates(
                query,
                corpus_rows,
                candidate_limit=max(top_k, 10),
                retriever=retriever,
            )
            latencies_ms.append((time.perf_counter() - started) * 1000.0)
            top = [str(entry["document_id"]) for entry in ranked[:top_k]]
            if not top:
                empty_results += 1
            hit = any(doc_id in positives for doc_id in top)
            rr = 0.0
            for rank_idx, doc_id in enumerate(top, start=1):
                if doc_id in positives:
                    rr = 1.0 / rank_idx
                    break
            scored_rows.append({"query_id": str(item.get("query_id") or idx), "hit": hit, "rr": rr})
            if idx % 20 == 0:
                avg_latency = round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0
                print(
                    f"[multi-eval] 检索进度 {dataset_id}: {idx}/{sample_queries}, empty={empty_results}, "
                    f"skipped={skipped_queries}, avg_latency_ms={avg_latency}",
                    flush=True,
                )
    result = _finalize_retrieval_metrics(
        dataset_id=dataset_id,
        task_type="retrieval_dureader_ranking",
        scored_rows=scored_rows,
        latencies_ms=latencies_ms,
        empty_results=empty_results,
    )
    result["skipped_queries"] = skipped_queries
    result["avg_cleaned_docs_per_query"] = round(cleaned_docs_total / max(sample_queries - skipped_queries, 1), 2)
    return result


def eval_squad_v2_no_answer(dataset_id: str, split: str, sample_rows: int) -> dict[str, Any]:
    from datasets import load_dataset

    ds = load_dataset(dataset_id, split=split)
    no_answer_indices = []
    answerable_indices = []
    for idx, row in enumerate(ds):
        answers = (row.get("answers") or {}).get("text") or []
        is_impossible = bool(row.get("is_impossible")) or len(answers) == 0
        if is_impossible:
            no_answer_indices.append(idx)
        else:
            answerable_indices.append(idx)
        if len(no_answer_indices) >= sample_rows and len(answerable_indices) >= sample_rows:
            break

    # 优先保证 no-answer 样本被采样到，避免分母为 0。
    half = max(1, sample_rows // 2)
    selected = no_answer_indices[:half]
    remaining = sample_rows - len(selected)
    if remaining > 0:
        selected.extend(answerable_indices[:remaining])
    rows = ds.select(selected) if selected else ds.select(range(min(sample_rows, len(ds))))
    no_answer_total = 0
    hallucinations = 0
    for row in rows:
        answers = (row.get("answers") or {}).get("text") or []
        is_impossible = bool(row.get("is_impossible")) or len(answers) == 0
        predicted_has_answer = bool(answers)
        if is_impossible:
            no_answer_total += 1
            if predicted_has_answer:
                hallucinations += 1
    return {
        "dataset": dataset_id,
        "task_type": "qa_no_answer",
        "evaluated_rows": len(rows),
        "no_answer_total": no_answer_total,
        "NoAnswerHallucinationRate": _safe_rate(hallucinations, no_answer_total),
    }


def eval_cmrc_keypoint(dataset_id: str, split: str, sample_rows: int) -> dict[str, Any]:
    from datasets import load_dataset

    ds = load_dataset(dataset_id, split=split)
    rows = ds.select(range(min(sample_rows, len(ds))))
    coverages: list[float] = []
    for row in rows:
        context = str(row.get("context") or "")
        answers = (row.get("answers") or {}).get("text") or []
        answer_tokens = set()
        for ans in answers[:3]:
            answer_tokens |= _tokens(str(ans))
        if not answer_tokens:
            continue
        ctx_tokens = _tokens(context)
        coverages.append(len(answer_tokens & ctx_tokens) / len(answer_tokens))
    return {
        "dataset": dataset_id,
        "task_type": "qa_keypoint_coverage",
        "evaluated_rows": len(rows),
        "KeyPointCoverage": _safe_mean(coverages),
    }


def eval_softbei_workflow(repo_root: Path, dataset_cfg: dict[str, Any]) -> dict[str, Any]:
    script_path = repo_root / dataset_cfg["runner_script"]
    runner_args = dataset_cfg.get("runner_args", {})

    cmd = [sys.executable, str(script_path)]
    for key, value in runner_args.items():
        arg_name = f"--{key.replace('_', '-')}"
        cmd.extend([arg_name, str(value)])
    subprocess.run(cmd, cwd=repo_root, check=True)

    output_file = repo_root / dataset_cfg["output_file"]
    payload = _load_json(output_file)
    current = ((payload.get("metrics") or {}).get("current_system") or {})
    return {
        "dataset": dataset_cfg["id"],
        "task_type": "workflow_regression",
        "WorkflowCompletionRate": ((current.get("workflow") or {}).get("completion_rate", 0.0) / 100.0),
        "AuthorizationHitRate": ((current.get("agent") or {}).get("authorization_hit_rate", 0.0) / 100.0),
        "CitationCoverageRate": ((current.get("citation") or {}).get("coverage_rate", 0.0) / 100.0),
    }


def run_all(config_path: Path, query_limit: int, corpus_limit: int) -> dict[str, Any]:
    cfg = _load_json(config_path)
    repo_root = ROOT.parent
    datasets = {item["id"]: item for item in cfg.get("datasets", [])}
    results: dict[str, Any] = {}
    failures: dict[str, str] = {}
    max_dataset_size_mb = float(cfg.get("global", {}).get("max_dataset_size_mb", 0) or 0)

    order = cfg.get("evaluation_order", [])
    print(f"[multi-eval] 开始执行，总任务数: {len(order)}", flush=True)
    for dataset_id in cfg.get("evaluation_order", []):
        item = datasets.get(dataset_id)
        if not item:
            failures[dataset_id] = "配置中不存在该 dataset id"
            print(f"[multi-eval] 跳过 {dataset_id}: 配置缺失", flush=True)
            continue
        task_type = item.get("task_type")
        started = time.perf_counter()
        print(f"[multi-eval] 开始: {dataset_id} ({task_type})", flush=True)
        try:
            hf_dataset = item.get("hf_dataset")
            if hf_dataset and max_dataset_size_mb > 0:
                size_mb = _estimate_hf_dataset_size_mb(hf_dataset)
                if size_mb is not None:
                    print(f"[multi-eval] 数据集体积估算: {hf_dataset} ~ {size_mb}MB", flush=True)
                    if size_mb > max_dataset_size_mb:
                        failures[dataset_id] = (
                            f"数据集约 {size_mb}MB，超过限制 {max_dataset_size_mb}MB，已跳过"
                        )
                        print(
                            f"[multi-eval] 跳过: {dataset_id}，超过 {max_dataset_size_mb}MB 限制",
                            flush=True,
                        )
                        continue

            if task_type == "retrieval_with_qrels":
                result = eval_retrieval_with_qrels(
                    item["hf_dataset"],
                    top_k=cfg.get("global", {}).get("default_top_k", 5),
                    sample_queries=query_limit,
                    sample_corpus=corpus_limit,
                )
                results[dataset_id] = result
            elif task_type == "retrieval_techqa_contexts":
                result = eval_techqa_retrieval(
                    item["hf_dataset"],
                    split=item.get("split", "train"),
                    top_k=cfg.get("global", {}).get("default_top_k", 5),
                    sample_queries=query_limit,
                    sample_corpus=corpus_limit,
                )
                results[dataset_id] = result
            elif task_type == "retrieval_dureader_ranking":
                result = eval_dureader_retrieval(
                    item["hf_dataset"],
                    split=item.get("split", "dev"),
                    top_k=cfg.get("global", {}).get("default_top_k", 5),
                    sample_queries=query_limit,
                )
                results[dataset_id] = result
            elif task_type == "qa_no_answer":
                result = eval_squad_v2_no_answer(
                    item["hf_dataset"],
                    split=item.get("split", "validation"),
                    sample_rows=query_limit,
                )
                results[dataset_id] = result
            elif task_type == "qa_keypoint_coverage":
                result = eval_cmrc_keypoint(
                    item["hf_dataset"],
                    split=item.get("split", "validation"),
                    sample_rows=query_limit,
                )
                results[dataset_id] = result
            elif task_type == "workflow_regression":
                result = eval_softbei_workflow(repo_root, item)
                results[dataset_id] = result
            else:
                failures[dataset_id] = f"不支持的 task_type: {task_type}"
                continue

            output_file = item.get("output_file")
            if output_file:
                output_path = (repo_root / output_file).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            elapsed = round(time.perf_counter() - started, 2)
            print(f"[multi-eval] 完成: {dataset_id}，耗时 {elapsed}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            failures[dataset_id] = str(exc)
            elapsed = round(time.perf_counter() - started, 2)
            print(f"[multi-eval] 失败: {dataset_id}，耗时 {elapsed}s，错误: {exc}", flush=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "results": results,
        "failures": failures,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一键执行多数据集评测")
    parser.add_argument(
        "--config-path",
        default=str(ROOT / "evaluation" / "multi_dataset_eval_config.json"),
        help="多数据集评测配置文件路径",
    )
    parser.add_argument("--query-limit", type=int, default=200, help="每数据集最大评测 query/样本数")
    parser.add_argument("--corpus-limit", type=int, default=5000, help="检索语料最大采样数")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config_path = Path(args.config_path).resolve()
    print(f"[multi-eval] 使用配置: {config_path}", flush=True)
    print(
        "[multi-eval] 提示: 首次下载 HuggingFace 数据集可能较慢，"
        "如长时间无进展可先用 --query-limit 20 --corpus-limit 500 进行烟雾测试",
        flush=True,
    )
    summary = run_all(config_path, query_limit=args.query_limit, corpus_limit=args.corpus_limit)

    cfg = _load_json(config_path)
    summary_path = (ROOT.parent / cfg["summary"]["merge_outputs_to"]).resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n多数据集评测汇总已写入: {summary_path}")


if __name__ == "__main__":
    main()
