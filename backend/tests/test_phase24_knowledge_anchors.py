"""Phase 24: 层级化知识锚点与可定位检索测试."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services.knowledge_chunking import build_anchored_chunk_payloads
from app.services.knowledge_query_profile import infer_query_profile
from app.services.knowledge_rerank import rerank_results
from app.services.knowledge_service import KnowledgeService


def test_build_anchored_chunk_payloads_extracts_section_path_and_step_anchor():
    """结构化手册文本应提取章节路径、步骤锚点和图片锚点。"""
    content = """
    第2章 点火系统

    2.1 火花塞检查

    1. 先关闭点火开关并等待发动机冷却。

    2. 拆下火花塞帽，检查电极积碳和间隙。
    """.strip()

    payloads = build_anchored_chunk_payloads(
        content,
        title="LX200 点火系统手册",
        section_reference="点火系统",
        page_reference="P12",
        image_anchor_prefix="IMG1#OCR",
        max_chars=120,
    )

    assert payloads
    assert payloads[0]["section_reference"] == "2.1 火花塞检查"
    assert payloads[0]["section_path"] == "第2章 点火系统 > 2.1 火花塞检查"
    assert payloads[0]["page_reference"] == "P12"
    assert payloads[0]["image_anchor"] == "IMG1#OCR-1"
    assert any(payload.get("step_anchor") for payload in payloads)


def test_build_anchored_chunk_payloads_prefers_procedural_grouping_for_step_manual():
    """连续步骤型手册应按步骤锚点聚合，而不是退化为普通长段切分。"""
    content = """
    第3章 火花塞拆装

    3.1 拆卸步骤

    1. 关闭点火开关并等待发动机冷却。

    2. 拆下火花塞帽，检查高压帽接触情况。

    3. 使用套筒扳手逆时针旋出火花塞。
    """.strip()

    payloads = build_anchored_chunk_payloads(
        content,
        title="LX200 火花塞拆装手册",
        section_reference="火花塞拆装",
        page_reference="P18",
        max_chars=120,
    )

    assert len(payloads) >= 2
    assert payloads[0]["step_anchor"] == "1. 关闭点火开关并等待发动机冷却。"
    assert "3.1 拆卸步骤" in (payloads[0]["section_path"] or "")
    assert "关闭点火开关" in (payloads[0]["content"] or "")


def test_build_anchored_chunk_payloads_formats_install_engine_step_blocks():
    content = """
    三、发动机

    3.3 安装发动机

    3. 加注机油 从 发动机右曲轴箱盖加油口 加入：

    1600 mL 机油（若未更换机油精滤芯）

    1700 mL 机油（若已更换机油精滤芯） 机油规格要求：

    粘度：SAE 10W-40 或 SAE 10W-50 质量等级：API SM 级或以上
    """.strip()

    payloads = build_anchored_chunk_payloads(
        content,
        title="摩托车发动机维修手册",
        page_reference="P8",
        max_chars=220,
    )

    target = next(payload for payload in payloads if payload.get("step_anchor", "").startswith("3. 加注机油"))
    assert target["section_reference"] == "3.3 安装发动机"
    assert "从 发动机右曲轴箱盖加油口 加入：" in (target["content"] or "")
    assert "- 1600 mL 机油（若未更换机油精滤芯）" in (target["content"] or "")
    assert "- 1700 mL 机油（若已更换机油精滤芯）" in (target["content"] or "")
    assert "机油规格要求：" in (target["content"] or "")
    assert "- 粘度：SAE 10W-40 或 SAE 10W-50" in (target["content"] or "")


def test_build_anchored_chunk_payloads_formats_coolant_fill_step_as_bullets():
    content = """
    三、发动机

    3.3 安装发动机

    4. 加注冷却液 向 右水箱 加注冷却液，直至加满。

    启动发动机运行 8 ～ 10 秒后关机。

    再次向 右水箱 补液至满。

    向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间。
    """.strip()

    payloads = build_anchored_chunk_payloads(
        content,
        title="摩托车发动机维修手册",
        page_reference="P8",
        max_chars=220,
    )

    target = next(payload for payload in payloads if payload.get("step_anchor", "").startswith("4. 加注冷却液"))
    assert target["content"].splitlines()[0] == "4. 加注冷却液"
    assert "- 向 右水箱 加注冷却液，直至加满" in (target["content"] or "")
    assert "- 启动发动机运行 8 ～ 10 秒后关机" in (target["content"] or "")
    assert "- 再次向 右水箱 补液至满" in (target["content"] or "")
    assert "- 向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间" in (target["content"] or "")


def test_build_anchored_chunk_payloads_splits_dense_inline_inspection_items():
    content = """
    八、传动装置

    8.4 检查传动装置

    （ 1 ）检查拨叉 检查部位： 拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉 （ 2 ）检查传动主轴与副轴 检查传动主轴与副轴转动是否灵活： 若不灵活 → 重新安装 （ 3 ）检查换挡是否顺畅 装上 换档星形凸轮，检查换档是否顺畅： 若不顺畅 → 重新安装传动装置
    """.strip()

    payloads = build_anchored_chunk_payloads(
        content,
        title="摩托车发动机维修手册",
        page_reference="P36",
        max_chars=220,
    )

    inspection_payloads = [payload for payload in payloads if payload.get("section_reference") == "8.4 检查传动装置"]
    assert len(inspection_payloads) == 3
    assert inspection_payloads[0]["step_anchor"] == "（ 1 ）检查拨叉 检查部位： 拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉"
    assert inspection_payloads[1]["step_anchor"] == "（ 2 ）检查传动主轴与副轴 检查传动主轴与副轴转动是否灵活： 若不灵活 → 重新安装"
    assert inspection_payloads[2]["step_anchor"] == "（ 3 ）检查换挡是否顺畅 装上 换档星形凸轮，检查换档是否顺畅： 若不顺畅 → 重新安装传动装置"


def test_infer_query_profile_marks_procedural_queries_with_step_bias():
    """步骤类查询应落到 procedural profile，并提升步骤锚点权重。"""
    profile = infer_query_profile(
        query_bundle=["LX200 火花塞拆卸步骤", "标准步骤", "操作流程"],
        has_image=False,
    )

    assert profile.query_type == "procedural"
    assert profile.step_anchor_bonus > profile.section_path_bonus
    assert profile.modality_bonus["text"] >= profile.modality_bonus["ocr"]


def test_infer_query_profile_marks_short_action_object_queries_as_procedural():
    profile = infer_query_profile(
        query_bundle=["如何加注机油"],
        has_image=False,
    )

    assert profile.query_type == "procedural"


def test_infer_query_profile_marks_operation_order_query_as_procedural():
    profile = infer_query_profile(
        query_bundle=["拆下发动机操作顺序"],
        has_image=False,
    )

    assert profile.query_type == "procedural"


def test_rerank_results_prefers_step_anchor_for_procedural_query():
    """步骤型查询重排时，应优先带 step_anchor 的 procedure chunk。"""
    request = KnowledgeSearchRequest(
        query="LX200 火花塞拆卸步骤",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        limit=2,
    )
    profile = infer_query_profile(
        query_bundle=["LX200 火花塞拆卸步骤", "操作流程"],
        has_image=False,
    )

    candidates = [
        {
            "chunk_id": 1,
            "title": "LX200 火花塞拆卸流程",
            "source_type": "procedure",
            "equipment_model": "LX200",
            "fault_type": None,
            "section_reference": "3.1 拆卸步骤",
            "section_path": "第3章 火花塞拆装 > 3.1 拆卸步骤",
            "step_anchor": "2. 拆下火花塞帽，检查高压帽接触情况。",
            "excerpt": "2. 拆下火花塞帽，检查高压帽接触情况。",
            "expanded_content": "1. 关闭点火开关。\n2. 拆下火花塞帽，检查高压帽接触情况。\n3. 旋出火花塞。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.0,
            "score": 1.0,
        },
        {
            "chunk_id": 2,
            "title": "LX200 火花塞简介",
            "source_type": "manual",
            "equipment_model": "LX200",
            "fault_type": None,
            "section_reference": "基础说明",
            "section_path": None,
            "step_anchor": None,
            "excerpt": "火花塞用于点火，需定期检查。",
            "expanded_content": "火花塞用于点火，需定期检查。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.1,
            "score": 1.1,
        },
    ]

    reranked = rerank_results(request, candidates, query_profile=profile)

    assert reranked[0]["chunk_id"] == 1
    assert "命中步骤锚点" in reranked[0]["recommendation_reason"]


def test_rerank_results_penalizes_installation_and_irrelevant_checks_for_disassembly_query():
    """拆卸类查询应压低安装章节和无关检测章节。"""
    request = KnowledgeSearchRequest(
        query="拆卸发动机步骤",
        equipment_type="摩托车发动机",
        limit=3,
    )
    profile = infer_query_profile(
        query_bundle=["拆卸发动机步骤", "操作流程"],
        has_image=False,
    )

    candidates = [
        {
            "chunk_id": 5,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "3.2 拆卸发动机",
            "section_path": "三、发动机 > 3.2 拆卸发动机",
            "step_anchor": "2. 排放冷却液 拆下水泵盖上的放水螺栓，让冷却液自动流出。",
            "excerpt": "2. 排放冷却液 拆下水泵盖上的放水螺栓，让冷却液自动流出。",
            "expanded_content": "2. 排放冷却液...\n3. 松开发动机安装螺栓...",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.0,
            "score": 1.0,
        },
        {
            "chunk_id": 6,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "3.3 安装发动机",
            "section_path": "三、发动机 > 3.3 安装发动机",
            "step_anchor": "1. 按反向顺序安装。",
            "excerpt": "1. 按反向顺序安装。",
            "expanded_content": "1. 按反向顺序安装。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.1,
            "score": 1.1,
        },
        {
            "chunk_id": 7,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "1.4 测量压缩压力",
            "section_path": "1.2 检查火花塞 > 1.4 测量压缩压力",
            "step_anchor": None,
            "excerpt": "测量压缩压力前拆下火花塞。",
            "expanded_content": "500-900 kPa，测量压缩压力。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.2,
            "score": 1.2,
        },
    ]

    reranked = rerank_results(request, candidates, query_profile=profile)

    assert reranked[0]["chunk_id"] == 5
    assert reranked[-1]["chunk_id"] == 7
    assert any("与当前操作意图不一致" in item.get("recommendation_reason", "") for item in reranked[1:])


def test_rerank_results_penalizes_starter_motor_for_engine_install_query():
    request = KnowledgeSearchRequest(
        query="安装发动机步骤",
        equipment_type="摩托车发动机",
        limit=3,
    )
    profile = infer_query_profile(
        query_bundle=["安装发动机步骤", "操作流程"],
        has_image=False,
    )

    candidates = [
        {
            "chunk_id": 11,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "3.3 安装发动机",
            "section_path": "三、发动机 > 3.3 安装发动机",
            "step_anchor": "3. 加注机油 从 发动机右曲轴箱盖加油口 加入：",
            "excerpt": "3. 加注机油 从 发动机右曲轴箱盖加油口 加入：",
            "expanded_content": "2. 安装各类放油 / 放水螺栓\n3. 加注机油\n4. 加注冷却液",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.0,
            "score": 1.0,
        },
        {
            "chunk_id": 12,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "2.3 安装起动电机",
            "section_path": "二、起动电机 > 2.3 安装起动电机",
            "step_anchor": "2. 安装本体 将起动电机头部对准左盖孔。",
            "excerpt": "2. 安装本体 将起动电机头部对准左盖孔。",
            "expanded_content": "1. 安装起动电机\n2. 安装本体",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.05,
            "score": 1.05,
        },
    ]

    reranked = rerank_results(request, candidates, query_profile=profile)

    assert reranked[0]["chunk_id"] == 11
    assert reranked[1]["chunk_id"] == 12


def test_rerank_results_prefers_exact_inspection_section_over_installation_checks():
    request = KnowledgeSearchRequest(
        query="如何检查传动装置",
        equipment_type="摩托车发动机",
        limit=3,
    )
    profile = infer_query_profile(
        query_bundle=["如何检查传动装置"],
        has_image=False,
    )

    candidates = [
        {
            "chunk_id": 21,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "8.4 检查传动装置",
            "section_path": "八、传动装置 > 8.4 检查传动装置",
            "step_anchor": "（ 1 ）检查拨叉 检查部位：",
            "excerpt": "检查拨叉、卡爪是否弯曲、损坏或裂纹。",
            "expanded_content": "（ 1 ）检查拨叉\n检查部位：拨叉凸轮从动件、拨叉卡爪。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.0,
            "score": 1.0,
        },
        {
            "chunk_id": 22,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "8.5 安装传动装置",
            "section_path": "八、传动装置 > 8.5 安装传动装置",
            "step_anchor": "7. 装上 换档星形凸轮，检查换档是否顺畅：",
            "excerpt": "装上换档星形凸轮，检查换档是否顺畅。",
            "expanded_content": "7. 装上换档星形凸轮，检查换档是否顺畅：若不顺畅，重新安装传动装置。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.1,
            "score": 1.1,
        },
    ]

    reranked = rerank_results(request, candidates, query_profile=profile)

    assert reranked[0]["chunk_id"] == 21


def test_rerank_results_prefers_exact_object_section_for_cylinder_head_disassembly():
    request = KnowledgeSearchRequest(
        query="如何拆卸气缸头",
        equipment_type="摩托车发动机",
        limit=3,
    )
    profile = infer_query_profile(
        query_bundle=["如何拆卸气缸头"],
        has_image=False,
    )

    candidates = [
        {
            "chunk_id": 31,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "4.7 气缸头 拆卸气缸头",
            "section_path": "四、气缸头与气门 > 4.7 气缸头 拆卸气缸头",
            "step_anchor": "2. 按顺序松开以下紧固件：",
            "excerpt": "按顺序松开以下紧固件，取下气缸头。",
            "expanded_content": "1. 拆下凸轮轴。\n2. 按顺序松开以下紧固件。\n3. 取下：气缸头、导向条、缸体缸头垫片。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.0,
            "score": 1.0,
        },
        {
            "chunk_id": 32,
            "title": "摩托车发动机维修手册",
            "source_type": "manual",
            "equipment_model": None,
            "fault_type": None,
            "section_reference": "4.3 凸轮轴 拆卸凸轮轴",
            "section_path": "四、气缸头与气门 > 4.3 凸轮轴 拆卸凸轮轴",
            "step_anchor": "1. 拆卸气缸头盖及相关密封件",
            "excerpt": "拆卸气缸头盖及相关密封件。",
            "expanded_content": "1. 拆卸气缸头盖及相关密封件。\n3. 拆卸涨紧器。",
            "recommendation_reason": "命中关键词",
            "retrieval_score": 1.1,
            "score": 1.1,
        },
    ]

    reranked = rerank_results(request, candidates, query_profile=profile)

    assert reranked[0]["chunk_id"] == 31


def test_fuse_ranked_candidates_uses_rank_signal_instead_of_raw_score_scale():
    """融合阶段应按 rank 信号汇总，而不是被某一路夸张原始分数劫持。"""
    service = KnowledgeService(session=SimpleNamespace())
    profile = infer_query_profile(
        query_bundle=["拆卸发动机步骤", "操作流程"],
        has_image=False,
    )

    channels = {
        "sql": [
            {
                "chunk_id": 2,
                "title": "发动机拆卸标准步骤",
                "source_type": "manual",
                "retrieval_score": 0.1,
                "score": 0.1,
                "rerank_score": 0.1,
                "_retrieval_path": ["sql"],
            },
            {
                "chunk_id": 1,
                "title": "发动机说明",
                "source_type": "manual",
                "retrieval_score": 999.0,
                "score": 999.0,
                "rerank_score": 999.0,
                "_retrieval_path": ["sql"],
            },
        ],
        "vector": [
            {
                "chunk_id": 2,
                "title": "发动机拆卸标准步骤",
                "source_type": "manual",
                "retrieval_score": 0.2,
                "score": 0.2,
                "rerank_score": 0.2,
                "_retrieval_path": ["vector"],
            }
        ],
        "bm25": [],
    }

    fused = service._fuse_ranked_candidates(channels=channels, query_profile=profile)

    assert fused[0]["chunk_id"] == 2


def _fake_chunk() -> SimpleNamespace:
    return SimpleNamespace(
        id=81,
        heading="2.1 火花塞检查",
        content="1. 先关闭点火开关。2. 拆下火花塞帽并检查积碳。",
        equipment_type="摩托车发动机",
        equipment_model="LX200",
        fault_type="启动困难",
        section_reference="2.1 火花塞检查",
        section_path="第2章 点火系统 > 2.1 火花塞检查",
        step_anchor="2. 拆下火花塞帽并检查积碳。",
        page_reference="P12",
        image_anchor=None,
    )


def _fake_document() -> SimpleNamespace:
    return SimpleNamespace(
        id=18,
        title="LX200 点火系统检修手册",
        source_name="manual-lx200.pdf",
        source_type="manual",
        equipment_model="LX200",
        fault_type="启动困难",
        section_reference="第2章 点火系统",
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_search_results_include_hierarchical_anchor_fields():
    """检索结果应把层级锚点透传给前端做定位跳转。"""
    fake_bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    fake_result = SimpleNamespace(all=lambda: [(_fake_chunk(), _fake_document(), 4.8)])
    mock_session = SimpleNamespace(
        get_bind=lambda: fake_bind,
        execute=AsyncMock(return_value=fake_result),
    )

    service = KnowledgeService(session=mock_session)
    results = await service.search(
        KnowledgeSearchRequest(
            query="LX200 火花塞检查",
            equipment_type="摩托车发动机",
            equipment_model="LX200",
            fault_type="启动困难",
            limit=1,
        )
    )

    assert len(results) == 1
    assert results[0]["section_path"] == "第2章 点火系统 > 2.1 火花塞检查"
    assert results[0]["step_anchor"] == "2. 拆下火花塞帽并检查积碳。"
    assert results[0]["page_reference"] == "P12"


def test_apply_metadata_filters_accepts_equipment_type_alias_via_document_title():
    service = KnowledgeService(session=SimpleNamespace())
    stmt = select(KnowledgeChunk, KnowledgeDocument).join(
        KnowledgeDocument,
        KnowledgeChunk.document_id == KnowledgeDocument.id,
    )

    filtered = service._apply_metadata_filters(
        stmt,
        KnowledgeSearchRequest(
            query="拆卸发动机步骤",
            equipment_type="摩托车发动机",
        ),
    )
    compiled = str(filtered)

    assert "knowledge_documents.title" in compiled
    assert "lower(:title_1)" in compiled or "lower(:title_2)" in compiled
    assert "knowledge_documents.source_name" in compiled


@pytest.mark.asyncio
async def test_refine_procedural_results_expands_same_section_chunks():
    rows = [
        (
            SimpleNamespace(
                id=628,
                document_id=8,
                heading="3.2 拆卸发动机",
                content="1. 排放机油 拆下发动机左曲轴箱上的放油螺栓。",
                equipment_type="摩托车",
                equipment_model=None,
                fault_type=None,
                section_reference="3.2 拆卸发动机",
                section_path="三、发动机 > 3.2 拆卸发动机",
                step_anchor="1. 排放机油",
                page_reference="P6",
                image_anchor=None,
                source_modality=None,
                ocr_text=None,
                image_caption=None,
                evidence_summary=None,
                chunk_index=21,
            ),
            SimpleNamespace(
                id=8,
                title="摩托车发动机维修手册",
                source_name="摩托车发动机维修手册.pdf",
                source_type="manual",
                equipment_type="摩托车",
                equipment_model=None,
                fault_type=None,
                section_reference=None,
                page_reference=None,
                updated_at=None,
            ),
        ),
        (
            SimpleNamespace(
                id=629,
                document_id=8,
                heading="3.2 拆卸发动机",
                content="2. 排放冷却液 拆下水泵盖上的放水螺栓。",
                equipment_type="摩托车",
                equipment_model=None,
                fault_type=None,
                section_reference="3.2 拆卸发动机",
                section_path="三、发动机 > 3.2 拆卸发动机",
                step_anchor="2. 排放冷却液",
                page_reference="P7",
                image_anchor=None,
                source_modality=None,
                ocr_text=None,
                image_caption=None,
                evidence_summary=None,
                chunk_index=22,
            ),
            SimpleNamespace(
                id=8,
                title="摩托车发动机维修手册",
                source_name="摩托车发动机维修手册.pdf",
                source_type="manual",
                equipment_type="摩托车",
                equipment_model=None,
                fault_type=None,
                section_reference=None,
                page_reference=None,
                updated_at=None,
            ),
        ),
    ]
    mock_session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
    )
    service = KnowledgeService(session=mock_session)
    request = KnowledgeSearchRequest(query="拆卸发动机步骤", limit=5)
    profile = infer_query_profile(query_bundle=["拆卸发动机步骤", "操作流程"], has_image=False)

    results = await service._refine_procedural_results(
        request,
        [
            {
                "chunk_id": 631,
                "document_id": 8,
                "title": "摩托车发动机维修手册",
                "source_name": "摩托车发动机维修手册.pdf",
                "source_type": "manual",
                "equipment_type": "摩托车",
                "equipment_model": None,
                "fault_type": None,
                "section_reference": "3.2 拆卸发动机",
                "section_path": "三、发动机 > 3.2 拆卸发动机",
                "excerpt": "4. 拆卸输出链轮组件。",
                "recommendation_reason": "命中关键词",
                "retrieval_score": 0.21,
                "rerank_score": 4.21,
                "score": 4.21,
            },
            {
                "chunk_id": 703,
                "document_id": 8,
                "title": "摩托车发动机维修手册",
                "source_name": "摩托车发动机维修手册.pdf",
                "source_type": "manual",
                "equipment_type": "摩托车",
                "equipment_model": None,
                "fault_type": None,
                "section_reference": "6.5 机油泵 拆卸机油泵",
                "section_path": "四、气缸头与气门 > 6.5 机油泵 拆卸机油泵",
                "excerpt": "拆卸机油泵。",
                "recommendation_reason": "命中关键词",
                "retrieval_score": 0.22,
                "rerank_score": 3.22,
                "score": 3.22,
            },
        ],
        query_profile=profile,
    )

    assert [item["chunk_id"] for item in results[:2]] == [628, 629]
    assert all(item["section_reference"] == "3.2 拆卸发动机" for item in results[:2])


@pytest.mark.asyncio
async def test_refine_procedural_results_keeps_single_step_scope_for_fill_oil_query():
    service = KnowledgeService(session=SimpleNamespace())
    request = KnowledgeSearchRequest(query="如何加注机油", limit=5)
    profile = infer_query_profile(query_bundle=["如何加注机油"], has_image=False)

    results = await service._refine_procedural_results(
        request,
        [
            {
                "chunk_id": 801,
                "document_id": 8,
                "title": "摩托车发动机维修手册",
                "source_name": "摩托车发动机维修手册.pdf",
                "source_type": "manual",
                "equipment_type": "摩托车",
                "equipment_model": None,
                "fault_type": None,
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "step_anchor": "3. 加注机油 从 发动机右曲轴箱盖加油口 加入：",
                "excerpt": "3. 加注机油 从 发动机右曲轴箱盖加油口 加入：",
                "expanded_content": "3. 加注机油\n4. 加注冷却液",
                "recommendation_reason": "命中关键词",
                "retrieval_score": 2.0,
                "rerank_score": 5.0,
                "score": 5.0,
            },
            {
                "chunk_id": 802,
                "document_id": 8,
                "title": "摩托车发动机维修手册",
                "source_name": "摩托车发动机维修手册.pdf",
                "source_type": "manual",
                "equipment_type": "摩托车",
                "equipment_model": None,
                "fault_type": None,
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "step_anchor": "4. 加注冷却液 向 右水箱 加注冷却液，直至加满。",
                "excerpt": "4. 加注冷却液 向 右水箱 加注冷却液，直至加满。",
                "expanded_content": "4. 加注冷却液",
                "recommendation_reason": "命中关键词",
                "retrieval_score": 1.9,
                "rerank_score": 4.8,
                "score": 4.8,
            },
        ],
        query_profile=profile,
    )

    assert [item["chunk_id"] for item in results[:1]] == [801]


@pytest.mark.asyncio
async def test_expand_chunk_context_does_not_cross_section_boundaries():
    rows = [
        SimpleNamespace(
            id=634,
            content="2. 安装各类放油 / 放水螺栓",
            chunk_index=27,
            section_path="三、发动机 > 3.3 安装发动机",
            section_reference="3.3 安装发动机",
        ),
        SimpleNamespace(
            id=635,
            content="3. 加注机油",
            chunk_index=28,
            section_path="三、发动机 > 3.3 安装发动机",
            section_reference="3.3 安装发动机",
        ),
        SimpleNamespace(
            id=636,
            content="4. 加注冷却液",
            chunk_index=29,
            section_path="三、发动机 > 3.3 安装发动机",
            section_reference="3.3 安装发动机",
        ),
    ]
    mock_session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
    )
    service = KnowledgeService(session=mock_session)

    expanded = await service._expand_chunk_context(
        chunk_id=635,
        document_id=8,
        section_path="三、发动机 > 3.3 安装发动机",
        section_reference="3.3 安装发动机",
        window=1,
    )

    assert "2. 安装各类放油 / 放水螺栓" in expanded
    assert "3. 加注机油" in expanded
    assert "4. 加注冷却液" in expanded
    assert "气缸头" not in expanded
