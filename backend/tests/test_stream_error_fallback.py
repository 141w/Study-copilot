
"""ask_question_stream 流式异常兜底的单元测试。

覆盖：
- 流内异常时落库 assistant 占位消息（不再出现「有问无答」）
- error + done 事件下发
- 部分回答 + 异常时落库完整部分并标注中断
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def fake_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _fake_user():
    u = MagicMock()
    u.id = "u1"
    return u


class TestAskStreamErrorFallback:
    async def test_stream_exception_persists_placeholder(self, fake_db):
        """流内抛异常 -> 落库占位 assistant 消息 + error/done 事件"""
        from app.services import chat_service

        with patch.object(chat_service, "get_llm_config_with_secret", new=AsyncMock(return_value={})), \
             patch.object(chat_service, "_validate_document_ids", new=AsyncMock(return_value=[])), \
             patch.object(chat_service, "_ensure_session", new=AsyncMock(return_value=("s1", None))), \
             patch.object(chat_service, "_get_history", new=AsyncMock(return_value=[])), \
             patch.object(chat_service, "_embed_text", new=AsyncMock(return_value=None)), \
             patch.object(chat_service, "_insert_message", new=AsyncMock()) as insert_mock, \
             patch.object(chat_service.settings, "pipeline_v2_enabled", False):

            async def boom(*a, **kw):
                raise RuntimeError("model unreachable")
                yield  # pragma: no cover

            with patch.object(chat_service.rag_engine, "ask_stream", side_effect=boom):
                events = [ev async for ev in chat_service.ask_question_stream(
                    fake_db, _fake_user(), "测试问题", [], None, None, mode="fast"
                )]
        types = [e["type"] for e in events]
        assert "error" in types
        assert "done" in types
        assert types.count("done") == 1  # 不应出现双重 done
        err = next(e for e in events if e["type"] == "error")
        assert err["code"] == "stream_error"
        # 4A 硬性语义：异常路径必须补发窗口关闭事件，UI 不得永久转圈
        closes = [
            e
            for e in events
            if e["type"] == "thinking" and e.get("step") == "window_close"
        ]
        close_windows = {c.get("window") for c in closes}
        assert "understand" in close_windows
        assert "retrieve" in close_windows
        assert all(c.get("status") == "error" for c in closes)
        # user + assistant(占位) 两条消息落库
        roles = [c.args[3] for c in insert_mock.call_args_list]
        assert roles == ["user", "assistant"]
        placeholder = insert_mock.call_args_list[1].args[4]
        assert "回答生成失败" in placeholder

    async def test_partial_answer_persisted_with_notice(self, fake_db):
        """部分 token 后异常 -> 落库部分内容 + 中断标注"""
        from app.services import chat_service

        with patch.object(chat_service, "get_llm_config_with_secret", new=AsyncMock(return_value={})), \
             patch.object(chat_service, "_validate_document_ids", new=AsyncMock(return_value=[])), \
             patch.object(chat_service, "_ensure_session", new=AsyncMock(return_value=("s1", None))), \
             patch.object(chat_service, "_get_history", new=AsyncMock(return_value=[])), \
             patch.object(chat_service, "_embed_text", new=AsyncMock(return_value=None)), \
             patch.object(chat_service, "_insert_message", new=AsyncMock()) as insert_mock, \
             patch.object(chat_service.settings, "pipeline_v2_enabled", False):

            async def partial_then_boom(*a, **kw):
                yield {"type": "token", "content": "前半段答案"}
                raise RuntimeError("connection reset")

            with patch.object(chat_service.rag_engine, "ask_stream", side_effect=partial_then_boom):
                events = [ev async for ev in chat_service.ask_question_stream(
                    fake_db, _fake_user(), "测试问题", [], None, None, mode="fast"
                )]
        types = [e["type"] for e in events]
        assert "error" in types and types.count("done") == 1
        placeholder = insert_mock.call_args_list[1].args[4]
        assert "前半段答案" in placeholder
        assert "生成中断" in placeholder
