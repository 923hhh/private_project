"""Phase 14: 知识库与知识检索主体测试."""
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import builtins

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services.image_analysis_service import FaultImageAnalysisService, ImageAnalysisResult
from app.services.knowledge_chunking import split_text_into_chunks
from app.services.knowledge_service import KnowledgeService
from app.services.bm25_service import BM25Service


def test_split_text_into_chunks_splits_long_content():
    """长文本会被稳定切分为多个检索分段。"""
    content = "\n\n".join(
        [
            "发动机启动困难时，应先检查火花塞和供油系统。" * 10,
            "若伴随异响，需要同步排查正时链条和气门间隙。" * 10,
        ]
    )

    chunks = split_text_into_chunks(content, max_chars=120)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 120 for chunk in chunks)


def test_bm25_service_degrades_gracefully_when_rank_bm25_missing():
    """缺少 rank_bm25 依赖时，不应让导入/检索主链直接失败。"""
    service = BM25Service(SimpleNamespace(faiss_index_path="data/faiss_index"))
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rank_bm25":
            raise ModuleNotFoundError("No module named 'rank_bm25'")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        service.ensure_loaded()

    assert service.search("拆卸发动机步骤") == []


def test_extract_search_tokens_prefers_domain_terms_from_long_query():
    """长中文故障描述会被收敛为更可检索的设备检修术语。"""
    service = KnowledgeService(session=SimpleNamespace())
    query = (
        "车辆在行驶过程中出现发动机动力下降现象，同时伴随发动机故障灯点亮。"
        "初步判断可能为燃油供给异常或点火系统故障。经检测发现节气门积碳严重，清洗后故障消除"
    )

    tokens = service._extract_search_tokens(query)

    assert "发动机" in tokens
    assert "动力下降" in tokens
    assert "故障灯" in tokens
    assert "燃油供给" in tokens
    assert "点火系统" in tokens
    assert "节气门" in tokens
    assert "积碳" in tokens
    assert "车辆" not in tokens


def test_build_excerpt_uses_token_when_full_query_not_found():
    """全文未命中时，摘要会回退到首个命中的关键 token。"""
    service = KnowledgeService(session=SimpleNamespace())
    content = "排气冒黑烟时，应重点检查空气滤芯堵塞、混合比过浓、喷油量异常和节气门积碳。"
    query = "车辆在行驶过程中出现发动机动力下降现象，同时伴随发动机故障灯点亮。经检测发现节气门积碳严重"

    excerpt = service._build_excerpt(content, query)

    assert "节气门积碳" in excerpt


def test_extract_search_tokens_expands_synonyms():
    """检修术语会扩展为稳定的同义词集合。"""
    service = KnowledgeService(session=SimpleNamespace())

    tokens = service._extract_search_tokens("发动机功率下降并伴随点火异常")

    assert "功率下降" in tokens
    assert "动力下降" in tokens
    assert "点火异常" in tokens
    assert "点火系统" in tokens
    assert "火花塞" in tokens


def test_build_effective_keywords_rewrites_fault_terms():
    """长故障描述会被重写成更稳定的检修关键词集合。"""
    service = KnowledgeService(session=SimpleNamespace())

    keywords = service._build_effective_keywords(
        query="发动机温度偏高，长时间运行后动力下降",
        equipment_model="LX200",
        fault_type="温度偏高",
    )

    assert "温度偏高" in keywords
    assert "动力下降" in keywords
    assert "润滑" in keywords
    assert "机油液位" in keywords
    assert "LX200" in keywords


