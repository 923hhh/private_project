"""PDF text extraction helpers for knowledge-base ingestion."""
from __future__ import annotations

import re
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path

from app.services.knowledge_chunking import (
    build_anchored_chunk_payloads,
    resolve_terminal_section_path,
)

WHITESPACE_PATTERN = re.compile(r"\s+")

# ── 页眉 / 页脚噪声过滤 ──────────────────────────────────────────────────────
# 匹配常见的页码行，如 "No. 3 / 41"、"第 3 页 / 共 41 页"、纯数字页码等
_PAGE_FOOTER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^No\.\s*\d+\s*/\s*\d+$"),           # No. 3 / 41
    re.compile(r"^第\s*\d+\s*页\s*/?\s*共?\s*\d+\s*页?$"),  # 第3页/共41页
    re.compile(r"^\d+\s*/\s*\d+$"),                   # 3 / 41
    re.compile(r"^\d+$"),                              # 纯数字页码（单独一行）
]

# 小节标题识别：以数字编号或中文序号开头的短行视为标题，不与下一行合并
_SECTION_LINE_PATTERN = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+){0,3}"          # 1 / 1.2 / 1.2.3
    r"|[一二三四五六七八九十]+[、．.]"  # 一、 二．
    r"|第[一二三四五六七八九十百\d]+[章节条]"  # 第三章
    r")"
    r"[\s　]*[一-鿿\w（(]"  # 后跟中文或字母
)

# 步骤行：以 "1." "（1）" "步骤1" 等开头
_STEP_LINE_PATTERN = re.compile(
    r"^(?:步骤\s*\d+|[（(]\s*\d+\s*[)）]|\d+[.、:：]\s*[一-鿿\w])"
)
_TOP_LEVEL_LIST_PATTERN = re.compile(r"^[一二三四五六七八九十]+[、．.]\s*.+$")
_INLINE_HEADING_BREAK_PATTERN = re.compile(
    r"(?<=[。；！？])\s+(?=(?:"
    r"第[一二三四五六七八九十百\d]+[章节条]"
    r"|[一二三四五六七八九十]+[、．.]"
    r"|\d+(?:\.\d+){1,3}\s+[一-鿿A-Za-z])"
    r")"
)
_COMPOUND_HEADING_LINE_PATTERN = re.compile(
    r"^(?P<first>(?:第[一二三四五六七八九十百\d]+[章节条](?:[：:\s-]+.+)?|[一二三四五六七八九十]+[、．.].+?))\s+"
    r"(?P<second>\d+(?:\.\d+){1,3}\s+[一-鿿A-Za-z].+)$"
)
_HEADING_WITH_BODY_PATTERN = re.compile(
    r"^(?P<heading>\d+(?:\.\d+){1,3}(?:\s+[^\s。；！？]{1,20}){1,2})\s+"
    r"(?P<body>(?:(?:步骤\s*\d+|[（(]?\d+[.、:：)）]?\s+).+|.+[。；！？].*))$"
)


def _is_footer_line(line: str) -> bool:
    """Return True if the line looks like a page header/footer to be discarded."""
    stripped = line.strip()
    return any(p.match(stripped) for p in _PAGE_FOOTER_PATTERNS)


def _is_structural_break(line: str) -> bool:
    """Return True if this line should start a new paragraph (section title or step)."""
    stripped = line.strip()
    return bool(
        _SECTION_LINE_PATTERN.match(stripped)
        or _STEP_LINE_PATTERN.match(stripped)
    )


def _explode_compound_structural_line(line: str) -> list[str]:
    """Split one extracted line when PDF text glues headings/body together."""
    stripped = line.strip()
    if not stripped:
        return []

    pieces = [piece.strip() for piece in _INLINE_HEADING_BREAK_PATTERN.split(stripped) if piece.strip()]
    expanded: list[str] = []
    for piece in pieces:
        compound_match = _COMPOUND_HEADING_LINE_PATTERN.match(piece)
        if compound_match:
            expanded.append(compound_match.group("first").strip())
            expanded.append(compound_match.group("second").strip())
            continue

        heading_body_match = _HEADING_WITH_BODY_PATTERN.match(piece)
        if heading_body_match:
            expanded.append(heading_body_match.group("heading").strip())
            expanded.append(heading_body_match.group("body").strip())
            continue

        expanded.append(piece)
    return expanded


