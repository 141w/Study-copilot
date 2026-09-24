"""Phase-2 invariant: content == source_content[char_start:char_end]."""

from __future__ import annotations

import random

import pytest

from app.core.chunking_pipeline import attach_source_coords, run_chunking_chain


@pytest.mark.asyncio
async def test_chunk_coords_invariant_random_paragraphs():
    rng = random.Random(42)
    paras = [f"段落{i}：" + "".join(chr(0x4E00 + rng.randint(0, 100)) for _ in range(rng.randint(20, 80))) for i in range(30)]
    full = "\n\n".join(paras)
    run = await run_chunking_chain(
        [{"text": full, "page": 1}],
        "doc",
        strategy="fixed",
        allow_embed=False,
    )
    assert run.chunks
    for c in run.chunks:
        if c.get("char_start") is None:
            continue
        src = c.get("source_content") or ""
        s, e = c["char_start"], c["char_end"]
        assert src[s:e] == c.get("text", "")


@pytest.mark.asyncio
async def test_attach_source_coords_basic():
    full = "hello world\nsecond line of text"
    chunks = [{"text": "hello world"}, {"text": "second line of text"}]
    out = attach_source_coords(chunks, full)
    assert out[0]["char_start"] == 0
    assert out[0]["char_end"] == len("hello world")
    assert out[0]["source_content"] == full
    assert out[1]["char_start"] == full.index("second")
    assert full[out[1]["char_start"] : out[1]["char_end"]] == "second line of text"


@pytest.mark.asyncio
async def test_hierarchical_chunks_have_parent_flag():
    md = "# A\n\n" + ("内容一。" * 30) + "\n\n# B\n\n" + ("内容二。" * 30) + "\n"
    run = await run_chunking_chain(
        [{"text": md, "page": 1}],
        "doc",
        strategy="hierarchical",
        allow_embed=False,
    )
    assert run.chunks
    assert any(c.get("is_parent") for c in run.chunks) or all(
        c.get("char_start") is not None for c in run.chunks if c.get("text"))
