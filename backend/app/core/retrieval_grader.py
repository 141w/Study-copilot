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

    def __init__(self, quality: str, reason: str, score: float, detail: str = ""):
        self.quality = quality  # "good" | "bad"
        self.reason = reason  # "high_relevance" | "low_relevance" | "irrelevant" | "no_results" | "llm_confirmed"
        self.score = score  # 0.0 ~ 1.0
        self.detail = detail

    @property
    def is_good(self) -> bool:
        return self.quality == "good"

    def to_dict(self) -> dict:
        return {"quality": self.quality, "reason": self.reason, "score": self.score, "detail": self.detail}


class RetrievalGrader:
    """检索质量评估器"""

    # 相关度阈值：1/(1+distance)，越高表示越相关
    HIGH_RELEVANCE_THRESHOLD = 0.5  # distance ≤ 1.0 → 相关
    LOW_RELEVANCE_THRESHOLD = 0.2  # distance ≤ 4.0 → 可能相关，需 LLM 确认

    GRADE_PROMPT = (
        "你是一个专业的文档相关性审查员。请评估以下召回的文档片段是否包含回答用户问题所需的信息。\n\n"
        "问题：{query}\n\n"
        "文档片段：\n{fragments}\n\n"
        "请输出 JSON 格式：\n"
        '{{"is_relevant": true/false, "analysis": "简要分析（指出哪些片段包含答案要点，或缺少什么关键信息）"}}\n'
        "分析结果："
    )

    async def grade(
        self, query: str, retrieved: list[dict], user_config: dict | None = None
    ) -> RetrievalQuality:
        """评估检索结果质量"""

        # ── 无结果 ──
        if not retrieved:
            logger.info("[Grader] No results → bad (no_results)")
            return RetrievalQuality("bad", "no_results", 0.0, "未检索到任何匹配切片，候选知识集为空")

        # ── 规则级评估 ──
        # 优先使用统一 [0,1] 相关度；旧结果回退 distance 换算
        best_rel = result_relevance(retrieved[0])
        if best_rel is not None:
            best_score = best_rel
        else:
            best_score = 1.0 / (1.0 + retrieved[0].get("distance", 1.0))

        if best_score >= self.HIGH_RELEVANCE_THRESHOLD:
            detail = f"首选切片语义相似度高达 {best_score:.2f}，知识密度高且与问题直接吻合"
            logger.info("[Grader] High relevance (score=%.3f) → good", best_score)
            return RetrievalQuality("good", "high_relevance", best_score, detail)

        if best_score < self.LOW_RELEVANCE_THRESHOLD:
            detail = f"切片最高相似度仅 {best_score:.2f}，低于置信阈值，将触发查询改写纠错"
            logger.info("[Grader] Very low relevance (score=%.3f) → bad", best_score)
            return RetrievalQuality("bad", "low_relevance", best_score, detail)

        # ── 中间地带：用 LLM 判断 ──
        logger.info("[Grader] Ambiguous relevance (score=%.3f), using LLM...", best_score)
        is_relevant, thought = await self._llm_grade(query, retrieved[:3], user_config)

        if is_relevant:
            detail = f"经审查片段包含有效解答信息（{thought or '知识点已命中'}）"
            return RetrievalQuality("good", "llm_confirmed", best_score, detail)
        else:
            detail = f"经审查片段相关度不足（{thought or '缺少核心解答依据'}），将触发纠错"
            return RetrievalQuality("bad", "irrelevant", best_score, detail)

    async def _llm_grade(
        self,
        query: str,
        top_results: list[dict],
        user_config: dict | None = None,
    ) -> tuple[bool, str]:
        """用 LLM 判断检索结果是否与问题相关，返回 (is_relevant, thought)"""
        try:
            llm = LLM.from_config(user_config)

            fragments = []
            for i, r in enumerate(top_results):
                text = r.get("chunk", {}).get("text", "")[:200]
                fragments.append(f"[片段{i + 1}] {text}")
            fragments_text = "\n".join(fragments)

            prompt = self.GRADE_PROMPT.format(query=query, fragments=fragments_text)
            # 轻量决策：10s 未响应即降级，避免拖死整条流
            response = await asyncio.wait_for(
                llm.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=150,
                ),
                timeout=10.0,
            )
            raw = response.strip()
            # 兼容 JSON 解析
            try:
                # 提取可能的代码块
                clean_json = raw
                if "```" in clean_json:
                    clean_json = clean_json.split("```")[1]
                    if clean_json.startswith("json"):
                        clean_json = clean_json[4:]
                data = json.loads(clean_json.strip())
                is_rel = bool(data.get("is_relevant", True))
                analysis = str(data.get("analysis", ""))
                return is_rel, analysis
            except Exception:
                pass

            # 纯文本兜底判断
            is_relevant = raw.lower().startswith("yes") or "是" in raw[:5] or "true" in raw.lower()[:10]
            logger.info(
                "[Grader] LLM judgment: %s → %s",
                raw[:30],
                "relevant" if is_relevant else "irrelevant",
            )
            return is_relevant, raw[:60]

        except Exception as e:
            logger.warning("[Grader] LLM grading failed: %s, defaulting to relevant", e)
            return True, "自动审校超时，默认放行"  # 失败时保守处理，认为相关


retrieval_grader = RetrievalGrader()
