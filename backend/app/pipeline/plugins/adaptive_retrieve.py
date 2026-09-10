"""Plugin: ADAPTIVE_RETRIEVE — selects retrieval strategy and fetches chunks."""

from __future__ import annotations

import logging

from app.core.adaptive_retriever import adaptive_retriever
from app.core.llm import LLM
from app.core.rag_engine import rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

logger = logging.getLogger(__name__)


class AdaptiveRetrievePlugin(Plugin):
    """Dynamically selects retrieval strategy and retrieves initial candidate chunks."""

    def activation_events(self) -> list[EventType]:
        return [EventType.ADAPTIVE_RETRIEVE]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        llm = LLM.from_config(state.user_config)
        target_query = state.standalone_query or state.query
        strategy = await adaptive_retriever.select_strategy(target_query, llm)
        logger.info("[Pipeline] Adaptive strategy selected: %s", strategy.value)

        retrieved, thinking_events = await adaptive_retriever.retrieve_adaptive(
            state.doc_ids, target_query, strategy, rag_engine, state.user_config
        )
        state.retrieved_chunks = retrieved
        for event in thinking_events:
            await emit_event(state, event)

        await next_fn()
