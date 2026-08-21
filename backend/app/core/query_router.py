"""
Query Router — 查询意图分类 + 上下文感知改写（合并为一步）

一次 LLM 调用同时完成：
1. 判断问题类型（rag_qa / direct / summary / out_of_scope）
2. 如果问题依赖对话历史，改写为独立问题

设计参考：open-notebook 的简洁方案（LLM 自行理解上下文）
"""

import json
import logging
from enum import Enum

from app.core.llm import LLM
from app.core.template_manager import render_template

logger = logging.getLogger(__name__)

class QueryType(str, Enum):
    RAG_QA = "rag_qa"
    DIRECT_ANSWER = "direct"
    SUMMARY = "summary"
    OUT_OF_SCOPE = "out_of_scope"

# ── 关键词规则（优先级高于 LLM，节省一次调用） ──────────────────────

_SUMMARY_KEYWORDS = [
    "总结", "概述", "概要", "摘要", "大纲",
    "总结一下", "帮我总结", "概括", "归纳",
    "全文总结", "内容概要", "主要讲了什么",
    "说了什么", "讲了什么", "主要内容",
]

_CHITCHAT_KEYWORDS = [
    "你好", "你是谁", "谢谢", "再见", "哈哈",
    "嗯嗯", "好的", "ok", "OK", "hi", "hello",
    "早上好", "晚上好", "下午好",
]

class QueryAnalysis:
    """查询分析结果"""
    def __init__(self, intent: QueryType, standalone_query: str):
        self.intent = intent
        self.standalone_query = standalone_query

class QueryRouter:
    """查询路由器 — 规则优先 + LLM 兜底（同时输出意图和改写查询）"""

    ANALYZE_PROMPT = (
        "你是一个查询分析器。根据用户问题和对话历史，完成两个任务：\n\n"
        "1. 判断问题类型：\n"
        "   - rag_qa: 基于文档内容的具体问答（需要检索相关段落）\n"
        "   - direct: 通用概念解释，不需要文档（如\"什么是Python\"）\n"
        "   - summary: 要求总结/概述整个文档\n"
        "   - out_of_scope: 闲聊或与学习无关的问题\n\n"
        "2. 如果问题依赖对话历史（含代词、省略、指代），改写为独立完整的问题。\n"
        "   如果不依赖历史，保持原样。\n\n"
        "输出 JSON 格式：\n"
        "{{\"intent\": \"rag_qa\", \"standalone_query\": \"改写后的独立问题\"}}\n\n"
        "{history_text}"
        "用户问题：{query}\n\n"
        "分析结果："
    )

    def __init__(self):
        pass

    async def analyze(
        self,
        query: str,
        doc_ids: list[str],
        history: list[dict] | None = None,
        llm: LLM | None = None,
    ) -> QueryAnalysis:
        """分析查询意图，同时处理上下文改写。

        Returns:
            QueryAnalysis(intent, standalone_query)
        """
        query_stripped = query.strip()

        # ── 规则 1：没有文档 → 直接回答 ──
        if not doc_ids:
            logger.info("[Router] No documents → DIRECT_ANSWER")
            return QueryAnalysis(QueryType.DIRECT_ANSWER, query_stripped)

        # ── 规则 2：闲聊 ──
        if query_stripped in _CHITCHAT_KEYWORDS:
            logger.info("[Router] Chitchat detected → OUT_OF_SCOPE")
            return QueryAnalysis(QueryType.OUT_OF_SCOPE, query_stripped)

        # ── 规则 3：总结类 ──
        if any(kw in query_stripped for kw in _SUMMARY_KEYWORDS):
            logger.info("[Router] Summary keywords → SUMMARY")
            return QueryAnalysis(QueryType.SUMMARY, query_stripped)

        # ── 规则 4：没有历史 → 不需要改写，直接走 LLM 分类 ──
        if not history or len(history) == 0:
            intent = await self._classify_intent(query_stripped, llm)
            return QueryAnalysis(intent, query_stripped)

        # ── 有历史 → 用 LLM 同时分类 + 改写 ──
        try:
            # 构建历史文本（最近 5 条）
            recent = history[-5:]
            history_parts = []
            for msg in recent:
                role = "用户" if msg.get("role") == "user" else "AI"
                content = msg.get("content", "")[:200]
                history_parts.append(f"{role}: {content}")
            history_text = "对话历史：\n" + "\n".join(history_parts) + "\n\n"

            prompt = self.ANALYZE_PROMPT.format(
                history_text=history_text, query=query_stripped
            )
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            return self._parse_response(response, query_stripped)

        except Exception as e:
            logger.warning("[Router] LLM analysis failed: %s, defaulting to RAG_QA", e)
            return QueryAnalysis(QueryType.RAG_QA, query_stripped)

    async def _classify_intent(self, query: str, llm: LLM | None = None) -> QueryType:
        """简单分类（无历史时使用）"""
        if llm is None:
            # 没有 LLM 实例，用规则兜底
            return QueryType.RAG_QA

        try:
            prompt = render_template("router/classify_intent.jinja2", query=query)
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            response = (response or "").strip().lower()

            if "summary" in response:
                return QueryType.SUMMARY
            elif "direct" in response:
                return QueryType.DIRECT_ANSWER
            elif "out_of_scope" in response:
                return QueryType.OUT_OF_SCOPE
            else:
                return QueryType.RAG_QA

        except Exception as e:
            logger.warning("[Router] Intent classification failed: %s", e)
            return QueryType.RAG_QA

    def _parse_response(self, response: str, original_query: str) -> QueryAnalysis:
        """解析 LLM 返回的 JSON"""
        response = response.strip()

        # 尝试直接解析 JSON
        try:
            data = json.loads(response)
            intent_str = data.get("intent", "rag_qa")
            standalone = data.get("standalone_query", original_query)
            intent = QueryType(intent_str) if intent_str in [e.value for e in QueryType] else QueryType.RAG_QA
            return QueryAnalysis(intent, standalone or original_query)
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试提取 JSON 块
        if "{" in response and "}" in response:
            start = response.index("{")
            end = response.rindex("}") + 1
            try:
                data = json.loads(response[start:end])
                intent_str = data.get("intent", "rag_qa")
                standalone = data.get("standalone_query", original_query)
                intent = QueryType(intent_str) if intent_str in [e.value for e in QueryType] else QueryType.RAG_QA
                return QueryAnalysis(intent, standalone or original_query)
            except (json.JSONDecodeError, ValueError):
                pass

        # 解析失败，用规则判断意图
        logger.warning("[Router] Failed to parse LLM response: %s", response[:100])
        return QueryAnalysis(QueryType.RAG_QA, original_query)

query_router = QueryRouter()
