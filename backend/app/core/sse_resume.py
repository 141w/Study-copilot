"""In-memory SSE event buffer for stream resume (Last-Event-ID).

Process-local only — suitable for single-node self-hosted deployments.
Multi-replica deployments need a shared store (Redis) later.
"""

from __future__ import annotations

import time
import uuid
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


class StreamResumeBuffer:
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

    def get_events_after(
        self, stream_id: str, user_id: str, last_event_id: int | None
    ) -> BufferedStream | None:
        self._evict_expired()
        stream = self._streams.get(stream_id)
        if not stream or stream.user_id != user_id:
            return None
        return stream

    def slice_after(
        self, stream: BufferedStream, last_event_id: int | None
    ) -> list[dict[str, Any]]:
        if last_event_id is None:
            return list(stream.events)
        return [e for e in stream.events if int(e.get("id", 0)) > last_event_id]

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._streams.items() if now - s.created_at > self.ttl_seconds]
        for sid in expired:
            self._streams.pop(sid, None)


stream_resume_buffer = StreamResumeBuffer()