@pytest.mark.asyncio
async def test_search_allows_generic_manual_for_specific_equipment_model():
    """指定具体型号时，通用手册条目仍应对该型号可见。"""
    fake_bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    fake_chunk = SimpleNamespace(
        id=101,
        equipment_type="摩托车发动机",
        equipment_model=None,
        fault_type=None,
        content="拆卸火花塞前应先检查火花塞帽和积碳情况。",
        section_reference=None,
        page_reference="P1",
    )
    fake_document = SimpleNamespace(
        id=2,
        title="摩托车发动机维修手册",
        source_name="manual.pdf",
        source_type="manual",
        section_reference=None,
    )
    fake_result = SimpleNamespace(all=lambda: [(fake_chunk, fake_document, 2.0)])
    mock_session = SimpleNamespace(
        get_bind=lambda: fake_bind,
        execute=AsyncMock(return_value=fake_result),
    )

    service = KnowledgeService(session=mock_session)
    results = await service.search(
        KnowledgeSearchRequest(
            query="火花塞",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
        )
    )

    executed_stmt = mock_session.execute.await_args.args[0]
    executed_sql = str(executed_stmt)

    assert "knowledge_chunks.equipment_model IS NULL" in executed_sql
    assert len(results) == 1
    assert results[0]["equipment_model"] is None
    assert "通用手册" in results[0]["recommendation_reason"]


@pytest.mark.asyncio
async def test_search_multimodal_returns_rewritten_keywords():
    """多模态检索应返回可直接展示的重写关键词。"""
    service = KnowledgeService(session=SimpleNamespace())
    service.search = AsyncMock(return_value=[])
    service.image_analysis_service.analyze = AsyncMock(
        return_value=ImageAnalysisResult(
            summary="火花塞积碳明显，建议检查点火系统。",
            keywords=["spark", "plug", "积碳"],
            source="fallback",
        )
    )

    payload = await service.search_multimodal(
        KnowledgeSearchRequest(
            query="发动机启动困难，火花塞积碳明显",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            image_base64=base64.b64encode(b"fake-image").decode("ascii"),
            image_mime_type="image/png",
            image_filename="spark-plug-fault.png",
        )
    )

    assert "火花塞" in payload["effective_keywords"]
    assert "点火系统" in payload["effective_keywords"]
    assert "LX200" in payload["effective_keywords"]
    assert "火花塞" in payload["effective_query"]


@pytest.mark.asyncio
async def test_image_fallback_converts_english_filename_to_domain_terms():
    """英文故障图片文件名也应转成中文检修术语。"""
    service = FaultImageAnalysisService()

    with patch.object(service, "_create_multimodal_llm", return_value=None):
        result = await service.analyze(
            image_base64=base64.b64encode(b"fake-image").decode("ascii"),
            image_mime_type="image/png",
            image_filename="spark-plug-oil-leak.png",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
        )

    assert result.source == "fallback"
    assert "火花塞" in result.keywords
    assert "机油渗漏" in result.keywords


