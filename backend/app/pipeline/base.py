"""Base types and interfaces for Onion Chat Pipeline (absorbed from WeKnora chat_pipeline)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Pipeline lifecycle event types."""

    LOAD_HISTORY = "load_history"
    MEMORY_RECALL = "memory_recall"
    QUERY_UNDERSTAND = "query_understand"
    ADAPTIVE_RETRIEVE = "adaptive_retrieve"
    CORRECTIVE_GRADE = "corrective_grade"
    BUILD_CONTEXT = "build_context"
    ANSWER_REFLECT = "answer_reflect"
    GENERATE = "generate"


@dataclass
class PipelineState:
    """State object passed along the pipeline stages."""

    query: str
    doc_ids: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    user_config: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None

    # Step outputs
    standalone_query: str = ""
    intent: str = ""
    memory_envelope: str = ""
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    context_text: str = ""
    sources_text: str = ""
    used_source_indices: list[int] = field(default_factory=list)
    thinking_events: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""

    # Short-circuit flag (e.g. out of scope or direct answer)
    short_circuited: bool = False
    short_circuit_result: dict[str, Any] | None = None

    # Streaming mode: plugins push SSE events onto event_queue for progressive UI
    stream_mode: bool = False
    event_queue: asyncio.Queue[dict[str, Any]] | None = None


async def emit_event(state: PipelineState, event: dict[str, Any]) -> None:
    """Record a thinking event and forward it to the stream queue when streaming."""
    if event.get("type") == "thinking":
        state.thinking_events.append(event)
    if state.event_queue is not None:
        await state.event_queue.put(event)


class PluginError(Exception):
    """Pipeline execution error."""

    def __init__(self, message: str, event_type: EventType | None = None) -> None:
        super().__init__(message)
        self.event_type = event_type


NextFn = Callable[[], Awaitable[None]]


class Plugin(ABC):
    """Base interface for all chat pipeline plugins."""

    @abstractmethod
    def activation_events(self) -> list[EventType]:
        """Return event types this plugin listens to."""
        ...

    @abstractmethod
    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        """Handle the pipeline event, then call await next_fn() unless short-circuiting."""
        ...
