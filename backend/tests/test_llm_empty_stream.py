
"""chat_stream 空流检测的单元测试。

背景：部分 LLM 供应商在速率限制或异常时返回「零 chunk 的成功流」
（create 无异常、async for 立即结束、无内容）。旧实现静默通过，
导致上层拿到空回复且不落库（静默失败）。修复：零产出时抛错走重试。
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_empty_stream():
    """构造零 chunk 的异步流（模拟供应商空流）"""
    async def _gen():
        if False:
            yield  # pragma: no cover
    return _gen()


def _make_chunk_stream(chunks):
    """构造带 chunk 的异步流"""
    async def _gen():
        for c in chunks:
            yield c
    return _gen()


def _make_choice(delta=None, finish_reason=None):
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.delta = delta if delta is not None else MagicMock(content=None)
    return choice


def _make_chunk(choice):
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


class TestChatStreamEmptyDetection:
    def _make_llm(self):
        from app.core.llm import LLM
        with patch.object(LLM, "__init__", lambda self, *a, **kw: None):
            llm = LLM.__new__(LLM)
        llm.model = "test-model"
        llm.client = MagicMock()
        llm.reasoning_fields = []
        llm.client.chat.completions.create = AsyncMock()
        return llm

    async def test_empty_stream_raises(self):
        """零 chunk 流 -> 抛 RuntimeError（而非静默返回）"""
        from app.core.llm import LLM
        llm = self._make_llm()
        llm.client.chat.completions.create = AsyncMock(
            side_effect=lambda **kw: _make_empty_stream()
        )
        with pytest.raises(RuntimeError, match="no content"):
            async for _ in llm.chat_stream(
                [{"role": "user", "content": "hi"}], max_retries=0
            ):
                pass

    async def test_empty_stream_retries(self):
        """空流应触发重试（max_retries=1 -> 2 次调用）"""
        from app.core.llm import LLM
        llm = self._make_llm()
        call_count = 0

        async def create(**kw):
            nonlocal call_count
            call_count += 1
            return _make_empty_stream()

        llm.client.chat.completions.create = create
        with pytest.raises(RuntimeError):
            async for _ in llm.chat_stream(
                [{"role": "user", "content": "hi"}], max_retries=1
            ):
                pass
        assert call_count == 2

    async def test_normal_stream_passes(self):
        """正常流（有 content）不抛异常"""
        from app.core.llm import LLM
        llm = self._make_llm()
        chunks = [
            _make_chunk(_make_choice(MagicMock(content="你好"))),
            _make_chunk(_make_choice(MagicMock(content="世界"))),
        ]
        llm.client.chat.completions.create = AsyncMock(
            side_effect=lambda **kw: _make_chunk_stream(chunks)
        )
        tokens = []
        async for t in llm.chat_stream(
            [{"role": "user", "content": "hi"}], max_retries=0
        ):
            tokens.append(t)
        assert tokens == ["你好", "世界"]

    async def test_finish_length_not_empty(self):
        """finish_reason=length 的空流不算空流（截断场景）"""
        from app.core.llm import LLM
        llm = self._make_llm()
        # 流无 content 但 finish_reason=length（极端截断）
        chunks = [_make_chunk(_make_choice(None, finish_reason="length"))]
        llm.client.chat.completions.create = AsyncMock(
            side_effect=lambda **kw: _make_chunk_stream(chunks)
        )
        tokens = []
        async for t in llm.chat_stream(
            [{"role": "user", "content": "hi"}], max_retries=0
        ):
            tokens.append(t)
        assert any("截断" in t for t in tokens)

    async def test_reasoning_only_stream_raises(self):
        """include_reasoning=False 时 reasoning-only 流（无 content）仍算空流"""
        from app.core.llm import LLM
        llm = self._make_llm()
        delta = MagicMock(content=None)
        delta.reasoning_content = "思考过程"
        chunks = [_make_chunk(_make_choice(delta))]
        llm.client.chat.completions.create = AsyncMock(
            side_effect=lambda **kw: _make_chunk_stream(chunks)
        )
        with pytest.raises(RuntimeError, match="no content"):
            async for _ in llm.chat_stream(
                [{"role": "user", "content": "hi"}], max_retries=0,
                include_reasoning=False,
            ):
                pass
