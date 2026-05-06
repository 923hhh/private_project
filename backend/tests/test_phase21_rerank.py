"""Phase 21: 检索 rerank 逻辑测试."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.knowledge.schemas.search import KnowledgeSearchRequest
from app.modules.knowledge.application.search_service import KnowledgeService


def _fake_chunk(
    *,
    chunk_id: int,
    content: str,
    equipment_model: str | None,
    fault_type: str | None,
    heading: str | None = None,
    equipment_type: str = "摩托车发动机",
):
    return SimpleNamespace(
        id=chunk_id,
        heading=heading,
        content=content,
        equipment_type=equipment_type,
        equipment_model=equipment_model,
        fault_type=fault_type,
        section_reference="第 2 章",
        page_reference="P12",
    )


def _fake_document(
    *,
    document_id: int,
    title: str,
    source_name: str,
    source_type: str,
):
    return SimpleNamespace(
        id=document_id,
        title=title,
        source_name=source_name,
        source_type=source_type,
        equipment_model="LX200",
        fault_type="启动困难",
        section_reference="第 2 章",
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_search_rerank_prefers_exact_model_match_over_generic_manual():
    """同型号结果即使原始分数略低，也应在 rerank 后优先。"""
    fake_bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    generic_chunk = _fake_chunk(
        chunk_id=11,
        content="火花塞积碳时先检查点火系统和供油状态。",
        equipment_model=None,
        fault_type="启动困难",
    )
    exact_chunk = _fake_chunk(
        chunk_id=12,
        content="LX200 冷启动困难时优先检查火花塞积碳和点火线圈。",
        equipment_model="LX200",
        fault_type="启动困难",
    )
    generic_document = _fake_document(
        document_id=1,
        title="摩托车发动机通用手册",
        source_name="manual-generic.pdf",
        source_type="manual",
    )
    exact_document = _fake_document(
        document_id=2,
        title="LX200 点火系统检修手册",
        source_name="manual-lx200.pdf",
        source_type="manual",
    )
    fake_result = SimpleNamespace(
        all=lambda: [
            (generic_chunk, generic_document, 5.4),
            (exact_chunk, exact_document, 4.9),
        ]
    )
    mock_session = SimpleNamespace(
        get_bind=lambda: fake_bind,
        execute=AsyncMock(return_value=fake_result),
    )

    service = KnowledgeService(session=mock_session)
    results = await service.search(
        KnowledgeSearchRequest(
            query="LX200 冷启动困难 火花塞积碳",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            limit=2,
        )
    )

    assert [item["chunk_id"] for item in results] == [12, 11]
    assert results[0]["rerank_score"] > results[0]["retrieval_score"]
    assert "同型号 LX200" in results[0]["recommendation_reason"]


@pytest.mark.asyncio
async def test_search_rerank_emergency_prefers_safety_manual_guidance():
    """应急检修场景应优先把带安全隔离提示的标准手册放到前面。"""
    fake_bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    case_chunk = _fake_chunk(
        chunk_id=21,
        content="历史案例提示先检查火花塞积碳，再观察冷启动现象。",
        equipment_model="LX200",
        fault_type="启动困难",
        heading="案例复盘",
    )
    safety_chunk = _fake_chunk(
        chunk_id=22,
        content="应急检修时必须先停机、断电并完成风险隔离，再检查火花塞积碳。",
        equipment_model="LX200",
        fault_type="启动困难",
        heading="安全隔离与点火排查",
    )
    case_document = _fake_document(
        document_id=3,
        title="LX200 冷启动困难案例",
        source_name="case-lx200",
        source_type="case",
    )
    manual_document = _fake_document(
        document_id=4,
        title="LX200 应急检修作业手册",
        source_name="manual-emergency.pdf",
        source_type="manual",
    )
    fake_result = SimpleNamespace(
        all=lambda: [
            (case_chunk, case_document, 6.2),
            (safety_chunk, manual_document, 4.8),
        ]
    )
    mock_session = SimpleNamespace(
        get_bind=lambda: fake_bind,
        execute=AsyncMock(return_value=fake_result),
    )

    service = KnowledgeService(session=mock_session)
    results = await service.search(
        KnowledgeSearchRequest(
            query="LX200 应急冷启动困难",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            priority="urgent",
            maintenance_level="emergency",
            limit=2,
        )
    )

    assert [item["chunk_id"] for item in results] == [22, 21]
    assert results[0]["rerank_score"] > results[0]["retrieval_score"]
    assert "应急场景优先标准作业依据" in results[0]["recommendation_reason"]
