"""5.2 追问建议：生成接口 + 解析容错 + 用量计入。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.chat_service import _parse_suggestion_list, generate_followup_suggestions


class TestParseSuggestionList:
    def test_plain_json_array(self):
        raw = '["怎么实现？","有什么坑？","举个例子？"]'
        assert _parse_suggestion_list(raw, 3) == ["怎么实现？", "有什么坑？", "举个例子？"]

    def test_fenced_json_block(self):
        raw = '```json\n["A？","B？","C？"]\n```'
        assert _parse_suggestion_list(raw, 3) == ["A？", "B？", "C？"]

    def test_number_prefix_stripped(self):
        raw = '["1. 第一问？","2) 第二问？"]'
        out = _parse_suggestion_list(raw, 3)
        assert out[0] == "第一问？"
        assert out[1] == "第二问？"

    def test_dedup_and_limit(self):
        raw = '["同？","同？","异？","多？","余？"]'
        out = _parse_suggestion_list(raw, 3)
        assert out == ["同？", "异？", "多？"]

    def test_garbage_returns_empty(self):
        assert _parse_suggestion_list("not json at all", 3) == []
        assert _parse_suggestion_list(None, 3) == []
        assert _parse_suggestion_list("{}", 3) == []

    def test_text_around_json_is_ok(self):
        raw = '好的，以下是建议：\n["追问A？","追问B？","追问C？"]\n希望有帮助'
        assert _parse_suggestion_list(raw, 3) == ["追问A？", "追问B？", "追问C？"]


@pytest.mark.asyncio
async def test_generate_followup_suggestions_success():
    async def fake_chat(*args, **kwargs):
        return '["深入？","应用？","对比？"]'

    mock_llm = AsyncMock()
    mock_llm.chat = fake_chat
    mock_cfg = {"model_name": "test-model", "provider": "openai"}

    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.chat_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=mock_cfg),
        ),
        patch("app.services.usage_service.record_usage", new=AsyncMock()) as mock_usage,
    ):
        db = AsyncMock()
        user = AsyncMock()
        user.id = "u1"
        out = await generate_followup_suggestions(db, user, "问题", "回答内容", n=3)

    assert out == ["深入？", "应用？", "对比？"]
    mock_usage.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_followup_suggestions_llm_error_returns_empty():
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=RuntimeError("boom"))
    mock_cfg = {"model_name": "m", "provider": "openai"}

    with (
        patch("app.core.llm.LLM.from_config", return_value=mock_llm),
        patch(
            "app.services.chat_service.get_llm_config_with_secret",
            new=AsyncMock(return_value=mock_cfg),
        ),
    ):
        db = AsyncMock()
        user = AsyncMock()
        user.id = "u1"
        out = await generate_followup_suggestions(db, user, "q", "a")
    assert out == []


@pytest.mark.asyncio
async def test_generate_followup_suggestions_empty_inputs():
    db = AsyncMock()
    user = AsyncMock()
    user.id = "u1"
    assert await generate_followup_suggestions(db, user, "", "a") == []
    assert await generate_followup_suggestions(db, user, "q", "  ") == []
