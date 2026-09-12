"""SSE event buffer for stream resume (Last-Event-ID).

Storage backends:
- In-memory (default): process-local, suitable for single-node self-hosted.
- Pluggable interface so multi-replica deployments can swap in Redis/PG later.

Multi-worker uvicorn: each worker has its own buffer; resume only works if
the resume request lands on the same worker. Use a shared backend for HA.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass
class BufferedStream:
    stream_id: str
    user_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished: bool = False
    interrupted: bool = False


class StreamResumeStore(ABC):
    """Abstract resume buffer — implement for Redis/PG in multi-replica setups."""

    @abstractmethod
    def create(self, user_id: str) -> BufferedStream: ...

    @abstractmethod
    def append(self, stream_id: str, event: dict[str, Any]) -> None: ...

    @abstractmethod
    def mark_finished(self, stream_id: str, *, interrupted: bool = False) -> None: ...

    @abstractmethod
    def get_stream(self, stream_id: str, user_id: str) -> BufferedStream | None: ...

    def get_events_after(
        self, stream_id: str, user_id: str, last_event_id: int | None  # noqa: ARG002
    ) -> BufferedStream | None:
        """Back-compat alias used by chat resume endpoint."""
        return self.get_stream(stream_id, user_id)

    def slice_after(
        self, stream: BufferedStream, last_event_id: int | None
    ) -> list[dict[str, Any]]:
        if last_event_id is None:
            return list(stream.events)
        return [e for e in stream.events if int(e.get("id", 0)) > last_event_id]


class InMemoryStreamResumeStore(StreamResumeStore):
    """Process-local dict buffer with TTL eviction."""

    def __init__(self, ttl_seconds: int | None = None, max_events: int | None = None) -> None:
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else settings.sse_resume_ttl_seconds
        )
        self.max_events = max_events if max_events is not None else settings.sse_resume_max_events
        self._streams: dict[str, BufferedStream] = {}

    def create(self, user_id: str) -> BufferedStream:
        self._evict_expired()
        stream = BufferedStream(stream_id=str(uuid.uuid4()), user_id=user_id)
        self._streams[stream.stream_id] = stream
        return stream

    def append(self, stream_id: str, event: dict[str, Any]) -> None:
        stream = self._streams.get(stream_id)
        if not stream:
            return
        if len(stream.events) >= self.max_events:
            return
        stream.events.append(event)

    def mark_finished(self, stream_id: str, *, interrupted: bool = False) -> None:
        stream = self._streams.get(stream_id)
        if not stream:
            return
        stream.finished = True
        stream.interrupted = interrupted

    def get_stream(self, stream_id: str, user_id: str) -> BufferedStream | None:
        self._evict_expired()
        stream = self._streams.get(stream_id)
        if not stream or stream.user_id != user_id:
            return None
        return stream

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._streams.items() if now - s.created_at > self.ttl_seconds]
        for sid in expired:
            self._streams.pop(sid, None)


# Back-compat alias used by chat API
class StreamResumeBuffer(InMemoryStreamResumeStore):
    """Deprecated name — prefer StreamResumeStore / InMemoryStreamResumeStore."""


def create_resume_store() -> StreamResumeStore:
    """Factory: default in-memory; override via settings.sse_resume_backend later."""
    backend = getattr(settings, "sse_resume_backend", "memory") or "memory"
    if backend == "memory":
        return InMemoryStreamResumeStore()
    logger_name = __name__
    import logging

    logging.getLogger(logger_name).warning(
        "Unknown sse_resume_backend=%r, falling back to in-memory", backend
    )
    return InMemoryStreamResumeStore()


stream_resume_buffer = InMemoryStreamResumeStore()
