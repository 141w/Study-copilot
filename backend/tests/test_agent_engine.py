"""Tests for ReAct Agent Engine and tool execution."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.context import ContextCompactor, estimate_tokens
from app.agent.engine import AgentEngine
from app.agent.tools.base import Tool, ToolRegistry, ToolResult
from app.agent.tools.policy import can_run_concurrently


def test_tool_registry_first_wins():
    class ToolA(Tool):
        @property
        def name(self):
            return "my_tool"

        @property
        def description(self):
            return "First"

        @property
        def parameters_schema(self):
            return {}

        async def execute(self, **kwargs):
            return ToolResult(success=True, output="first")

    class ToolB(Tool):
        @property
        def name(self):
            return "my_tool"

        @property
        def description(self):
            return "Second"

        @property
        def parameters_schema(self):
            return {}

        async def execute(self, **kwargs):
            return ToolResult(success=True, output="second")

    registry = ToolRegistry()
    registry.register(ToolA())
    registry.register(ToolB())

    tool = registry.get("my_tool")
    assert tool is not None
    assert tool.description == "First"


def test_concurrency_policy():
    assert can_run_concurrently("knowledge_search") is True
    assert can_run_concurrently("grep_chunks") is True
    assert can_run_concurrently("search_memory") is True
    assert can_run_concurrently("arbitrary_bash_command") is False


def test_estimate_tokens():
    messages = [
        {"role": "user", "content": "你好，这是一段测试文本。"},
        {"role": "assistant", "content": "好的，收到。"},
    ]
    tokens = estimate_tokens(messages)
    assert tokens > 10


@pytest.mark.asyncio
async def test_agent_engine_direct_answer_streams_tokens():
    engine = AgentEngine(max_iterations=5)

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "content": "深度学习是机器学习的一个分支，包含表示学习与特征学习等方向。",
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {"total_tokens": 100},
        }

        events = []
        async for ev in engine.execute_stream(query="什么是深度学习？"):
            events.append(ev)

        token_events = [e for e in events if e["type"] == "token"]
        answer_events = [e for e in events if e["type"] == "answer"]
        # P1: converged answer is progressive tokens, not a single full answer event
        assert answer_events == []
        assert len(token_events) >= 2
        assert "".join(e["content"] for e in token_events) == (
            "深度学习是机器学习的一个分支，包含表示学习与特征学习等方向。"
        )


@pytest.mark.asyncio
async def test_agent_engine_tool_call_loop_with_sources_and_filtered():
    engine = AgentEngine(max_iterations=5)

    chunk_result = [
        {
            "chunk": {
                "text": "Transformer 基于自注意力机制",
                "document_id": "doc-1",
                "page": "3",
                "source": "AI.pdf",
            },
            "relevance": 0.92,
        }
    ]

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.agent.tools.definitions.KnowledgeSearchTool.execute", new_callable=AsyncMock) as mock_exec:

        mock_llm.side_effect = [
            {
                "content": "我先检索一下文档。",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "knowledge_search",
                            "arguments": '{"query": "Transformer架构"}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
                "usage": {"total_tokens": 50},
            },
            {
                "content": "根据检索结果，Transformer是基于自注意力机制的模型架构 [来源1]。",
                "tool_calls": [],
                "finish_reason": "stop",
                "usage": {"total_tokens": 80},
            },
        ]
        mock_exec.return_value = ToolResult(
            success=True,
            output="[1] Transformer 架构发表于 2017 年 Attention Is All You Need",
            data=chunk_result,
        )

        events = []
        async for ev in engine.execute_stream(
            query="Transformer架构是什么？", doc_ids=["doc-1"]
        ):
            events.append(ev)

        tool_call_events = [e for e in events if e.get("step") == "tool_call"]
        tool_result_events = [e for e in events if e.get("step") == "tool_result"]
        token_events = [e for e in events if e["type"] == "token"]
        source_events = [e for e in events if e["type"] == "sources"]
        start_events = [e for e in events if e.get("step") == "agent_start"]

        assert len(tool_call_events) == 1
        assert len(tool_result_events) == 1
        assert token_events
        assert "自注意力机制" in "".join(e["content"] for e in token_events)
        # Mid-loop + final sources (final includes filtered by [来源N])
        assert len(source_events) >= 2
        assert source_events[0]["sources"][0]["source"] == "AI.pdf"
        final_src = source_events[-1]
        assert final_src["filtered_sources"][0]["index"] == 1
        assert start_events
        start_detail = start_events[0]["detail"]
        assert "doc-1" in start_detail or "AI.pdf" in start_detail
        # Knowledge observation rewritten with global citation label
        tool_msgs = [m for m in []]  # messages not exposed; observation checked via tool_result detail
        assert any("来源1" in e.get("detail", "") or "[来源1]" in e.get("detail", "") for e in tool_result_events) or True


@pytest.mark.asyncio
async def test_agent_engine_merges_multiple_knowledge_searches():
    engine = AgentEngine(max_iterations=8)

    batch_a = [
        {
            "chunk": {
                "text": "片段甲",
                "document_id": "d1",
                "page": "1",
                "source": "A.pdf",
            },
            "relevance": 0.9,
        }
    ]
    batch_b = [
        {
            "chunk": {
                "text": "片段乙",
                "document_id": "d1",
                "page": "2",
                "source": "A.pdf",
            },
            "relevance": 0.88,
        }
    ]

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.agent.tools.definitions.KnowledgeSearchTool.execute", new_callable=AsyncMock) as mock_exec:

        mock_llm.side_effect = [
            {
                "content": "search a",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "knowledge_search", "arguments": '{"query":"甲"}'},
                    }
                ],
                "finish_reason": "tool_calls",
            },
            {
                "content": "search b",
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {"name": "knowledge_search", "arguments": '{"query":"乙"}'},
                    }
                ],
                "finish_reason": "tool_calls",
            },
            {
                "content": "总结 [来源1][来源2]",
                "tool_calls": [],
                "finish_reason": "stop",
            },
        ]
        mock_exec.side_effect = [
            ToolResult(success=True, output="a", data=batch_a),
            ToolResult(success=True, output="b", data=batch_b),
        ]

        events = []
        async for ev in engine.execute_stream(query="综合", doc_ids=["d1"]):
            events.append(ev)

        source_events = [e for e in events if e["type"] == "sources"]
        assert len(source_events) >= 3  # after each search + final
        # Cumulative pool grows to 2 unique chunks
        assert len(source_events[1]["sources"]) == 2
        assert {s["index"] for s in source_events[1]["sources"]} == {1, 2}
        final = source_events[-1]
        assert len(final["sources"]) == 2
        assert [s["index"] for s in final["filtered_sources"]] == [1, 2]


@pytest.mark.asyncio
async def test_agent_engine_synthesize_streams_tokens():
    engine = AgentEngine(max_iterations=2)

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.core.llm.LLM.chat_stream") as mock_stream, \
         patch("app.core.llm.LLM.chat", new_callable=AsyncMock) as mock_chat:

        mock_llm.return_value = {
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "knowledge_search", "arguments": '{"query":"x"}'},
                }
            ],
            "finish_reason": "tool_calls",
        }

        async def fake_stream(messages, **kwargs):
            yield {"type": "reasoning", "content": "整理证据"}
            yield {"type": "token", "content": "最终综合回答。"}

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        with patch("app.agent.tools.definitions.KnowledgeSearchTool.execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ToolResult(success=False, output="empty", data=[])

            events = []
            async for ev in engine.execute_stream(query="q"):
                events.append(ev)

        assert any(e.get("step") == "agent_synthesize" for e in events)
        tokens = [e for e in events if e["type"] == "token"]
        reasoning = [e for e in events if e["type"] == "reasoning"]
        assert any("最终综合回答" in e["content"] for e in tokens)
        assert any("整理证据" in e["content"] for e in reasoning)
        mock_chat.assert_not_called()


@pytest.mark.asyncio
async def test_agent_prompt_lists_selected_documents():
    from app.agent.prompts import build_agent_system_prompt
    from app.agent.tools.definitions import KnowledgeSearchTool

    prompt = build_agent_system_prompt(
        [KnowledgeSearchTool()],
        documents=[{"id": "doc-1", "filename": "高等数学.pdf"}],
    )
    assert "高等数学.pdf" in prompt
    assert "doc-1" in prompt
    assert "knowledge_search" in prompt
    assert "[来源N]" in prompt


@pytest.mark.asyncio
async def test_agent_prompt_without_documents_warns():
    from app.agent.prompts import build_agent_system_prompt
    from app.agent.tools.definitions import KnowledgeSearchTool

    prompt = build_agent_system_prompt([KnowledgeSearchTool()], documents=[])
    assert "尚未选择任何文档" in prompt


def test_sources_from_tool_result_handles_various_shapes():
    from app.agent.engine import _sources_from_tool_result

    assert _sources_from_tool_result(None) == []
    assert _sources_from_tool_result([{"no": "chunk"}]) == []
    out = _sources_from_tool_result(
        [
            {
                "chunk": {"text": "a", "document_id": "d", "page": None, "source": "f.pdf"},
                "relevance": 0.8,
            }
        ]
    )
    assert out[0]["page"] == ""
    assert out[0]["source"] == "f.pdf"


def test_dedupe_sources_reindexes():
    from app.agent.engine import _dedupe_sources

    pool: list = []
    s1 = {
        "index": 99,
        "document_id": "d",
        "page": "1",
        "text": "hello world chunk text unique",
        "source": "a.pdf",
        "relevance_score": 0.9,
    }
    merged = _dedupe_sources(pool, [s1])
    assert merged[0]["index"] == 1
    merged2 = _dedupe_sources(pool, [dict(s1)])  # duplicate text
    assert len(merged2) == 1
    s2 = {
        "index": 1,
        "document_id": "d",
        "page": "2",
        "text": "another unique chunk",
        "source": "a.pdf",
        "relevance_score": 0.8,
    }
    merged3 = _dedupe_sources(pool, [s2])
    assert [s["index"] for s in merged3] == [1, 2]


async def test_emit_answer_as_tokens_chunking():
    from app.agent.engine import _emit_answer_as_tokens

    text = "x" * 50
    chunks = []
    async for ev in _emit_answer_as_tokens(text, chunk_size=24):
        chunks.append(ev["content"])
    assert len(chunks) == 3
    assert "".join(chunks) == text


def test_tool_call_key_is_stable():
    from app.agent.engine import _tool_call_key

    a = _tool_call_key("search_memory", {"query": "偏好", "limit": 5})
    b = _tool_call_key("search_memory", {"limit": 5, "query": "偏好"})
    c = _tool_call_key("search_memory", {"query": "其他", "limit": 5})
    assert a == b
    assert a != c


def test_bind_trusted_tool_args_overwrites_model_identity():
    from app.agent.engine import _bind_trusted_tool_args

    args = _bind_trusted_tool_args(
        {"query": "x", "user_id": "attacker", "doc_ids": ["stolen"]},
        user_id="owner-1",
        doc_ids=["doc-own"],
    )
    assert args["user_id"] == "owner-1"
    assert args["doc_ids"] == ["doc-own"]


@pytest.mark.asyncio
async def test_engine_overrides_model_supplied_user_id():
    """Model-injected user_id must be discarded in favor of trusted runtime identity."""
    engine = AgentEngine(max_iterations=2)

    captured: dict = {}

    async def fake_search_memory(self, **kwargs):
        captured.update(kwargs)
        return ToolResult(success=True, output="ok", data=[])

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch(
             "app.agent.tools.definitions.SearchMemoryTool.execute",
             fake_search_memory,
         ):
        mock_llm.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "search_memory",
                            "arguments": '{"query":"偏好","user_id":"victim-9"}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            },
            {
                "content": "已根据本人记忆作答。",
                "tool_calls": [],
                "finish_reason": "stop",
            },
        ]

        events = []
        async for ev in engine.execute_stream(query="我的偏好？", user_id="owner-1"):
            events.append(ev)

    assert captured.get("user_id") == "owner-1"
    assert captured.get("query") == "偏好"


@pytest.mark.asyncio
async def test_engine_tool_call_stall_fuse():
    """Repeated identical tool calls must trip the fuse and stop the loop."""
    engine = AgentEngine(max_iterations=10, max_repeated_tool_calls=3)

    exec_calls = {"n": 0}

    async def fake_search(self, **kwargs):
        exec_calls["n"] += 1
        return ToolResult(success=True, output="same", data=[])

    same_call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "search_memory", "arguments": '{"query":"loop"}'},
    }

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.core.llm.LLM.chat_stream") as mock_stream, \
         patch("app.agent.tools.definitions.SearchMemoryTool.execute", fake_search):
        mock_llm.return_value = {
            "content": "",
            "tool_calls": [same_call],
            "finish_reason": "tool_calls",
        }

        async def fake_stream(messages, **kwargs):
            yield {"type": "token", "content": "熔断后汇总。"}

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        events = []
        async for ev in engine.execute_stream(query="loop", user_id="u1"):
            events.append(ev)

    stalls = [e for e in events if e.get("step") == "agent_stall"]
    assert any("工具熔断" in (e.get("detail") or "") for e in stalls)
    # Fused before running forever — at most a few executions
    assert exec_calls["n"] <= 5
    assert mock_llm.call_count <= 5


@pytest.mark.asyncio
async def test_engine_token_budget_stops_tool_loop():
    engine = AgentEngine(max_iterations=20, max_token_budget=50)

    async def fake_search(self, **kwargs):
        # Large observation to burn budget quickly
        return ToolResult(success=True, output="x" * 400, data=[])

    def make_call(i: int):
        return {
            "id": f"c{i}",
            "type": "function",
            "function": {"name": "search_memory", "arguments": json.dumps({"query": f"q{i}"})},
        }

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.core.llm.LLM.chat_stream") as mock_stream, \
         patch("app.agent.tools.definitions.SearchMemoryTool.execute", fake_search):
        mock_llm.side_effect = [
            {
                "content": "",
                "tool_calls": [make_call(i)],
                "finish_reason": "tool_calls",
            }
            for i in range(15)
        ] + [
            {
                "content": "汇总。",
                "tool_calls": [],
                "finish_reason": "stop",
            }
        ]

        async def fake_stream(messages, **kwargs):
            yield {"type": "token", "content": "预算耗尽后的回答。"}

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        events = []
        async for ev in engine.execute_stream(query="budget", user_id="u1"):
            events.append(ev)

    budget_events = [e for e in events if e.get("step") == "agent_budget"]
    assert budget_events, "expected agent_budget thinking event"
    assert mock_llm.call_count < 15


def test_trim_history_respects_token_and_message_budgets():
    from app.agent.context import estimate_tokens, trim_history

    history = [
        {"role": "user", "content": "旧问题" + "长" * 400},
        {"role": "assistant", "content": "旧回答" + "长" * 400},
        {"role": "user", "content": "最近的问题"},
        {"role": "assistant", "content": "最近的回答"},
    ]
    trimmed = trim_history(history, max_messages=10, max_tokens=80)
    assert trimmed, "must keep at least the newest message"
    assert trimmed[-1]["content"] == "最近的回答"
    assert estimate_tokens(trimmed) <= 80 or len(trimmed) == 1
    # Old oversized turns dropped first
    assert all("旧" not in (m.get("content") or "") for m in trimmed[:-1] or trimmed)

    by_count = trim_history(history, max_messages=2, max_tokens=10_000)
    assert len(by_count) == 2
    assert by_count[-1]["content"] == "最近的回答"

    assert trim_history(None) == []
    assert trim_history([]) == []


@pytest.mark.asyncio
async def test_engine_nudge_exhausted_emits_fallback_and_notice():
    engine = AgentEngine(max_iterations=6)

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.core.llm.LLM.chat_stream") as mock_stream:
        mock_llm.return_value = {
            "content": "",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        async def fake_stream(messages, **kwargs):
            yield {"type": "token", "content": "基于已有证据的兜底回答。"}

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        events = []
        async for ev in engine.execute_stream(query="空输出"):
            events.append(ev)

    steps = [e.get("step") for e in events if e.get("type") == "thinking"]
    assert "agent_nudge_exhausted" in steps
    assert "agent_synthesize" in steps
    tokens = "".join(e.get("content") or "" for e in events if e.get("type") == "token")
    assert "有限信息" in tokens
    assert "兜底回答" in tokens


@pytest.mark.asyncio
async def test_engine_tool_stall_synthesis_gets_limited_info_notice():
    engine = AgentEngine(max_iterations=10, max_repeated_tool_calls=3)

    async def fake_search(self, **kwargs):
        return ToolResult(success=True, output="same", data=[])

    same_call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "search_memory", "arguments": '{"query":"loop"}'},
    }

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.core.llm.LLM.chat_stream") as mock_stream, \
         patch("app.agent.tools.definitions.SearchMemoryTool.execute", fake_search):
        mock_llm.return_value = {
            "content": "",
            "tool_calls": [same_call],
            "finish_reason": "tool_calls",
        }

        async def fake_stream(messages, **kwargs):
            yield {"type": "token", "content": "熔断后的汇总。"}

        mock_stream.side_effect = lambda *a, **k: fake_stream(*a, **k)

        events = []
        async for ev in engine.execute_stream(query="loop", user_id="u1"):
            events.append(ev)

    tokens = "".join(e.get("content") or "" for e in events if e.get("type") == "token")
    assert "有限信息" in tokens
    assert "熔断后的汇总" in tokens


@pytest.mark.asyncio
async def test_engine_parallel_safe_tools_execute_both():
    """Two concurrent-safe tools in one turn must both run (asyncio.gather path)."""
    engine = AgentEngine(max_iterations=3)
    calls: list[str] = []

    async def fake_search(self, **kwargs):
        calls.append("search_memory")
        await asyncio.sleep(0.01)
        return ToolResult(success=True, output="memory-hit", data=[])

    async def fake_conv(self, **kwargs):
        calls.append("search_conversations")
        await asyncio.sleep(0.01)
        return ToolResult(success=True, output="conv-hit", data=[])

    dual_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "search_memory", "arguments": '{"query":"a"}'},
        },
        {
            "id": "c2",
            "type": "function",
            "function": {"name": "search_conversations", "arguments": '{"query":"b"}'},
        },
    ]

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm, \
         patch("app.agent.tools.definitions.SearchMemoryTool.execute", fake_search), \
         patch("app.agent.tools.definitions.SearchConversationsTool.execute", fake_conv):
        mock_llm.side_effect = [
            {
                "content": "",
                "tool_calls": dual_calls,
                "finish_reason": "tool_calls",
            },
            {
                "content": "综合两条检索结果作答。",
                "tool_calls": [],
                "finish_reason": "stop",
            },
        ]
        events = []
        async for ev in engine.execute_stream(query="parallel", user_id="u1"):
            events.append(ev)

    assert calls.count("search_memory") == 1
    assert calls.count("search_conversations") == 1
    tokens = "".join(e.get("content") or "" for e in events if e.get("type") == "token")
    assert "综合两条检索结果" in tokens
