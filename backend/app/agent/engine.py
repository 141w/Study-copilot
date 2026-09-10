"""ReAct Agent Engine (absorbed from WeKnora internal/agent/engine.go, think.go, act.go, observe.go)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.agent.context import ContextCompactor
from app.agent.prompts import build_agent_system_prompt
from app.agent.tools.base import Tool, ToolRegistry, ToolResult
from app.agent.tools.definitions import (
    GetDocumentInfoTool,
    GrepChunksTool,
    KnowledgeSearchTool,
    ListDocumentChunksTool,
    SearchConversationsTool,
    SearchMemoryTool,
)
from app.agent.tools.policy import can_run_concurrently
from app.core.llm import LLM
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Event emitted during ReAct iterations for UI feedback."""

    type: str  # "thinking" | "tool_call" | "tool_result" | "token" | "done" | "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_output: str = ""
    step: str = ""
    detail: str = ""


class AgentEngine:
    """Autonomous ReAct Agent Engine with Think-Act-Observe loop, stall prevention, and safety fuses."""

    def __init__(
        self,
        max_iterations: int = 15,
        max_repeated_rounds: int = 2,
        max_concurrency: int = 4,
    ) -> None:
        self.max_iterations = max_iterations
        self.max_repeated_rounds = max_repeated_rounds
        self.max_concurrency = max_concurrency
        self.compactor = ContextCompactor()

        # Build default tool registry
        self.registry = ToolRegistry()
        self.registry.register(KnowledgeSearchTool())
        self.registry.register(GrepChunksTool())
        self.registry.register(ListDocumentChunksTool())
        self.registry.register(GetDocumentInfoTool())
        self.registry.register(SearchConversationsTool())
        self.registry.register(SearchMemoryTool())

    async def execute_stream(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
        user_config: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the agent research loop, yielding fine-grained thinking and token events."""
        cfg = user_config or {}
        llm = LLM.from_config(cfg)
        tools = self.registry.list_tools()
        schemas = self.registry.to_openai_schemas()

        # 1. Recall memory envelope if user is present
        user_envelope = ""
        if user_id:
            try:
                from app.db.database import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    recall = await memory_service.recall(user_id, query, db)
                    if recall and recall.prompt_envelope:
                        user_envelope = recall.prompt_envelope
            except Exception as e:
                logger.warning("[AgentEngine] Memory recall failed: %s", e)

        # 2. Build system prompt and initial message array
        system_prompt = build_agent_system_prompt(tools, user_envelope=user_envelope)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": query})

        yield {
            "type": "thinking",
            "step": "agent_start",
            "detail": f"启动【深度研究模式】(ReAct Agent)。已装载 {len(tools)} 项工具，正在规划研究路径...",
        }

        repeated_responses = 0
        last_response_text = ""
        nudge_count = 0
        accumulated_answer = ""

        # Main ReAct iteration loop
        for iteration in range(1, self.max_iterations + 1):
            # Check context window and compact if needed
            messages = await self.compactor.maybe_compact(messages, llm)

            yield {
                "type": "thinking",
                "step": "agent_think",
                "detail": f"正在进行第 {iteration}/{self.max_iterations} 轮自主思考与研判...",
            }

            # ── Think: Call LLM with tool schemas ──
            try:
                llm_res = await llm.chat_with_tools(
                    messages=messages,
                    tools=schemas,
                    temperature=0.4,
                )
            except Exception as e:
                logger.error("[AgentEngine] LLM invocation error: %s", e)
                yield {
                    "type": "thinking",
                    "step": "agent_error",
                    "detail": f"模型调用异常：{e}，正在尝试降级并基于已有事实生成回答...",
                }
                break

            content = llm_res.get("content") or ""
            tool_calls = llm_res.get("tool_calls") or []
            finish_reason = llm_res.get("finish_reason") or "stop"

            # Check for length truncation (WeKnora safety rule: refuse partial execution)
            if finish_reason == "length":
                yield {
                    "type": "thinking",
                    "step": "agent_truncated",
                    "detail": "模型输出因达到最大 token 上限被截断，拒绝执行不完整参数，请求模型重试收敛...",
                }
                messages.append({
                    "role": "assistant",
                    "content": content,
                })
                messages.append({
                    "role": "user",
                    "content": "你上一次调用的参数已被截断。请不要生成过长的单次调用，或者直接基于现有结论进行总结。",
                })
                continue

            # Append assistant turn
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # Check for repetitive non-tool responses (stall fuse)
            if not tool_calls:
                if content == last_response_text and content.strip():
                    repeated_responses += 1
                    if repeated_responses >= self.max_repeated_rounds:
                        yield {
                            "type": "thinking",
                            "step": "agent_stall",
                            "detail": "检测到重复回答陷入循环，强制终止研究并输出最终结果。",
                        }
                        accumulated_answer = content
                        break
                else:
                    repeated_responses = 0
                last_response_text = content

                # Empty content nudge (WeKnora rule: nudge <= 2 times if stopped with empty content)
                if not content.strip() and nudge_count < 2:
                    nudge_count += 1
                    messages.append({
                        "role": "user",
                        "content": "Please provide your complete answer now as plain text.",
                    })
                    continue

                # Model decided to stop calling tools and provide final answer
                accumulated_answer = content
                break

            # ── Act: Execute tool calls ──
            yield {
                "type": "thinking",
                "step": "agent_act",
                "detail": f"第 {iteration} 轮：模型决定调用 {len(tool_calls)} 个工具获取客观证据...",
            }

            # Partition into concurrent and barrier calls
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                call_id = tc.get("id", "")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                # Automatically bind implicit runtime parameters
                if doc_ids and "doc_ids" not in args:
                    args["doc_ids"] = doc_ids
                if user_id and "user_id" not in args:
                    args["user_id"] = user_id

                yield {
                    "type": "thinking",
                    "step": "tool_call",
                    "detail": f"正在调用工具 `{fn_name}`，参数: {json.dumps(args, ensure_ascii=False)[:100]}...",
                }

                tool_impl = self.registry.get(fn_name)
                if not tool_impl:
                    tool_res = ToolResult(success=False, output=f"未知工具: {fn_name}", error="unknown_tool")
                else:
                    tool_res = await tool_impl.execute(**args)

                yield {
                    "type": "thinking",
                    "step": "tool_result",
                    "detail": f"工具 `{fn_name}` 执行完成 ({'成功' if tool_res.success else '失败'})：{tool_res.output[:120]}...",
                }

                # Append tool observation message
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": tool_res.output,
                })

        # ── Output answer streaming / completion ──
        if accumulated_answer:
            yield {"type": "answer", "content": accumulated_answer}
        else:
            # Final synthesis fallback if loop ran out of iterations
            yield {
                "type": "thinking",
                "step": "agent_synthesize",
                "detail": "达到研究轮次上限，正在汇总所有已收集到的文献与证据进行终答生成...",
            }
            messages.append({
                "role": "user",
                "content": "请根据你前面所收集到的所有工具检索结果与笔记，直接给出最终详细完整的回答。",
            })
            final_ans = await llm.chat(messages, temperature=0.5)
            yield {"type": "answer", "content": final_ans}
