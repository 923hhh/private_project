"""Deterministic query rewrite helpers for knowledge retrieval."""
from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
SEARCH_TOKEN_LIMIT = 24
SEARCH_IGNORE_TOKENS = {
    "当前",
    "需要",
    "建议",
    "已经",
    "进行",
    "经过",
    "同时",
    "初步判断",
    "可能",
    "现象",
    "问题",
    "情况",
    "车辆",
    "过程",
    "出现",
    "发现",
    "严重",
    "当前仅",
    "使用",
    "文本",
}
DOMAIN_SEARCH_HINTS = [
    "点火系统",
    "点火线圈",
    "点火线束",
    "火花塞",
    "启动困难",
    "冷启动困难",
    "起动电机",
    "压缩压力",
    "供油",
    "燃油供给",
    "燃油",
    "喷油嘴",
    "化油器",
    "怠速不稳",
    "怠速",
    "回火",
    "进气系统",
    "空气滤芯",
    "混合气",
    "节气门",
    "积碳",
    "故障灯",
    "功率下降",
    "动力下降",
    "异响",
    "正时链条",
    "正时",
    "张紧器",
    "气门间隙",
    "气门",
    "凸轮轴",
    "润滑",
    "机油液位",
    "机油",
    "温度偏高",
    "高温",
    "散热",
    "尾气异常",
    "黑烟",
    "机油渗漏",
    "渗漏",
    "油封",
    "缸盖垫片",
    "曲轴油封",
    "仪表背光",
    "仪表灯",
    "照明",
    "远近光",
    "组合开关",
    "USB",
    "充电口",
    "无线充电",
    "蓝牙",
    "麦克风",
    "回声",
    "导航语音",
    "胎压监测",
    "TPMS",
    "防盗报警",
    "误触发",
    "行车记录仪",
    "夜视",
    "附件供电",
    "发动机",
    "故障",
]
SEARCH_SYNONYM_MAP = {
    "动力下降": ["功率下降", "加速无力"],
    "功率下降": ["动力下降", "加速无力"],
    "加速无力": ["动力下降", "功率下降"],
    "点火异常": ["点火系统", "火花塞", "点火线圈"],
    "点火系统": ["点火异常", "火花塞", "点火线圈"],
    "启动困难": ["冷启动困难", "起动困难"],
    "冷启动困难": ["启动困难", "起动困难"],
    "起动困难": ["启动困难", "冷启动困难"],
    "节气门积碳": ["节气门", "积碳"],
    "异响": ["正时链条", "张紧器"],
    "机油渗漏": ["渗漏", "油封", "缸盖垫片"],
    "温度偏高": ["高温", "润滑", "机油液位"],
    "仪表背光": ["仪表灯", "背光", "仪表显示异常"],
    "仪表灯": ["仪表背光", "背光"],
    "USB口": ["USB", "充电口", "供电接口"],
    "充电口": ["USB", "USB口", "供电接口"],
    "无线充电": ["充电口", "USB", "供电接口"],
    "蓝牙连接": ["蓝牙", "配对", "通信故障"],
    "麦克风回声": ["回声", "音频回授", "蓝牙通信"],
    "电流杂音": ["音频回授", "通信噪声", "蓝牙通信"],
    "胎压离线": ["胎压监测", "TPMS离线", "传感器离线"],
    "TPMS离线": ["胎压监测", "胎压离线", "传感器离线"],
    "防盗报警": ["误触发", "报警复位", "报警主机"],
    "组合开关": ["车把开关", "多功能按键", "按键触点"],
    "行车记录仪": ["黑屏", "附件供电", "显示设备"],
    "夜视": ["摄像头", "显示设备", "附件供电"],
    "火花塞帽": ["火花塞帽", "点火线帽", "高压帽"],
    "正时链条松动": ["正时链条", "张紧器", "异响"],
    "拆卸步骤": ["拆卸", "步骤", "流程"],
    "安装步骤": ["安装", "步骤", "流程"],
}
PROCEDURE_ACTION_TOKENS = [
    "拆下",
    "安装",
    "拆卸",
    "更换",
    "检查",
    "调整",
    "测量",
    "排查",
    "加注",
    "排放",
    "松开",
    "取下",
    "断开",
    "拔下",
    "抽出",
    "打开",
    "关闭",
    "清洗",
    "复装",
]
PROCEDURE_SUFFIX_TOKENS = ["步骤", "流程", "顺序", "方法", "操作", "怎么做", "如何做"]
PROCEDURE_INTENT_PREFIXES = ("如何", "怎么", "怎样", "请问", "请教", "帮我", "帮忙")
PROCEDURE_WHOLE_SECTION_CUES = (
    "步骤",
    "流程",
    "顺序",
    "操作顺序",
    "操作步骤",
    "标准步骤",
    "标准流程",
    "检查方法",
    "操作指引",
    "怎么拆",
    "怎么装",
    "如何拆",
    "如何装",
    "如何安装",
    "如何拆卸",
    "如何检查",
    "如何更换",
)
PROCEDURE_SINGLE_STEP_ACTIONS = {
    "加注",
    "排放",
    "松开",
    "取下",
    "断开",
    "拔下",
    "抽出",
    "打开",
    "关闭",
}
PROCEDURE_WHOLE_SECTION_ACTIONS = {"拆卸", "拆下", "安装", "更换", "检查"}
PROCEDURE_BROAD_OBJECT_HINTS = (
    "发动机",
    "传动装置",
    "气缸头",
    "凸轮轴",
    "机油泵",
    "减速齿轮",
    "曲轴",
    "平衡轴",
    "涨紧器",
    "火花塞",
    "离合器",
    "齿轮",
    "总成",
    "装置",
    "系统",
)
PROCEDURE_NARROW_OBJECT_HINTS = (
    "机油",
    "冷却液",
    "螺栓",
    "螺母",
    "垫片",
    "定位销",
    "火花塞帽",
    "水箱",
    "放油螺栓",
    "放水螺栓",
)


