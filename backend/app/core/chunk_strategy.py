"""Adaptive Chunking Strategy for Study Copilot.

Absorbed from WeKnora chunker architecture:
1. Profiler (profiler.go): Single-pass document structure inspection
2. Strategy Chain Selector: Generates prioritized chunking chain
3. Output Validator (validator.go): Permissive 5-rule check ensuring chunk usability
4. Degradation / Fallback: Seamless progression across tiers ending at fixed chunking
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Heuristic regex patterns
_RE_NUM_SECTION = re.compile(r"^\s*(\d+\.)+\d*\s+", re.MULTILINE)
_RE_ZH_CHAPTER = re.compile(
    r"^\s*第[0-9一二三四五六七八九十百千万]+[章节回篇部卷]\s*", re.MULTILINE
)
_RE_EN_CHAPTER = re.compile(r"^\s*(Chapter|Section|Part|Book)\s+\d+", re.IGNORECASE | re.MULTILINE)
_RE_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


@dataclass
class DocProfile:
    """Document structure profile holding structural signals."""

    total_chars: int = 0
    total_lines: int = 0
    avg_line_len: float = 0.0
    form_feed_count: int = 0
    md_heading_counts: dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(1, 7)})
    md_heading_total: int = 0
    numbered_section_count: int = 0
    chinese_chapter_count: int = 0
    english_chapter_count: int = 0
    has_code: bool = False
    code_lines: int = 0

    def heading_density(self) -> float:
        """Ratio of Markdown headings to total lines."""
        if self.total_lines == 0:
            return 0.0
        return self.md_heading_total / self.total_lines

    def dominant_heading_level(self) -> int:
        """Find structural backbone heading level.

        Preference order (mirrors WeKnora DominantHeadingLevel):
        1. Lowest level (closest to root H1) with at least 3 occurrences
        2. Deepest level present at least once
        3. 0 if no Markdown headings exist
        """
        if self.md_heading_total == 0:
            return 0
        for level in range(1, 7):
            if self.md_heading_counts.get(level, 0) >= 3:
                return level
        for level in range(6, 0, -1):
            if self.md_heading_counts.get(level, 0) > 0:
                return level
        return 0

    def heuristic_marker_total(self) -> int:
        """Sum of non-Markdown chapter/section structure markers."""
        return (
            self.numbered_section_count
            + self.chinese_chapter_count
            + self.english_chapter_count
            + self.form_feed_count
        )


def profile_document(text: str) -> DocProfile:
    """Run a single-pass scan over document text to gather structural indicators.

    Handles fenced code blocks to prevent '#' in comments from being misidentified
    as Markdown headings.
    """
    profile = DocProfile()
    if not text:
        return profile

    profile.total_chars = len(text)
    profile.form_feed_count = text.count("\f")

    lines = text.split("\n")
    profile.total_lines = len(lines)
    if profile.total_lines > 0:
        profile.avg_line_len = profile.total_chars / profile.total_lines

    in_fence = False
    fence_char = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check code fence state
        if stripped.startswith("```") or stripped.startswith("~~~"):
            tag = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_char = tag
                profile.has_code = True
            elif tag == fence_char:
                in_fence = False
                fence_char = ""
            profile.code_lines += 1
            continue

        if in_fence:
            profile.code_lines += 1
            continue

        # Markdown heading check
        m_hd = _RE_MD_HEADING.match(line)
        if m_hd:
            level = len(m_hd.group(1))
            profile.md_heading_counts[level] = profile.md_heading_counts.get(level, 0) + 1
            profile.md_heading_total += 1
            continue

        # Check heuristic markers
        if _RE_ZH_CHAPTER.match(line):
            profile.chinese_chapter_count += 1
        elif _RE_EN_CHAPTER.match(line):
            profile.english_chapter_count += 1
        elif _RE_NUM_SECTION.match(line):
            profile.numbered_section_count += 1

    return profile


def select_chunking_chain(profile: DocProfile, filename: str = "") -> list[str]:
    """Select prioritized chunking strategy chain.

    Returns an ordered list of strategies (e.g. ['hierarchical', 'semantic', 'fixed']).
    """
    fn = filename.lower()
    # Presentations preserve slide boundaries best via fixed chunking
    if fn.endswith((".pptx", ".ppt")):
        return ["fixed"]

    # If document has clear Markdown headings or chapter markers -> hierarchical is primary
    has_strong_headings = profile.dominant_heading_level() > 0 or profile.md_heading_total >= 3
    has_chapters = (profile.chinese_chapter_count + profile.english_chapter_count) >= 2

    if has_strong_headings or has_chapters:
        return ["hierarchical", "semantic", "fixed"]

    # Medium-length unstructured or narrative text: semantic first, then hierarchical, then fixed
    if 2500 <= profile.total_chars <= 30000 and profile.total_lines >= 10:
        return ["semantic", "hierarchical", "fixed"]

    # Short document (< 800 chars): fixed is fastest and safest
    if profile.total_chars < 800:
        return ["fixed"]

    # Default fallback chain
    return ["hierarchical", "fixed"]


def validate_chunks(
    chunks: list[dict[str, Any]],
    total_chars: int,
    chunk_size: int = 500,
) -> tuple[bool, str]:
    """Inspect chunking output usability against WeKnora's 5 validation rules.

    Permissive philosophy: reasonable variance is accepted, but broken output is rejected
    to trigger the next tier in the strategy chain.
    """
    if not chunks:
        return False, "no chunks produced"

    # Rule 2: Single chunk for a document much larger than chunkSize means split failed
    if len(chunks) == 1 and total_chars > 2 * chunk_size:
        return False, "single chunk for large document"

    lengths = [len(c.get("text", "") or c.get("content", "")) for c in chunks]
    max_len = max(lengths) if lengths else 0

    # Rule 3: Fragmentation check - non-tail chunks < 50 characters
    tiny_count = 0
    for l in lengths[:-1]:
        if l < 50:
            tiny_count += 1

    if tiny_count > len(chunks) // 4 and tiny_count > 2:
        return False, "too many tiny chunks"

    # Rule 4: All chunks far below target size
    if max_len < max(chunk_size // 4, 80) and total_chars > chunk_size:
        return False, "all chunks far below target size"

    # Rule 5: Chunk excessively exceeds target size
    # In hierarchical chunking parent contexts or Chinese text, 2.5x is a robust permissive boundary
    if max_len > int(2.5 * chunk_size) and chunk_size > 0:
        return False, f"chunk exceeds target size limit ({max_len} > {int(2.5 * chunk_size)})"

    return True, "ok"


def enrich_chunk_breadcrumbs(
    chunks: list[dict[str, Any]],
    profile: DocProfile | None = None,
) -> list[dict[str, Any]]:
    """Enrich chunks with breadcrumb navigation headers in metadata.

    Inserts `context_header` into `chunk['metadata']` if section or heading info is present.
    """
    for c in chunks:
        meta = c.setdefault("metadata", {})
        section_title = c.get("section_title") or meta.get("section_title")
        heading_chain = c.get("heading_chain") or meta.get("heading_chain")

        if heading_chain:
            meta["context_header"] = heading_chain
        elif section_title:
            meta["context_header"] = section_title

    return chunks
