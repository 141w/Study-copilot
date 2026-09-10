"""Plugin: QUERY_UNDERSTAND — analyzes intent and performs context-aware rewriting."""

from __future__ import annotations

import logging

from app.core.llm import LLM
from app.core.query_router import QueryType, query_router
from app.core.rag_engine import rag_engine
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
                {
                    "type": "thinking",
                    "step": "intent_analysis",
                    "detail": f"意图识别：【超出范围】。问题「{state.standalone_query[:40]}」与学习场景无关，终止检索。",
                },
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
                {"type": "thinking", "step": "intent_analysis", "detail": detail},
            )

        await next_fn()

    async def _stream_direct(self, state: PipelineState, llm: LLM) -> None:
        state.short_circuited = True
        await emit_event(
            state,
            {
                "type": "thinking",
                "step": "intent_analysis",
                "detail": f"意图识别：【通用常识问答】。无需检索文档，由模型直接给出解答：「{state.standalone_query}」",
            },
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
            {
                "type": "thinking",
                "step": "intent_analysis",
                "detail": "意图识别：【全篇知识总结】。正在检索并整合文档全部核心切片...",
            },
        )
        all_results = await rag_engine.retrieve(state.doc_ids, "文档内容总结", top_k=100)
        if not all_results:
            state.answer = "未找到任何文档内容，请先上传文档。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            await emit_event(state, {"type": "answer", "content": state.answer})
            return

        from app.core.rag_engine import _display_relevance

        ctx = rag_engine.build_context(all_results, max_context_tokens=60000)
        sources_text = rag_engine.build_sources_text(all_results)
        sources_list = []
        for i, r in enumerate(all_results[:10]):
            chunk = r.get("chunk", {})
            sources_list.append(
                {
                    "index": i + 1,
                    "document_id": chunk.get("document_id", ""),
                    "page": str(chunk.get("page", "")),
                    "source": chunk.get("source", ""),
                    "text": chunk.get("text", ""),
                    "relevance_score": _display_relevance(r),
                }
            )
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
            {
                "type": "thinking",
                "step": "intent_analysis",
                "detail": f"意图识别：【学习笔记沉淀】。正在提取核心概念与考点，编排结构化笔记：「{state.standalone_query}」",
            },
        )
        ctx = ""
        if state.doc_ids:
            results = await rag_engine.retrieve(state.doc_ids, state.standalone_query, top_k=5)
            if results:
                ctx = rag_engine.build_context(results, max_context_tokens=16000)
                sources_list = []
                for i, r in enumerate(results[:10]):
                    chunk = r.get("chunk", {})
                    page = chunk.get("page", "")
                    if page is None:
                        page = ""
                    elif not isinstance(page, str):
                        page = str(page)
                    sources_list.append(
                        {
                            "index": i + 1,
                            "document_id": chunk.get("document_id", ""),
                            "page": page,
                            "source": chunk.get("source", ""),
                            "text": chunk.get("text", ""),
                            "relevance_score": _display_relevance(r),
                        }
                    )
                await emit_event(
                    state,
                    {"type": "sources", "sources": sources_list, "filtered_sources": sources_list},
                )
        await emit_event(
            state,
            {
                "type": "thinking",
                "step": "strategy_select",
                "detail": "策略规划：应用标准化知识卡片模板，生成包含核心定义、原理解析、易错陷阱与思考题的结构化笔记。",
            },
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
