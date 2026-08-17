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
