"""EventManager for registering plugins and executing onion handler chains."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.pipeline.base import EventType, PipelineState, Plugin, PluginError

logger = logging.getLogger(__name__)

HandlerFn = Callable[[EventType, PipelineState], Awaitable[None]]


class EventManager:
    """Manages plugins and orchestrates onion middleware chains per event type."""

    def __init__(self) -> None:
        self.listeners: dict[EventType, list[Plugin]] = {}
        self.handlers: dict[EventType, HandlerFn] = {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin and re-build handlers for its activation events."""
        for event_type in plugin.activation_events():
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(plugin)
            self.handlers[event_type] = self._build_handler(self.listeners[event_type])

    def _build_handler(self, plugins: list[Plugin]) -> HandlerFn:
        """Construct onion middleware chain using backwards closure wrapping.

        Each plugin executes its logic and decides when/whether to call await next_fn().
        """

        async def terminal_next(ev: EventType, st: PipelineState) -> None:
            return None

        current_next: HandlerFn = terminal_next

        for plugin in reversed(plugins):
            prev_plugin = plugin
            prev_next = current_next

            async def chained_handler(
                ev: EventType,
                st: PipelineState,
                p: Plugin = prev_plugin,
                nxt: HandlerFn = prev_next,
            ) -> None:
                if st.short_circuited:
                    return

                async def step_next() -> None:
                    await nxt(ev, st)

                await p.on_event(ev, st, step_next)

            current_next = chained_handler

        return current_next

    async def trigger(self, event_type: EventType, state: PipelineState) -> None:
        """Trigger the onion handler chain for a given event type."""
        if state.short_circuited:
            return

        handler = self.handlers.get(event_type)
        if handler is not None:
            try:
                await handler(event_type, state)
            except Exception as e:
                if not isinstance(e, PluginError):
                    logger.exception("[Pipeline] Plugin error on event %s: %s", event_type.value, e)
                    raise PluginError(str(e), event_type=event_type) from e
                raise
