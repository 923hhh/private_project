"""Run offline evaluation against generated maintenance RAG datasets."""
from __future__ import annotations

import argparse
import asyncio
import json
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
from app.evaluation.offline_eval import (
    compute_offline_scorecard,
    load_json,
    normalize_text,
    result_matches_expectation,
    procedural_completeness_ok,
    write_json,
)
from app.main import app as fastapi_app

import app.db.models as app_models  # noqa: F401


DEFAULT_CONFIG_PATH = ROOT / "evaluation" / "offline_eval_config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline maintenance RAG evaluation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--with-ragas-metrics", action="store_true", help="Try optional RAGAS metrics if installed.")
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    config = load_json(args.config.resolve())
    dataset_path = args.dataset_path.resolve() if args.dataset_path else resolve_generated_dataset_path(config)
    if not dataset_path.exists():
        print(f"离线评测数据集不存在: {dataset_path}", file=sys.stderr)
        return 1

    seed_docs = load_json(resolve_backend_path(config["seed_documents_path"]))
    dataset_rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    client, _, engine = await create_eval_client("offline-rag-eval")
    try:
        await seed_documents(client, seed_docs)
        records = await execute_offline_eval(client, dataset_rows, top_k=int((config.get("runner") or {}).get("top_k") or 5))
        report: dict[str, Any] = {
            "dataset_path": str(dataset_path),
            "case_count": len(dataset_rows),
            "metrics": compute_offline_scorecard(records),
            "records": records,
        }
        if args.with_ragas_metrics:
            report["ragas"] = await try_run_ragas_metrics(dataset_rows, records)

        output_path = args.output_path.resolve() if args.output_path else resolve_output_path(config)
        write_json(output_path, report)
        print(f"[offline-rag-eval] report => {output_path}")
        return 0
    finally:
        await client.aclose()
        fastapi_app.dependency_overrides.pop(get_session, None)
        await engine.dispose()


def resolve_backend_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if raw_path.startswith("backend/"):
        return (ROOT.parent / raw_path).resolve()
    return (ROOT / raw_path).resolve()


def resolve_generated_dataset_path(config: dict[str, Any]) -> Path:
    output_dir = resolve_backend_path(str(config["output_dir"]))
    dataset_prefix = str(config.get("dataset_prefix") or "maintenance_rag")
    return output_dir / f"{dataset_prefix}_testset.jsonl"


def resolve_output_path(config: dict[str, Any]) -> Path:
    runner = config.get("runner") or {}
    output_file = runner.get("output_file") or "backend/evaluation/generated/maintenance_rag_eval_report.json"
    return resolve_backend_path(str(output_file))


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
    client = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://offline-eval")
    return client, session_factory, engine


async def seed_documents(client: AsyncClient, seed_documents: list[dict[str, Any]]) -> None:
    for item in seed_documents:
        response = await client.post("/api/v1/knowledge/documents", json=item)
        response.raise_for_status()


async def execute_offline_eval(
    client: AsyncClient,
    dataset_rows: list[dict[str, Any]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in dataset_rows:
        metadata = row.get("metadata") or {}
        payload = {
            "query": row["user_input"],
            "equipment_type": metadata.get("equipment_type"),
            "equipment_model": metadata.get("equipment_model"),
            "fault_type": metadata.get("fault_type"),
            "limit": top_k,
        }
        response = await client.post("/api/v1/knowledge/search", json=payload)
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        top_result = results[0] if results else None
        retrieval_hit = bool(top_result and result_matches_expectation(top_result, metadata))
        citation_hit = bool(top_result and (top_result.get("source_name") and (top_result.get("page_reference") or top_result.get("section_reference") or top_result.get("image_anchor"))))
        sample_type = metadata.get("sample_type")
        expected_reject = metadata.get("category") == "failure"
        reject_ok = expected_reject and not bool(data.get("grounded"))
        procedural_ok = True
        if sample_type == "procedural":
            procedural_ok = bool(top_result) and procedural_completeness_ok(top_result, str(row.get("reference") or ""))

        records.append(
            {
                "case_id": metadata.get("case_id"),
                "sample_type": sample_type,
                "category": metadata.get("category"),
                "query": row["user_input"],
                "retrieval_hit": retrieval_hit,
                "citation_hit": citation_hit,
                "grounded": bool(data.get("grounded")),
                "answer_confidence": float(data.get("answer_confidence") or 0.0),
                "procedural_completeness_ok": procedural_ok,
                "expected_reject": expected_reject,
                "reject_ok": reject_ok,
                "retrieval_path": data.get("retrieval_path") or [],
                "top_title": top_result.get("title") if top_result else None,
                "top_source_modality": top_result.get("source_modality") if top_result else None,
            }
        )
    return records


async def try_run_ragas_metrics(dataset_rows: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from ragas import evaluate
        from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
        from ragas.metrics import Faithfulness, ResponseRelevancy
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    except Exception as exc:
        return {"enabled": False, "error": f"ragas unavailable: {exc}"}

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return {"enabled": False, "error": "OPENAI_API_KEY 未配置，跳过 RAGAS 指标。"}

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

    samples: list[SingleTurnSample] = []
    for row, record in zip(dataset_rows, records):
        retrieved_contexts = [record.get("top_title") or ""]
        samples.append(
            SingleTurnSample(
                user_input=row["user_input"],
                response=(record.get("top_title") or "") + " " + " ".join(record.get("retrieval_path") or []),
                retrieved_contexts=retrieved_contexts,
                reference=row.get("reference") or "",
                reference_contexts=row.get("reference_contexts") or [],
            )
        )
    result = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=False,
    )
    return {"enabled": True, "summary": result.to_pandas().mean(numeric_only=True).to_dict()}


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