@pytest.fixture(autouse=True)
def override_db_session():
    """为知识接口测试覆盖数据库依赖，避免本机驱动差异影响接口验证。"""

    async def _override_get_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_create_knowledge_document_endpoint():
    """知识文档导入端点返回 201 和分段数量。"""
    fake_document = SimpleNamespace(
        id=1,
        title="发动机检修手册 - 启动困难",
        source_name="motor_manual.pdf",
        source_type="manual",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        fault_type="启动困难",
        status="published",
    )

    with patch(
        "app.modules.knowledge.router.KnowledgeService.create_document",
        new=AsyncMock(return_value=(fake_document, 3)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/documents",
                json={
                    "title": "发动机检修手册 - 启动困难",
                    "source_name": "motor_manual.pdf",
                    "source_type": "manual",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "fault_type": "启动困难",
                    "content": "发动机启动困难时，应优先检查点火系统、油路以及气门间隙是否正常。",
                },
            )

    assert response.status_code == 201
    data = response.json()
    assert data["chunk_count"] == 3
    assert data["equipment_model"] == "LX200"


@pytest.mark.asyncio
async def test_search_knowledge_endpoint():
    """检索端点返回带出处和推荐理由的结果。"""
    mocked_payload = {
        "query": "启动困难",
        "effective_query": "启动困难 LX200 火花塞 供油",
        "effective_keywords": ["启动困难", "LX200", "火花塞", "供油"],
        "query_type": "multimodal_joint",
        "image_analysis_used": True,
        "retrieval_path": ["query_profile:multimodal_joint", "sql", "vector"],
        "answer_confidence": 0.84,
        "coverage_warnings": [],
        "grounded": True,
        "image_analysis": {
            "summary": "图中疑似火花塞积碳，建议检查点火系统。",
            "keywords": ["火花塞", "积碳", "点火系统"],
            "source": "vision_model",
            "warning": None,
        },
        "results": [
            {
                "chunk_id": 11,
                "document_id": 2,
                "title": "发动机标准检修流程",
                "source_name": "engine_manual.pdf",
                "source_type": "manual",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "excerpt": "发动机启动困难时，应重点检查火花塞、供油和压缩比。",
                "section_reference": "第 2 章",
                "page_reference": "P12",
                "source_modality": "text",
                "ocr_text": None,
                "image_caption": None,
                "evidence_summary": "标准检修手册片段",
                "expanded_content": "发动机启动困难时，应重点检查火花塞、供油和压缩比。\n\n随后检查点火线圈和线路接触情况。",
                "recommendation_reason": "命中了检索关键词“启动困难”，设备型号过滤匹配，来源于 engine_manual.pdf",
                "score": 5.0,
            }
        ],
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeService.search_multimodal",
        new=AsyncMock(return_value=mocked_payload),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "启动困难",
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["effective_query"] == "启动困难 LX200 火花塞 供油"
    assert data["query_type"] == "multimodal_joint"
    assert data["grounded"] is True
    assert data["effective_keywords"] == ["启动困难", "LX200", "火花塞", "供油"]
    assert data["image_analysis"]["source"] == "vision_model"
    assert data["results"][0]["expanded_content"]
    assert data["results"][0]["source_name"] == "engine_manual.pdf"
    assert data["results"][0]["recommendation_reason"]


@pytest.mark.asyncio
async def test_search_knowledge_requires_input():
    """未提供任何检索条件时，返回 422。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/knowledge/search", json={"limit": 5})

    assert response.status_code == 422


def test_search_request_accepts_image_only():
    """图片可单独作为多模态检索入口。"""
    request = KnowledgeSearchRequest(
        image_base64="ZmFrZV9pbWFnZQ==",
        image_mime_type="image/png",
        image_filename="spark-plug-fault.png",
    )

    assert request.image_filename == "spark-plug-fault.png"
    assert request.image_base64 == "ZmFrZV9pbWFnZQ=="


@pytest.mark.asyncio
async def test_search_multimodal_marks_ungrounded_when_no_results():
    """低命中场景应返回 grounded=false 和补充提示。"""
    service = KnowledgeService(session=SimpleNamespace())
    service.search = AsyncMock(return_value=[])
    service.image_analysis_service.analyze = AsyncMock(
        return_value=ImageAnalysisResult(
            summary="疑似火花塞区域存在积碳。",
            keywords=["火花塞", "积碳"],
            source="vision_model",
        )
    )

    payload = await service.search_multimodal(
        KnowledgeSearchRequest(
            query="看图判断故障原因",
            equipment_type="摩托车发动机",
            image_base64=base64.b64encode(b"fake-image").decode("ascii"),
            image_mime_type="image/png",
            image_filename="spark-plug.png",
        )
    )

    assert payload["grounded"] is False
    assert payload["coverage_warnings"]


@pytest.mark.asyncio
async def test_search_multimodal_assigns_chunk_level_citation_labels():
    """多模态检索结果应自动补齐 chunk 级 citation_label。"""
    service = KnowledgeService(session=SimpleNamespace())
    service.search = AsyncMock(
        return_value=[
            {
                "chunk_id": 31,
                "document_id": 7,
                "title": "火花塞拆卸步骤",
                "source_name": "engine_manual.pdf",
                "source_type": "procedure",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "excerpt": "步骤2：拆下火花塞帽并检查积碳。",
                "section_reference": "3.1 拆卸步骤",
                "page_reference": "P18",
                "recommendation_reason": "命中步骤关键词",
                "score": 3.2,
            }
        ]
    )
    service._attach_expanded_context = AsyncMock(
        return_value=[
            {
                "chunk_id": 31,
                "document_id": 7,
                "title": "火花塞拆卸步骤",
                "source_name": "engine_manual.pdf",
                "source_type": "procedure",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "excerpt": "步骤2：拆下火花塞帽并检查积碳。",
                "section_reference": "3.1 拆卸步骤",
                "page_reference": "P18",
                "expanded_content": "步骤1：关闭点火开关。\n步骤2：拆下火花塞帽并检查积碳。",
                "recommendation_reason": "命中步骤关键词",
                "score": 3.2,
            }
        ]
    )

    payload = await service.search_multimodal(
        KnowledgeSearchRequest(
            query="LX200 火花塞拆卸步骤",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
        )
    )

    assert payload["results"][0]["chunk_id"] == 31
    assert payload["results"][0]["citation_label"] == "C1"


@pytest.mark.asyncio
async def test_search_multimodal_fuses_query_variants_globally():
    """多 query 结果应做全局融合，而不是按返回顺序先到先得去重。"""
    service = KnowledgeService(session=SimpleNamespace())
    service.search = AsyncMock(
        side_effect=[
            [
                {
                    "chunk_id": 11,
                    "document_id": 5,
                    "title": "发动机拆卸步骤 A",
                    "source_name": "manual.pdf",
                    "source_type": "manual",
                    "equipment_type": "摩托车发动机",
                    "excerpt": "步骤 1：先排空机油。",
                    "section_reference": "3.2 拆卸发动机",
                    "page_reference": "P10",
                    "retrieval_score": 1.2,
                    "rerank_score": 1.4,
                    "score": 1.4,
                    "_retrieval_path": ["sql"],
                },
                {
                    "chunk_id": 12,
                    "document_id": 5,
                    "title": "发动机拆卸步骤 B",
                    "source_name": "manual.pdf",
                    "source_type": "manual",
                    "equipment_type": "摩托车发动机",
                    "excerpt": "步骤 2：拆下托架固定螺栓。",
                    "section_reference": "3.2 拆卸发动机",
                    "page_reference": "P11",
                    "retrieval_score": 0.9,
                    "rerank_score": 1.0,
                    "score": 1.0,
                    "_retrieval_path": ["sql"],
                },
            ],
            [
                {
                    "chunk_id": 12,
                    "document_id": 5,
                    "title": "发动机拆卸步骤 B",
                    "source_name": "manual.pdf",
                    "source_type": "manual",
                    "equipment_type": "摩托车发动机",
                    "excerpt": "步骤 2：拆下托架固定螺栓。",
                    "section_reference": "3.2 拆卸发动机",
                    "page_reference": "P11",
                    "retrieval_score": 1.5,
                    "rerank_score": 1.8,
                    "score": 1.8,
                    "_retrieval_path": ["vector"],
                },
                {
                    "chunk_id": 13,
                    "document_id": 5,
                    "title": "发动机拆卸步骤 C",
                    "source_name": "manual.pdf",
                    "source_type": "manual",
                    "equipment_type": "摩托车发动机",
                    "excerpt": "步骤 3：吊离发动机总成。",
                    "section_reference": "3.2 拆卸发动机",
                    "page_reference": "P12",
                    "retrieval_score": 0.8,
                    "rerank_score": 0.9,
                    "score": 0.9,
                    "_retrieval_path": ["vector"],
                },
            ],
        ]
    )
    service._attach_expanded_context = AsyncMock(side_effect=lambda results: results)

    with patch(
        "app.services.query_rewrite_service.generate_multi_queries",
        new=AsyncMock(return_value=["拆卸发动机步骤", "发动机拆卸流程"]),
    ), patch(
        "app.services.graph_rag_service.graph_expand",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.modules.knowledge.application.search_service.build_grounding_assessment",
        return_value={"answer_confidence": 0.91, "coverage_warnings": [], "grounded": True},
    ):
        payload = await service.search_multimodal(
            KnowledgeSearchRequest(
                query="拆卸发动机步骤",
                equipment_type="摩托车发动机",
                limit=5,
            )
        )

    assert [item["chunk_id"] for item in payload["results"][:3]] == [12, 11, 13]
    assert set(payload["results"][0]["_retrieval_path"]) == {"sql", "vector"}
