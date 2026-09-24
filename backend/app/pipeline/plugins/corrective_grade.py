"""Plugin: CORRECTIVE_GRADE — grades retrieval quality and retries corrective query if needed."""

from __future__ import annotations

import logging

from app.core.rag_engine import (
    WINDOW_RETRIEVE,
    rag_engine,
    result_doc_count,
    thinking_event,
    window_close_event,
)
from app.core.retrieval_grader import retrieval_grader
from app.pipeline.base import EventType, NextFn, PipelineState, Plugin, emit_event

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
            check_event = thinking_event(
                "retrieval_check",
                quality.detail
                or f"检索到 {len(retrieved)} 条结果，质量评分：{quality.score:.2f}（{quality.reason}）",
                window=WINDOW_RETRIEVE,
                count=len(retrieved),
                doc_count=result_doc_count(retrieved),
            )
            await emit_event(state, check_event)

            if not quality.is_good:
                logger.info(
                    "[Pipeline] Retrieval %s (%s), attempting corrective...",
                    quality.quality,
                    quality.reason,
                )
                await emit_event(
                    state,
                    thinking_event(
                        "retrieval_retry",
                        f"检索质量评分偏低（{quality.score:.2f}），正在针对问题核心要点重写查询执行纠错检索...",
                        window=WINDOW_RETRIEVE,
                        count=len(retrieved),
                        doc_count=result_doc_count(retrieved),
                    ),
                )
                corrected, _ = await rag_engine._corrective_retrieve(
                    state.doc_ids, target_query, state.user_config, top_k=5
                )
                if corrected:
                    state.retrieved_chunks = corrected
                    quality_corrected = await retrieval_grader.grade(
                        target_query, corrected, state.user_config
                    )
                    await emit_event(
                        state,
                        thinking_event(
                            "retrieval_check",
                            f"纠错检索完成：{quality_corrected.detail or f'重新召回 {len(corrected)} 条切片，质量评分提升至 {quality_corrected.score:.2f}'}",
                            window=WINDOW_RETRIEVE,
                            count=len(corrected),
                            doc_count=result_doc_count(corrected),
                        ),
                    )
                    logger.info("[Pipeline] Corrective improved: %d chunks", len(corrected))

        # 4A 硬性语义：检索窗口必须在任何终止路径前关闭
        final_chunks = state.retrieved_chunks or []
        await emit_event(
            state,
            window_close_event(
                WINDOW_RETRIEVE,
                f"检索完成：{len(final_chunks)} 条候选 / {result_doc_count(final_chunks)} 篇文档",
                count=len(final_chunks),
                doc_count=result_doc_count(final_chunks),
                status="done" if final_chunks else "empty",
            ),
        )

        if not state.retrieved_chunks:
            state.short_circuited = True
            state.answer = "文档中没有找到与您问题相关的内容，请尝试换个方式提问。"
            state.short_circuit_result = {
                "answer": state.answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }
            await emit_event(state, {"type": "answer", "content": state.answer})
            return

        await next_fn()