def normalize_pdf_text(text: str) -> str:
    """Normalize extracted PDF text into stable paragraphs.

    Improvements over the original version:
    - Strips page-footer lines (e.g. "No. 3 / 41").
    - Treats section-heading lines and step lines as paragraph boundaries so
      that structural markers are preserved for the chunker's heading detector.
    - Continuation lines (trailing comma / mid-sentence) are still joined to
      the previous line to avoid spurious paragraph breaks.
    """
    raw_lines: list[str] = []
    for line in text.splitlines():
        normalized_line = WHITESPACE_PATTERN.sub(" ", line).strip()
        if not normalized_line:
            raw_lines.append("")
            continue
        raw_lines.extend(_explode_compound_structural_line(normalized_line))

    # Remove footer / header noise but preserve blank lines (paragraph separators)
    lines = [
        line for line in raw_lines
        if not line or not _is_footer_line(line)
    ]

    paragraphs: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer).strip())
            buffer.clear()

    for line in lines:
        if not line:
            flush()
            continue

        # Section titles and step markers always start a new paragraph
        if _is_structural_break(line):
            flush()
            buffer.append(line)
            continue

        # A line that ends with a sentence-ending punctuation flushes after itself
        # so the next line starts fresh (avoids merging "安装火花塞" into the prior step)
        buffer.append(line)
        if line.endswith(("。", "；", "！", "？", ".", ":", "：")):
            flush()

    flush()
    return "\n\n".join(p for p in paragraphs if p).strip()


@dataclass(frozen=True)
class ExtractedPdfPage:
    """Single PDF page text extracted for knowledge import."""

    page_number: int
    text: str


# ── 目录页检测 ────────────────────────────────────────────────────────────────
# 如果一页里超过 60% 的段落都是纯标题行（无正文句子），视为目录页跳过
_SENTENCE_PATTERN = re.compile(r"[一-鿿]{4,}[，。；！？]")
_TOC_DOTTED_LINE_PATTERN = re.compile(r"[.．·•…]{2,}")


def _is_toc_page(text: str) -> bool:
    """Heuristic: return True if the page looks like a table of contents."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return False

    step_count = sum(1 for p in paragraphs if _STEP_LINE_PATTERN.match(p))
    sectionish_count = sum(1 for p in paragraphs if _SECTION_LINE_PATTERN.match(p))
    sentence_count = sum(1 for p in paragraphs if _SENTENCE_PATTERN.search(p))
    dotted_count = sum(1 for p in paragraphs if _TOC_DOTTED_LINE_PATTERN.search(p))

    # Real TOC pages are usually heading-heavy, sentence-light, and often
    # contain dotted leaders. We require multiple structural clues here to
    # avoid dropping compact procedural pages such as "8.3 拆卸传动装置".
    sparse_sentence_ratio = sentence_count / len(paragraphs) < 0.2
    heading_heavy = sectionish_count >= max(2, len(paragraphs) // 2)
    has_dotted_leaders = dotted_count >= 1
    has_real_body = sentence_count > 0
    if step_count and has_real_body and not has_dotted_leaders:
        return False
    return sparse_sentence_ratio and (heading_heavy or has_dotted_leaders)


def _trim_leading_toc_prelude(text: str) -> str:
    """Trim TOC-like prelude when one PDF page contains both目录 and 正文."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 4:
        return text.strip()

    def _has_sentence(paragraph: str) -> bool:
        return bool(_SENTENCE_PATTERN.search(paragraph))

    candidates: list[tuple[int, bool]] = []
    for index in range(1, len(paragraphs) - 2):
        current = paragraphs[index]
        if not (_SECTION_LINE_PATTERN.match(current) or current.startswith("第")):
            continue
        window = paragraphs[index : min(index + 5, len(paragraphs))]
        if not any(_STEP_LINE_PATTERN.match(item) for item in window[1:]):
            continue
        if not any(_has_sentence(item) for item in window):
            continue
        leading = paragraphs[:index]
        heading_like_leading = sum(
            1
            for item in leading
            if _SECTION_LINE_PATTERN.match(item) or _STEP_LINE_PATTERN.match(item)
        )
        if leading and heading_like_leading / len(leading) >= 0.8:
            candidates.append((index, bool(_TOP_LEVEL_LIST_PATTERN.match(current))))

    # Prefer a true top-level chapter heading such as "一、火花塞" as the
    # restart point when a page contains TOC tail followed by正文.
    for index, is_top_level in candidates:
        if is_top_level:
            return "\n\n".join(paragraphs[index:]).strip()

    return text.strip()


def _detect_repeated_headers(raw_pages: list[str], *, threshold: float = 0.4) -> set[str]:
    """Return short lines that appear in >= threshold fraction of pages.

    These are typically running headers/footers like the document title that
    pypdf extracts as a separate line on every page.
    """
    if not raw_pages:
        return set()
    from collections import Counter

    line_counts: Counter[str] = Counter()
    for page_text in raw_pages:
        seen_on_page: set[str] = set()
        for line in page_text.splitlines():
            stripped = WHITESPACE_PATTERN.sub(" ", line).strip()
            # Only consider short lines (likely headers, not content)
            if stripped and len(stripped) <= 40 and stripped not in seen_on_page:
                line_counts[stripped] += 1
                seen_on_page.add(stripped)

    total = len(raw_pages)
    return {line for line, count in line_counts.items() if count / total >= threshold}


