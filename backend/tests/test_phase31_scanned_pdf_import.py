"""扫描件 PDF：文本层为空时走逐页渲染 + OCR 回退。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_import_service import KnowledgeImportService
from app.services.ocr_service import ImageOcrResult


@pytest.mark.asyncio
async def test_prepare_upload_content_scanned_pdf_uses_page_ocr():
    session = MagicMock()
    svc = KnowledgeImportService(session)
    with patch.object(
        svc.importer,
        "extract_pages_from_bytes",
        side_effect=ValueError("未从 PDF 中提取到可用文本"),
    ):
        with patch(
            "app.modules.knowledge.application.import_service.render_pdf_pages_as_png_bytes",
            return_value=[b"\x89PNG\r\n\x1a\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"],
        ):
            with patch.object(
                svc.ocr_service,
                "extract_text",
                new=AsyncMock(
                    return_value=ImageOcrResult(
                        recognized_text="火花塞检查要点",
                        summary="摘要",
                        keywords=["火花塞"],
                        source="vision_model",
                    )
                ),
            ):
                prepared = await svc._prepare_upload_content(
                    import_type="pdf",
                    filename="scan.pdf",
                    file_bytes=b"%PDF-1.4",
                    content_type="application/pdf",
                    title="手册",
                    equipment_type="摩托车发动机",
                    equipment_model=None,
                    fault_type=None,
                    section_reference=None,
                )
    assert prepared["final_import_type"] == "pdf_scanned_ocr"
    assert prepared["page_count"] == 1
    assert "火花塞检查要点" in prepared["content"]
    assert len(prepared["chunk_payloads"]) >= 1
    assert prepared["chunk_payloads"][0]["source_modality"] == "ocr"


def test_render_pdf_pages_returns_empty_without_pymupdf_bytes():
    """非 PDF 字节不应误解析出页（返回空列表由上层决定错误提示）。"""
    from app.services.knowledge_import_service import render_pdf_pages_as_png_bytes

    assert render_pdf_pages_as_png_bytes(b"not a pdf") == []


@pytest.mark.asyncio
async def test_get_document_detail_builds_document_level_summary():
    session = MagicMock()
    svc = KnowledgeImportService(session)
    document = SimpleNamespace(
        id=9,
        title="摩托车发动机维修手册",
        source_name="manual.pdf",
        source_type="manual",
        equipment_type="摩托车",
        equipment_model="LX200",
        fault_type="火花塞检查",
        status="published",
        section_reference="1.2 检查火花塞",
        page_reference="第3页",
        created_at=None,
        updated_at=None,
        content="旧的原文截断不应该再直接展示在摘要里。",
    )
    preview_chunks = [
        SimpleNamespace(
            chunk_index=1,
            heading="1.2 检查火花塞",
            step_anchor=None,
            section_reference="1.2 检查火花塞",
            section_path=None,
            content="检查火花塞螺纹以及中心电极，若有损坏或变形，则应更换火花塞。",
        ),
        SimpleNamespace(
            chunk_index=2,
            heading="1.3 安装火花塞",
            step_anchor=None,
            section_reference="1.3 安装火花塞",
            section_path=None,
            content="用套筒顺时针转动预紧，然后再转动四分之一圈，并按扭矩要求拧紧。",
        ),
    ]

    session.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one=lambda: 2),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: preview_chunks)),
        ]
    )
    svc._ensure_document = AsyncMock(return_value=document)

    payload = await svc.get_document_detail(9)

    assert payload["content_excerpt"] is not None
    assert "文档用途：摩托车发动机维修手册是一份面向摩托车、LX200、火花塞检查的检修指导资料" in payload["content_excerpt"]
    assert "主要覆盖模块：文档主要覆盖检查火花塞、安装火花塞等系统或部件的维修内容" in payload["content_excerpt"]
    assert "可用于哪些检修/诊断场景：可用于检查、安装等检修流程" in payload["content_excerpt"]