@dataclass(frozen=True)
class ProceduralQueryAnalysis:
    is_procedural: bool
    action: str | None
    object_text: str
    object_terms: tuple[str, ...]
    focus_terms: tuple[str, ...]
    scope: str
QUERY_REWRITE_RULES = [
    {
        "name": "启动困难-点火积碳",
        "requires": ["启动困难"],
        "any_of": ["火花塞", "积碳", "点火异常", "点火系统", "失火"],
        "add": ["火花塞", "积碳", "点火系统", "点火线圈"],
    },
    {
        "name": "怠速与供油",
        "requires": ["怠速不稳"],
        "any_of": ["冷启动困难", "喷油嘴", "回火", "加速无力"],
        "add": ["喷油嘴", "空气滤芯", "供油", "节气门"],
    },
    {
        "name": "正时异响",
        "requires": ["异响"],
        "any_of": ["正时", "正时链条", "张紧器", "金属异响"],
        "add": ["正时链条", "张紧器", "气门间隙"],
    },
    {
        "name": "机油渗漏",
        "requires": ["渗漏"],
        "any_of": ["机油", "缸盖", "油封", "垫片"],
        "add": ["机油渗漏", "缸盖垫片", "油封"],
    },
    {
        "name": "高温润滑",
        "requires": ["温度偏高"],
        "any_of": ["高温", "动力下降", "功率下降", "润滑"],
        "add": ["润滑", "机油液位", "散热"],
    },
    {
        "name": "照明与背光",
        "requires": ["大灯"],
        "any_of": ["远近光", "背光", "仪表灯", "组合开关"],
        "add": ["照明", "仪表背光", "组合开关", "继电器"],
    },
    {
        "name": "USB与附件供电",
        "requires": ["USB"],
        "any_of": ["充电口", "无线充电", "接触不良", "供电"],
        "add": ["充电口", "供电接口", "线束压降", "稳压模块"],
    },
    {
        "name": "蓝牙音频通信",
        "requires": ["蓝牙"],
        "any_of": ["麦克风", "回声", "导航语音", "连接失败"],
        "add": ["蓝牙通信", "音频增益", "配对缓存", "天线屏蔽"],
    },
    {
        "name": "胎压与传感器离线",
        "requires": ["胎压"],
        "any_of": ["离线", "TPMS", "同步", "传感器"],
        "add": ["胎压监测", "TPMS离线", "传感器离线", "重新配对"],
    },
]


