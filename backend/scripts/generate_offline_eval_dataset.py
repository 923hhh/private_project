"""Generate offline evaluation datasets under backend/evaluation.

Usage:
    python scripts/generate_offline_eval_dataset.py
    python scripts/generate_offline_eval_dataset.py --with-ragas
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evaluation.offline_eval import (
    build_eval_dataset,
    flatten_dataset_rows,
    load_json,
    write_csv,
    write_json,
    write_jsonl,
)


DEFAULT_CONFIG_PATH = ROOT / "evaluation" / "offline_eval_config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate offline maintenance RAG eval datasets.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--with-ragas", action="store_true", help="Try optional RAGAS synthetic augmentation.")
    parser.add_argument("--ragas-size", type=int, default=None, help="Override optional RAGAS testset size.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config.resolve())
    output_dir = resolve_backend_path(str(config["output_dir"]))

    source_cases = load_json(resolve_backend_path(str(config["source_cases_path"])))
    seed_docs = load_json(resolve_backend_path(str(config["seed_documents_path"])))
    rows = build_eval_dataset(source_cases, seed_docs)

    dataset_prefix = str(config.get("dataset_prefix") or "maintenance_rag")
    jsonl_path = output_dir / f"{dataset_prefix}_testset.jsonl"
    csv_path = output_dir / f"{dataset_prefix}_testset.csv"
    summary_path = output_dir / f"{dataset_prefix}_testset_summary.json"

    write_jsonl(jsonl_path, rows)
    write_csv(csv_path, flatten_dataset_rows(rows))

    summary: dict[str, Any] = {
        "config_path": str(args.config.resolve()),
        "dataset_prefix": dataset_prefix,
        "case_count": len(rows),
        "sample_types": sorted({row["metadata"]["sample_type"] for row in rows}),
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path),
        "ragas_requested": bool(args.with_ragas),
        "ragas_generated": False,
    }

    if args.with_ragas:
        ragas_payload = try_generate_ragas_rows(
            seed_docs=seed_docs,
            output_dir=output_dir,
            dataset_prefix=dataset_prefix,
            testset_size=args.ragas_size or int((config.get("ragas") or {}).get("testset_size") or 12),
        )
        summary.update(ragas_payload)

    write_json(summary_path, summary)
    print(f"[offline-eval] jsonl => {jsonl_path}")
    print(f"[offline-eval] csv   => {csv_path}")
    print(f"[offline-eval] meta  => {summary_path}")
    if summary.get("ragas_generated"):
        print(f"[offline-eval] ragas => {summary['ragas_jsonl_path']}")
    return 0


def resolve_backend_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if raw_path.startswith("backend/"):
        return (ROOT.parent / raw_path).resolve()
    return (ROOT / raw_path).resolve()


def try_generate_ragas_rows(
    *,
    seed_docs: list[dict[str, Any]],
    output_dir: Path,
    dataset_prefix: str,
    testset_size: int,
) -> dict[str, Any]:
    try:
        from ragas.testset import TestsetGenerator
        from langchain_core.documents import Document
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    except Exception as exc:
        return {
            "ragas_generated": False,
            "ragas_error": f"ragas unavailable: {exc}",
        }

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "ragas_generated": False,
            "ragas_error": "OPENAI_API_KEY 未配置，跳过 RAGAS 合成。",
        }

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        model="gpt-4o-mini",
        temperature=0.0,
    )
    embeddings = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        model="text-embedding-3-small",
    )
    docs = [
        Document(
            page_content=str(item.get("content") or ""),
            metadata={
                "title": item.get("title"),
                "equipment_type": item.get("equipment_type"),
                "equipment_model": item.get("equipment_model"),
                "fault_type": item.get("fault_type"),
            },
        )
        for item in seed_docs
        if str(item.get("content") or "").strip()
    ]
    if not docs:
        return {"ragas_generated": False, "ragas_error": "无可用于 RAGAS 的 seed 文档。"}

    generator = TestsetGenerator.from_langchain(llm=llm, embedding_model=embeddings)
    testset = generator.generate_with_langchain_docs(
        docs,
        testset_size=testset_size,
        with_debugging_logs=False,
        raise_exceptions=True,
    )
    ragas_jsonl_path = output_dir / f"{dataset_prefix}_ragas_testset.jsonl"
    ragas_csv_path = output_dir / f"{dataset_prefix}_ragas_testset.csv"
    testset.to_jsonl(str(ragas_jsonl_path))
    testset.to_csv(str(ragas_csv_path))
    return {
        "ragas_generated": True,
        "ragas_testset_size": testset_size,
        "ragas_jsonl_path": str(ragas_jsonl_path),
        "ragas_csv_path": str(ragas_csv_path),
    }


if __name__ == "__main__":
    raise SystemExit(main())
