"""Helpers for producing structured diagnosis payloads and legacy text reports."""
from __future__ import annotations

import json
import re
from typing import Any

from app.schemas.diagnosis import (
    DiagnosisEvidenceItem,
    DiagnosisRootCause,
    DiagnosisStep,
    DiagnosisStepSection,
    DiagnosisStructuredPayload,
)
from app.services.knowledge_query_rewrite import analyze_procedural_query


def strip_report_heading_markdown(text: str | None) -> str:
    return re.sub(r"^■\s*", "", (text or "").replace("**", ""), flags=re.MULTILINE).strip()


def extract_report_section(report: str | None, headings: list[str]) -> str:
    text = (report or "").strip()
    if not text:
        return ""

    escaped = [re.escape(heading) for heading in headings]
    pattern = re.compile(rf"(?:{'|'.join(escaped)})\s*([\s\S]*?)(?=\n(?:■|\*\*)\s*|$)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def split_sentences(text: str | None) -> list[str]:
    return [
        item.replace("**", "").strip()
        for item in re.split(r"[；;。\n]+", (text or "").strip())
        if item and item.strip()
    ]


def _normalize_step_text(text: str) -> str:
    return re.sub(r"^[\-•●]\s*", "", (text or "").strip())


def _normalize_step_compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).strip("，。；; ")


def _count_step_markers(text: str | None) -> int:
    compact = _normalize_step_compact_text(text or "")
    if not compact:
        return 0
    return len(re.findall(r"(?:步骤\s*\d+|[（(]\s*\d+\s*[)）]|\b\d+\.)", compact))


def _detect_step_marker_style(text: str | None) -> str | None:
    compact = _normalize_step_compact_text(text or "")
    if not compact:
        return None
    if re.match(r"^[（(]\s*\d+\s*[)）]", compact):
        return "paren"
    if re.match(r"^(?:步骤\s*)?\d+[.、:：)]", compact):
        return "number"
    return None


def _extract_in_between_step_detail(step_anchor_text: str, expanded_text: str) -> str:
    step_no = _extract_step_number(step_anchor_text)
    if step_no is None:
        return ""

    lines = [line.rstrip() for line in str(expanded_text or "").splitlines()]
    marker_indexes = [
        index
        for index, line in enumerate(lines)
        if _extract_step_number(line) is not None
    ]
    if len(marker_indexes) < 2:
        return ""

    step_anchor_compact = _normalize_step_compact_text(step_anchor_text)
    for marker_index, line_index in enumerate(marker_indexes):
        marker_line = lines[line_index]
        marker_no = _extract_step_number(marker_line)
        if marker_no == step_no:
            current_style = _detect_step_marker_style(marker_line)
            end_index = len(lines)
            for next_line_index in marker_indexes[marker_index + 1 :]:
                next_style = _detect_step_marker_style(lines[next_line_index])
                if current_style == "paren" and next_style != "paren":
                    continue
                end_index = next_line_index
                break
            chunk_lines = [line.strip() for line in lines[line_index:end_index] if line.strip()]
            compact = _normalize_step_compact_text(" ".join(chunk_lines))
            if compact:
                return compact

    first_marker = marker_indexes[0]
    last_marker = marker_indexes[-1]
    if step_no <= _extract_step_number(lines[first_marker]) or step_no >= _extract_step_number(lines[last_marker]):
        return ""

    middle_lines = [line.strip() for line in lines[first_marker + 1 : last_marker] if line.strip()]
    if not middle_lines:
        return ""

    anchor_terms = [
        term
        for term in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", step_anchor_compact)
        if term not in PROCEDURAL_ACTION_TERMS and term not in {"步骤", "检查", "操作", "顺序", "流程"}
    ]
    for index, line in enumerate(middle_lines):
        if any(term in line for term in anchor_terms):
            middle_lines = middle_lines[index:]
            break

    anchor_body = re.sub(r"^[（(]?\s*\d+\s*[)）.]?\s*", "", step_anchor_compact).strip()
    normalized_lines: list[str] = []
    for line in middle_lines:
        cleaned_line = re.sub(r"^[\-•●]\s*", "", line).strip()
        if not cleaned_line:
            continue
        if cleaned_line in anchor_body:
            continue
        label_prefix = cleaned_line.split("：", 1)[0] + "：" if "：" in cleaned_line else ""
        ascii_label_prefix = cleaned_line.split(":", 1)[0] + ":" if ":" in cleaned_line else ""
        if anchor_body and cleaned_line.startswith(anchor_body):
            cleaned_line = cleaned_line[len(anchor_body) :].strip(" ：:;-")
        elif label_prefix and anchor_body.endswith(label_prefix):
            cleaned_line = cleaned_line[len(label_prefix) :].strip(" ：:;-")
        elif ascii_label_prefix and anchor_body.endswith(ascii_label_prefix):
            cleaned_line = cleaned_line[len(ascii_label_prefix) :].strip(" ：:;-")
        if cleaned_line:
            normalized_lines.append(cleaned_line)

    compact = _normalize_step_compact_text(" ".join([step_anchor_compact, *normalized_lines]))
    if compact and compact != step_anchor_compact:
        return compact
    return ""


