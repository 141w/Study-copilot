"""Plugin: CORRECTIVE_GRADE — grades retrieval quality and retries corrective query if needed."""

from __future__ import annotations

import logging

from app.core.rag_engine import rag_engine
from app.core.retrieval_grader import retrieval_grader
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin

logger = logging.getLogger(__name__)


class CorrectiveGradePlugin(Plugin):
    """Evaluates chunk relevance and runs corrective retrieval when quality is low."""

    def activation_events(self) -> list[EventType]:
        return [EventType.CORRECTIVE_GRADE]

    async def on_event(
        self,
        event_type: EventType,
        state: PipelineState,
        next_fn: NextFn,
    ) -> None:
        target_query = state.standalone_query or state.query
        retrieved = state.retrieved_chunks

        if retrieved:
            quality = await retrieval_grader.grade(target_query, retrieved, state.user_config)
            state.thinking_events.append({
                "type": "thinking",
                "step": "retrieval_check",
                "detail": quality.detail
                or f"检索到 {len(retrieved)} 条结果，质量评分：{quality.score:.2f}（{quality.reason}）",
            })

            if not quality.is_good:
                logger.info(
                    "[Pipeline] Retrieval %s (%s), attempting corrective...",
                    quality.quality,
                    quality.reason,
                )
                state.thinking_events.append({
                    "type": "thinking",
                    "step": "retrieval_retry",
                    "detail": f"检索质量评分偏低（{quality.score:.2f}），正在针对问题核心要点重写查询执行纠错检索...",
                })
                corrected, _ = await rag_engine._corrective_retrieve(
                    state.doc_ids, target_query, state.user_config, top_k=5
                )
                if corrected:
                    state.retrieved_chunks = corrected
                    quality_corrected = await retrieval_grader.grade(
                        target_query, corrected, state.user_config
                    )
                    state.thinking_events.append({
                        "type": "thinking",
                        "step": "retrieval_check",
                        "detail": f"纠错检索完成：{quality_corrected.detail or f'重新召回 {len(corrected)} 条切片，质量评分提升至 {quality_corrected.score:.2f}'}",
                    })
                    logger.info("[Pipeline] Corrective improved: %d chunks", len(corrected))

        if not state.retrieved_chunks:
            # WeKnora semantics: ErrSearchNothing does not block, but short circuits gracefully
            state.short_circuited = True
            state.answer = "文档中没有找到与您问题相关的内容，请尝试换个方式提问。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            return

        await next_fn()
