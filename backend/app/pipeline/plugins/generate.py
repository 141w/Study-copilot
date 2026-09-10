"""Plugin: GENERATE — LLM answer generation (stream-aware) and source citation extraction."""

from __future__ import annotations

import logging

from app.core.rag_engine import extract_source_indices, rag_engine
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

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

        if state.stream_mode and state.event_queue is not None:
            await self._stream_generate(state, target_query)
        else:
            state.answer = await rag_engine.generate_answer(
                target_query,
                state.context_text,
                state.sources_text,
                state.history,
                llm_config=state.user_config,
            )

        state.used_source_indices = extract_source_indices(state.answer)
        await next_fn()

    async def _stream_generate(self, state: PipelineState, target_query: str) -> None:
        """Stream tokens/reasoning onto the event queue while accumulating the full answer."""
        answer_parts: list[str] = []
        async for chunk in rag_engine.generate_answer_stream(
            target_query,
            state.context_text,
            state.sources_text,
            state.history,
            llm_config=state.user_config,
        ):
            if isinstance(chunk, dict):
                ctype = chunk.get("type")
                if ctype == "reasoning":
                    await emit_event(state, {"type": "reasoning", "content": chunk.get("content", "")})
                elif ctype == "token":
                    content = chunk.get("content", "")
                    answer_parts.append(content)
                    await emit_event(state, {"type": "token", "content": content})
                else:
                    await emit_event(state, chunk)
            else:
                text = str(chunk)
                answer_parts.append(text)
                await emit_event(state, {"type": "token", "content": text})

        state.answer = "".join(answer_parts)