PROCEDURAL_ACTION_TERMS = (
    "拆下",
    "拆开",
    "拆卸",
    "取下",
    "松开",
    "抽出",
    "排放",
    "放净",
    "断开",
    "拔下",
    "拆除",
    "安装",
    "检查",
    "打开",
    "关闭",
    "取出",
    "支撑",
    "加注",
    "敲平",
)


def _looks_like_parts_catalog_line(text: str) -> bool:
    normalized = " ".join((text or "").split())
    if not normalized:
        return False
    if not re.match(r"^(?:\d+|[（(]?\d+[)）.、：:]?)", normalized):
        return False
    catalog_markers = ("螺栓", "螺母", "吊片", "托架", "套筒", "N·m", "达克罗", "数量", "备注")
    has_catalog_marker = any(marker in normalized for marker in catalog_markers)
    has_action_term = any(term in normalized for term in PROCEDURAL_ACTION_TERMS)
    return has_catalog_marker and not has_action_term


def _extract_query_focus_terms(symptom_description: str | None) -> list[str]:
    text = (symptom_description or "").strip()
    if not text:
        return []
    procedural_analysis = analyze_procedural_query(text)
    if procedural_analysis.focus_terms:
        return list(procedural_analysis.focus_terms[:4])
    normalized = text
    for suffix in ("操作顺序", "操作步骤", "标准步骤", "步骤", "流程", "顺序", "怎么拆", "如何拆", "如何安装"):
        normalized = normalized.replace(suffix, " ")
    terms = [part.strip() for part in re.split(r"[\s/、，,；;]+", normalized) if part.strip()]
    return terms[:4]


def _trim_opposite_action_tail(text: str, symptom_description: str | None) -> str:
    procedural_analysis = analyze_procedural_query(symptom_description or "")
    compact = _normalize_step_compact_text(text)
    if not compact or not procedural_analysis.action:
        return compact

    trailing_patterns: list[str] = []
    if procedural_analysis.action in {"拆卸", "拆下"}:
        trailing_patterns.extend([r"\s+安装[\u4e00-\u9fffA-Za-z0-9]{2,16}$", r"\s+检查[\u4e00-\u9fffA-Za-z0-9]{2,16}$"])
    elif procedural_analysis.action == "安装":
        trailing_patterns.extend([r"\s+拆卸[\u4e00-\u9fffA-Za-z0-9]{2,16}$", r"\s+拆下[\u4e00-\u9fffA-Za-z0-9]{2,16}$"])

    trimmed = compact
    for pattern in trailing_patterns:
        trimmed = re.sub(pattern, "", trimmed).strip()
    return trimmed or compact


def _is_action_compatible_step(text: str, symptom_description: str | None) -> bool:
    procedural_analysis = analyze_procedural_query(symptom_description or "")
    action = procedural_analysis.action
    normalized = _normalize_step_compact_text(text)
    normalized_body = re.sub(r"^\d+\.\s*", "", normalized)
    if not action or not normalized:
        return True
    if action in {"拆卸", "拆下"}:
        return not normalized_body.startswith(("安装", "装上"))
    if action == "安装":
        return not normalized_body.startswith(("拆卸", "拆下", "取下", "松开", "排放"))
    if action == "检查":
        return "检查" in normalized_body or not normalized_body.startswith(("安装", "拆卸", "拆下"))
    return True


def _extract_step_number(value: str | None) -> int | None:
    text = _normalize_step_compact_text(value or "")
    if not text:
        return None
    matched = re.match(r"^(?:步骤\s*)?(\d+)(?:[.、:：)|）-]+|\s)", text)
    if matched:
        return int(matched.group(1))
    matched = re.match(r"^[（(]\s*(\d+)\s*[)）]", text)
    if matched:
        return int(matched.group(1))
    return None


def _measure_step_sequence(step_numbers: list[int]) -> tuple[int, int]:
    if not step_numbers:
        return 0, 0
    ordered = sorted(set(step_numbers))
    longest_run = 1
    current_run = 1
    continuity_pairs = 0
    for index in range(1, len(ordered)):
        if ordered[index] == ordered[index - 1] + 1:
            current_run += 1
            continuity_pairs += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    return longest_run, continuity_pairs


def _collect_group_step_numbers(
    items: list[dict[str, Any]],
    symptom_description: str | None,
) -> list[int]:
    step_numbers: list[int] = []
    for item in items:
        best_text = _select_best_procedural_text(item, symptom_description)
        step_numbers.extend(
            step_no
            for step_no in (_extract_step_number(step) for step in _extract_steps_from_text(best_text))
            if step_no is not None
        )
    return step_numbers


