"""ReAct Agent Engine (absorbed from WeKnora internal/agent/engine.go, think.go, act.go, observe.go)."""

from __future__ import annotations

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
from app.core.rag_engine import extract_source_indices
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

_ANSWER_TOKEN_CHUNK = 24


def _sources_from_tool_result(data: Any) -> list[dict[str, Any]]:
    """Convert knowledge_search retrieve results into SSE sources payload (local 1..k)."""
    if not isinstance(data, list) or not data:
        return []
    sources: list[dict[str, Any]] = []
    for i, r in enumerate(data[:10], 1):
        if not isinstance(r, dict):
            continue
        chunk = r.get("chunk")
        if not isinstance(chunk, dict):
            continue
        page = chunk.get("page", "")
        if page is None:
            page = ""
        elif not isinstance(page, str):
            page = str(page)
        sources.append(
            {
                "index": i,
                "document_id": chunk.get("document_id", ""),
                "page": page,
                "source": chunk.get("source", ""),
                "text": chunk.get("text", ""),
                "relevance_score": float(r.get("relevance") or r.get("reranker_score") or 0.9),
            }
        )
    return sources


def _source_dedup_key(s: dict[str, Any]) -> str:
    return f"{s.get('document_id')}|{s.get('page')}|{(s.get('text') or '')[:80]}"


def _format_numbered_observation(sources: list[dict[str, Any]]) -> str:
    """Rewrite knowledge tool observation with global [来源N] labels for citation alignment."""
    if not sources:
        return ""
    lines: list[str] = []
    for s in sources:
        text = (s.get("text") or "").strip()
        if len(text) > 400:
            text = text[:400] + "…"
        lines.append(
            f"[来源{s.get('index')}] 《{s.get('source') or s.get('document_id')}》"
            f" p{s.get('page') or '-'}:\n{text}"
        )
    return "\n\n".join(lines)


async def _emit_answer_as_tokens(
    answer: str, chunk_size: int = _ANSWER_TOKEN_CHUNK
) -> AsyncGenerator[dict[str, Any], None]:
    """Emit a finished answer as progressive SSE tokens (perceived streaming)."""
    text = answer or ""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield {"type": "token", "content": text[i : i + chunk_size]}