class PdfKnowledgeImportService:
    """Extract PDF pages and turn them into knowledge chunk payloads."""

    def _extract_from_reader(
        self,
        reader: object,
        *,
        skip_toc: bool = True,
    ) -> list[ExtractedPdfPage]:
        """Extract non-empty pages from a pypdf reader object."""
        # First pass: collect raw text to detect repeated header/footer lines
        raw_texts = [page.extract_text() or "" for page in reader.pages]
        repeated_headers = _detect_repeated_headers(raw_texts)

        pages: list[ExtractedPdfPage] = []
        for page_number, raw_text in enumerate(raw_texts, start=1):
            # Strip repeated header lines before normalizing
            cleaned_lines = [
                line for line in raw_text.splitlines()
                if WHITESPACE_PATTERN.sub(" ", line).strip() not in repeated_headers
            ]
            normalized = normalize_pdf_text("\n".join(cleaned_lines))
            if not normalized:
                continue
            normalized = _trim_leading_toc_prelude(normalized)
            if not normalized:
                continue
            if skip_toc and _is_toc_page(normalized):
                continue
            pages.append(ExtractedPdfPage(page_number=page_number, text=normalized))

        if not pages:
            raise ValueError(
                "未从 PDF 中提取到可用文本。该文件可能是扫描件、受保护文件，或需要 OCR 后再导入。"
            )

        return pages

    def extract_pages(self, pdf_path: Path) -> list[ExtractedPdfPage]:
        """Extract non-empty text pages from a PDF file."""
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "当前环境缺少 pypdf，无法解析 PDF。请先安装 requirements.txt 中的依赖。"
            ) from exc

        reader = PdfReader(str(pdf_path))
        return self._extract_from_reader(reader)

    def extract_pages_from_bytes(self, pdf_bytes: bytes) -> list[ExtractedPdfPage]:
        """Extract non-empty text pages from raw PDF bytes."""
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "当前环境缺少 pypdf，无法解析 PDF。请先安装 requirements.txt 中的依赖。"
            ) from exc

        reader = PdfReader(BytesIO(pdf_bytes))
        return self._extract_from_reader(reader)

    def build_document_content(self, pages: list[ExtractedPdfPage]) -> str:
        """Build a single document body from extracted pages."""
        return "\n\n".join(f"[第 {page.page_number} 页]\n{page.text}" for page in pages)

    def build_chunk_payloads(
        self,
        title: str,
        pages: list[ExtractedPdfPage],
        max_chars: int = 480,
    ) -> list[dict[str, str | None]]:
        """Build page-aware chunk payloads for the knowledge service.

        Cross-page section inheritance: when a page starts mid-section (no
        heading on the first paragraph), the last known section_path from the
        previous page is carried forward so that continuation pages are not
        labelled with the bare document title.
        """
        payloads: list[dict[str, str | None]] = []
        last_section_path: str | None = None  # inherited across page boundaries

        for page in pages:
            page_chunks = build_anchored_chunk_payloads(
                page.text,
                title=title,
                max_chars=max_chars,
                page_reference=f"P{page.page_number}",
                inherited_section_path=last_section_path,
            )
            # If a new page starts with tail text from the previous section and
            # then immediately enters a new heading, merge that leading residue
            # back into the previous payload instead of keeping a dangling chunk.
            if (
                payloads
                and page_chunks
                and page_chunks[0].get("section_path") == last_section_path
                and not page_chunks[0].get("step_anchor")
                and len(page_chunks) > 1
                and page_chunks[1].get("section_path") != last_section_path
                and payloads[-1].get("section_path") == last_section_path
            ):
                merged_tail = (page_chunks[0].get("content") or "").strip()
                if merged_tail:
                    previous = (payloads[-1].get("content") or "").strip()
                    payloads[-1]["content"] = f"{previous}\n{merged_tail}".strip() if previous else merged_tail
                page_chunks = page_chunks[1:]
            for chunk_index, chunk_payload in enumerate(page_chunks, start=1):
                suffix = "" if len(page_chunks) == 1 else f" - 第 {chunk_index} 段"
                effective_section_path = chunk_payload.get("section_path") or last_section_path
                effective_section_reference = (
                    chunk_payload.get("section_reference")
                    or (effective_section_path.split(" > ")[-1] if effective_section_path else None)
                )
                payloads.append(
                    {
                        "heading": (
                            f"{effective_section_path}{suffix}"
                            if effective_section_path
                            else f"{title} - 第 {page.page_number} 页{suffix}"
                        ),
                        "content": chunk_payload["content"],
                        "page_reference": chunk_payload.get("page_reference") or f"P{page.page_number}",
                        "section_reference": effective_section_reference,
                        "section_path": effective_section_path,
                        "step_anchor": chunk_payload.get("step_anchor"),
                        "image_anchor": chunk_payload.get("image_anchor"),
                    }
                )
            # Track the terminal heading context even when the page ends with
            # pure heading lines and produces no corresponding content chunk.
            last_sp = resolve_terminal_section_path(
                page.text,
                inherited_section_path=last_section_path,
            )
            if last_sp:
                last_section_path = last_sp

        return payloads