def analyze_procedural_query(query: str | None) -> ProceduralQueryAnalysis:
    normalized_query = (query or "").strip()
    if not normalized_query:
        return ProceduralQueryAnalysis(
            is_procedural=False,
            action=None,
            object_text="",
            object_terms=(),
            focus_terms=(),
            scope="unknown",
        )

    action = next(
        (token for token in sorted(PROCEDURE_ACTION_TOKENS, key=len, reverse=True) if token in normalized_query),
        None,
    )
    has_whole_section_cue = any(cue in normalized_query for cue in PROCEDURE_WHOLE_SECTION_CUES)
    has_procedural_prefix = any(normalized_query.startswith(prefix) for prefix in PROCEDURE_INTENT_PREFIXES)
    is_procedural = bool(action or has_whole_section_cue or has_procedural_prefix)
    if not is_procedural:
        return ProceduralQueryAnalysis(
            is_procedural=False,
            action=None,
            object_text="",
            object_terms=(),
            focus_terms=(),
            scope="unknown",
        )

    object_text = normalized_query
    for prefix in PROCEDURE_INTENT_PREFIXES:
        if object_text.startswith(prefix):
            object_text = object_text[len(prefix) :].strip()
    for cue in PROCEDURE_WHOLE_SECTION_CUES:
        object_text = object_text.replace(cue, " ")
    if action:
        object_text = object_text.replace(action, " ")
    object_text = re.sub(r"[\s/、，,；;：:（）()]+", " ", object_text).strip()

    object_terms: list[str] = []
    if object_text:
        object_terms.append(object_text)
        for token in TOKEN_PATTERN.findall(object_text):
            stripped = token.strip()
            if len(stripped) >= 2 and stripped not in object_terms:
                object_terms.append(stripped)

    broad_object = any(hint in object_text for hint in PROCEDURE_BROAD_OBJECT_HINTS)
    narrow_object = any(hint in object_text for hint in PROCEDURE_NARROW_OBJECT_HINTS)

    if action in PROCEDURE_SINGLE_STEP_ACTIONS:
        scope = "single_step"
    elif has_whole_section_cue:
        scope = "whole_section"
    elif action in PROCEDURE_WHOLE_SECTION_ACTIONS and broad_object and not narrow_object:
        scope = "whole_section"
    else:
        scope = "single_step"

    focus_terms: list[str] = []
    if action:
        focus_terms.append(action)
    for term in object_terms:
        if term not in focus_terms:
            focus_terms.append(term)

    return ProceduralQueryAnalysis(
        is_procedural=True,
        action=action,
        object_text=object_text,
        object_terms=tuple(object_terms[:4]),
        focus_terms=tuple(focus_terms[:5]),
        scope=scope,
    )


def build_effective_keywords(
    *,
    query: str | None,
    equipment_model: str | None,
    fault_type: str | None,
    image_keywords: list[str] | None = None,
) -> list[str]:
    """Build a deterministic rewritten keyword set for retrieval and UI display."""
    base_tokens = extract_search_tokens(query or "") if query else []
    combined = list(base_tokens)

    if fault_type:
        combined.extend(extract_search_tokens(fault_type))
    if image_keywords:
        for keyword in image_keywords:
            combined.extend(extract_search_tokens(keyword))
    if equipment_model:
        combined.append(equipment_model)
        combined.append(f"{equipment_model} 检修")

    combined = apply_query_rewrite_rules(query or "", combined)
    combined = _inject_query_intent_tokens(query or "", combined)

    deduped: list[str] = []
    seen: set[str] = set()
    for token in combined:
        normalized = token.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
        if len(deduped) >= SEARCH_TOKEN_LIMIT:
            break
    return deduped