def _dedupe_sources(pool: list[dict[str, Any]], new_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge new sources into pool; reindex 1..N; return full pool snapshot."""
    existing_keys = {_source_dedup_key(s) for s in pool}
    for s in new_sources:
        key = _source_dedup_key(s)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        pool.append(s)
    # Stable reindex so [来源N] stays aligned with UI cards
    for i, s in enumerate(pool, 1):
        s["index"] = i
    return list(pool)


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

    async def _load_documents(self, doc_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch filenames for selected document IDs (best-effort)."""
        if not doc_ids:
            return []
        try:
            from sqlalchemy import select

            from app.db import AsyncSessionLocal, Document

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
                docs = res.scalars().all()
                return [{"id": d.id, "filename": d.filename} for d in docs]
        except Exception as e:
            logger.warning("[AgentEngine] Failed to load document metadata: %s", e)
            return [{"id": d, "filename": d} for d in doc_ids]

    async def _stream_final_answer(
        self, llm: LLM, messages: list[dict[str, Any]]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """True streaming synthesis for the fallback / overflow path."""
        try:
            async for chunk in llm.chat_stream(
                messages, temperature=0.5, include_reasoning=True
            ):
                if isinstance(chunk, dict):
                    ctype = chunk.get("type")
                    if ctype in ("reasoning", "token"):
                        yield {"type": ctype, "content": chunk.get("content", "")}
                    else:
                        yield chunk
                else:
                    yield {"type": "token", "content": str(chunk)}
        except Exception as e:
            logger.warning("[AgentEngine] chat_stream failed, falling back to chat: %s", e)
            try:
                final_ans = await llm.chat(messages, temperature=0.5)
            except Exception as e2:
                logger.error("[AgentEngine] chat fallback failed: %s", e2)
                yield {
                    "type": "thinking",
                    "step": "agent_error",
                    "detail": f"终答生成失败：{e2}",
                }
                return
            async for ev in _emit_answer_as_tokens(final_ans or ""):
                yield ev

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

        # 1.5 Resolve selected document metadata so the model knows the research scope
        documents = await self._load_documents(doc_ids or [])
        if doc_ids and not documents:
            documents = [{"id": d, "filename": d} for d in doc_ids]

        # 2. Build system prompt and initial message array
        system_prompt = build_agent_system_prompt(
            tools,
            user_envelope=user_envelope,
            documents=documents,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": query})

        if documents:
            bound = doc_ids or [d.get("id", "") for d in documents]
            names = "、".join(f"《{d.get('filename') or d.get('id')}》" for d in documents[:5])
            scope_detail = (
                f"已锁定研究范围 {len(documents)} 篇文档（{names}）。"
                f"将通过 knowledge_search 等工具在 doc_ids={bound[:3]}… 内检索。"
            )
        else:
            scope_detail = "未选择参考文档，文档类问题将提示用户先选择文档。"
        yield {
            "type": "thinking",
            "step": "agent_start",
            "detail": f"启动【深度研究模式】(ReAct Agent)。已装载 {len(tools)} 项工具。{scope_detail}",
        }

        repeated_responses = 0
        last_response_text = ""
        nudge_count = 0
        accumulated_answer = ""
        source_pool: list[dict[str, Any]] = []

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

            # 真实模型原生 CoT（若供应商在非流式 tool-use 响应中返回 reasoning_content）
            reasoning_text = (llm_res.get("reasoning") or "").strip()
            if reasoning_text:
                # 分批下发，前端深度思考面板可逐段呈现
                step = 48
                for i in range(0, len(reasoning_text), step):
                    yield {"type": "reasoning", "content": reasoning_text[i : i + step]}

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

                observation = tool_res.output
                if tool_res.success and fn_name in (
                    "knowledge_search",
                    "grep_chunks",
                    "list_document_chunks",
                ):
                    batch = _sources_from_tool_result(tool_res.data)
                    if batch:
                        merged = _dedupe_sources(source_pool, batch)
                        # Rewrite observation with global [来源N] so citations stay aligned
                        numbered = _format_numbered_observation(
                            self._aligned_batch(source_pool, batch)
                        )
                        if numbered:
                            observation = numbered
                        yield {
                            "type": "sources",
                            "sources": merged,
                            "filtered_sources": merged,
                        }
                        yield {
                            "type": "thinking",
                            "step": "tool_result",
                            "detail": (
                                f"工具 `{fn_name}` 执行完成 (成功)：累计 {len(merged)} 条来源。"
                                f"{observation[:120]}..."
                            ),
                        }
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": fn_name,
                            "content": observation or tool_res.output,
                        })
                        continue

                yield {
                    "type": "thinking",
                    "step": "tool_result",
                    "detail": f"工具 `{fn_name}` 执行完成 ({'成功' if tool_res.success else '失败'})：{tool_res.output[:120]}...",
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": observation,
                })

        # ── Surface cumulative sources + emit answer as progressive tokens ──
        if accumulated_answer:
            if source_pool:
                used = extract_source_indices(accumulated_answer)
                filtered = (
                    [s for s in source_pool if s.get("index") in used]
                    if used
                    else list(source_pool)
                )
                yield {
                    "type": "sources",
                    "sources": list(source_pool),
                    "filtered_sources": filtered,
                }
            async for ev in _emit_answer_as_tokens(accumulated_answer):
                yield ev
            return

        # Final synthesis fallback if loop ran out of iterations
        yield {
            "type": "thinking",
            "step": "agent_synthesize",
            "detail": "达到研究轮次上限，正在汇总所有已收集到的文献与证据进行终答生成...",
        }
        messages.append({
            "role": "user",
            "content": (
                "请根据你前面所收集到的所有工具检索结果与笔记，"
                "直接给出最终详细完整的回答。若引用文档事实，请使用与工具 observation 中一致的 [来源N] 编号。"
            ),
        })
        syn_answer_parts: list[str] = []
        async for chunk in self._stream_final_answer(llm, messages):
            if chunk.get("type") == "token":
                syn_answer_parts.append(chunk.get("content", ""))
            yield chunk
        if source_pool:
            syn_answer = "".join(syn_answer_parts)
            used = extract_source_indices(syn_answer)
            filtered = (
                [s for s in source_pool if s.get("index") in used] if used else list(source_pool)
            )
            yield {
                "type": "sources",
                "sources": list(source_pool),
                "filtered_sources": filtered,
            }

    @staticmethod
    def _aligned_batch(
        pool: list[dict[str, Any]], batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return the pool entries that correspond to this batch (newly added or reindexed)."""
        if not batch:
            return []
        batch_keys = {_source_dedup_key(s) for s in batch}
        return [s for s in pool if _source_dedup_key(s) in batch_keys]
