"""Tests for ReAct Agent Engine and tool execution."""

from __future__ import annotations

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
async def test_agent_engine_direct_answer():
    engine = AgentEngine(max_iterations=5)

    with patch("app.core.llm.LLM.chat_with_tools", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "content": "深度学习是机器学习的一个分支。",
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {"total_tokens": 100},
        }

        events = []
        async for ev in engine.execute_stream(query="什么是深度学习？"):
            events.append(ev)

        answer_events = [e for e in events if e["type"] == "answer"]
        assert len(answer_events) == 1
        assert "机器学习" in answer_events[0]["content"]


@pytest.mark.asyncio
async def test_agent_engine_tool_call_loop():
    engine = AgentEngine(max_iterations=5)

    # First call triggers tool call, second call provides final answer
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
                "content": "根据检索结果，Transformer是基于自注意力机制的模型架构。",
                "tool_calls": [],
                "finish_reason": "stop",
                "usage": {"total_tokens": 80},
            },
        ]
        mock_exec.return_value = ToolResult(
            success=True,
            output="[1] Transformer 架构发表于 2017 年 Attention Is All You Need",
        )

        events = []
        async for ev in engine.execute_stream(query="Transformer架构是什么？"):
            events.append(ev)

        tool_call_events = [e for e in events if e.get("step") == "tool_call"]
        tool_result_events = [e for e in events if e.get("step") == "tool_result"]
        answer_events = [e for e in events if e["type"] == "answer"]

        assert len(tool_call_events) == 1
        assert len(tool_result_events) == 1
        assert len(answer_events) == 1
        assert "自注意力机制" in answer_events[0]["content"]
