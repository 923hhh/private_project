"""Offline evaluation dataset and metrics helpers for maintenance RAG."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
STEP_HINTS = ("步骤", "流程", "拆卸", "安装", "检查", "调整")
IMAGE_HINTS = ("图片", "图像", "照片", "看图", "外观", "裂纹", "渗漏")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return path


def write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def tokenize(value: str | None) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(value or "") if token.strip()]


def infer_sample_type(case: dict[str, Any]) -> str:
    query = str(case.get("query") or "")
    if any(hint in query for hint in IMAGE_HINTS):
        return "image"
    if case.get("fault_type") in {"机油渗漏", "照明故障", "尾气异常"}:
        return "image"
    return "text"


def build_reference_contexts(case: dict[str, Any], seed_docs: list[dict[str, Any]]) -> list[str]:
    expected_titles = {normalize_text(item) for item in case.get("expected_titles", []) if item}
    contexts: list[str] = []
    for doc in seed_docs:
        if normalize_text(doc.get("title")) not in expected_titles:
            continue
        contexts.append(
            "\n".join(
                part
                for part in [
                    f"标题：{doc.get('title', '')}",
                    f"章节：{doc.get('section_reference', '')}",
                    f"页码：{doc.get('page_reference', '')}",
                    doc.get("content", ""),
                ]
                if part
            ).strip()
        )
    return contexts


def build_reference_answer(case: dict[str, Any], reference_contexts: list[str]) -> str:
    expected_terms = [str(item).strip() for item in case.get("expected_terms", []) if str(item).strip()]
    resolution_summary = str(case.get("resolution_summary") or "").strip()
    steps = [str(item).strip() for item in case.get("processing_steps") or [] if str(item).strip()]
    sample_type = infer_sample_type(case)

    lines: list[str] = []
    if resolution_summary:
        lines.append(resolution_summary)
    if expected_terms:
        lines.append(f"关键检查项：{'、'.join(expected_terms[:4])}。")
    if sample_type == "procedural" and steps:
        lines.append("建议步骤：")
        lines.extend(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))
    elif sample_type == "image":
        lines.append("需要结合图片可见现象与手册片段共同判断。")
    if not lines and reference_contexts:
        lines.append(reference_contexts[0][:160])
    return "\n".join(lines).strip()


def build_eval_dataset(
    cases: list[dict[str, Any]],
    seed_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        reference_contexts = build_reference_contexts(case, seed_docs)
        base_row = {
            "user_input": case["query"],
            "reference": build_reference_answer(case, reference_contexts),
            "reference_contexts": reference_contexts,
            "metadata": {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "sample_type": infer_sample_type(case),
                "equipment_type": case.get("equipment_type"),
                "equipment_model": case.get("equipment_model"),
                "fault_type": case.get("fault_type"),
                "expected_titles": case.get("expected_titles", []),
                "expected_terms": case.get("expected_terms", []),
                "workflow_expected": bool(case.get("workflow_expected")),
                "feedback_expected": bool(case.get("feedback_expected")),
            },
        }
        rows.append(base_row)
        if case.get("processing_steps"):
            procedural_row = dict(base_row)
            procedural_row["user_input"] = f"针对“{case['query']}”，给出标准检修步骤与注意事项。"
            procedural_row["metadata"] = dict(base_row["metadata"])
            procedural_row["metadata"]["case_id"] = f"{case.get('id')}-PROC"
            procedural_row["metadata"]["sample_type"] = "procedural"
            rows.append(procedural_row)
    return rows


def flatten_dataset_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata") or {}
        flattened.append(
            {
                "user_input": row.get("user_input"),
                "reference": row.get("reference"),
                "reference_context_count": len(row.get("reference_contexts") or []),
                "sample_type": metadata.get("sample_type"),
                "case_id": metadata.get("case_id"),
                "category": metadata.get("category"),
                "equipment_type": metadata.get("equipment_type"),
                "equipment_model": metadata.get("equipment_model"),
                "fault_type": metadata.get("fault_type"),
                "expected_terms": " | ".join(metadata.get("expected_terms") or []),
            }
        )
    return flattened


def compute_offline_scorecard(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    retrieval_hits = sum(1 for item in records if item.get("retrieval_hit"))
    citation_hits = sum(1 for item in records if item.get("citation_hit"))
    grounded_hits = sum(1 for item in records if item.get("grounded"))
    procedure_total = sum(1 for item in records if item.get("sample_type") == "procedural")
    procedure_hits = sum(1 for item in records if item.get("procedural_completeness_ok"))
    reject_total = sum(1 for item in records if item.get("expected_reject"))
    reject_hits = sum(1 for item in records if item.get("reject_ok"))

    return {
        "case_count": total,
        "retrieval": _rate_bucket(retrieval_hits, total),
        "citation": _rate_bucket(citation_hits, total),
        "grounded": _rate_bucket(grounded_hits, total),
        "procedural_completeness": _rate_bucket(procedure_hits, procedure_total),
        "low_confidence_reject": _rate_bucket(reject_hits, reject_total),
        "by_sample_type": _breakdown_by_sample_type(records),
    }


def _rate_bucket(hits: int, total: int) -> dict[str, Any]:
    rate = round((hits / total) * 100, 2) if total else 0.0
    return {"hits": hits, "total": total, "rate": rate}


def _breakdown_by_sample_type(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, int]] = {}
    for item in records:
        sample_type = str(item.get("sample_type") or "unknown")
        bucket = grouped.setdefault(sample_type, {"total": 0, "hit": 0})
        bucket["total"] += 1
        if item.get("retrieval_hit"):
            bucket["hit"] += 1
    return {
        key: {
            "hits": value["hit"],
            "total": value["total"],
            "rate": round((value["hit"] / value["total"]) * 100, 2) if value["total"] else 0.0,
        }
        for key, value in grouped.items()
    }


def result_matches_expectation(result: dict[str, Any], metadata: dict[str, Any]) -> bool:
    haystack = normalize_text(
        " ".join(
            [
                result.get("title", ""),
                result.get("excerpt", ""),
                result.get("recommendation_reason", ""),
                result.get("source_name", ""),
                result.get("expanded_content", ""),
            ]
        )
    )
    expected_titles = [normalize_text(item) for item in metadata.get("expected_titles", []) if item]
    expected_terms = [normalize_text(item) for item in metadata.get("expected_terms", []) if item]
    return any(title in haystack for title in expected_titles) or any(term in haystack for term in expected_terms)


def procedural_completeness_ok(result: dict[str, Any], reference: str) -> bool:
    expanded = str(result.get("expanded_content") or result.get("excerpt") or "")
    reference_steps = [line for line in reference.splitlines() if line[:2].strip(".").isdigit()]
    if not reference_steps:
        return bool(result.get("step_anchor"))
    return sum(1 for step in reference_steps[:3] if step.split(".", 1)[-1].strip()[:6] in expanded) >= min(2, len(reference_steps))
