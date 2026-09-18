"""Multi-turn chat must inject history and keep a safe completion budget."""

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
            {"role": "user", "content": "第一轮问题"},
            {"role": "assistant", "content": "第一轮回答"},
        ],
        "第二轮问题",
    )
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1]["content"] == "第一轮问题"
    assert msgs[2]["content"] == "第一轮回答"
    assert msgs[-1]["content"] == "第二轮问题"


def test_build_chat_messages_skips_empty_history():
    msgs = build_chat_messages("sys", [{"role": "user", "content": "  "}, None], "q")
    assert [m["role"] for m in msgs] == ["system", "user"]


def test_thinking_model_budget_floor():
    assert is_thinking_model("step-3.7-flash")
    assert resolve_completion_max_tokens("step-3.7-flash", 2048) >= 8000
    assert resolve_completion_max_tokens("step-3.7-flash", None) == 8000


def test_thinking_budget_scales_with_long_multiturn_prompt():
    short = resolve_completion_max_tokens("step-3.7-flash", 2048, prompt_chars=0)
    long = resolve_completion_max_tokens("step-3.7-flash", 2048, prompt_chars=20000)
    assert long > short + 2000
    assert long <= 16000


def test_normal_model_budget_floor():
    assert not is_thinking_model("gpt-4o-mini")
    assert resolve_completion_max_tokens("gpt-4o-mini", 2048) == 4096
    assert resolve_completion_max_tokens("gpt-4o-mini", 8192) == 8192
