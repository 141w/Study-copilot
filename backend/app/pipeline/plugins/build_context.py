"""Plugin: BUILD_CONTEXT — formats chunks into prompt context and reference sources."""

from __future__ import annotations

import logging

from app.core.rag_engine import _display_relevance, rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

logger = logging.getLogger(__name__)


def build_sources_list(retrieved: list[dict]) -> list[dict]:
    """Format retrieved chunks into the SSE sources payload (top 10)."""
    sources_list = []
    for i, r in enumerate(retrieved[:10]):
        chunk = r.get("chunk", {})
        chunk_text = chunk.get("text", "")
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
                "text": chunk_text,
                "relevance_score": _display_relevance(r),
            }
        )
    return sources_list


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

        if state.stream_mode:
            sources_list = build_sources_list(state.retrieved_chunks)
            await emit_event(
                state,
                {"type": "sources", "sources": sources_list, "filtered_sources": sources_list},
            )

        await next_fn()