def _select_best_procedural_text(item: dict[str, Any], symptom_description: str | None = None) -> str:
    procedural_analysis = analyze_procedural_query(symptom_description or "")
    if procedural_analysis.scope == "single_step" and item.get("step_anchor"):
        return str(item.get("step_anchor") or "").strip()
    local_text = str(item.get("_content") or item.get("content") or "").strip()
    expanded_text = str(item.get("expanded_content") or "").strip()
    step_anchor_text = str(item.get("step_anchor") or "").strip()
    if step_anchor_text and expanded_text:
        if _count_step_markers(expanded_text) > 1:
            isolated_text = _extract_in_between_step_detail(step_anchor_text, expanded_text)
            if isolated_text:
                return isolated_text
            step_anchor_no = _extract_step_number(step_anchor_text)
            if step_anchor_no is not None:
                return step_anchor_text
    if item.get("step_anchor") and local_text:
        local_steps = _extract_steps_from_text(local_text)
        expanded_steps = _extract_steps_from_text(expanded_text)
        if len(local_steps) == 1 and len(expanded_steps) > 1:
            return local_text
    candidates = [
        ("_content", item.get("_content")),
        ("content", item.get("content")),
        ("excerpt", item.get("excerpt")),
        ("expanded_content", item.get("expanded_content")),
    ]
    source_bonus = {
        "_content": 2.0,
        "content": 1.8,
        "excerpt": 0.4,
        "expanded_content": 0.0,
    }
    evaluated: list[tuple[str, str, float, int, int]] = []
    for source_name, raw_text in candidates:
        text = str(raw_text or "").strip()
        if not text:
            continue
        steps = _extract_steps_from_text(text)
        step_numbers = [step_no for step_no in (_extract_step_number(step) for step in steps) if step_no is not None]
        longest_run, continuity_pairs = _measure_step_sequence(step_numbers)
        embedded_section_heading_count = len(
            re.findall(r"(?m)^\s*\d+\.\d+(?:\.\d+){0,2}\s+\S+", text)
        )
        score = source_bonus[source_name]
        score += len(steps) * 8
        score += len(set(step_numbers)) * 4
        score += longest_run * 3 + continuity_pairs * 2
        if any(marker in text for marker in ("依次取下", "具体操作顺序为", "拧紧力矩要求", "机油规格要求")):
            score += 2.5
        if embedded_section_heading_count:
            score -= embedded_section_heading_count * 6
        if "…" in text or "..." in text:
            score -= 1.5
        if len(text) > 1200:
            score -= 0.8
        evaluated.append((source_name, text, score, len(steps), embedded_section_heading_count))

    local_candidates = [
        entry for entry in evaluated
        if entry[0] in {"_content", "content"} and entry[3] > 0
    ]
    expanded_candidate = next((entry for entry in evaluated if entry[0] == "expanded_content"), None)
    if local_candidates and expanded_candidate is not None and expanded_candidate[4] > 0:
        local_candidates.sort(key=lambda entry: (entry[3], entry[2]), reverse=True)
        return local_candidates[0][1]

    best_text = ""
    best_score = float("-inf")
    for _, text, score, _, _ in evaluated:
        if score > best_score:
            best_score = score
            best_text = text
    return best_text


def _score_procedural_section_match(
    item: dict[str, Any],
    focus_terms: list[str],
) -> int:
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("section_path", "section_reference", "title", "excerpt", "expanded_content")
    )
    score = 0
    if any(term in haystack for term in ("拆卸", "拆下", "步骤", "流程")):
        score += 2
    for term in focus_terms:
        if term and term in haystack:
            score += 3
    install_conflict = any(
        term in haystack
        for term in ("安装发动机", "按反向顺序安装", "安装步骤", "安装流程", "3.3 安装发动机")
    )
    irrelevant_conflict = any(term in haystack for term in ("压缩压力", "起动电机"))
    if (install_conflict or irrelevant_conflict) and any(
        term in "".join(focus_terms) for term in ("发动机", "拆卸", "拆下")
    ):
        score -= 2
    return score


