"""Query profiling helpers for multimodal maintenance retrieval."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.knowledge_query_rewrite import analyze_procedural_query


IMAGE_QUERY_HINTS = (
    "图片",
    "图像",
    "照片",
    "截图",
    "图中",
    "看图",
    "外观",
    "裂纹",
    "渗漏",
    "磨损",
    "烧蚀",
)
TEXT_QUERY_HINTS = (
    "步骤",
    "流程",
    "手册",
    "标准",
    "检修",
    "操作",
    "注意事项",
    "怎么拆",
    "怎么装",
)
PROCEDURAL_QUERY_HINTS = (
    "步骤",
    "流程",
    "顺序",
    "拆卸",
    "拆下",
    "安装",
    "更换",
    "检查",
    "加注",
    "排放",
    "松开",
    "取下",
    "检查方法",
    "操作指引",
    "怎么拆",
    "怎么装",
    "如何更换",
)
PROCEDURAL_ACTION_HINTS = (
    "拆下",
    "拆卸",
    "安装",
    "更换",
    "检查",
    "加注",
    "排放",
    "松开",
    "取下",
    "检查方法",
    "操作指引",
    "怎么拆",
    "怎么装",
    "如何更换",
)


@dataclass(frozen=True)
class KnowledgeQueryProfile:
    query_type: str
    preferred_modalities: tuple[str, ...]
    retrieval_path_tag: str
    modality_bonus: dict[str, float]
    step_anchor_bonus: float = 0.0
    section_path_bonus: float = 0.0
    source_type_bonus: dict[str, float] | None = None


def infer_query_profile(
    *,
    query_bundle: list[str],
    has_image: bool,
) -> KnowledgeQueryProfile:
    combined = " ".join(item.strip().lower() for item in query_bundle if item.strip())
    procedural_analysis = analyze_procedural_query(query_bundle[0] if query_bundle else "")
    image_hits = sum(1 for hint in IMAGE_QUERY_HINTS if hint in combined)
    text_hits = sum(1 for hint in TEXT_QUERY_HINTS if hint in combined)
    procedural_hits = sum(1 for hint in PROCEDURAL_QUERY_HINTS if hint in combined)
    procedural_action_hits = sum(1 for hint in PROCEDURAL_ACTION_HINTS if hint in combined)

    if has_image and combined:
        return KnowledgeQueryProfile(
            query_type="multimodal_joint",
            preferred_modalities=("ocr", "vision", "image", "text"),
            retrieval_path_tag="query_profile:multimodal_joint",
            modality_bonus={"ocr": 0.08, "vision": 0.06, "image": 0.05, "text": 0.05},
            step_anchor_bonus=0.05,
            section_path_bonus=0.04,
            source_type_bonus={"manual": 0.05, "procedure": 0.07, "case": 0.02},
        )
    if procedural_analysis.is_procedural or (
        procedural_hits > 0 and (procedural_action_hits > 0 or procedural_hits >= max(1, text_hits - 1))
    ):
        return KnowledgeQueryProfile(
            query_type="procedural",
            preferred_modalities=("text", "ocr", "vision", "image"),
            retrieval_path_tag="query_profile:procedural",
            modality_bonus={"text": 0.07, "ocr": 0.04, "vision": 0.02, "image": 0.02},
            step_anchor_bonus=0.12,
            section_path_bonus=0.08,
            source_type_bonus={"procedure": 0.12, "manual": 0.08, "case": 0.03},
        )
    if has_image or image_hits > text_hits:
        return KnowledgeQueryProfile(
            query_type="image_related",
            preferred_modalities=("ocr", "vision", "image", "text"),
            retrieval_path_tag="query_profile:image_related",
            modality_bonus={"ocr": 0.1, "vision": 0.08, "image": 0.06, "text": 0.02},
            step_anchor_bonus=0.03,
            section_path_bonus=0.03,
            source_type_bonus={"manual": 0.04, "procedure": 0.04, "case": 0.03},
        )
    return KnowledgeQueryProfile(
        query_type="text_related",
        preferred_modalities=("text", "ocr", "vision", "image"),
        retrieval_path_tag="query_profile:text_related",
        modality_bonus={"text": 0.06, "ocr": 0.03, "vision": 0.01, "image": 0.01},
        step_anchor_bonus=0.04,
        section_path_bonus=0.05,
        source_type_bonus={"manual": 0.05, "procedure": 0.06, "case": 0.03},
    )


def build_query_bundle(
    *,
    query: str | None,
    effective_keywords: list[str],
    image_summary: str | None,
    equipment_model: str | None,
) -> list[str]:
    bundle: list[str] = []
    for item in [query or "", *effective_keywords, equipment_model or "", image_summary or ""]:
        normalized = item.strip()
        if normalized and normalized not in bundle:
            bundle.append(normalized)

    expanded: list[str] = list(bundle)
    if any(term in " ".join(bundle).lower() for term in ("图片", "图像", "照片", "ocr", "裂纹", "渗漏")):
        for item in bundle[:2]:
            if "图片内容" not in item:
                expanded.append(f"{item} 图片内容")
            if "故障图片" not in item:
                expanded.append(f"{item} 故障图片")

    deduped: list[str] = []
    for item in expanded:
        normalized = item.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped
