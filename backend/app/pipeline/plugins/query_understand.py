"""Plugin: QUERY_UNDERSTAND — analyzes intent and performs context-aware rewriting."""

from __future__ import annotations

import logging

from app.core.llm import LLM
from app.core.query_router import QueryType, query_router
from app.core.rag_engine import (
    WINDOW_RETRIEVE,
    WINDOW_UNDERSTAND,
    rag_engine,
    result_doc_count,
    thinking_event,
    window_close_event,
)
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

logger = logging.getLogger(__name__)


class QueryUnderstandPlugin(Plugin):
    """Understands user query intent, rewrites follow-up questions, and handles short-circuit routes."""

    def activation_events(self) -> list[EventType]:
        return [EventType.QUERY_UNDERSTAND]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        llm = LLM.from_config(state.user_config)
        analysis = await query_router.analyze(state.query, state.doc_ids, state.history, llm)
        state.intent = analysis.intent.value
        state.standalone_query = analysis.standalone_query

        logger.info("[Pipeline] Intent: %s, Query: '%s'", state.intent, state.standalone_query[:50])

        if analysis.intent == QueryType.OUT_OF_SCOPE:
            await emit_event(
                state,
                thinking_event(
                    "intent_analysis",
                    f"意图识别：【超出范围】。问题「{state.standalone_query[:40]}」与学习场景无关，终止检索。",
                    window=WINDOW_UNDERSTAND,
                    status="done",
                ),
            )
            await emit_event(
                state,
                window_close_event(
                    WINDOW_UNDERSTAND, "问题理解完成，短路终止", status="done"
                ),
            )
            state.short_circuited = True
            state.answer = "这个问题超出了我的知识范围，请问一些与学习相关的问题。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            await emit_event(state, {"type": "answer", "content": state.answer})
            return

        if analysis.intent == QueryType.DIRECT_ANSWER:
            if state.stream_mode and state.event_queue is not None:
                await self._stream_direct(state, llm)
                return
            state.short_circuited = True
            ans = await rag_engine._direct_answer(state.standalone_query, state.user_config)
            state.answer = ans
            state.short_circuit_result = {
                "answer": ans,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            return

        if analysis.intent == QueryType.SUMMARY:
            if state.stream_mode and state.event_queue is not None:
                await self._stream_summary(state)
                return
            state.short_circuited = True
            res = await rag_engine._summarize_docs(state.doc_ids, state.user_config)
            state.answer = res.get("answer", "")
            state.short_circuit_result = res
            return

        if analysis.intent == QueryType.NOTE_TAKING:
            if state.stream_mode and state.event_queue is not None:
                await self._stream_note_taking(state)
                return
            state.short_circuited = True
            res = await rag_engine._synthesize_note_doc(
                state.doc_ids, state.standalone_query, state.user_config
            )
            state.answer = res.get("answer", "")
            state.short_circuit_result = res
            return

        # Regular RAG intent: surface rewrite for the stream UI
        if state.stream_mode:
            detail = (
                f"意图识别：【文档知识检索】。结合对话历史消除指代，改写为独立提问：「{state.standalone_query}」"
                if state.standalone_query != state.query
                else f"意图识别：【文档知识检索】。问题独立明确：「{state.standalone_query}」"
            )
            await emit_event(
                state,
                thinking_event(
                    "intent_analysis",
                    detail,
                    window=WINDOW_UNDERSTAND,
                    status="done",
                ),
            )
            await emit_event(
                state,
                window_close_event(
                    WINDOW_UNDERSTAND, "问题理解完成", status="done"
                ),
            )

        await next_fn()

    async def _stream_direct(self, state: PipelineState, llm: LLM) -> None:
        state.short_circuited = True
        await emit_event(
            state,
            thinking_event(
                "intent_analysis",
                f"意图识别：【通用常识问答】。无需检索文档，由模型直接给出解答：「{state.standalone_query}」",
                window=WINDOW_UNDERSTAND,
                status="done",
            ),
        )
        await emit_event(
            state,
            window_close_event(
                WINDOW_UNDERSTAND, "问题理解完成，转直接回答", status="done"
            ),
        )
        from app.core.template_manager import render_template

        system_prompt = render_template("rag/general_chat_system.jinja2")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.standalone_query},
        ]
        answer_parts: list[str] = []
        async for token in llm.chat_stream(messages):
            text = token if isinstance(token, str) else token.get("content", "")
            answer_parts.append(text)
            await emit_event(state, {"type": "token", "content": text})
        state.answer = "".join(answer_parts)
        state.short_circuit_result = {
            "answer": state.answer,
            "sources": [],
            "used_source_indices": [],
            "context_used": False,
        }

    async def _stream_summary(self, state: PipelineState) -> None:
        state.short_circuited = True
        await emit_event(
            state,
            thinking_event(
                "intent_analysis",
                "意图识别：【全篇知识总结】。正在检索并整合文档全部核心切片...",
                window=WINDOW_UNDERSTAND,
                status="done",
            ),
        )
        await emit_event(
            state,
            window_close_event(
                WINDOW_UNDERSTAND, "问题理解完成，转全篇总结", status="done"
            ),
        )
        all_results = await rag_engine.retrieve(
            state.doc_ids,
            "文档内容总结",
            top_k=100,
            retrieval_config=(state.user_config or {}).get("retrieval"),
        )
        if not all_results:
            await emit_event(
                state,
                thinking_event(
                    "adaptive_retrieve",
                    "全篇检索命中 0 条切片",
                    window=WINDOW_RETRIEVE,
                    count=0,
                    doc_count=0,
                    status="empty",
                ),
            )
            await emit_event(
                state,
                window_close_event(
                    WINDOW_RETRIEVE, "检索无结果", count=0, doc_count=0, status="empty"
                ),
            )
            state.answer = "未找到任何文档内容，请先上传文档。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            await emit_event(state, {"type": "answer", "content": state.answer})
            return
        await emit_event(
            state,
            thinking_event(
                "adaptive_retrieve",
                f"全篇检索完成，命中 {len(all_results)} 条切片",
                window=WINDOW_RETRIEVE,
                count=len(all_results),
                doc_count=result_doc_count(all_results),
                status="done",
            ),
        )
        await emit_event(
            state,
            window_close_event(
                WINDOW_RETRIEVE,
                f"检索完成：{len(all_results)} 条切片",
                count=len(all_results),
                doc_count=result_doc_count(all_results),
                status="done",
            ),
        )

        from app.core.rag_engine import build_source_entry

        ctx = rag_engine.build_context(all_results, max_context_tokens=60000)
        sources_text = rag_engine.build_sources_text(all_results)
        sources_list = [build_source_entry(i + 1, r) for i, r in enumerate(all_results[:10])]
        await emit_event(
            state,
            {"type": "sources", "sources": sources_list, "filtered_sources": sources_list},
        )
        answer_parts: list[str] = []
        async for chunk in rag_engine.generate_answer_stream(
            "请总结文档内容", ctx, sources_text, llm_config=state.user_config
        ):
            if isinstance(chunk, dict):
                ctype = chunk.get("type")
                if ctype in ("reasoning", "token"):
                    text = chunk.get("content", "")
                    if ctype == "token":
                        answer_parts.append(text)
                    await emit_event(state, {"type": ctype, "content": text})
                else:
                    await emit_event(state, chunk)
            else:
                text = str(chunk)
                answer_parts.append(text)
                await emit_event(state, {"type": "token", "content": text})
        state.answer = "".join(answer_parts)
        state.short_circuit_result = {
            "answer": state.answer,
            "sources": sources_list,
            "used_source_indices": [],
            "context_used": True,
        }

    async def _stream_note_taking(self, state: PipelineState) -> None:
        from app.core.rag_engine import _display_relevance
        from app.core.template_manager import render_template

        state.short_circuited = True
        await emit_event(state, {"type": "intent", "intent": "note_taking"})
        await emit_event(
            state,
            thinking_event(
                "intent_analysis",
                f"意图识别：【学习笔记沉淀】。正在提取核心概念与考点，编排结构化笔记：「{state.standalone_query}」",
                window=WINDOW_UNDERSTAND,
                status="done",
            ),
        )
        await emit_event(
            state,
            window_close_event(
                WINDOW_UNDERSTAND, "问题理解完成，转笔记沉淀", status="done"
            ),
        )
        ctx = ""
        if state.doc_ids:
            results = await rag_engine.retrieve(
                state.doc_ids,
                state.standalone_query,
                top_k=5,
                retrieval_config=(state.user_config or {}).get("retrieval"),
            )
            await emit_event(
                state,
                thinking_event(
                    "adaptive_retrieve",
                    f"笔记素材检索完成，命中 {len(results)} 条切片",
                    window=WINDOW_RETRIEVE,
                    count=len(results),
                    doc_count=result_doc_count(results),
                    status="done" if results else "empty",
                ),
            )
            await emit_event(
                state,
                window_close_event(
                    WINDOW_RETRIEVE,
                    f"检索完成：{len(results)} 条切片",
                    count=len(results),
                    doc_count=result_doc_count(results),
                    status="done" if results else "empty",
                ),
            )
            if results:
                from app.core.rag_engine import build_source_entry

                ctx = rag_engine.build_context(results, max_context_tokens=16000)
                sources_list = [build_source_entry(i + 1, r) for i, r in enumerate(results[:10])]
                await emit_event(
                    state,
                    {"type": "sources", "sources": sources_list, "filtered_sources": sources_list},
                )
        else:
            await emit_event(
                state,
                window_close_event(
                    WINDOW_RETRIEVE, "未选择文档，跳过检索", count=0, doc_count=0, status="empty"
                ),
            )
        await emit_event(
            state,
            thinking_event(
                "strategy_select",
                "策略规划：应用标准化知识卡片模板，生成包含核心定义、原理解析、易错陷阱与思考题的结构化笔记。",
                window=WINDOW_UNDERSTAND,
            ),
        )
        system_prompt = render_template(
            "notes/synthesize_note.jinja2", query=state.standalone_query, context=ctx
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.standalone_query},
        ]
        answer_parts: list[str] = []
        async for chunk in llm_stream(state, messages):
            if isinstance(chunk, dict):
                ctype = chunk.get("type")
                if ctype in ("reasoning", "token"):
                    text = chunk.get("content", "")
                    if ctype == "token":
                        answer_parts.append(text)
                    await emit_event(state, {"type": ctype, "content": text})
                else:
                    await emit_event(state, chunk)
            else:
                text = str(chunk)
                answer_parts.append(text)
                await emit_event(state, {"type": "token", "content": text})
        state.answer = "".join(answer_parts)
        state.short_circuit_result = {
            "answer": state.answer,
            "sources": [],
            "used_source_indices": [],
            "context_used": bool(ctx),
        }


async def llm_stream(state: PipelineState, messages: list[dict]):
    llm = LLM.from_config(state.user_config)
    async for chunk in llm.chat_stream(messages, include_reasoning=True):
        yield chunk
