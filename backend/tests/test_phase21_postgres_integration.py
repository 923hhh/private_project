"""Phase 21: PostgreSQL 索引与主链路集成测试.

运行前请设置:
    TEST_POSTGRESQL_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>

该 URL 应指向专用测试数据库。
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base
from app.schemas.agents import AgentAssistRequest
from app.schemas.cases import MaintenanceCaseCreate, MaintenanceCaseReviewRequest
from app.schemas.knowledge import KnowledgeSearchRequest
from app.schemas.tasks import MaintenanceTaskCreate
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.services.case_service import MaintenanceCaseService
from app.services.knowledge_import_service import KnowledgeImportService
from app.services.knowledge_service import KnowledgeService
from app.services.maintenance_task_service import MaintenanceTaskService
from app.services.ocr_service import ImageOcrResult

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """Return the dedicated PostgreSQL test URL or skip the module."""
    url = os.getenv("TEST_POSTGRESQL_URL")
    if not url:
        pytest.skip("TEST_POSTGRESQL_URL 未设置，跳过 PostgreSQL 集成测试。")
    return url


@pytest_asyncio.fixture(scope="module")
async def postgres_engine(postgres_url: str):
    """Upgrade the target database to head and provide an async engine."""
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_url
    get_settings.cache_clear()

    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def clear_postgres_tables(postgres_engine):
    """Keep the dedicated PostgreSQL test database clean between tests."""
    table_names = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
    async with postgres_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def postgres_session(postgres_engine):
    """Yield a fresh AsyncSession bound to PostgreSQL."""
    session_factory = async_sessionmaker(postgres_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_postgres_migration_creates_expected_indexes(postgres_engine):
    """迁移后应存在全文检索和业务列表索引。"""
    expected_indexes = {
        "ix_knowledge_documents_search_tsv",
        "ix_knowledge_chunks_search_tsv",
        "ix_knowledge_chunks_document_chunk_order",
        "ix_maintenance_tasks_status_priority_updated",
        "ix_maintenance_cases_status_priority_updated",
        "ix_knowledge_import_jobs_status_updated",
    }

    async with postgres_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
        )
        existing_indexes = {row[0] for row in rows.fetchall()}

    assert expected_indexes.issubset(existing_indexes)


@pytest.mark.asyncio
async def test_postgres_import_search_task_case_and_agent_workflow(postgres_session):
    """在 PostgreSQL 上验证导入、检索、任务、案例和 Agent 回放主链路。"""
    import_service = KnowledgeImportService(postgres_session)
    import_service.ocr_service.extract_text = AsyncMock(
        return_value=ImageOcrResult(
            recognized_text=(
                "LX200 冷启动困难时，应先停机、断电并完成风险隔离，"
                "随后检查火花塞积碳、点火线圈与供油状态。"
            ),
            summary="图片已抽取点火系统与安全隔离步骤。",
            keywords=["LX200", "启动困难", "火花塞", "风险隔离"],
            source="vision_model",
        )
    )

    job = await import_service.import_pdf_upload(
        filename="spark-plug.png",
        file_bytes=b"fake-image",
        content_type="image/png",
        title="LX200 点火系统图示",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        fault_type="启动困难",
        section_reference="点火系统",
        source_type="manual",
        replace_existing=False,
    )
    processed = await import_service.process_job(job["id"])

    assert processed["status"] == "completed"
    assert processed["document_id"] is not None

    knowledge_service = KnowledgeService(postgres_session)
    search_payload = await knowledge_service.search_multimodal(
        KnowledgeSearchRequest(
            query="LX200 冷启动困难 火花塞积碳",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            priority="high",
            maintenance_level="emergency",
            limit=3,
        )
    )

    assert search_payload["results"]
    top_hit = search_payload["results"][0]
    assert top_hit["rerank_score"] >= top_hit["retrieval_score"]

    task_service = MaintenanceTaskService(postgres_session)
    task = await task_service.create_task(
        MaintenanceTaskCreate(
            work_order_id="WO-PG-001",
            asset_code="ENG-LX200-01",
            report_source="巡检上报",
            priority="high",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            maintenance_level="emergency",
            fault_type="启动困难",
            symptom_description="发动机冷启动困难，伴随火花塞积碳",
            source_chunk_ids=[top_hit["chunk_id"]],
        )
    )

    assert task["source_refs"]
    assert task["steps"]

    case_service = MaintenanceCaseService(postgres_session)
    maintenance_case = await case_service.create_case(
        MaintenanceCaseCreate(
            title="LX200 火花塞积碳应急检修案例",
            task_id=task["id"],
            work_order_id=task["work_order_id"],
            asset_code=task["asset_code"],
            report_source=task["report_source"],
            priority=task["priority"],
            equipment_type=task["equipment_type"],
            equipment_model=task["equipment_model"],
            fault_type=task["fault_type"],
            symptom_description=task["symptom_description"] or "冷启动困难",
            processing_steps=[step["title"] for step in task["steps"]],
            resolution_summary="完成停机隔离、火花塞清洁和点火系统复核后，冷启动恢复正常。",
            knowledge_refs=task["source_refs"],
        )
    )
    approved_case = await case_service.review_case(
        maintenance_case["id"],
        MaintenanceCaseReviewRequest(action="approve", reviewer_name="postgres-tester"),
    )

    assert approved_case["status"] == "approved"
    assert approved_case["source_document_id"] is not None

    agent_service = AgentOrchestrationService(postgres_session)
    agent_run = await agent_service.assist(
        AgentAssistRequest(
            work_order_id="WO-PG-001",
            asset_code="ENG-LX200-01",
            report_source="巡检上报",
            priority="high",
            maintenance_level="emergency",
            query="LX200 冷启动困难，伴随火花塞积碳",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            limit=3,
        )
    )
    replayed = await agent_service.get_run(agent_run["run_id"])

    assert replayed is not None
    assert replayed["run_id"] == agent_run["run_id"]
    assert replayed["related_cases"]
