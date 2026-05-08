"""Image-assisted retrieval helpers for TODO-SB-3."""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_LangChainOpenAI = None
_LangChainAnthropic = None

try:
    from langchain_openai import ChatOpenAI as LangChainOpenAI
except ImportError:
    pass

try:
    from langchain_anthropic import ChatAnthropic as LangChainAnthropic
except ImportError:
    pass

try:
    from langchain_core.messages import HumanMessage
except ImportError:  # pragma: no cover - langchain-core is already required
    HumanMessage = None


MAX_IMAGE_BYTES = 4 * 1024 * 1024
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
_IGNORE_TOKENS = {
    "img",
    "image",
    "photo",
    "picture",
    "jpeg",
    "jpg",
    "png",
    "webp",
    "故障",
    "上传",
}
_ALIAS_KEYWORDS = {
    "spark": "火花塞",
    "plug": "火花塞",
    "ignition": "点火系统",
    "coil": "点火线圈",
    "wire": "点火线束",
    "wiring": "点火线束",
    "idle": "怠速不稳",
    "starter": "起动电机",
    "motor": "起动电机",
    "timing": "正时链条",
    "chain": "正时链条",
    "tensioner": "张紧器",
    "oil": "机油",
    "leak": "机油渗漏",
    "seal": "油封",
    "gasket": "缸盖垫片",
    "temperature": "温度偏高",
    "overheat": "温度偏高",
    "smoke": "排气冒黑烟",
    "black": "排气冒黑烟",
    "throttle": "节气门",
    "carbon": "积碳",
}
_COMPOSITE_HINTS = [
    (("spark", "plug"), ["火花塞"]),
    (("timing", "chain"), ["正时链条"]),
    (("oil", "leak"), ["机油渗漏"]),
    (("starter", "motor"), ["起动电机"]),
    (("black", "smoke"), ["排气冒黑烟"]),
]


@dataclass
class ImageAnalysisResult:
    """Internal image analysis result."""

    summary: str
    keywords: list[str]
    source: str
    warning: str | None = None


