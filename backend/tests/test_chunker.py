import pytest

from app.core.chunker import (
    FixedChunker,
    HierarchicalChunker,
    SemanticChunker,
    create_chunker,
    deduplicate_chunks,
)


def test_create_chunker_fixed():
    chunker = create_chunker(method="fixed", chunk_size=500, chunk_overlap=50)
    assert isinstance(chunker, FixedChunker)


def test_create_chunker_semantic():
    chunker = create_chunker(method="semantic")
    assert isinstance(chunker, SemanticChunker)


@pytest.mark.asyncio
async def test_semantic_chunker_no_breakpoints_size_limited(monkeypatch):
    """连贯文档（无语义边界）不得合成单个巨块。

    2026-09-20 实测：40 页技术书 46K 字曾被 SemanticChunker 合成 1 个
    chunk——超出 embedding token 上限（截断成垃圾向量）与 LLM 上下文。
    修复：无语义边界时退化为尺寸受限的句子级切分。
    """
    from app.core.chunker import SemanticChunker

    chunker = SemanticChunker(max_chunk_size=500)

    async def _no_boundaries(sentences: list[str]) -> list[int]:
        return []  # 模拟连贯文档：语义相似度全程高于阈值

    monkeypatch.setattr(chunker, "_find_semantic_boundaries", _no_boundaries)

    # 8 个约 200 字的长句（句号后有空格，保证按句切分），总长 ~1600 字
    text = ("词" * 200 + "。 ") * 8
    pages = [{"text": text, "page": 7}]

    chunks = await chunker.chunk_document(pages, "doc")

    assert len(chunks) > 1, "无语义边界时必须按尺寸切分，不得合成单个巨块"
    assert all(c["char_count"] <= chunker.max_chunk_size + 250 for c in chunks)
    assert all(c["page"] == 7 for c in chunks), "页码映射应保留"


def test_create_chunker_hierarchical():
    chunker = create_chunker(method="hierarchical")
    assert isinstance(chunker, HierarchicalChunker)


@pytest.mark.asyncio
async def test_fixed_chunker():
    chunker = FixedChunker(chunk_size=50, chunk_overlap=10)

    # chunk_document 需要 pages: List[Dict]
    pages = [
        {"page_number": 1, "text": "This is a test paragraph. " * 10},
        {"page_number": 2, "text": "Another page with content. " * 10},
    ]

    chunks = await chunker.chunk_document(pages, source_name="test")

    assert len(chunks) > 0
    assert all(isinstance(chunk, dict) for chunk in chunks)
    assert all("text" in chunk for chunk in chunks)


def test_deduplicate_chunks():
    chunks = [
        {"text": "This is a test chunk.", "metadata": {}},
        {"text": "This is a test chunk.", "metadata": {}},  # duplicate
        {"text": "This is another chunk.", "metadata": {}},
    ]

    deduped = deduplicate_chunks(chunks)
    assert len(deduped) == 2
