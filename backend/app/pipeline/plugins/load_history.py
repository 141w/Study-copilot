"""Plugin: LOAD_HISTORY — summarizes or trims long chat history."""

from __future__ import annotations

import logging

from app.agent.context import trim_history
from app.core.llm import LLM
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin

logger = logging.getLogger(__name__)


class LoadHistoryPlugin(Plugin):
    """Summarizes history when length > 10, otherwise passes through."""

    def activation_events(self) -> list[EventType]:
        return [EventType.LOAD_HISTORY]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        history = state.history
        if history and len(history) > 10:
            llm = LLM.from_config(state.user_config)
            early_history = history[:-5]
            recent_history = trim_history(history[-5:], max_messages=5, max_tokens=1500)
            try:
                history_text = "\n".join(
                    f"{'用户' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')[:150]}"
                    for m in early_history[-15:]
                )
                prompt = (
                    "请用 1-2 句话概括以下对话的主要内容和结论，作为后续对话的上下文参考：\n\n"
                    f"{history_text}\n\n摘要："
                )
                summary = await llm.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=150,
                )
                logger.info("[Pipeline] History summarized: %s...", (summary or "")[:80])
                state.history = [
                    {"role": "system", "content": f"之前的对话摘要：{summary}"},
                    *recent_history,
                ]
            except Exception as e:
                logger.warning("[Pipeline] History summarization failed: %s, using truncation", e)
                state.history = trim_history(history, max_messages=10, max_tokens=2000)
        elif history:
            state.history = trim_history(history, max_messages=10, max_tokens=2000)

        await next_fn()
