"""PipelineBuilder for declarative assembly of pipeline stages."""

from __future__ import annotations

from app.pipeline.base import EventType


class PipelineBuilder:
    """Dynamically assembles an ordered list of pipeline EventTypes."""

    def __init__(self) -> None:
        self._stages: list[EventType] = []

    def add(self, *stages: EventType) -> PipelineBuilder:
        """Append one or more stages unconditionally."""
        self._stages.extend(stages)
        return self

    def add_if(self, condition: bool, *stages: EventType) -> PipelineBuilder:
        """Append one or more stages only if condition is True."""
        if condition:
            self._stages.extend(stages)
        return self

    def build(self) -> list[EventType]:
        """Return a copy of the ordered stages."""
        return list(self._stages)
