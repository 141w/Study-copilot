"""
Retrieval Grader — 评估检索结果质量

两级评估：
1. 规则级：基于 distance 阈值快速判断
2. LLM 级：当规则不确定时，用 LLM 判断 top-3 结果是否与问题相关
"""

import asyncio
import logging

from app.core.llm import LLM
from app.core.vector_store import result_relevance

logger = logging.getLogger(__name__)


class RetrievalQuality:
    """检索质量评估结果"""

    def __init__(self, quality: str, reason: str, score: float):
        self.quality = quality  # "good" | "bad"
        self.reason = reason    # "high_relevance" | "low_relevance" | "irrelevant" | "no_results"
        self.score = score      # 0.0 ~ 1.0

    @property
    def is_good(self) -> bool:
        return self.quality == "good"

    def to_dict(self) -> dict:
        return {"quality": self.quality, "reason": self.reason, "score": self.score}


class RetrievalGrader:
    """检索质量评估器"""

    # 相关度阈值：1/(1+distance)，越高表示越相关
    HIGH_RELEVANCE_THRESHOLD = 0.5   # distance ≤ 1.0 → 相关
    LOW_RELEVANCE_THRESHOLD = 0.2    # distance ≤ 4.0 → 可能相关，需 LLM 确认

    GRADE_PROMPT = (
        "你是一个文档相关性评估器。判断以下文档片段是否与用户问题相关。\n\n"
        "问题：{query}\n\n"
        "文档片段：\n{fragments}\n\n"
        "只需回答 yes 或 no：这些文档片段是否包含回答问题所需的信息？\n"
        "回答："
    )

    async def grade(
        self, query: str, retrieved: list[dict], user_config: dict | None = None
    ) -> RetrievalQuality:
        """评估检索结果质量"""

        # ── 无结果 ──
        if not retrieved:
            logger.info("[Grader] No results → bad (no_results)")
            return RetrievalQuality("bad", "no_results", 0.0)

        # ── 规则级评估 ──
        # 优先使用统一 [0,1] 相关度；旧结果回退 distance 换算
        best_rel = result_relevance(retrieved[0])
        if best_rel is not None:
            best_score = best_rel
        else:
            best_score = 1.0 / (1.0 + retrieved[0].get("distance", 1.0))

        if best_score >= self.HIGH_RELEVANCE_THRESHOLD:
            logger.info("[Grader] High relevance (score=%.3f) → good", best_score)
            return RetrievalQuality("good", "high_relevance", best_score)

        if best_score < self.LOW_RELEVANCE_THRESHOLD:
            logger.info("[Grader] Very low relevance (score=%.3f) → bad", best_score)
            return RetrievalQuality("bad", "low_relevance", best_score)

        # ── 中间地带：用 LLM 判断 ──
        logger.info("[Grader] Ambiguous relevance (score=%.3f), using LLM...", best_score)
        is_relevant = await self._llm_grade(query, retrieved[:3], user_config)

        if is_relevant:
            return RetrievalQuality("good", "llm_confirmed", best_score)
        else:
            return RetrievalQuality("bad", "irrelevant", best_score)

    async def _llm_grade(
        self,
        query: str,
        top_results: list[dict],
        user_config: dict | None = None,
    ) -> bool:
        """用 LLM 判断检索结果是否与问题相关"""
        try:
            llm = LLM.from_config(user_config)

            fragments = []
            for i, r in enumerate(top_results):
                text = r.get("chunk", {}).get("text", "")[:200]
                fragments.append(f"[片段{i+1}] {text}")
            fragments_text = "\n".join(fragments)

            prompt = self.GRADE_PROMPT.format(query=query, fragments=fragments_text)
            # 轻量决策：15s 未响应即降级，避免拖死整条流
            response = await asyncio.wait_for(
                llm.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=10,
                ),
                timeout=10.0,
            )
            response = response.strip().lower()
            is_relevant = response.startswith("yes") or "是" in response[:5]
            logger.info("[Grader] LLM judgment: %s → %s", response[:20], "relevant" if is_relevant else "irrelevant")
            return is_relevant

        except Exception as e:
            logger.warning("[Grader] LLM grading failed: %s, defaulting to relevant", e)
            return True  # 失败时保守处理，认为相关


retrieval_grader = RetrievalGrader()
