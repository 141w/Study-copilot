"""Plugin: ANSWER_REFLECT — validates factual faithfulness and refines hallucinations."""

from __future__ import annotations

import logging

from app.core.answer_reflector import answer_reflector
from app.core.llm import LLM
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

logger = logging.getLogger(__name__)


class AnswerReflectPlugin(Plugin):
    """Reflects on answer faithfulness and triggers self-correction if hallucination is detected."""

    def activation_events(self) -> list[EventType]:
        return [EventType.ANSWER_REFLECT]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        if not state.answer:
            await next_fn()
            return

        target_query = state.standalone_query or state.query
        llm = LLM.from_config(state.user_config)

        try:
            evaluation = await answer_reflector.evaluate(
                target_query, state.context_text, state.answer, llm
            )
            score = evaluation.get("score", 90)
            reason = evaluation.get("reason", "")
            analysis_text = evaluation.get("analysis", "")

            if not evaluation.get("pass", True):
                logger.info(
                    "[Pipeline] Answer reflection failed (%s), refining...",
                    reason,
                )
                fail_event = {
                    "type": "thinking",
                    "step": "reflection_fail",
                    "detail": f"事实依据核验未达标（评分 {score}/100，{reason}）：{analysis_text}。改进策略：{evaluation.get('suggestions', '')}，正在触发自我纠错与精炼...",
                }
                await emit_event(state, fail_event)
                refined = await answer_reflector.refine(
                    target_query,
                    state.context_text,
                    state.answer,
                    evaluation.get("suggestions", ""),
                    llm,
                )
                state.answer = refined
                if state.stream_mode:
                    await emit_event(state, {"type": "answer_refined", "content": refined})
            else:
                pass_event = {
                    "type": "thinking",
                    "step": "reflection_pass",
                    "detail": f"事实依据核验通过（合规评分 {score}/100）：{analysis_text or reason or '核心论述均在参考文档中有可靠依据，未检测到幻觉编造'}",
                }
                await emit_event(state, pass_event)
        except Exception as e:
            logger.warning("[Pipeline] Reflection error for '%s': %s", target_query[:30], e)

        await next_fn()
