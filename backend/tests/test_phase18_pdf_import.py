"""Phase 18: PDF 知识导入辅助能力测试."""
from app.services.pdf_import_service import (
    ExtractedPdfPage,
    PdfKnowledgeImportService,
    _trim_leading_toc_prelude,
    _is_toc_page,
    normalize_pdf_text,
)


def test_normalize_pdf_text_merges_wrapped_lines():
    """PDF 提取结果中的换行和空白会被规范化为稳定段落。"""
    raw_text = "  发动机启动困难 \n 常见原因包括火花塞积碳 \n\n 需要检查点火系统。  "

    normalized = normalize_pdf_text(raw_text)

    assert normalized == "发动机启动困难 常见原因包括火花塞积碳\n\n需要检查点火系统。"


def test_build_chunk_payloads_preserves_page_references():
    """基于页面文本构造的知识分段应保留页码引用。"""
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(page_number=2, text="点火系统检修步骤。"),
        ExtractedPdfPage(page_number=3, text="供油系统检查要点。"),
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=20)

    assert len(payloads) == 2
    assert payloads[0]["page_reference"] == "P2"
    assert payloads[1]["page_reference"] == "P3"
    assert payloads[0]["heading"] == "摩托车发动机维修手册 - 第 2 页"


def test_normalize_pdf_text_splits_inline_heading_boundaries():
    """页尾混入下一节标题时，应切成独立段落，避免污染当前 chunk。"""
    raw_text = (
        "锁止螺母拧紧力矩：95 ± 5 N·m 所需工具：27# 套筒 3.3 安装发动机 1. 按反向顺序安装。 "
        "向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间。 四、气缸头与气门 4.1 气缸头装配部件清单"
    )

    normalized = normalize_pdf_text(raw_text)

    assert "3.3 安装发动机" in normalized
    assert "\n\n四、气缸头与气门\n\n4.1 气缸头装配部件清单" in normalized


def test_build_chunk_payloads_inherits_terminal_heading_context_across_pages():
    """页面只以纯标题收尾时，下一页仍应继承更新后的章节路径。"""
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(page_number=8, text="四、气缸头与气门\n\n4.1 气缸头装配部件清单"),
        ExtractedPdfPage(page_number=9, text="1. 检查气缸头部件是否齐全。"),
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=120)

    assert len(payloads) == 1
    assert payloads[0]["section_path"] == "四、气缸头与气门 > 4.1 气缸头装配部件清单"


def test_build_chunk_payloads_keeps_section_path_for_cross_page_procedural_continuation():
    """跨页延续的步骤块即使没有新标题，也应继承上一页的 section_path。"""
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(
            page_number=6,
            text=(
                "三、发动机\n\n3.2 拆卸发动机\n\n"
                "1. 排放机油 拆下发动机左曲轴箱上的放油螺栓，将发动机内部机油全部放出。"
            ),
        ),
        ExtractedPdfPage(
            page_number=7,
            text=(
                "2. 排放冷却液 拆下水泵盖上的放水螺栓，让冷却液自动流出。\n\n"
                "3. 松开发动机安装螺栓 依次松开上吊片、托架、后平叉轴。"
            ),
        ),
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=180)

    assert len(payloads) >= 2
    assert payloads[1]["section_path"] == "三、发动机 > 3.2 拆卸发动机"
    assert payloads[1]["section_reference"] == "3.2 拆卸发动机"


def test_build_chunk_payloads_merges_page_leading_tail_into_previous_section():
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(
            page_number=7,
            text=(
                "3.2 拆卸发动机\n\n"
                "4. 拆卸输出链轮组件 用一字螺丝刀将 锁止片 2 敲平。\n\n"
                "松开 锁止螺母 1 并依次取下：\n\n"
                "螺母 1 锁止片 2 输出链轮 3 轴套 4"
            ),
        ),
        ExtractedPdfPage(
            page_number=8,
            text=(
                "锁止螺母拧紧力矩：95 ± 5 N·m 所需工具：27# 套筒\n\n"
                "3.3 安装发动机\n\n"
                "1. 按反向顺序安装 安装顺序与拆卸顺序相反。"
            ),
        ),
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=220)

    assert len(payloads) == 2
    assert payloads[0]["section_reference"] == "3.2 拆卸发动机"
    assert "锁止螺母拧紧力矩：95 ± 5 N·m" in (payloads[0]["content"] or "")
    assert payloads[1]["section_reference"] == "3.3 安装发动机"


def test_build_chunk_payloads_trim_compact_section_heading_label():
    """紧贴正文的小节标题应裁成稳定 heading，而不是整句都做 section label。"""
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(
            page_number=14,
            text="4.6 气门间隙 测量气门间隙 拆下气缸头盖。\n\n将塞尺插入凸轮轴基圆与滑动挺柱之间测量间隙。",
        )
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=180)

    assert len(payloads) == 1
    assert payloads[0]["section_reference"] == "4.6 气门间隙 测量气门间隙"


def test_build_chunk_payloads_flushes_previous_step_when_section_changes():
    service = PdfKnowledgeImportService()
    pages = [
        ExtractedPdfPage(
            page_number=36,
            text=(
                "8.3 拆卸传动装置\n\n"
                "4. 依次取下以下部件： 换挡轴 拨叉轴 变速鼓 拨叉 传动主轴 传动副轴\n\n"
                "8.4 检查传动装置\n\n"
                "（ 1 ）检查拨叉 检查部位：\n\n"
                "拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉"
            ),
        )
    ]

    payloads = service.build_chunk_payloads("摩托车发动机维修手册", pages, max_chars=480)

    assert len(payloads) == 2
    assert payloads[0]["section_reference"] == "8.3 拆卸传动装置"
    assert payloads[0]["step_anchor"] == "4. 依次取下以下部件： 换挡轴 拨叉轴 变速鼓 拨叉 传动主轴 传动副轴"
    assert "检查拨叉" not in (payloads[0]["content"] or "")
    assert payloads[1]["section_reference"] == "8.4 检查传动装置"
    assert payloads[1]["step_anchor"] == "（ 1 ）检查拨叉 检查部位："


def test_is_toc_page_keeps_step_numbered_manual_pages():
    text = (
        "8.3 拆卸传动装置\n\n"
        "1. 松开固定起动电机螺栓，拆卸起动电机。\n\n"
        "2. 松开箱体所有螺栓：先松右曲轴箱上的 M6×30 螺栓。"
    )

    assert _is_toc_page(text) is False


def test_is_toc_page_detects_heading_heavy_catalog_page():
    text = (
        "目录\n\n"
        "第一章 总则 ........ 1\n\n"
        "第二章 检修流程 ........ 5\n\n"
        "第三章 扭矩表 ........ 12\n\n"
        "第四章 常见故障 ........ 18"
    )

    assert _is_toc_page(text) is True


def test_trim_leading_toc_prelude_keeps_only_actual_content_part():
    text = (
        "8.3 拆卸传动装置\n\n"
        "8.4 检查传动装置\n\n"
        "8.5 安装传动装置\n\n"
        "一、火花塞\n\n"
        "1.1 拆卸火花塞\n\n"
        "1. 用尖嘴钳将高压帽拔出。\n\n"
        "2. 用火花塞专用套筒将火花塞拆下。"
    )

    trimmed = _trim_leading_toc_prelude(text)

    assert trimmed.startswith("一、火花塞")
    assert "8.3 拆卸传动装置" not in trimmed
