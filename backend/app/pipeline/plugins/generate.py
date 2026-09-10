"""Plugin: GENERATE — handles non-streaming LLM answer generation and sources formatting."""

from __future__ import annotations

import logging

from app.core.rag_engine import _display_relevance, extract_source_indices, rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin

logger = logging.getLogger(__name__)


class GeneratePlugin(Plugin):
    """Generates the final QA answer given prompt context and conversation history."""

    def activation_events(self) -> list[EventType]:
        return [EventType.GENERATE]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        target_query = state.standalone_query or state.query

        # In non-streaming mode, generate answer text
        ans = await rag_engine.generate_answer(
            target_query,
            state.context_text,
            state.sources_text,
            state.history,
            llm_config=state.user_config,
        )
        state.answer = ans

        # Extract source citations and build source metadata
        state.used_source_indices = extract_source_indices(ans)

        await next_fn()