def _select_procedural_focus_results(
    retrieval_results: list[dict[str, Any]],
    symptom_description: str | None,
) -> list[dict[str, Any]]:
    if not retrieval_results:
        return []
    focus_terms = _extract_query_focus_terms(symptom_description)
    procedural_analysis = analyze_procedural_query(symptom_description or "")
    if procedural_analysis.action and procedural_analysis.object_text:
        exact_phrase = f"{procedural_analysis.action}{procedural_analysis.object_text}"
        exact_match_item = next(
            (
                item for item in retrieval_results
                if exact_phrase in " ".join(
                    str(item.get(key) or "") for key in ("section_reference", "section_path")
                )
            ),
            None,
        )
        if exact_match_item is not None:
            target_path = str(exact_match_item.get("section_path") or "").strip()
            target_ref = str(exact_match_item.get("section_reference") or "").strip()
            exact_section_items = [
                item for item in retrieval_results
                if (target_path and str(item.get("section_path") or "").strip() == target_path)
                or (target_ref and str(item.get("section_reference") or "").strip() == target_ref)
            ]
            if exact_section_items:
                return exact_section_items
    section_buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    ungrouped: list[tuple[dict[str, Any], int]] = []

    if procedural_analysis.scope == "single_step":
        ranked_items = sorted(
            retrieval_results,
            key=lambda item: (
                _score_single_step_item_match(item, procedural_analysis),
                float(item.get("rerank_score") or item.get("score") or item.get("retrieval_score") or 0.0),
            ),
            reverse=True,
        )
        best_item_score = _score_single_step_item_match(ranked_items[0], procedural_analysis)
        if best_item_score > 0:
            return [
                item
                for item in ranked_items
                if _score_single_step_item_match(item, procedural_analysis) >= max(best_item_score - 1.0, 1.0)
            ][:3]

    for item in retrieval_results:
        section_path = str(item.get("section_path") or "").strip()
        section_reference = str(item.get("section_reference") or "").strip()
        if section_path or section_reference:
            section_buckets.setdefault((section_path, section_reference), []).append(item)
        else:
            ungrouped.append((item, _score_procedural_section_match(item, focus_terms)))

    ranked_groups: list[tuple[float, list[dict[str, Any]], list[int]]] = []
    for items in section_buckets.values():
        base_score = max(_score_procedural_section_match(item, focus_terms) for item in items)
        best_item_score = max(
            float(item.get("rerank_score") or item.get("score") or item.get("retrieval_score") or 0.0)
            for item in items
        )
        step_numbers = _collect_group_step_numbers(items, symptom_description)
        total_steps = 0
        for item in items:
            total_steps += len(_extract_steps_from_text(_select_best_procedural_text(item, symptom_description)))
        longest_run, continuity_pairs = _measure_step_sequence(step_numbers)
        group_score = float(base_score)
        group_score += best_item_score
        group_score += len(items) * 1.5
        group_score += total_steps * 1.2
        group_score += len(set(step_numbers)) * 2.5
        group_score += longest_run * 2.5 + continuity_pairs * 2.0
        ranked_groups.append((group_score, items, step_numbers))

    ranked_groups.sort(key=lambda entry: entry[0], reverse=True)
    if ranked_groups:
        merged_items = list(ranked_groups[0][1])
        merged_step_numbers = list(ranked_groups[0][2])
        merged_step_set = set(merged_step_numbers)
        if merged_step_numbers:
            for _, items, step_numbers in ranked_groups[1:]:
                if not step_numbers:
                    continue
                candidate_set = set(step_numbers)
                if candidate_set & merged_step_set:
                    merged_items.extend(items)
                    merged_step_numbers.extend(step_numbers)
                    merged_step_set.update(candidate_set)
                    continue
                min_gap = min(abs(a - b) for a in candidate_set for b in merged_step_set)
                if min_gap == 1:
                    merged_items.extend(items)
                    merged_step_numbers.extend(step_numbers)
                    merged_step_set.update(candidate_set)
        if merged_items:
            return merged_items

    if ungrouped:
        ungrouped.sort(key=lambda entry: entry[1], reverse=True)
        best_score = ungrouped[0][1]
        return [item for item, score in ungrouped if score >= max(best_score - 1, 1)]
    return retrieval_results[:5]


def _score_single_step_item_match(item: dict[str, Any], procedural_analysis) -> float:
    structural_text = " ".join(
        str(part or "")
        for part in (
            item.get("section_reference"),
            item.get("section_path"),
            item.get("step_anchor"),
        )
    )
    narrative_text = " ".join(
        str(part or "")
        for part in (
            item.get("title"),
            item.get("excerpt"),
            item.get("expanded_content"),
        )
    )
    score = 0.0
    if procedural_analysis.action:
        if procedural_analysis.action in structural_text:
            score += 3.0
        elif procedural_analysis.action in narrative_text:
            score += 1.0
    for term in procedural_analysis.object_terms:
        if term in structural_text:
            score += 2.2
        elif term in narrative_text:
            score += 0.6
    if item.get("step_anchor"):
        score += 1.0
    return score


def _extract_steps_from_text(raw_text: str) -> list[str]:
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    steps: list[str] = []
    current_step: str | None = None

    def is_numbered_step_line(text: str) -> bool:
        if re.match(r"^步骤\s*\d+", text):
            return True
        if re.match(r"^[（(]?\d+[)）.、：:]", text):
            return True
        inline_match = re.match(r"^(\d+)\s+(.+)$", text)
        if not inline_match:
            return False
        remainder = inline_match.group(2).strip()
        return any(token in remainder for token in PROCEDURAL_ACTION_TERMS)

    def flush() -> None:
        nonlocal current_step
        if current_step:
            compact = re.sub(r"\s+", " ", current_step).strip("，。；; ")
            if compact:
                steps.append(compact)
        current_step = None

    def is_decimal_section_heading(text: str) -> bool:
        compact = _normalize_step_compact_text(text)
        if not compact:
            return False
        if not re.match(r"^\d+\.\d+(?:\.\d+){0,2}\s+", compact):
            return False
        body = re.sub(r"^\d+\.\d+(?:\.\d+){0,2}\s+", "", compact).strip()
        if not body or len(body) > 24:
            return False
        return not any(token in body for token in ("：", ":", "，", ",", "。", "；", ";", "（", "("))

    for line in lines:
        normalized = _normalize_step_text(line)
        if not normalized:
            continue
        if _looks_like_parts_catalog_line(normalized):
            flush()
            continue

        is_numbered = is_numbered_step_line(normalized)
        has_action = any(token in normalized for token in PROCEDURAL_ACTION_TERMS)
        is_heading = bool(re.match(r"^\d+(?:\.\d+){1,3}\s+", normalized))
        if is_decimal_section_heading(normalized):
            flush()
            continue

        if is_heading and not has_action:
            flush()
            continue

        if is_numbered:
            flush()
            if has_action:
                current_step = normalized
            continue

        if current_step and not _looks_like_parts_catalog_line(normalized):
            current_step = f"{current_step} {normalized}"
        elif has_action:
            current_step = normalized

    flush()
    return steps


def _split_procedure_items(text: str) -> list[str]:
    compact = _normalize_step_compact_text(text)
    if not compact:
        return []
    if " " in compact:
        return [item.strip() for item in compact.split() if item.strip()]
    return [compact]


