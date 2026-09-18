"""Multi-turn chat: history injection + completion token budget resolution."""

from __future__ import annotations

from app.core.llm import (
    build_chat_messages,
    is_thinking_model,
    resolve_completion_max_tokens,
)


def test_build_chat_messages_injects_history():
    msgs = build_chat_messages(
        "sys",
        [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
            {"role": "system", "content": "之前的对话摘要：xxx"},
        ],
        "当前问题",
    )
    assert msgs[0] == {"role": "system", "content": "sys"}
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "system", "user"]
    assert msgs[-1]["content"] == "当前问题"


def test_build_chat_messages_skips_empty_history():
    msgs = build_chat_messages("sys", [{"role": "user", "content": "  "}, None], "q")
    assert len(msgs) == 2
    assert msgs[1]["content"] == "q"


def test_resolve_max_tokens_thinking_model_floors():
    assert is_thinking_model("step-3.7-flash") is True
    assert resolve_completion_max_tokens("step-3.7-flash", 2048) >= 8000
    assert resolve_completion_max_tokens("step-3.7-flash", None) == 8000


def test_resolve_max_tokens_normal_model_min_4096():
    assert is_thinking_model("gpt-4o-mini") is False
    assert resolve_completion_max_tokens("gpt-4o-mini", 2048) == 4096
    assert resolve_completion_max_tokens("gpt-4o-mini", 8192) == 8192
    assert resolve_completion_max_tokens("gpt-4o-mini", None) is None
