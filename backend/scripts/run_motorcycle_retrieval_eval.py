"""Run batch retrieval evaluation for the motorcycle engine validation CSV.

Usage:
    venv\\Scripts\\python.exe scripts/run_motorcycle_retrieval_eval.py
    venv\\Scripts\\python.exe scripts/run_motorcycle_retrieval_eval.py --top-k 3
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_session
from app.evaluation.offline_eval import normalize_text, write_csv, write_json
from app.integrations.pdf_import import PdfKnowledgeImportService
from app.main import app as fastapi_app
from app.modules.knowledge.application.search_service import KnowledgeService
from app.modules.knowledge.schemas.search import KnowledgeDocumentCreate

import app.db.models as app_models  # noqa: F401


DEFAULT_DATASET_PATH = ROOT.parent / "datasets" / "validation" / "motorcycle_engine_retrieval_eval.csv"
DEFAULT_PDF_PATH = ROOT.parent / "datasets" / "pdf" / "摩托车发动机维修手册.pdf"
DEFAULT_OUTPUT_DIR = ROOT / "evaluation" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量运行摩托车发动机知识检索验证集")
    parser.add_argument("--dataset-csv", type=Path, default=DEFAULT_DATASET_PATH, help="验证集 CSV 路径")
    parser.add_argument("--pdf-path", type=Path, default=DEFAULT_PDF_PATH, help="待导入的发动机维修手册 PDF")
    parser.add_argument("--top-k", type=int, default=5, help="每次检索返回结果数量，默认 5")
    parser.add_argument(
        "--failure-confidence-threshold",
        type=float,
        default=0.55,
        help="failure 样例判定通过的置信度阈值，默认 0.55",
    )
    parser.add_argument(
        "--output-prefix",
        default="motorcycle_engine_eval",
        help="输出文件名前缀，默认 motorcycle_engine_eval",
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = []
        for row in reader:
            image_path = (row.get("image_path") or "").strip() or None
            rows.append(
                {
                    "case_id": row["case_id"].strip(),
                    "category": row["category"].strip(),
                    "modality": row["modality"].strip(),
                    "query": row["query"].strip(),
                    "image_path": image_path,
                    "equipment_type": row["equipment_type"].strip() or None,
                    "equipment_model": row["equipment_model"].strip() or None,
                    "fault_type": row["fault_type"].strip() or None,
                    "expected_section_reference": row["expected_section_reference"].strip() or None,
                    "expected_page_reference": row["expected_page_reference"].strip() or None,
                    "expected_terms": [
                        item.strip()
                        for item in (row["expected_terms"] or "").split("|")
                        if item.strip()
                    ],
                    "expected_behavior": row["expected_behavior"].strip(),
                    "notes": row["notes"].strip(),
                }
            )
        return rows


def resolve_case_image_path(dataset_path: Path, raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    repo_relative = (ROOT.parent / path).resolve()
    if repo_relative.exists():
        return repo_relative
    return (dataset_path.parent / path).resolve()


def encode_image_payload(image_path: Path) -> tuple[str, str, str]:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    resolved_mime = mime_type or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return encoded, resolved_mime, image_path.name


async def create_eval_client(db_name: str) -> tuple[AsyncClient, async_sessionmaker[AsyncSession], Any]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False, "uri": True},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    client = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://motorcycle-eval")
    return client, session_factory, engine


async def seed_pdf_manual(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    pdf_path: Path,
    equipment_type: str,
    equipment_model: str | None,
) -> dict[str, Any]:
    importer = PdfKnowledgeImportService()
    pages = importer.extract_pages(pdf_path)
    chunk_payloads = importer.build_chunk_payloads(
        title=pdf_path.stem,
        pages=pages,
        max_chars=320,
    )
    request = KnowledgeDocumentCreate(
        title=pdf_path.stem,
        source_name=pdf_path.name,
        source_type="manual",
        equipment_type=equipment_type,
        equipment_model=equipment_model,
        fault_type=None,
        section_reference=f"P1-P{pages[-1].page_number}",
        page_reference=f"P1-P{pages[-1].page_number}",
        content=importer.build_document_content(pages),
    )

    async with session_factory() as session:
        service = KnowledgeService(session)
        document, chunk_count = await service.create_document(request, chunk_payloads=chunk_payloads)

    return {
        "document_id": document.id,
        "title": document.title,
        "page_count": len(pages),
        "chunk_count": chunk_count,
    }


def build_search_payload(case: dict[str, Any], top_k: int) -> dict[str, Any]:
    equipment_model = case.get("equipment_model")
    if normalize_text(equipment_model) in {"", "通用", "generic"}:
        equipment_model = None
    payload = {
        "query": case["query"],
        "equipment_type": case.get("equipment_type"),
        "equipment_model": equipment_model,
        "limit": top_k,
    }
    image_path = case.get("_resolved_image_path")
    if image_path:
        image_base64, image_mime_type, image_filename = encode_image_payload(image_path)
        payload["image_base64"] = image_base64
        payload["image_mime_type"] = image_mime_type
        payload["image_filename"] = image_filename
    return payload


def result_matches_case(result: dict[str, Any], case: dict[str, Any]) -> bool:
    haystack = normalize_text(
        " ".join(
            [
                result.get("title", ""),
                result.get("excerpt", ""),
                result.get("expanded_content", ""),
                result.get("recommendation_reason", ""),
                result.get("section_reference", ""),
                result.get("page_reference", ""),
            ]
        )
    )
    expected_section = normalize_text(case.get("expected_section_reference"))
    expected_page = normalize_text(case.get("expected_page_reference"))
    expected_terms = [normalize_text(item) for item in case.get("expected_terms", []) if item]

    section_match = bool(expected_section and expected_section in haystack)
    page_match = bool(expected_page and expected_page in haystack)
    term_hits = sum(1 for term in expected_terms if term and term in haystack)
    term_match = term_hits >= max(1, min(2, len(expected_terms)))

    return section_match or page_match or term_match


def evaluate_failure_case(data: dict[str, Any], *, threshold: float) -> tuple[bool, str]:
    confidence = float(data.get("answer_confidence") or 0.0)
    grounded = bool(data.get("grounded"))
    warnings = data.get("coverage_warnings") or []
    total = int(data.get("total") or 0)

    if total == 0:
        return True, "无结果返回"
    if not grounded:
        return True, "grounded=False"
    if warnings:
        return True, "存在 coverage_warnings"
    if confidence <= threshold:
        return True, f"answer_confidence={confidence:.2f} <= {threshold:.2f}"
    return False, f"answer_confidence={confidence:.2f} 偏高"


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    positive_records = [item for item in records if item["category"] != "failure"]
    failure_records = [item for item in records if item["category"] == "failure"]

    def bucket(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
        hits = sum(1 for row in rows if row.get(key))
        total = len(rows)
        rate = round((hits / total) * 100, 2) if total else 0.0
        return {"hits": hits, "total": total, "rate": rate}

    return {
        "case_count": len(records),
        "positive_case_count": len(positive_records),
        "failure_case_count": len(failure_records),
        "top1_hit": bucket(positive_records, "top1_hit"),
        "top3_hit": bucket(positive_records, "top3_hit"),
        "top5_hit": bucket(positive_records, "top5_hit"),
        "failure_boundary_ok": bucket(failure_records, "passed"),
        "overall_pass": bucket(records, "passed"),
    }


async def run_cases(
    client: AsyncClient,
    cases: list[dict[str, Any]],
    *,
    top_k: int,
    failure_confidence_threshold: float,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in cases:
        payload = build_search_payload(case, top_k=top_k)
        response = await client.post("/api/v1/knowledge/search", json=payload)
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []

        top1_hit = bool(results[:1] and result_matches_case(results[0], case)) if case["category"] != "failure" else False
        top3_hit = any(result_matches_case(item, case) for item in results[:3]) if case["category"] != "failure" else False
        top5_hit = any(result_matches_case(item, case) for item in results[:5]) if case["category"] != "failure" else False

        failure_ok = False
        failure_reason = ""
        if case["category"] == "failure":
            failure_ok, failure_reason = evaluate_failure_case(
                data,
                threshold=failure_confidence_threshold,
            )

        top_result = results[0] if results else None
        passed = failure_ok if case["category"] == "failure" else top3_hit
        records.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "modality": case.get("modality"),
                "query": case["query"],
                "image_path": str(case.get("_resolved_image_path") or ""),
                "expected_section_reference": case.get("expected_section_reference"),
                "expected_page_reference": case.get("expected_page_reference"),
                "expected_terms": " | ".join(case.get("expected_terms") or []),
                "result_total": int(data.get("total") or 0),
                "grounded": bool(data.get("grounded")),
                "image_analysis_used": bool(data.get("image_analysis_used")),
                "image_analysis_source": (
                    (data.get("image_analysis") or {}).get("source")
                    if data.get("image_analysis")
                    else None
                ),
                "effective_query": data.get("effective_query"),
                "answer_confidence": float(data.get("answer_confidence") or 0.0),
                "retrieval_path": " | ".join(data.get("retrieval_path") or []),
                "coverage_warnings": " | ".join(data.get("coverage_warnings") or []),
                "top1_hit": top1_hit,
                "top3_hit": top3_hit,
                "top5_hit": top5_hit,
                "passed": passed,
                "failure_reason": failure_reason,
                "top_title": top_result.get("title") if top_result else None,
                "top_section_reference": top_result.get("section_reference") if top_result else None,
                "top_page_reference": top_result.get("page_reference") if top_result else None,
                "top_excerpt": (top_result.get("excerpt") or "")[:240] if top_result else None,
            }
        )
    return records


async def main_async() -> int:
    args = parse_args()
    dataset_path = args.dataset_csv.resolve()
    pdf_path = args.pdf_path.resolve()
    if not dataset_path.exists():
        print(f"验证集不存在: {dataset_path}", file=sys.stderr)
        return 1
    if not pdf_path.exists():
        print(f"PDF 文件不存在: {pdf_path}", file=sys.stderr)
        return 1

    cases = load_cases(dataset_path)
    if not cases:
        print("验证集为空。", file=sys.stderr)
        return 1
    for case in cases:
        resolved_image_path = resolve_case_image_path(dataset_path, case.get("image_path"))
        if resolved_image_path and not resolved_image_path.exists():
            print(f"样例图片不存在: {resolved_image_path}", file=sys.stderr)
            return 1
        case["_resolved_image_path"] = resolved_image_path

    client, session_factory, engine = await create_eval_client("motorcycle-retrieval-eval")
    try:
        seed_meta = await seed_pdf_manual(
            session_factory,
            pdf_path=pdf_path,
            equipment_type=str(cases[0].get("equipment_type") or "摩托车发动机"),
            equipment_model=str(cases[0].get("equipment_model") or "通用"),
        )
        records = await run_cases(
            client,
            cases,
            top_k=args.top_k,
            failure_confidence_threshold=float(args.failure_confidence_threshold),
        )
        summary = summarize(records)

        output_dir = DEFAULT_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{args.output_prefix}.json"
        csv_path = output_dir / f"{args.output_prefix}.csv"

        report = {
            "dataset_path": str(dataset_path),
            "pdf_path": str(pdf_path),
            "seed_document": seed_meta,
            "top_k": int(args.top_k),
            "failure_confidence_threshold": float(args.failure_confidence_threshold),
            "summary": summary,
            "records": records,
        }
        write_json(json_path, report)
        write_csv(csv_path, records)

        print(f"[motorcycle-eval] seed_document => {seed_meta}")
        print(f"[motorcycle-eval] summary       => {json.dumps(summary, ensure_ascii=False)}")
        print(f"[motorcycle-eval] json report   => {json_path}")
        print(f"[motorcycle-eval] csv report    => {csv_path}")
        return 0
    finally:
        await client.aclose()
        fastapi_app.dependency_overrides.pop(get_session, None)
        await engine.dispose()


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