def _split_procedure_action_items(text: str) -> list[str]:
    compact = _normalize_step_compact_text(text)
    if not compact:
        return []
    parts = re.split(r"(?=取下|拆下|松开|断开|打开|关闭|拔下|取出)", compact)
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned or [compact]


def _split_sentence_items(text: str) -> list[str]:
    return [
        _normalize_step_compact_text(item)
        for item in re.split(r"[。；]+", text or "")
        if _normalize_step_compact_text(item)
    ]


def _split_numbered_items(text: str) -> list[str]:
    compact = _normalize_step_compact_text(text)
    if not compact:
        return []
    matches = re.findall(r"(\d+\.\s+[^\d\s][\s\S]*?)(?=\s+\d+\.\s+[^\d\s]|$)", compact)
    cleaned = [_normalize_step_compact_text(item) for item in matches if _normalize_step_compact_text(item)]
    return cleaned or ([compact] if re.match(r"^\d+\.\s+[^\d\s]", compact) else [])


def _looks_like_numbered_check_item(text: str) -> bool:
    compact = _normalize_step_compact_text(text)
    if not re.match(r"^\d+\.\s*", compact):
        return False
    return any(marker in compact for marker in ("：", ":", "mm", "N·m", "≤", "≥", "→", "更换"))


def _split_label_value_items(text: str) -> list[str]:
    compact = _normalize_step_compact_text(text)
    if not compact:
        return []
    matches = re.findall(r"([^:：\s]{2,12}[:：][\s\S]*?)(?=\s+[^:：\s]{2,12}[:：]|$)", compact)
    cleaned = [_normalize_step_compact_text(item) for item in matches if _normalize_step_compact_text(item)]
    return cleaned or [compact]


def _split_volume_items(text: str) -> list[str]:
    compact = _normalize_step_compact_text(text)
    if not compact:
        return []
    matches = re.findall(r"(\d+\s*mL[\s\S]*?)(?=\s+\d+\s*mL|$)", compact, flags=re.IGNORECASE)
    cleaned = [_normalize_step_compact_text(item) for item in matches if _normalize_step_compact_text(item)]
    return cleaned or [compact]


def _extract_step_title_and_remainder(body: str) -> tuple[str, str]:
    compact = _normalize_step_compact_text(body)
    if not compact:
        return "", ""

    split_markers = (
        " 安装顺序",
        " 安装 ",
        " 从 ",
        " 向 ",
        " 用 ",
        " 启动",
        " 再次向 ",
        " 依次松开",
        " 依次取下",
        " 具体操作顺序为",
        " 将 ",
        " 让 ",
        " 拆下",
        " 取下",
        " 松开",
        " 断开",
        " 打开",
        " 关闭",
        " 拔下",
        " 取出",
        " 1. ",
        " 拧紧力矩要求",
        " 机油规格要求",
        " 提示",
    )
    split_index: int | None = None
    for marker in split_markers:
        position = compact.find(marker)
        if position > 3:
            if split_index is None or position < split_index:
                split_index = position

    if split_index is not None:
        title = compact[:split_index].strip()
        remainder = compact[split_index:].strip()
        if title:
            return title, remainder

    first_sentence = re.match(r"^([^。；]+)[。；]?\s*(.*)$", compact)
    if first_sentence:
        title = first_sentence.group(1).strip()
        remainder = first_sentence.group(2).strip()
        if title:
            return title, remainder
    return compact, ""


def _extract_labeled_sections(text: str) -> tuple[list[DiagnosisStepSection], str]:
    if not text:
        return [], ""

    sections: list[DiagnosisStepSection] = []
    remaining = text

    oil_fill_match = re.match(
        r"^\s*(从[\s\S]{2,60}?加入)[:：]\s*([\s\S]*?)(?=(机油规格要求|提示)[:：]|$)",
        remaining,
    )
    if oil_fill_match:
        label = _normalize_step_compact_text(oil_fill_match.group(1))
        items = _split_volume_items(oil_fill_match.group(2))
        if items:
            sections.append(DiagnosisStepSection(label=label, items=items))
        remaining = remaining[oil_fill_match.end() :].strip()

    label_patterns = [
        (re.compile(r"(依次松开以下部件的固定螺栓)[:：]\s*([\s\S]*?)(?=(具体操作顺序为|依次取下|拧紧力矩要求|机油规格要求|提示)[:：]|$)"), _split_procedure_items),
        (re.compile(r"(具体操作顺序为)[:：]\s*([\s\S]*?)(?=(依次取下|拧紧力矩要求|机油规格要求|提示)[:：]|$)"), _split_procedure_action_items),
        (re.compile(r"(依次取下)[:：]\s*([\s\S]*?)(?=(拧紧力矩要求|机油规格要求|提示)[:：]|$)"), _split_procedure_items),
        (re.compile(r"(拧紧力矩要求)[:：]\s*([\s\S]*?)(?=(机油规格要求|提示)[:：]|$)"), _split_label_value_items),
        (re.compile(r"(机油规格要求)[:：]\s*([\s\S]*?)(?=(提示)[:：]|$)"), _split_label_value_items),
        (re.compile(r"(提示)[:：]\s*([\s\S]*?)(?=$)"), _split_sentence_items),
    ]
    for pattern, splitter in label_patterns:
        while True:
            section_match = pattern.search(remaining)
            if not section_match:
                break
            label = _normalize_step_compact_text(section_match.group(1))
            items = splitter(section_match.group(2))
            if items:
                sections.append(DiagnosisStepSection(label=label, items=items))
            remaining = (remaining[: section_match.start()] + " " + remaining[section_match.end() :]).strip()

    return sections, _normalize_step_compact_text(remaining)


