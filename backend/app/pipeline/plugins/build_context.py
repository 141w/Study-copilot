"""Plugin: BUILD_CONTEXT — formats chunks into prompt context and reference sources."""

from __future__ import annotations

import logging

from app.core.rag_engine import rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin

logger = logging.getLogger(__name__)


class BuildContextPlugin(Plugin):
    """Formats retrieved chunks into token-budgeted context text and source list."""

    def activation_events(self) -> list[EventType]:
        return [EventType.BUILD_CONTEXT]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        user_config = state.user_config
        ctx_budget = 64000
        if user_config and user_config.get("context_window"):
            ctx_budget = max(4000, min(120000, user_config["context_window"] // 2))

        state.context_text = rag_engine.build_context(
            state.retrieved_chunks, max_context_tokens=ctx_budget
        )
        state.sources_text = rag_engine.build_sources_text(state.retrieved_chunks)

        await next_fn()
