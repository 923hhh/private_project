"""Phase 19: 正式知识导入管理接口测试."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def override_db_session():
    """覆盖数据库依赖，避免端点测试落到真实数据库。"""

    async def _override_get_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_preview_knowledge_import_endpoint():
    """导入前预览接口应返回页数、分段数和预览摘录。"""
    mocked_preview = {
        "import_type": "pdf",
        "processing_note": None,
        "normalized_title": "摩托车发动机维修手册",
        "source_name": "manual.pdf",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": None,
        "section_reference": None,
        "replace_existing": False,
        "page_count": 18,
        "chunk_count": 42,
        "preview_excerpt": "火花塞检查与拆装步骤。",
        "existing_document_detected": True,
        "warning_message": "已存在同名知识文档，确认导入前请勾选覆盖导入或调整文件名。",
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.preview_pdf_upload",
        new=AsyncMock(return_value=mocked_preview),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/imports/preview",
                files={"file": ("manual.pdf", b"%PDF-1.4\n", "application/pdf")},
                data={
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "replace_existing": "false",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_count"] == 18
    assert payload["existing_document_detected"] is True
    assert payload["warning_message"] is not None


@pytest.mark.asyncio
async def test_knowledge_import_upload_endpoint():
    """上传 PDF 时应先返回已受理的导入任务摘要。"""
    mocked_payload = {
        "id": 7,
        "import_type": "pdf",
        "processing_note": None,
        "title": "摩托车发动机维修手册",
        "source_name": "manual.pdf",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": None,
        "section_reference": None,
        "replace_existing": True,
        "status": "pending",
        "page_count": None,
        "chunk_count": None,
        "document_id": None,
        "preview_excerpt": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.import_pdf_upload",
        new=AsyncMock(return_value=mocked_payload),
    ), patch("app.modules.knowledge.router.KnowledgeImportWorker.schedule_job"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/imports",
                files={"file": ("manual.pdf", b"%PDF-1.4\n", "application/pdf")},
                data={
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "replace_existing": "true",
                },
            )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["chunk_count"] is None
    assert payload["document_id"] is None


@pytest.mark.asyncio
async def test_knowledge_import_upload_rejects_non_pdf():
    """导入接口应拒绝不受支持的文件类型。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/imports",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"equipment_type": "摩托车发动机"},
        )

    assert response.status_code == 400
    assert "PDF" in response.json()["message"] or "PNG" in response.json()["message"]


