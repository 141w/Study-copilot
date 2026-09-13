"""ReAct Agent Engine (absorbed from WeKnora internal/agent/engine.go, think.go, act.go, observe.go)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.agent.context import ContextCompactor, estimate_tokens, trim_history
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
from app.core.tracing import async_trace_span_ctx, trace_span_ctx
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

_ANSWER_TOKEN_CHUNK = 12
_TOOL_EXEC_TIMEOUT = 30.0
_DEFAULT_TOKEN_BUDGET = 48000
_DEFAULT_MAX_REPEATED_TOOL_CALLS = 3
_HISTORY_MAX_MESSAGES = 6
_HISTORY_MAX_TOKENS = 1500
_LIMITED_INFO_REASON = frozenset(
    {
        "nudge_exhausted",
        "tool_stall",
        "token_budget_exhausted",
        "iterations_exhausted",
    }
)
_LIMITED_INFO_PREFIX = (
    "> ⚠️ **该回答基于有限信息**：研究未能完整收敛或预算已耗尽，以下内容可能不完整。\n\n"
)


def _apply_limited_info_notice(answer: str, terminate_reason: str) -> str:
    if terminate_reason not in _LIMITED_INFO_REASON:
        return answer
    text = (answer or "").strip()
    if not text:
        return (
            _LIMITED_INFO_PREFIX
            + "未能基于已收集证据生成完整结论。请补充文档范围、精简问题后重试，"
            "或改用「快速问答」模式。"
        )
    if text.startswith(_LIMITED_INFO_PREFIX.strip()[:8]):
        return text
    return _LIMITED_INFO_PREFIX + text


def _tool_call_key(name: str, args: dict[str, Any]) -> str:
    """Stable hash for (tool_name, canonical args) used by the tool-call stall fuse."""
    payload = json.dumps({"name": name, "args": args}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _bind_trusted_tool_args(
    args: dict[str, Any],
    *,
    user_id: str | None,
    doc_ids: list[str] | None,
) -> dict[str, Any]:
    """Strip model-supplied identity/scope params and re-inject trusted runtime values."""
    args.pop("user_id", None)
    args.pop("doc_ids", None)
    if doc_ids:
        args["doc_ids"] = list(doc_ids)
    if user_id:
        args["user_id"] = user_id
    return args


def _shingle_set(text: str, n: int = 10) -> set[str]:
    norm = "".join((text or "").split())
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i : i + n] for i in range(0, len(norm) - n + 1, max(1, n // 2))}


def _observation_novelty(new_obs: str, prior_obs: list[str]) -> float:
    """1.0 = fully novel, 0.0 = duplicate of prior context. Uses shingle Jaccard."""
    new_s = _shingle_set(new_obs)
    if not new_s:
        return 0.0
    if not prior_obs:
        return 1.0
    prior: set[str] = set()
    for p in prior_obs:
        prior |= _shingle_set(p)
    if not prior:
        return 1.0
    inter = len(new_s & prior)
    union = len(new_s | prior)
    jaccard = inter / union if union else 0.0
    return 1.0 - jaccard


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
        max_token_budget: int = _DEFAULT_TOKEN_BUDGET,
        max_repeated_tool_calls: int = _DEFAULT_MAX_REPEATED_TOOL_CALLS,
    ) -> None:
        self.max_iterations = max_iterations
        self.max_repeated_rounds = max_repeated_rounds
        self.max_concurrency = max_concurrency
        self.max_token_budget = max_token_budget
        self.max_repeated_tool_calls = max_repeated_tool_calls
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
            messages.extend(
                trim_history(
                    history,
                    max_messages=_HISTORY_MAX_MESSAGES,
                    max_tokens=_HISTORY_MAX_TOKENS,
                )
            )
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
        token_usage = 0
        real_prompt_tokens = 0
        real_completion_tokens = 0
        last_tool_key = ""
        repeated_tool_calls = 0
        terminate_reason = "iterations_exhausted"
        prior_observations: list[str] = []
        low_novelty_nudged = False

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
                async with async_trace_span_ctx(
                    "agent.llm.chat_with_tools",
                    metadata={"iteration": iteration},
                    input_data={"query": query[:200]},
                ):
                    llm_res = await llm.chat_with_tools(
                        messages=messages,
                        tools=schemas,
                        temperature=0.4,
                    )
            except Exception as e:
                logger.error("[AgentEngine] LLM invocation error: %s", e)
                err_text = str(e)
                code = "llm_error"
                lower = err_text.lower()
                if "rate" in lower or "429" in err_text or "quota" in lower:
                    code = "rate_limit"
                elif "timeout" in lower or "timed out" in lower:
                    code = "timeout"
                yield {
                    "type": "thinking",
                    "step": "agent_error",
                    "detail": f"模型调用异常：{e}，正在尝试降级并基于已有事实生成回答...",
                }
                yield {
                    "type": "error",
                    "code": code,
                    "message": f"模型调用失败：{err_text}",
                    "recoverable": True,
                }
                break

            content = llm_res.get("content") or ""
            tool_calls = llm_res.get("tool_calls") or []
            finish_reason = llm_res.get("finish_reason") or "stop"

            # 累计 provider 真实用量（优先于启发式 estimate）
            _u = llm_res.get("usage") or {}
            if _u:
                real_prompt_tokens += int(_u.get("prompt_tokens") or 0)
                real_completion_tokens += int(_u.get("completion_tokens") or 0)

            # Incremental token spend via shared estimator (output + tool-call args)
            token_usage += estimate_tokens([{"role": "assistant", "content": content, "tool_calls": tool_calls or []}])

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
                if not content.strip():
                    if nudge_count < 2:
                        nudge_count += 1
                        messages.append({
                            "role": "user",
                            "content": "Please provide your complete answer now as plain text.",
                        })
                        continue
                    # Nudge exhausted — do not pretend convergence; force synthesis + disclaimer
                    yield {
                        "type": "thinking",
                        "step": "agent_nudge_exhausted",
                        "detail": (
                            "连续 Nudge 后模型仍输出空内容，转入基于已有证据的兜底终答，"
                            "并在回答中标注信息可能不完整。"
                        ),
                    }
                    terminate_reason = "nudge_exhausted"
                    break

                # Model decided to stop calling tools and provide final answer
                accumulated_answer = content
                terminate_reason = "model_converged"
                break

            # ── Act: Execute tool calls (parallel for concurrent-safe read tools) ──
            yield {
                "type": "thinking",
                "step": "agent_act",
                "detail": f"第 {iteration} 轮：模型决定调用 {len(tool_calls)} 个工具获取客观证据...",
            }

            tool_loop_break = False
            prepared: list[dict[str, Any]] = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                call_id = tc.get("id", "")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
                except Exception:
                    args = {}

                # Force-bind trusted identity/scope; model cannot override user_id/doc_ids
                args = _bind_trusted_tool_args(args, user_id=user_id, doc_ids=doc_ids)

                # Tool-call stall fuse: same (name, args) repeatedly
                tool_key = _tool_call_key(fn_name, args)
                if tool_key == last_tool_key:
                    repeated_tool_calls += 1
                    if repeated_tool_calls >= self.max_repeated_tool_calls:
                        yield {
                            "type": "thinking",
                            "step": "agent_stall",
                            "detail": (
                                f"检测到连续 {repeated_tool_calls} 次相同工具调用 `{fn_name}`"
                                "（同参数，本次已拦截），触发工具熔断并转入终答汇总。"
                            ),
                        }
                        terminate_reason = "tool_stall"
                        tool_loop_break = True
                        break
                else:
                    repeated_tool_calls = 1
                    last_tool_key = tool_key

                yield {
                    "type": "thinking",
                    "step": "tool_call",
                    "detail": f"正在调用工具 `{fn_name}`，参数: {json.dumps(args, ensure_ascii=False)[:100]}...",
                }

                tool_impl = self.registry.get(fn_name)
                prepared.append(
                    {
                        "name": fn_name,
                        "args": args,
                        "call_id": call_id,
                        "impl": tool_impl,
                        "concurrent": bool(tool_impl) and can_run_concurrently(fn_name),
                    }
                )

            # Stall fuse may set tool_loop_break mid-prepare; still execute tools
            # already accepted into `prepared` so earlier calls in the same turn
            # are not silently dropped (matches pre-parallel semantics).

            async def _run_one(entry: dict[str, Any]) -> ToolResult:
                fn_name = entry["name"]
                if not entry["impl"]:
                    return ToolResult(success=False, output=f"未知工具: {fn_name}", error="unknown_tool")
                with trace_span_ctx(
                    f"agent.tool.{fn_name}",
                    metadata={"tool": fn_name},
                    input_data={k: v for k, v in entry["args"].items() if k not in ("user_id",)},
                ):
                    return await asyncio.wait_for(
                        entry["impl"].execute(**entry["args"]),
                        timeout=_TOOL_EXEC_TIMEOUT,
                    )

            concurrent = [e for e in prepared if e["concurrent"]]
            sequential = [e for e in prepared if not e["concurrent"]]
            results_by_call: dict[str, ToolResult] = {}
            if len(concurrent) > 1:
                gathered = await asyncio.gather(
                    *(_run_one(e) for e in concurrent), return_exceptions=True
                )
                for entry, res in zip(concurrent, gathered):
                    if isinstance(res, Exception):
                        logger.warning("[AgentEngine] parallel tool %s failed: %s", entry["name"], res)
                        res = ToolResult(success=False, output=f"工具执行失败: {res}", error=str(res))
                    results_by_call[entry["call_id"] or entry["name"]] = res
            else:
                for entry in concurrent:
                    results_by_call[entry["call_id"] or entry["name"]] = await _run_one(entry)
            for entry in sequential:
                results_by_call[entry["call_id"] or entry["name"]] = await _run_one(entry)

            for entry in prepared:
                fn_name = entry["name"]
                call_id = entry["call_id"]
                tool_res = results_by_call.get(call_id or fn_name) or ToolResult(
                    success=False, output="工具结果缺失", error="missing_result"
                )

                observation = tool_res.output
                token_usage += estimate_tokens([{"role": "tool", "content": observation or ""}])
                # Marginal information gain: soft-converge when observations stop being novel
                novelty = _observation_novelty(observation or "", prior_observations)
                prior_observations.append(observation or "")
                if novelty < 0.15 and not low_novelty_nudged and len(prior_observations) >= 2:
                    low_novelty_nudged = True
                    yield {
                        "type": "thinking",
                        "step": "agent_low_novelty",
                        "detail": (
                            f"最新工具结果与已有上下文高度重叠（新颖度 {novelty:.2f}），"
                            "已提示模型可考虑收敛给出结论。"
                        ),
                    }
                    messages.append({
                        "role": "user",
                        "content": (
                            "最近的检索结果与已有上下文重叠度很高，边际信息有限。"
                            "若证据已足够，请停止继续调用工具并直接给出最终回答。"
                        ),
                    })
                if token_usage >= self.max_token_budget:
                    # Still record this observation so synthesis can use it
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": observation,
                    })
                    terminate_reason = "token_budget_exhausted"
                    yield {
                        "type": "thinking",
                        "step": "agent_budget",
                        "detail": (
                            f"累计新增 token 预算已达 {token_usage}/{self.max_token_budget}，"
                            "提前终止工具循环并汇总已有证据生成终答。"
                        ),
                    }
                    tool_loop_break = True
                    break
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

            if tool_loop_break:
                break

            # Dual-threshold fuse: stop runaway tool loops once incremental spend exceeds budget
            if token_usage >= self.max_token_budget:
                terminate_reason = "token_budget_exhausted"
                yield {
                    "type": "thinking",
                    "step": "agent_budget",
                    "detail": (
                        f"累计新增 token 预算已达 {token_usage}/{self.max_token_budget}，"
                        "提前终止工具循环并汇总已有证据生成终答。"
                    ),
                }
                break

        logger.info(
            "[AgentEngine] loop finished reason=%s iterations_token_est=%s budget=%s",
            terminate_reason,
            token_usage,
            self.max_token_budget,
        )

        # ── Emit real provider usage for dashboards (chat_service prefers this) ──
        if real_prompt_tokens or real_completion_tokens:
            yield {
                "type": "usage",
                "prompt_tokens": real_prompt_tokens,
                "completion_tokens": real_completion_tokens,
                "estimated_budget": token_usage,
            }

        # ── Surface cumulative sources + emit answer as progressive tokens ──
        if accumulated_answer:
            final_text = _apply_limited_info_notice(accumulated_answer, terminate_reason)
            if source_pool:
                used = extract_source_indices(final_text)
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
            async for ev in _emit_answer_as_tokens(final_text):
                yield ev
            return

        # Final synthesis fallback if loop ran out of iterations / budget / nudge
        synth_detail = {
            "iterations_exhausted": "达到研究轮次上限，正在汇总所有已收集到的文献与证据进行终答生成...",
            "token_budget_exhausted": "Token 预算耗尽，正在汇总已有证据进行终答生成...",
            "nudge_exhausted": "模型多次空输出，正在基于已有工具结果进行兜底终答生成...",
            "tool_stall": "工具调用触发熔断，正在汇总已有证据进行终答生成...",
        }.get(terminate_reason, "正在汇总所有已收集到的文献与证据进行终答生成...")
        yield {
            "type": "thinking",
            "step": "agent_synthesize",
            "detail": synth_detail,
        }
        messages.append({
            "role": "user",
            "content": (
                "请根据你前面所收集到的所有工具检索结果与笔记，"
                "直接给出最终详细完整的回答。若引用文档事实，请使用与工具 observation 中一致的 [来源N] 编号。"
            ),
        })
        if terminate_reason in _LIMITED_INFO_REASON:
            yield {"type": "token", "content": _LIMITED_INFO_PREFIX}
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