def _build_diagnosis_step(text: str, index: int) -> DiagnosisStep:
    compact = _normalize_step_compact_text(text)
    matched = re.match(r"^(\d+)\.\s*(.*)$", compact)
    parenthesized_match = re.match(r"^[（(]\s*(\d+)\s*[)）]\s*(.*)$", compact)
    step_no = int(matched.group(1)) if matched else (int(parenthesized_match.group(1)) if parenthesized_match else index)
    body = (matched.group(2) if matched else (parenthesized_match.group(2) if parenthesized_match else compact)).strip()

    meta: list[str] = []
    cleaned_body = body

    tool_match = re.search(r"所需工具[:：]?\s*([^。；]+)$", cleaned_body)
    if tool_match:
        meta.append(f"所需工具：{tool_match.group(1).strip()}")
        cleaned_body = cleaned_body[: tool_match.start()].strip()

    torque_match = re.search(r"([^。；]*扭矩[:：]?\s*[^。；]+)", cleaned_body)
    if torque_match:
        meta.insert(0, torque_match.group(1).strip())
        cleaned_body = cleaned_body.replace(torque_match.group(1), "").strip()

    title, remainder = _extract_step_title_and_remainder(cleaned_body)

    sections, mutable_remainder = _extract_labeled_sections(remainder)

    summary = (
        _normalize_step_compact_text(mutable_remainder)
        .removesuffix("具体操作顺序为")
        .removesuffix("依次取下")
        .strip()
    )

    if not sections:
        numbered_items = _split_numbered_items(summary)
        if numbered_items and len(numbered_items) >= 1:
            sections = [DiagnosisStepSection(label="检查项", items=numbered_items)]
            summary = ""

    if not sections:
        sentence_items = _split_sentence_items(summary)
        if len(sentence_items) >= 2:
            sections = [DiagnosisStepSection(label="执行要点", items=sentence_items)]
            summary = ""

    return DiagnosisStep(
        step_no=step_no,
        title=title or f"步骤 {index}",
        summary=summary,
        sections=sections,
        meta=meta,
        raw_text=compact or None,
    )


def _dedupe_structured_steps(steps: list[DiagnosisStep]) -> list[DiagnosisStep]:
    def extra_step_marker_count(step: DiagnosisStep) -> int:
        text = _normalize_step_compact_text(step.raw_text or f"{step.title} {step.summary}")
        if not text:
            return 0
        if re.match(r"^[（(]\s*\d+\s*[)）]", text):
            return max(len(re.findall(r"[（(]\s*\d+\s*[)）]", text)) - 1, 0)
        if re.match(r"^(?:步骤\s*)?\d+[.、:：)]", text):
            return max(len(re.findall(r"(?:步骤\s*)?\d+[.、:：)]", text)) - 1, 0)
        return max(_count_step_markers(text) - 1, 0)

    deduped: list[DiagnosisStep] = []
    index_by_no: dict[int, int] = {}
    seen_raw: set[str] = set()
    for step in steps:
        raw_text = _normalize_step_compact_text(step.raw_text or f"{step.title} {step.summary}")
        if raw_text and raw_text in seen_raw:
            continue
        step_no = step.step_no or len(deduped) + 1
        existing_index = index_by_no.get(step_no)
        if existing_index is not None:
            current = deduped[existing_index]
            current_text = _normalize_step_compact_text(current.raw_text or f"{current.title} {current.summary}")
            current_marker_count = extra_step_marker_count(current)
            next_marker_count = extra_step_marker_count(step)
            should_replace = False
            if next_marker_count < current_marker_count:
                should_replace = True
            elif next_marker_count == current_marker_count and len(raw_text) > len(current_text):
                should_replace = True
            if should_replace:
                if current_text:
                    seen_raw.discard(current_text)
                deduped[existing_index] = step
                if raw_text:
                    seen_raw.add(raw_text)
            continue
        index_by_no[step_no] = len(deduped)
        deduped.append(step)
        if raw_text:
            seen_raw.add(raw_text)
    return deduped


def _derive_operation_subject(symptom_description: str | None, retrieval_results: list[dict[str, Any]]) -> str:
    query = (symptom_description or "").strip()
    if query:
        for suffix in ("操作顺序", "操作步骤", "标准步骤", "步骤", "流程", "顺序", "怎么拆", "如何拆"):
            if query.endswith(suffix):
                query = query[: -len(suffix)].strip()
        if query:
            return query
    top_title = str((retrieval_results[:1] or [{}])[0].get("title") or "").strip()
    return top_title or "标准操作顺序"


