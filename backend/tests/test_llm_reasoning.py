"""
Tests for LLM CoT reasoning stream (reasoning_content + <think> parsing)
and thinking/reasoning persistence in ChatService.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLM
from app.db.database import User
from app.services import chat_service


@pytest.mark.asyncio
async def test_llm_chat_stream_with_reasoning_content():
    llm = LLM(api_key="test-key", base_url="http://test", model="deepseek-reasoner")

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.reasoning_content = "让我推导一下..."
    chunk1.choices[0].delta.content = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.reasoning_content = None
    chunk2.choices[0].delta.content = "答案是 42。"

    async def mock_stream_gen():
        yield chunk1
        yield chunk2

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream_gen()
    llm.client = mock_client

    events = []
    async for item in llm.chat_stream([{"role": "user", "content": "hi"}], include_reasoning=True):
        events.append(item)

    assert len(events) == 2
    assert events[0] == {"type": "reasoning", "content": "让我推导一下..."}
    assert events[1] == {"type": "token", "content": "答案是 42。"}


@pytest.mark.asyncio
async def test_llm_chat_stream_with_think_tags_in_content():
    llm = LLM(api_key="test-key", base_url="http://test", model="qwen-qwq")

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.reasoning_content = None
    chunk1.choices[0].delta.content = "<think>思考步骤1"

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.reasoning_content = None
    chunk2.choices[0].delta.content = "思考步骤2</think>正式回答内容"

    async def mock_stream_gen():
        yield chunk1
        yield chunk2

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream_gen()
    llm.client = mock_client

    events = []
    async for item in llm.chat_stream([{"role": "user", "content": "hi"}], include_reasoning=True):
        events.append(item)

    reasoning_parts = [e["content"] for e in events if e["type"] == "reasoning"]
    token_parts = [e["content"] for e in events if e["type"] == "token"]

    assert "".join(reasoning_parts) == "思考步骤1思考步骤2"
    assert "".join(token_parts) == "正式回答内容"


@pytest.mark.asyncio
async def test_llm_chat_stream_backward_compatibility_str_only():
    llm = LLM(api_key="test-key", base_url="http://test", model="gpt-4o")

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.reasoning_content = "some internal reasoning"
    chunk1.choices[0].delta.content = "Hello"

    async def mock_stream_gen():
        yield chunk1

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream_gen()
    llm.client = mock_client

    events = []
    async for item in llm.chat_stream([{"role": "user", "content": "hi"}], include_reasoning=False):
        events.append(item)

    # When include_reasoning=False, must yield plain string
    assert events == ["Hello"]


@pytest.mark.asyncio
async def test_chat_service_stream_reasoning_and_thinking_persistence(db_session: AsyncSession):
    u = User(
        id="test-user-reasoning",
        username="reasoning_user",
        email="reasoning@example.com",
        password_hash="hash",
    )
    db_session.add(u)
    await db_session.commit()

    async def mock_rag_stream(*args, **kwargs):
        yield {"type": "thinking", "step": "intent_analysis", "detail": "意图解析成功"}
        yield {"type": "reasoning", "content": "这是推理过程"}
        yield {"type": "token", "content": "这是回答正文"}

    with (
        patch.object(chat_service, "get_llm_config_with_secret", return_value={}),
        patch.object(chat_service.rag_engine, "ask_stream", side_effect=mock_rag_stream),
        patch.object(chat_service, "_embed_text", return_value=None),
    ):
        chunks = []
        async for item in chat_service.ask_question_stream(db_session, u, "问个问题", []):
            chunks.append(item)

        assert any(c["type"] == "thinking" and c["step"] == "intent_analysis" for c in chunks)
        assert any(c["type"] == "reasoning" and c["content"] == "这是推理过程" for c in chunks)
        assert any(c["type"] == "token" and c["content"] == "这是回答正文" for c in chunks)
        assert chunks[-1]["type"] == "done"

        # 验证持久化内容
        session_chunk = next(c for c in chunks if c["type"] == "session")
        sess_id = session_chunk["session_id"]
        _, msgs = await chat_service.get_session_history(db_session, u, sess_id)
        assert len(msgs) == 2
        assistant_msg = msgs[1]

        payload = json.loads(assistant_msg.sources)
        assert isinstance(payload, dict)
        assert payload["thinking"][0]["step"] == "intent_analysis"
        assert payload["reasoning"] == "这是推理过程"