class FaultImageAnalysisService:
    """Analyze a single fault image and turn it into retrieval hints."""

    async def analyze(
        self,
        image_base64: str,
        image_mime_type: str | None = None,
        image_filename: str | None = None,
        query: str | None = None,
        equipment_type: str | None = None,
        equipment_model: str | None = None,
        model_provider: str = "openai",
        model_name: str | None = None,
    ) -> ImageAnalysisResult:
        """Analyze an image via a multimodal model, with deterministic fallback."""
        image_bytes = self._decode_image(image_base64)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError("单张故障图片不能超过 4 MB。")

        fallback = self._build_fallback(
            image_filename=image_filename,
            query=query,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
        )

        llm = self._create_multimodal_llm(model_provider=model_provider, model_name=model_name)
        if llm is None or HumanMessage is None:
            return fallback

        content = self._build_message_content(
            model_provider=model_provider,
            image_base64=image_base64,
            image_mime_type=image_mime_type or "image/jpeg",
            query=query,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=content)])
        except Exception:
            fallback.warning = "视觉模型当前不可用，已退化为文件名和文本条件辅助检索。"
            return fallback

        response_text = self._extract_response_text(response.content)
        parsed = self._parse_model_response(response_text)
        if parsed is None:
            fallback.warning = "视觉模型响应未能稳定结构化解析，已退化为文件名和文本条件辅助检索。"
            return fallback

        keywords = self._normalize_keywords(parsed.get("keywords", []))
        summary = str(parsed.get("summary") or "").strip()

        if not summary and not keywords:
            fallback.warning = "视觉模型未返回有效标签，已退化为文件名和文本条件辅助检索。"
            return fallback

        if not keywords and summary:
            keywords = self._extract_keywords(summary)

        return ImageAnalysisResult(
            summary=summary or fallback.summary,
            keywords=keywords or fallback.keywords,
            source="vision_model",
        )

    def merge_query(
        self,
        query: str | None,
        analysis: ImageAnalysisResult | None,
        equipment_model: str | None = None,
    ) -> str | None:
        """Build the effective retrieval query after image analysis."""
        parts: list[str] = []
        if query:
            parts.append(query.strip())
        if equipment_model:
            parts.append(equipment_model.strip())
        if analysis:
            parts.extend(analysis.keywords)
            if analysis.summary:
                parts.append(analysis.summary)

        unique_parts: list[str] = []
        seen: set[str] = set()
        for part in parts:
            normalized = part.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique_parts.append(normalized)

        return " ".join(unique_parts) or None

    def _decode_image(self, image_base64: str) -> bytes:
        normalized = image_base64.strip()
        if "," in normalized and normalized.startswith("data:"):
            normalized = normalized.split(",", 1)[1]

        try:
            return base64.b64decode(normalized, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("故障图片 Base64 数据无效。") from exc

    def _build_fallback(
        self,
        image_filename: str | None,
        query: str | None,
        equipment_type: str | None,
        equipment_model: str | None,
    ) -> ImageAnalysisResult:
        filename_tokens = self._extract_keywords(Path(image_filename or "").stem)
        keywords = []
        if query:
            keywords.append(query.strip())
        if equipment_type:
            keywords.append(equipment_type.strip())
        if equipment_model:
            keywords.append(equipment_model.strip())
        keywords.extend(filename_tokens)

        deduped = self._normalize_keywords(keywords)
        summary = "未调用视觉模型，已使用文本条件和图片文件名标签作为检索线索。"
        return ImageAnalysisResult(summary=summary, keywords=deduped, source="fallback")

    def _normalize_keywords(self, values: list[Any]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            text = _ALIAS_KEYWORDS.get(text.lower(), text)
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(text)
        return deduped

    def _extract_keywords(self, raw_text: str) -> list[str]:
        tokens = []
        lowered_text = raw_text.lower()
        for parts, aliases in _COMPOSITE_HINTS:
            if all(part in lowered_text for part in parts):
                tokens.extend(aliases)
        for token in _TOKEN_PATTERN.findall(raw_text):
            lowered = token.lower()
            if lowered in _IGNORE_TOKENS:
                continue
            tokens.append(_ALIAS_KEYWORDS.get(lowered, token))
        return self._normalize_keywords(tokens)

    def _create_multimodal_llm(self, model_provider: str, model_name: str | None) -> Any | None:
        settings = get_settings()

        if model_provider == "anthropic" and LangChainAnthropic and settings.anthropic_api_key:
            return LangChainAnthropic(
                model=model_name or "claude-sonnet-4-20250514",
                api_key=settings.anthropic_api_key,
                temperature=0.1,
            )

        if LangChainOpenAI is None:
            return None

        if settings.openai_api_key:
            return LangChainOpenAI(
                model=model_name or "gpt-4o-mini",
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base,
                temperature=0.1,
            )

        if settings.deepseek_api_key:
            return LangChainOpenAI(
                model=model_name or "deepseek-chat",
                api_key=settings.deepseek_api_key,
                base_url=settings.openai_api_base or "https://api.deepseek.com",
                temperature=0.1,
            )

        return None

    def _build_message_content(
        self,
        model_provider: str,
        image_base64: str,
        image_mime_type: str,
        query: str | None,
        equipment_type: str | None,
        equipment_model: str | None,
    ) -> list[dict[str, Any]]:
        prompt = (
            "你是设备检修知识系统的视觉预处理器。"
            "请基于故障图片提炼用于知识检索的关键信息。"
            "只返回 JSON，格式为 {\"summary\": \"...\", \"keywords\": [\"...\", \"...\"]}。"
            "summary 控制在 40 字以内，keywords 返回 3 到 6 个部件、故障现象或检修术语。"
        )

        context_parts = []
        if equipment_type:
            context_parts.append(f"设备类型：{equipment_type}")
        if equipment_model:
            context_parts.append(f"设备型号：{equipment_model}")
        if query:
            context_parts.append(f"补充文本：{query}")
        if context_parts:
            prompt = f"{prompt}\n\n已知上下文：{'；'.join(context_parts)}"

        if model_provider == "anthropic":
            return [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source_type": "base64",
                    "data": image_base64,
                    "mime_type": image_mime_type,
                },
            ]

        return [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_mime_type};base64,{image_base64}",
                },
            },
        ]

    def _extract_response_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(part for part in parts if part)
        return str(content)

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
