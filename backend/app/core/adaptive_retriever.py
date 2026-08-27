"""
Adaptive Retriever — 根据查询复杂度自适应选择检索策略

策略类型：
- SINGLE:    简单事实题，top-1 直取
- STANDARD:  标准问答，top-5 + rerank
- MULTI_HOP: 多跳推理，分解子问题 + 多次检索 + 合并
- COMPARE:   对比类问题，提取实体 + 分别检索 + 合并
"""

import asyncio
import logging
from enum import Enum

from app.core.llm import LLM
from app.core.query_decomposer import query_decomposer
from app.core.template_manager import render_template

logger = logging.getLogger(__name__)

class RetrievalStrategy(str, Enum):
    SINGLE = "single"
    STANDARD = "standard"
    MULTI_HOP = "multi_hop"
    COMPARE = "compare"

class AdaptiveRetriever:
    """根据查询复杂度选择检索策略"""

    async def select_strategy(self, query: str, llm: LLM) -> RetrievalStrategy:
        """用 LLM 判断查询复杂度，返回最优检索策略。"""
        try:
            prompt = render_template("retriever/strategy_select.jinja2", query=query)
            # 轻量决策：15s 未响应即降级 STANDARD，避免拖死整条流
            response = await asyncio.wait_for(
                llm.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=20,
                ),
                timeout=10.0,
            )
            response = response.strip().lower()

            if "compare" in response:
                return RetrievalStrategy.COMPARE
            elif "multi_hop" in response or "multi" in response:
                return RetrievalStrategy.MULTI_HOP
            elif "single" in response:
                return RetrievalStrategy.SINGLE
            else:
                return RetrievalStrategy.STANDARD

        except Exception as e:
            logger.warning("[Adaptive] Strategy selection failed: %s, defaulting to STANDARD", e)
            return RetrievalStrategy.STANDARD

    async def retrieve_adaptive(
        self,
        doc_ids: list[str],
        query: str,
        strategy: RetrievalStrategy,
        rag_engine,
        user_config: dict | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """根据策略执行自适应检索。

        Returns:
            (results, thinking_events) — 检索结果列表和思考事件列表。
        """
        thinking_events: list[dict] = []

        thinking_events.append({
            "type": "thinking",
            "step": "strategy_select",
            "detail": f"检索策略：{strategy.value}",
        })

        if strategy == RetrievalStrategy.SINGLE:
            results = await rag_engine.retrieve(doc_ids, query, top_k=1)
            thinking_events.append({
                "type": "thinking",
                "step": "adaptive_retrieve",
                "detail": f"单次检索，获取 {len(results)} 条结果",
            })
            return results, thinking_events

        elif strategy == RetrievalStrategy.STANDARD:
            results = await rag_engine.retrieve(doc_ids, query, top_k=5)
            thinking_events.append({
                "type": "thinking",
                "step": "adaptive_retrieve",
                "detail": f"标准检索，获取 {len(results)} 条结果",
            })
            return results, thinking_events

        elif strategy == RetrievalStrategy.MULTI_HOP:
            return await self._multi_hop_retrieve(doc_ids, query, rag_engine, user_config, thinking_events)

        elif strategy == RetrievalStrategy.COMPARE:
            return await self._compare_retrieve(doc_ids, query, rag_engine, user_config, thinking_events)

        # 兜底
        results = await rag_engine.retrieve(doc_ids, query, top_k=5)
        return results, thinking_events

    async def _multi_hop_retrieve(
        self,
        doc_ids: list[str],
        query: str,
        rag_engine,
        user_config: dict | None = None,
        thinking_events: list[dict] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """多跳检索：分解查询 → 分别检索 → 合并去重"""
        if thinking_events is None:
            thinking_events = []

        llm_config = user_config or {}
        llm = LLM(
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model_name"),
        )

        sub_queries = await query_decomposer.decompose(query, llm)
        logger.info("[Adaptive] MULTI_HOP: decomposed into %d sub-queries", len(sub_queries))

        thinking_events.append({
            "type": "thinking",
            "step": "query_decompose",
            "detail": f"分解为 {len(sub_queries)} 个子问题：" + "；".join(sub_queries),
        })

        all_results = []
        for sq in sub_queries:
            results = await rag_engine.retrieve(doc_ids, sq, top_k=3)
            all_results.extend(results)

        merged = rag_engine.deduplicate_results(all_results)
        # 按距离排序，取 top 5
        merged.sort(key=lambda x: x.get("distance", float("inf")))
        merged = merged[:5]

        thinking_events.append({
            "type": "thinking",
            "step": "adaptive_retrieve",
            "detail": f"多跳检索完成，合并后 {len(merged)} 条结果",
        })

        return merged, thinking_events

    async def _compare_retrieve(
        self,
        doc_ids: list[str],
        query: str,
        rag_engine,
        user_config: dict | None = None,
        thinking_events: list[dict] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """对比检索：提取实体 → 分别检索 → 合并去重"""
        if thinking_events is None:
            thinking_events = []

        llm_config = user_config or {}
        llm = LLM(
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model_name"),
        )

        entities = await query_decomposer.extract_entities(query, llm)

        if not entities:
            # 提取失败，降级为标准检索
            logger.warning("[Adaptive] COMPARE: entity extraction failed, falling back to STANDARD")
            thinking_events.append({
                "type": "thinking",
                "step": "compare_fallback",
                "detail": "实体提取失败，降级为标准检索",
            })
            results = await rag_engine.retrieve(doc_ids, query, top_k=5)
            return results, thinking_events

        logger.info("[Adaptive] COMPARE: extracted entities: %s", entities)

        thinking_events.append({
            "type": "thinking",
            "step": "compare_entities",
            "detail": f"提取对比实体：{'、'.join(entities)}",
        })

        all_results = []
        for entity in entities:
            # 构造针对每个实体的检索查询
            sub_q = f"{entity} {query}"
            results = await rag_engine.retrieve(doc_ids, sub_q, top_k=3)
            all_results.extend(results)

        merged = rag_engine.deduplicate_results(all_results)
        merged.sort(key=lambda x: x.get("distance", float("inf")))
        merged = merged[:5]

        thinking_events.append({
            "type": "thinking",
            "step": "adaptive_retrieve",
            "detail": f"对比检索完成，合并后 {len(merged)} 条结果",
        })

        return merged, thinking_events

adaptive_retriever = AdaptiveRetriever()
