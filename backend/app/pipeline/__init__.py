"""Onion Chat Pipeline Package (absorbed from WeKnora architecture)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.rag_engine import _display_relevance, rag_engine
from app.pipeline.base import EventType, PipelineState, Plugin, PluginError
from app.pipeline.builder import PipelineBuilder
from app.pipeline.manager import EventManager
from app.pipeline.plugins.adaptive_retrieve import AdaptiveRetrievePlugin
from app.pipeline.plugins.answer_reflect import AnswerReflectPlugin
from app.pipeline.plugins.build_context import BuildContextPlugin
from app.pipeline.plugins.corrective_grade import CorrectiveGradePlugin
from app.pipeline.plugins.generate import GeneratePlugin
from app.pipeline.plugins.load_history import LoadHistoryPlugin
from app.pipeline.plugins.memory_recall import MemoryRecallPlugin
from app.pipeline.plugins.query_understand import QueryUnderstandPlugin

logger = logging.getLogger(__name__)


def create_default_event_manager() -> EventManager:
    """Instantiate and register all default pipeline plugins."""
    mgr = EventManager()
    mgr.register(LoadHistoryPlugin())
    mgr.register(MemoryRecallPlugin())
    mgr.register(QueryUnderstandPlugin())
    mgr.register(AdaptiveRetrievePlugin())
    mgr.register(CorrectiveGradePlugin())
    mgr.register(BuildContextPlugin())
    mgr.register(GeneratePlugin())
    mgr.register(AnswerReflectPlugin())
    return mgr


# Global default event manager
default_event_manager = create_default_event_manager()


async def execute_chat_pipeline(
    doc_ids: list[str],
    query: str,
    history: list[dict[str, Any]] | None = None,
    user_config: dict[str, Any] | None = None,
    user_id: str | None = None,
    event_manager: EventManager | None = None,
) -> dict[str, Any]:
    """Execute the onion chat pipeline for non-streaming question answering."""
    mgr = event_manager or default_event_manager
    state = PipelineState(
        query=query,
        doc_ids=doc_ids,
        history=history or [],
        user_config=user_config or {},
        user_id=user_id or (user_config.get("user_id") if user_config else None),
    )

    # Declaratively build pipeline stages
    builder = PipelineBuilder()
    builder.add_if(bool(state.history), EventType.LOAD_HISTORY)
    builder.add(EventType.MEMORY_RECALL)
    builder.add(EventType.QUERY_UNDERSTAND)
    builder.add(EventType.ADAPTIVE_RETRIEVE)
    builder.add(EventType.CORRECTIVE_GRADE)
    builder.add(EventType.BUILD_CONTEXT)
    builder.add(EventType.GENERATE)
    builder.add(EventType.ANSWER_REFLECT)

    stages = builder.build()
    logger.info("[Pipeline] Assembled pipeline (%d stages): %s", len(stages), [s.value for s in stages])

    for stage in stages:
        if state.short_circuited:
            break
        await mgr.trigger(stage, state)

    if state.short_circuited and state.short_circuit_result is not None:
        return state.short_circuit_result

    # Format sources list matching legacy rag_engine contract
    sources_list = []
    for i, r in enumerate(state.retrieved_chunks[:10]):
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

    if state.used_source_indices:
        filtered_sources = [s for s in sources_list if s["index"] in state.used_source_indices]
    else:
        filtered_sources = sources_list

    return {
        "answer": state.answer,
        "sources": sources_list,
        "used_source_indices": state.used_source_indices,
        "filtered_sources": filtered_sources,
        "context_used": True,
        "intent": state.intent,
        "thinking_events": state.thinking_events,
    }


__all__ = [
    "EventType",
    "PipelineState",
    "Plugin",
    "PluginError",
    "EventManager",
    "PipelineBuilder",
    "default_event_manager",
    "execute_chat_pipeline",
]
