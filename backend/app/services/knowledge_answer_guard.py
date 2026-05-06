"""Grounding and coverage checks for knowledge retrieval results."""
from __future__ import annotations

from typing import Any


STEP_HINTS = ("步骤", "流程", "拆卸", "安装", "检查", "调整")


def build_grounding_assessment(
    *,
    request_query: str | None,
    query_type: str,
    results: list[dict[str, Any]],
    image_analysis_used: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    if not results:
        warnings.append("当前未命中可直接引用的知识片段，请补充设备型号、故障现象或上传更清晰图片。")
        return {
            "grounded": False,
            "answer_confidence": 0.0,
            "coverage_warnings": warnings,
        }

    top_score = float(results[0].get("rerank_score") or results[0].get("retrieval_score") or 0.0)
    grounded = bool(top_score > 0.12)
    if not grounded:
        warnings.append("当前命中依据较弱，建议补充更具体的故障描述或检修图片。")

    query = (request_query or "").strip()
    if any(hint in query for hint in STEP_HINTS):
        step_results = [item for item in results[:3] if item.get("step_anchor")]
        if not step_results:
            grounded = False
            warnings.append("这是步骤类问题，但当前结果缺少明确步骤锚点。")

    if query_type == "multimodal_joint":
        has_image_side = any((item.get("source_modality") or "") in {"ocr", "vision", "image"} for item in results)
        has_text_side = any((item.get("source_modality") or "") == "text" for item in results)
        if not (has_image_side and has_text_side):
            grounded = False
            warnings.append("图文联合问题当前未同时覆盖图片线索和手册依据。")

    if query_type == "image_related" and image_analysis_used:
        has_image_evidence = any((item.get("source_modality") or "") in {"ocr", "vision", "image"} for item in results)
        if not has_image_evidence:
            grounded = False
            warnings.append("已解析图片，但结果仍未命中图片/OCR侧证据。")

    confidence = min(1.0, max(0.0, top_score))
    if grounded and len(results) >= 2:
        confidence = min(1.0, confidence + 0.12)
    if query_type == "multimodal_joint" and grounded:
        confidence = min(1.0, confidence + 0.08)

    return {
        "grounded": grounded,
        "answer_confidence": round(confidence, 4),
        "coverage_warnings": warnings,
    }
