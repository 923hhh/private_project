"""OCR helpers for scanned manuals and image-based knowledge uploads."""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from app.services.image_analysis_service import FaultImageAnalysisService

try:
    from langchain_core.messages import HumanMessage
except ImportError:  # pragma: no cover - langchain-core is already required
    HumanMessage = None


@dataclass
class ImageOcrResult:
    """OCR result for one uploaded image or scanned page."""

    recognized_text: str
    summary: str
    keywords: list[str]
    source: str
    warning: str | None = None


class KnowledgeOcrService:
    """Extract readable text from uploaded knowledge images via multimodal OCR."""

    def __init__(self) -> None:
        self.image_analysis_service = FaultImageAnalysisService()

    async def extract_text(
        self,
        *,
        image_bytes: bytes,
        image_mime_type: str,
        image_filename: str | None,
        equipment_type: str | None,
        equipment_model: str | None,
        title: str | None,
        section_reference: str | None,
        model_provider: str = "openai",
        model_name: str | None = None,
    ) -> ImageOcrResult:
        """Extract OCR text from one uploaded knowledge image."""
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        llm = self.image_analysis_service._create_multimodal_llm(  # noqa: SLF001
            model_provider=model_provider,
            model_name=model_name,
        )
        if llm is None or HumanMessage is None:
            return self._build_fallback(
                image_filename=image_filename,
                equipment_type=equipment_type,
                equipment_model=equipment_model,
                title=title,
                section_reference=section_reference,
                warning="当前环境不可用视觉 OCR，已退化为文件名和元数据生成导入文本，请导入后人工校对。",
            )

        prompt = (
            "你是设备检修知识系统的 OCR 预处理器。"
            "请识别图片中的检修标题、步骤、注意事项和可见术语。"
            "只返回 JSON，格式为 "
            "{\"recognized_text\":\"...\", \"summary\":\"...\", \"keywords\":[\"...\", \"...\"]}。"
            "recognized_text 尽量保留完整可读文本，summary 控制在 50 字以内，"
            "keywords 返回 3 到 8 个检修术语、部件名或故障词。"
        )

        context_parts = []
        if title:
            context_parts.append(f"文档标题：{title}")
        if equipment_type:
            context_parts.append(f"设备类型：{equipment_type}")
        if equipment_model:
            context_parts.append(f"设备型号：{equipment_model}")
        if section_reference:
            context_parts.append(f"章节说明：{section_reference}")
        if context_parts:
            prompt = f"{prompt}\n\n已知上下文：{'；'.join(context_parts)}"

        content = self.image_analysis_service._build_message_content(  # noqa: SLF001
            model_provider=model_provider,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
            query=prompt,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=content)])
        except Exception:
            return self._build_fallback(
                image_filename=image_filename,
                equipment_type=equipment_type,
                equipment_model=equipment_model,
                title=title,
                section_reference=section_reference,
                warning="视觉 OCR 调用失败，已退化为文件名和元数据生成导入文本，请导入后人工校对。",
            )

        response_text = self.image_analysis_service._extract_response_text(response.content)  # noqa: SLF001
        payload = self._parse_model_response(response_text)
        if payload is None:
            return self._build_fallback(
                image_filename=image_filename,
                equipment_type=equipment_type,
                equipment_model=equipment_model,
                title=title,
                section_reference=section_reference,
                warning="视觉 OCR 响应未能稳定解析，已退化为文件名和元数据生成导入文本，请导入后人工校对。",
            )

        recognized_text = str(payload.get("recognized_text") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        keywords = self.image_analysis_service._normalize_keywords(  # noqa: SLF001
            list(payload.get("keywords") or [])
        )

        if not recognized_text:
            return self._build_fallback(
                image_filename=image_filename,
                equipment_type=equipment_type,
                equipment_model=equipment_model,
                title=title,
                section_reference=section_reference,
                warning="视觉 OCR 未返回可用文本，已退化为文件名和元数据生成导入文本，请导入后人工校对。",
            )

        if not keywords:
            keywords = self.image_analysis_service._extract_keywords(recognized_text)  # noqa: SLF001

        return ImageOcrResult(
            recognized_text=recognized_text,
            summary=summary or "图片已通过视觉 OCR 提取为可导入知识文本。",
            keywords=keywords,
            source="vision_model",
        )

    def _build_fallback(
        self,
        *,
        image_filename: str | None,
        equipment_type: str | None,
        equipment_model: str | None,
        title: str | None,
        section_reference: str | None,
        warning: str,
    ) -> ImageOcrResult:
        filename_stem = (image_filename or "未命名图片").rsplit(".", maxsplit=1)[0]
        keywords = self.image_analysis_service._extract_keywords(filename_stem)  # noqa: SLF001
        context_lines = [
            f"文档标题：{title or filename_stem}",
            f"来源文件：{image_filename or '未命名图片'}",
            f"设备类型：{equipment_type or '未提供'}",
        ]
        if equipment_model:
            context_lines.append(f"设备型号：{equipment_model}")
        if section_reference:
            context_lines.append(f"章节说明：{section_reference}")
        if keywords:
            context_lines.append(f"文件名推断关键词：{'、'.join(keywords)}")
        context_lines.append("当前导入文本为 OCR 回退结果，请在导入后结合原图进行人工校对。")

        return ImageOcrResult(
            recognized_text="\n".join(context_lines),
            summary="图片已按回退模式生成可导入文本，建议后续人工校对。",
            keywords=keywords,
            source="fallback",
            warning=warning,
        )

    def _parse_model_response(self, text: str) -> dict[str, Any] | None:
        if not text.strip():
            return None
        json_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        candidate = json_match.group(0) if json_match else text
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload
