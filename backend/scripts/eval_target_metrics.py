"""评测指定指标：Recall@5、MRR、关键点覆盖、引用命中、无答案乱编率、平均延迟。"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import sys
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_softbei_eval import create_eval_client, load_json, seed_documents
from run_softbei_eval import result_matches_case, normalize_text

CASES_PATH = ROOT / "evaluation" / "softbei_eval_cases.json"
SEED_PATH = ROOT / "evaluation" / "softbei_knowledge_seed.json"


def _match_item(item: dict[str, Any], case: dict[str, Any]) -> bool:
    return result_matches_case([item], case)


def _keypoint_coverage(case: dict[str, Any], results: list[dict[str, Any]]) -> float:
    key_points = [str(x).strip() for x in case.get("expected_terms", []) if str(x).strip()]
    if not key_points:
        return 0.0
    haystack = normalize_text(
        " ".join(
            " ".join(
                [
                    item.get("title", ""),
                    item.get("excerpt", ""),
                    item.get("recommendation_reason", ""),
                    item.get("source_name", ""),
                ]
            )
            for item in results[:5]
        )
    )
    hits = sum(1 for kp in key_points if normalize_text(kp) in haystack)
    return hits / len(key_points)


async def run() -> dict[str, Any]:
    seed = load_json(SEED_PATH)
    cases = load_json(CASES_PATH)
    client: AsyncClient
    client, _session_factory, engine = await create_eval_client("target_metrics_eval")
    try:
        await seed_documents(client, seed)

        recall_hits = 0
        mrr_sum = 0.0
        key_cov_sum = 0.0
        key_cov_count = 0
        citation_hits = 0
        citation_total = 0
        no_answer_total = 0
        hallucination_total = 0
        latencies_ms: list[float] = []

        for case in cases:
            payload = {
                "query": case["query"],
                "equipment_type": case["equipment_type"],
                "equipment_model": case.get("equipment_model"),
                "fault_type": case.get("fault_type"),
                "limit": 5,
            }
            t0 = time.perf_counter()
            resp = await client.post("/api/v1/knowledge/search", json=payload)
            latency = (time.perf_counter() - t0) * 1000
            latencies_ms.append(latency)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            is_has_answer = bool(case.get("expected_titles")) or case.get("category") != "failure"
            hit = result_matches_case(results[:5], case)
            if hit:
                recall_hits += 1

            rank = 0
            for idx, item in enumerate(results[:5], start=1):
                if _match_item(item, case):
                    rank = idx
                    break
            if rank > 0:
                mrr_sum += 1.0 / rank

            if is_has_answer:
                key_cov_sum += _keypoint_coverage(case, results)
                key_cov_count += 1

                citation_total += 1
                top = results[0] if results else {}
                citation_ok = bool(top.get("source_name")) and bool(
                    top.get("section_reference") or top.get("page_reference") or top.get("step_anchor")
                )
                if citation_ok:
                    citation_hits += 1
            else:
                no_answer_total += 1
                # 无答案场景若仍返回匹配结果，视为乱编风险。
                if hit:
                    hallucination_total += 1

        n = len(cases)
        avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
        p95_latency = sorted(latencies_ms)[int(0.95 * (len(latencies_ms) - 1))] if latencies_ms else 0.0
        return {
            "case_count": n,
            "Recall@5": round(recall_hits / n, 4) if n else 0.0,
            "MRR": round(mrr_sum / n, 4) if n else 0.0,
            "关键点覆盖率": round(key_cov_sum / key_cov_count, 4) if key_cov_count else 0.0,
            "引用命中率": round(citation_hits / citation_total, 4) if citation_total else 0.0,
            "无答案题乱编率": round(hallucination_total / no_answer_total, 4) if no_answer_total else 0.0,
            "平均响应时间(ms)": round(avg_latency, 2),
            "P95延迟(ms)": round(p95_latency, 2),
            "no_answer_total": no_answer_total,
        }
    finally:
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
