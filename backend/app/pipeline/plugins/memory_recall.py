"""Plugin: MEMORY_RECALL — recalls user long-term memory and builds prompt envelope."""

from __future__ import annotations

import logging

from app.config import settings
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


class MemoryRecallPlugin(Plugin):
    """Zero-LLM memory recall based on resident blocks and lexical search."""

    def activation_events(self) -> list[EventType]:
        return [EventType.MEMORY_RECALL]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        if getattr(settings, "memory_enabled", True) and state.user_id:
            try:
                from app.db.database import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    recall_res = await memory_service.recall(state.user_id, state.query, db)
                    if recall_res and recall_res.prompt_envelope:
                        state.memory_envelope = recall_res.prompt_envelope
                        logger.info(
                            "[Pipeline] Memory recalled for user %s (%d items)",
                            state.user_id,
                            len(recall_res.resident_items) + len(recall_res.situational_items),
                        )
            except Exception as e:
                logger.warning("[Pipeline] Memory recall failed: %s", e)

        await next_fn()
