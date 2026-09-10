"""Tests for Adaptive Chunking Strategy (app/core/chunk_strategy.py)."""

import pytest

from app.core.chunk_strategy import (
    DocProfile,
    enrich_chunk_breadcrumbs,
    profile_document,
    select_chunking_chain,
    validate_chunks,
)


def test_profile_empty_text():
    p = profile_document("")
    assert p.total_chars == 0
    assert p.total_lines == 0
    assert p.dominant_heading_level() == 0


def test_profile_markdown_structure():
    md = """# 操作系统引论
这是引言部分。

## 进程管理
进程是资源分配的基本单位。

## 内存管理
虚拟内存提供了大地址空间。

## 文件系统
文件是外存上存储的数据集合。
"""
    p = profile_document(md)
    assert p.md_heading_counts[1] == 1
    assert p.md_heading_counts[2] == 3
    assert p.md_heading_total == 4
    # Dominant level: level 2 has 3 occurrences (>=3)
    assert p.dominant_heading_level() == 2
    assert p.heading_density() > 0


def test_profile_fenced_code_block_protection():
    doc = """# 主标题

```python
# 这是 Python 注释，不应该被判定为 Markdown 标题
# 另外一行注释
def hello():
    pass
```

## 次级标题
正文内容。
"""
    p = profile_document(doc)
    assert p.has_code is True
    # Only # 主标题 and ## 次级标题 should be counted
    assert p.md_heading_total == 2
    assert p.md_heading_counts[1] == 1
    assert p.md_heading_counts[2] == 1


def test_profile_chinese_and_english_chapters():
    text = """
第一章 基础概念
一些内容。
第二章 核心算法
更多内容。
Chapter 3 Experiments
Results here.
1.1 背景介绍
1.2 研究目标
"""
    p = profile_document(text)
    assert p.chinese_chapter_count >= 2
    assert p.english_chapter_count >= 1
    assert p.numbered_section_count >= 2
    assert p.heuristic_marker_total() >= 5


def test_select_chunking_chain():
    # PPTX -> fixed
    assert select_chunking_chain(DocProfile(), "lecture.pptx") == ["fixed"]
    assert select_chunking_chain(DocProfile(), "SLIDES.PPT") == ["fixed"]

    # Markdown with headings -> hierarchical primary
    p_md = DocProfile(md_heading_total=4, md_heading_counts={2: 3})
    chain = select_chunking_chain(p_md, "notes.md")
    assert chain == ["hierarchical", "semantic", "fixed"]

    # Narrative text (medium length, no headings) -> semantic primary
    p_narrative = DocProfile(total_chars=5000, total_lines=40)
    chain = select_chunking_chain(p_narrative, "novel.txt")
    assert chain == ["semantic", "hierarchical", "fixed"]

    # Tiny text -> fixed
    p_tiny = DocProfile(total_chars=300, total_lines=5)
    assert select_chunking_chain(p_tiny, "short.txt") == ["fixed"]


def test_validate_chunks_rules():
    # Rule 1: No chunks
    ok, reason = validate_chunks([], total_chars=1000)
    assert not ok
    assert "no chunks" in reason

    # Rule 2: Single chunk for large document
    chunks = [{"text": "x" * 1500}]
    ok, reason = validate_chunks(chunks, total_chars=1500, chunk_size=500)
    assert not ok
    assert "single chunk" in reason

    # Rule 3: Too many tiny chunks (<50 chars in non-tail chunks)
    tiny_chunks = [
        {"text": "短"},
        {"text": "短"},
        {"text": "短"},
        {"text": "这是相对正常的一个句子内容"},
        {"text": "结尾"},
    ]
    ok, reason = validate_chunks(tiny_chunks, total_chars=300, chunk_size=200)
    assert not ok
    assert "too many tiny chunks" in reason

    # Rule 4: All chunks far below target size
    all_tiny = [{"text": "短句一"}, {"text": "短句二"}, {"text": "短句三"}]
    ok, reason = validate_chunks(all_tiny, total_chars=800, chunk_size=500)
    assert not ok
    assert "far below target size" in reason

    # Rule 5: Chunk excessively exceeds target size
    giant_chunk = [{"text": "a" * 1600}, {"text": "b" * 200}]
    ok, reason = validate_chunks(giant_chunk, total_chars=1800, chunk_size=500)
    assert not ok
    assert "exceeds target size limit" in reason

    # Normal usable chunks: pass
    normal_chunks = [
        {"text": "第一部分较为详尽的内容。" * 15},
        {"text": "第二部分较为详尽的内容。" * 15},
        {"text": "末尾小段。"},
    ]
    ok, reason = validate_chunks(normal_chunks, total_chars=1000, chunk_size=500)
    assert ok
    assert reason == "ok"


def test_enrich_chunk_breadcrumbs():
    chunks = [
        {"text": "内容1", "section_title": "1.1 引论"},
        {"text": "内容2", "heading_chain": "第一章 > 第二节", "metadata": {}},
        {"text": "内容3"},
    ]
    enriched = enrich_chunk_breadcrumbs(chunks)
    assert enriched[0]["metadata"]["context_header"] == "1.1 引论"
    assert enriched[1]["metadata"]["context_header"] == "第一章 > 第二节"
    assert "context_header" not in enriched[2]["metadata"]