def _looks_like_procedural_query(symptom_description: str | None, retrieval_results: list[dict[str, Any]]) -> bool:
    text = (symptom_description or "").strip()
    if analyze_procedural_query(text).is_procedural:
        return True
    for item in retrieval_results[:3]:
        section_text = " ".join(
            str(item.get(key) or "")
            for key in ("section_path", "section_reference", "title")
        )
        if any(marker in section_text for marker in ("步骤", "拆卸", "拆下", "安装", "检查", "加注", "发动机拆下", "操作")):
            return True
    return False


def _collect_procedural_steps(
    retrieval_results: list[dict[str, Any]],
    symptom_description: str | None,
    advice_card: str | None,
) -> list[DiagnosisStep]:
    procedural_analysis = analyze_procedural_query(symptom_description or "")
    candidates: list[str] = []
    focused_results = _select_procedural_focus_results(retrieval_results, symptom_description)
    for item in focused_results:
        raw_text = _select_best_procedural_text(item, symptom_description)
        extracted_steps = [
            _trim_opposite_action_tail(step_text, symptom_description)
            for step_text in _extract_steps_from_text(str(raw_text))
        ]
        if extracted_steps:
            candidates.extend(extracted_steps)
            continue
        compact_raw_text = _normalize_step_compact_text(raw_text)
        if (
            procedural_analysis.action == "检查"
            and _looks_like_numbered_check_item(compact_raw_text)
            and candidates
        ):
            if compact_raw_text not in candidates[-1]:
                candidates[-1] = _normalize_step_compact_text(f"{candidates[-1]} {compact_raw_text}")
    candidates = [
        candidate
        for candidate in candidates
        if _normalize_step_compact_text(candidate) and _is_action_compatible_step(candidate, symptom_description)
    ]
    if not candidates and advice_card:
        candidates.extend(
            item for item in _extract_steps_from_text("\n".join(split_sentences(advice_card)))
        )

    structured_steps = [
        _build_diagnosis_step(item, index + 1)
        for index, item in enumerate(candidates)
        if _normalize_step_compact_text(item)
    ]
    return _dedupe_structured_steps(structured_steps)


def _build_simple_action_steps(items: list[str]) -> list[DiagnosisStep]:
    return [
        DiagnosisStep(
            step_no=index + 1,
            title=_normalize_step_compact_text(item) or f"步骤 {index + 1}",
            summary="",
            sections=[],
            meta=[],
            raw_text=_normalize_step_compact_text(item) or None,
        )
        for index, item in enumerate(items[:6])
        if _normalize_step_compact_text(item)
    ]


def _detect_risk_level(raw_text: str, maintenance_level: str | None) -> str:
    merged = f"{raw_text} {(maintenance_level or '').lower()}"
    if re.search(r"(高风险|重大|严重|立即|停机|紧急|应急)", merged):
        return "高风险"
    if re.search(r"(关注|排查|复核|标准|中等|观察)", merged):
        return "中风险"
    return "低风险"