@pytest.mark.asyncio
async def test_preview_knowledge_import_accepts_image_upload():
    """导入预览接口应接受图片型知识文档。"""
    mocked_preview = {
        "import_type": "image_ocr",
        "processing_note": "图片已通过视觉 OCR 提取为知识文本。",
        "normalized_title": "点火系统图示",
        "source_name": "spark-plug.png",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": None,
        "section_reference": "点火系统",
        "replace_existing": False,
        "page_count": 1,
        "chunk_count": 3,
        "preview_excerpt": "图像 OCR 已识别火花塞拆装与检查步骤。",
        "existing_document_detected": False,
        "warning_message": None,
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.preview_pdf_upload",
        new=AsyncMock(return_value=mocked_preview),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/imports/preview",
                files={"file": ("spark-plug.png", b"fakepng", "image/png")},
                data={
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "section_reference": "点火系统",
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["import_type"] == "image_ocr"
    assert payload["page_count"] == 1


@pytest.mark.asyncio
async def test_knowledge_import_upload_accepts_image_upload():
    """正式导入接口应接受图片型知识文档并先返回排队状态。"""
    mocked_payload = {
        "id": 12,
        "import_type": "image_ocr",
        "processing_note": "图片已通过视觉 OCR 导入知识库，建议结合来源回溯进行人工校对。",
        "title": "点火系统图示",
        "source_name": "spark-plug.png",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": None,
        "section_reference": "点火系统",
        "replace_existing": True,
        "status": "pending",
        "page_count": None,
        "chunk_count": None,
        "document_id": None,
        "preview_excerpt": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.import_pdf_upload",
        new=AsyncMock(return_value=mocked_payload),
    ), patch("app.modules.knowledge.router.KnowledgeImportWorker.schedule_job"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/knowledge/imports",
                files={"file": ("spark-plug.png", b"fakepng", "image/png")},
                data={
                    "equipment_type": "摩托车发动机",
                    "equipment_model": "LX200",
                    "replace_existing": "true",
                },
            )

    assert response.status_code == 202
    payload = response.json()
    assert payload["import_type"] == "image_ocr"
    assert payload["status"] == "pending"


@pytest.mark.asyncio
async def test_retry_knowledge_import_job_endpoint():
    """失败任务应能重新入队。"""
    mocked_payload = {
        "id": 15,
        "import_type": "pdf",
        "processing_note": None,
        "title": "摩托车发动机维修手册",
        "source_name": "manual.pdf",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": None,
        "fault_type": None,
        "section_reference": None,
        "replace_existing": False,
        "status": "pending",
        "page_count": None,
        "chunk_count": None,
        "document_id": None,
        "preview_excerpt": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.retry_job",
        new=AsyncMock(return_value=mocked_payload),
    ), patch("app.modules.knowledge.router.KnowledgeImportWorker.schedule_job"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/knowledge/imports/15/retry")

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == 15
    assert payload["status"] == "pending"


@pytest.mark.asyncio
async def test_list_knowledge_import_jobs_endpoint():
    """知识中心应能获取最近的导入记录列表。"""
    mocked_jobs = [
        {
            "id": 11,
            "import_type": "pdf",
            "processing_note": None,
            "title": "摩托车发动机维修手册",
            "source_name": "manual.pdf",
            "source_type": "manual",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": None,
            "section_reference": None,
            "replace_existing": True,
            "status": "completed",
            "page_count": 12,
            "chunk_count": 31,
            "document_id": 18,
            "preview_excerpt": "火花塞检查与拆装步骤。",
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.list_import_jobs",
        new=AsyncMock(return_value=mocked_jobs),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/imports?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["jobs"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_knowledge_import_job_endpoint():
    """应能查询单个导入任务详情。"""
    mocked_payload = {
        "id": 9,
        "import_type": "pdf",
        "processing_note": None,
        "title": "正时链条维修手册",
        "source_name": "timing.pdf",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": None,
        "fault_type": "异响",
        "section_reference": "正时系统",
        "replace_existing": False,
        "status": "failed",
        "page_count": None,
        "chunk_count": None,
        "document_id": None,
        "preview_excerpt": None,
        "error_message": "已存在同名知识文档，请勾选覆盖导入后重试。",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.get_import_job",
        new=AsyncMock(return_value=mocked_payload),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/imports/9")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 9
    assert payload["status"] == "failed"


@pytest.mark.asyncio
async def test_list_knowledge_documents_endpoint():
    """知识中心应能获取文档列表和分段数。"""
    mocked_documents = [
        {
            "id": 1,
            "title": "摩托车发动机维修手册",
            "source_name": "manual.pdf",
            "source_type": "manual",
            "equipment_type": "摩托车发动机",
            "equipment_model": None,
            "fault_type": None,
            "status": "published",
            "chunk_count": 41,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.list_documents",
        new=AsyncMock(return_value=mocked_documents),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/documents?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["documents"][0]["chunk_count"] == 41


@pytest.mark.asyncio
async def test_list_knowledge_documents_forwards_filters():
    """文档列表接口应透传筛选条件到服务层。"""
    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.list_documents",
        new=AsyncMock(return_value=[]),
    ) as mocked_list_documents:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/knowledge/documents?limit=5&query=火花塞&equipment_type=摩托车发动机&equipment_model=LX200&source_type=manual"
            )

    assert response.status_code == 200
    mocked_list_documents.assert_awaited_once_with(
        limit=5,
        query="火花塞",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        source_type="manual",
    )


@pytest.mark.asyncio
async def test_get_knowledge_document_detail_endpoint():
    """知识文档详情接口应返回来源回溯字段。"""
    mocked_detail = {
        "id": 1,
        "title": "摩托车发动机维修手册",
        "source_name": "manual.pdf",
        "source_type": "manual",
        "equipment_type": "摩托车发动机",
        "equipment_model": "LX200",
        "fault_type": "启动困难",
        "status": "published",
        "chunk_count": 41,
        "section_reference": "第2章 点火系统",
        "page_reference": "P12",
        "content_excerpt": "火花塞检查与拆装步骤。",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.get_document_detail",
        new=AsyncMock(return_value=mocked_detail),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/documents/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_reference"] == "P12"
    assert payload["section_reference"] == "第2章 点火系统"


@pytest.mark.asyncio
async def test_get_knowledge_document_chunks_endpoint():
    """文档分段预览接口应返回前若干个知识分段。"""
    mocked_chunks = [
        {
            "id": 51,
            "chunk_index": 1,
            "heading": "火花塞检查",
            "content": "检查火花塞积碳和间隙。",
            "page_reference": "P1",
            "section_reference": "1.1",
            "section_path": "第1章 点火系统 > 1.1 火花塞检查",
            "step_anchor": "1. 检查火花塞积碳和间隙。",
            "image_anchor": None,
        }
    ]

    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.list_document_chunks",
        new=AsyncMock(return_value=mocked_chunks),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/documents/3/chunks?limit=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 3
    assert payload["chunks"][0]["chunk_id"] == 51
    assert payload["chunks"][0]["section_path"] == "第1章 点火系统 > 1.1 火花塞检查"
    assert payload["chunks"][0]["step_anchor"] == "1. 检查火花塞积碳和间隙。"


@pytest.mark.asyncio
async def test_get_knowledge_document_chunks_forwards_focus_chunk_id():
    """来源回看模式应把 focus_chunk_id 透传到服务层，确保命中 chunk 被包含在预览窗口里。"""
    with patch(
        "app.modules.knowledge.router.KnowledgeImportService.list_document_chunks",
        new=AsyncMock(return_value=[]),
    ) as mocked_list_chunks:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge/documents/3/chunks?limit=8&focus_chunk_id=51")

    assert response.status_code == 200
    mocked_list_chunks.assert_awaited_once_with(3, limit=8, focus_chunk_id=51)
