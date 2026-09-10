"""Plugin: QUERY_UNDERSTAND — analyzes intent and performs context-aware rewriting."""

from __future__ import annotations

import logging

from app.core.llm import LLM
from app.core.query_router import QueryType, query_router
from app.core.rag_engine import rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin

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
            state.short_circuited = True
            state.answer = "这个问题超出了我的知识范围，请问一些与学习相关的问题。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            return

        if analysis.intent == QueryType.DIRECT_ANSWER:
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
            state.short_circuited = True
            res = await rag_engine._summarize_docs(state.doc_ids, state.user_config)
            state.answer = res.get("answer", "")
            state.short_circuit_result = res
            return

        if analysis.intent == QueryType.NOTE_TAKING:
            state.short_circuited = True
            res = await rag_engine._synthesize_note_doc(
                state.doc_ids, state.standalone_query, state.user_config
            )
            state.answer = res.get("answer", "")
            state.short_circuit_result = res
            return

        # Regular RAG intent continues down the pipeline
        await next_fn()