def _derive_confidence(
    evidence_count: int,
    preliminary_conclusion: str,
    root_causes: list[str],
    next_steps: list[DiagnosisStep],
) -> int:
    score = 34
    score += min(evidence_count * 10, 30)
    if preliminary_conclusion:
        score += 16
    score += min(len(root_causes) * 8, 24)
    score += min(len(next_steps) * 4, 16)
    return max(35, min(92, score))


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?|```$", "", candidate, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(candidate)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_llm_structured_json(content: str) -> DiagnosisStructuredPayload | None:
    parsed = _safe_json_loads(content)
    if not parsed:
        return None
    try:
        return DiagnosisStructuredPayload.model_validate(parsed)
    except Exception:
        return None


def build_structured_diagnosis(
    *,
    diagnosis_report: str | None,
    advice_card: str | None,
    retrieval_results: list[dict[str, Any]] | None = None,
    maintenance_level: str | None = None,
    symptom_description: str | None = None,
    work_order_ready: bool = False,
    answer_mode: str = "diagnosis",
) -> DiagnosisStructuredPayload:
    retrieval_results = retrieval_results or []
    retrieval_count = len(retrieval_results)
    inferred_answer_mode = (
        "procedure"
        if answer_mode == "procedure" or _looks_like_procedural_query(symptom_description, retrieval_results)
        else "diagnosis"
    )
    conclusion_section = extract_report_section(diagnosis_report, ["■ 诊断结论", "诊断结论", "结论"])
    reason_section = extract_report_section(diagnosis_report, ["■ 原因判断", "原因判断"])
    knowledge_section = extract_report_section(diagnosis_report, ["■ 知识依据", "知识依据"])
    advice_section = extract_report_section(diagnosis_report, ["■ 建议措施", "建议措施", "■ 下一步建议", "下一步建议"])

    conclusion_lines = split_sentences(conclusion_section)
    reason_lines = split_sentences(reason_section)
    knowledge_lines = split_sentences(knowledge_section)
    advice_lines = split_sentences(advice_section or advice_card)
    symptom_lines = split_sentences(symptom_description)[:3]

    evidence_items: list[DiagnosisEvidenceItem] = []
    evidence_source_results = (
        _select_procedural_focus_results(retrieval_results, symptom_description)
        if inferred_answer_mode == "procedure"
        else retrieval_results
    )
    for idx, item in enumerate(evidence_source_results[:5]):
        relevance = max(40, min(95, 82 - idx * 9))
        evidence_items.append(
            DiagnosisEvidenceItem(
                document_title=item.get("title") or f"知识条目 {idx + 1}",
                chunk_id=item.get("chunk_id"),
                citation_label=item.get("citation_label"),
                section=item.get("section_reference") or item.get("page_reference") or "命中片段",
                excerpt=(item.get("excerpt") or item.get("content") or "")[:240] or None,
                source_name=item.get("source_name"),
                relevance_score=relevance,
            )
        )

    if inferred_answer_mode == "procedure":
        operation_subject = _derive_operation_subject(symptom_description, retrieval_results)
        procedure_steps = _collect_procedural_steps(retrieval_results, symptom_description, advice_section or advice_card)
        preliminary_conclusion = (
            f"该问题属于操作步骤查询。以下根据当前命中的手册片段整理“{operation_subject}”的推荐顺序。"
            if procedure_steps
            else f"该问题属于操作步骤查询，但当前证据不足，暂未能稳定整理“{operation_subject}”的完整顺序。"
        )
        confidence = max(45, min(95, 42 + retrieval_count * 10 + min(len(procedure_steps) * 5, 25)))
        return DiagnosisStructuredPayload(
            answer_mode="procedure",
            most_likely_fault=operation_subject,
            risk_level="低风险",
            confidence=confidence,
            main_symptoms=[],
            preliminary_conclusion=preliminary_conclusion,
            next_steps=procedure_steps,
            root_causes=[],
            evidence_items=evidence_items,
            evidence_count=retrieval_count,
            top_similarity=evidence_items[0].relevance_score if evidence_items else None,
            work_order_ready=False,
        )

    preliminary_conclusion = (
        strip_report_heading_markdown(conclusion_section)
        or strip_report_heading_markdown(diagnosis_report)
        or "当前未形成稳定诊断结论。"
    )
    most_likely_fault = (reason_lines or conclusion_lines or symptom_lines or ["待进一步定位"])[0]
    risk_level = _detect_risk_level(
        " ".join([preliminary_conclusion, reason_section, advice_section, knowledge_section]),
        maintenance_level,
    )

    root_cause_titles = (reason_lines or conclusion_lines)[:4]
    if not root_cause_titles:
        root_cause_titles = ["待进一步定位的复合故障"]

    confidence = _derive_confidence(
        retrieval_count,
        preliminary_conclusion,
        root_cause_titles,
        advice_lines,
    )

    root_causes = [
        DiagnosisRootCause(
            name=title,
            confidence=max(28, min(95, confidence - index * 14)),
            evidence=(
                evidence_items[index].document_title
                if index < len(evidence_items)
                else (knowledge_lines[index] if index < len(knowledge_lines) else "当前基于综合诊断文本推断")
            ),
        )
        for index, title in enumerate(root_cause_titles[:4])
    ]

    return DiagnosisStructuredPayload(
        answer_mode="diagnosis",
        most_likely_fault=most_likely_fault,
        risk_level=risk_level,
        confidence=confidence,
        main_symptoms=symptom_lines,
        preliminary_conclusion=preliminary_conclusion,
        next_steps=_build_simple_action_steps(advice_lines),
        root_causes=root_causes,
        evidence_items=evidence_items,
        evidence_count=retrieval_count,
        top_similarity=evidence_items[0].relevance_score if evidence_items else None,
        work_order_ready=work_order_ready,
    )


def render_structured_diagnosis_report(payload: DiagnosisStructuredPayload) -> str:
    evidence_lines = [
        f"- [{item.citation_label or '--'}|chunk_id={item.chunk_id or '--'}] {item.document_title}（{item.section or '命中片段'}，相关度：{item.relevance_score or '--'}%，摘录：{item.excerpt or '无摘录'}）"
        for item in payload.evidence_items[:3]
    ] or ["- 当前未命中稳定知识条目。"]
    if payload.answer_mode == "procedure":
        action_lines = [
            f"{item.step_no or index + 1}. {item.raw_text or item.title}"
            for index, item in enumerate(payload.next_steps)
        ] or ["1. 当前证据不足，请补充更明确的操作对象或章节后重新检索。"]
        return (
            "■ 操作主题\n"
            f"{payload.most_likely_fault}\n\n"
            "■ 操作结论\n"
            f"{payload.preliminary_conclusion}\n\n"
            "■ 知识依据\n"
            + "\n".join(evidence_lines)
            + "\n\n■ 操作步骤\n"
            + "\n".join(action_lines)
        )
    reason_lines = [
        f"- {item.name}（置信度 {item.confidence}%：{item.evidence}）"
        for item in payload.root_causes[:3]
    ] or ["- 当前尚未形成稳定根因排序。"]
    action_lines = [
        f"{item.step_no or index + 1}. {item.raw_text or item.title}"
        for index, item in enumerate(payload.next_steps[:6])
    ] or ["1. 补充故障现象或现场资料后重新触发诊断。"]

    return (
        "■ 诊断结论\n"
        f"{payload.preliminary_conclusion}\n\n"
        "■ 原因判断\n"
        f"最可能故障：{payload.most_likely_fault}；风险等级：{payload.risk_level}；综合置信度：{payload.confidence}%\n"
        + "\n".join(reason_lines)
        + "\n\n■ 知识依据\n"
        + "\n".join(evidence_lines)
        + "\n\n■ 建议措施\n"
        + "\n".join(action_lines)
    )
