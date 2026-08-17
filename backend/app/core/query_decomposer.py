"""
Query Decomposer — 将复杂查询分解为多个可独立检索的子问题

用于 MULTI_HOP 和 COMPARE 策略，将一个复杂问题拆成 2-4 个子问题，
每个子问题可以独立检索文档找到答案。
"""

import logging

from app.core.llm import LLM
from app.core.template_manager import render_template

logger = logging.getLogger(__name__)

class QueryDecomposer:
    """将复杂查询分解为多个可独立检索的子问题"""

    DECOMPOSE_PROMPT = render_template("decomposer/decompose.jinja2")
        "每个子问题应该能独立检索文档找到答案。\n\n"
        "要求：\n"
        "1. 每个子问题保持完整，不依赖其他子问题\n"
        "2. 子问题的答案组合起来能回答原始问题\n"
        "3. 输出格式：每行一个子问题，不要编号，不要解释\n\n"
        "原始问题：{query}\n"
        "子问题："
    )

    EXTRACT_ENTITIES_PROMPT = (
        "从以下对比类问题中提取需要对比的实体（概念、方法、技术等）。\n\n"
        "要求：\n"
        "1. 提取2-4个需要对比的实体\n"
        "2. 每行输出一个实体名称\n"
        "3. 不要编号，不要解释\n\n"
        "对比问题：{query}\n"
        "实体："
    )

    async def decompose(self, query: str, llm: LLM) -> list[str]:
        """将复杂查询分解为子问题列表。

        如果分解失败或结果为空，返回原始查询作为单元素列表。
        """
        try:
            prompt = render_template(self.DECOMPOSE_PROMPT_TEMPLATE, query=query)
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            sub_queries = [q.strip() for q in response.strip().split("\n") if q.strip()]
            # 过滤掉编号前缀（如 "1. ", "2. "）
            cleaned = []
            for q in sub_queries:
                if q and q[0].isdigit() and ". " in q[:5]:
                    q = q.split(". ", 1)[1].strip()
                if q:
                    cleaned.append(q)
            return cleaned if cleaned else [query]
        except Exception as e:
            logger.warning("[Decomposer] Query decomposition failed: %s", e)
            return [query]

    async def extract_entities(self, query: str, llm: LLM) -> list[str]:
        """从对比类问题中提取需要对比的实体。

        如果提取失败，返回空列表。
        """
        try:
            prompt = render_template(self.EXTRACT_ENTITIES_PROMPT_TEMPLATE, query=query)
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            entities = [e.strip() for e in response.strip().split("\n") if e.strip()]
            # 过滤编号前缀
            cleaned = []
            for e in entities:
                if e and e[0].isdigit() and ". " in e[:5]:
                    e = e.split(". ", 1)[1].strip()
                if e:
                    cleaned.append(e)
            return cleaned
        except Exception as e:
            logger.warning("[Decomposer] Entity extraction failed: %s", e)
            return []

query_decomposer = QueryDecomposer()