def extract_search_tokens(query: str) -> list[str]:
    """Extract deterministic retrieval tokens for Chinese/English maintenance queries."""
    normalized = query.strip()
    if not normalized:
        return []

    tokens: list[str] = []

    for hint in DOMAIN_SEARCH_HINTS:
        if hint in normalized:
            tokens.append(hint)

    for token in TOKEN_PATTERN.findall(normalized):
        stripped = token.strip()
        if not stripped:
            continue
        if stripped in SEARCH_IGNORE_TOKENS:
            continue
        if len(stripped) <= 12:
            tokens.append(stripped)
        tokens.extend(_expand_procedure_like_token(stripped))

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(token)
        if len(deduped) >= SEARCH_TOKEN_LIMIT:
            break

    expanded = expand_tokens_with_synonyms(normalized, deduped)
    if expanded:
        return expanded

    if deduped:
        return deduped

    return [normalized[:24]]


def _expand_procedure_like_token(token: str) -> list[str]:
    """Split compact procedural Chinese phrases into searchable action/object hints."""
    expanded: list[str] = []
    normalized_token = token.strip()
    for prefix in PROCEDURE_INTENT_PREFIXES:
        if normalized_token.startswith(prefix):
            normalized_token = normalized_token[len(prefix) :].strip()
            break
    for action in PROCEDURE_ACTION_TOKENS:
        if action not in normalized_token:
            continue
        expanded.append(action)
        for suffix in PROCEDURE_SUFFIX_TOKENS:
            if suffix in normalized_token:
                expanded.append(suffix)
        remainder = normalized_token.replace(action, "")
        for suffix in PROCEDURE_SUFFIX_TOKENS:
            remainder = remainder.replace(suffix, "")
        remainder = remainder.strip()
        if remainder and remainder != normalized_token:
            expanded.append(remainder)
            expanded.append(f"{action}{remainder}")
            expanded.append(f"{remainder}{action}")
        break
    return [item for item in expanded if len(item.strip()) >= 2]


def _inject_query_intent_tokens(query: str, tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    seen = {token.lower() for token in expanded}
    normalized_query = query.strip()
    if not normalized_query:
        return expanded

    def add_token(value: str) -> None:
        lowered = value.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        expanded.append(value)

    if any(marker in normalized_query for marker in ("图片", "图像", "照片", "图中", "看图")):
        for item in ("图片内容", "图像特征", "故障图片"):
            add_token(item)
    if any(marker in normalized_query for marker in PROCEDURE_SUFFIX_TOKENS):
        for item in ("标准步骤", "操作流程", "注意事项"):
            add_token(item)
    if any(marker in normalized_query for marker in ("拆卸", "安装", "更换", "检查")):
        for item in ("步骤", "流程", "顺序"):
            add_token(item)
    return expanded[:SEARCH_TOKEN_LIMIT]


def expand_tokens_with_synonyms(query: str, tokens: list[str]) -> list[str]:
    """Expand extracted tokens with deterministic maintenance-domain synonyms."""
    expanded = list(tokens)
    seen = {token.lower() for token in expanded}

    for key, aliases in SEARCH_SYNONYM_MAP.items():
        if key not in query and all(token.lower() != key.lower() for token in tokens):
            continue
        lowered_key = key.lower()
        if lowered_key not in seen:
            seen.add(lowered_key)
            expanded.append(key)
            if len(expanded) >= SEARCH_TOKEN_LIMIT:
                return expanded
        for alias in aliases:
            lowered = alias.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            expanded.append(alias)
            if len(expanded) >= SEARCH_TOKEN_LIMIT:
                return expanded

    return expanded


def apply_query_rewrite_rules(query: str, tokens: list[str]) -> list[str]:
    """Inject canonical maintenance terms when a known symptom pattern appears."""
    expanded = list(tokens)
    joined_text = " ".join([query, *tokens]).lower()
    seen = {token.lower() for token in expanded}

    for rule in QUERY_REWRITE_RULES:
        required = [part.lower() for part in rule["requires"]]
        any_of = [part.lower() for part in rule["any_of"]]
        if not all(part in joined_text for part in required):
            continue
        if any_of and not any(part in joined_text for part in any_of):
            continue
        for addition in rule["add"]:
            lowered = addition.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            expanded.append(addition)
            if len(expanded) >= SEARCH_TOKEN_LIMIT:
                return expanded

    return expanded


__all__ = [
    "SEARCH_TOKEN_LIMIT",
    "apply_query_rewrite_rules",
    "build_effective_keywords",
    "expand_tokens_with_synonyms",
    "extract_search_tokens",
]
