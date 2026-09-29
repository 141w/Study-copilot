"""F10/F12 · 检索参数真生效（fix(phase2-audit): 第三批）。

F10：keyword_threshold 全链路零消费、关键词路无 @@ 命中过滤 → 词法噪声进融合。
F12：Agent 检索工具不透传 retrieval_config → 调参对深度研究无效。
"""

from __future__ import annotations

import inspect


def test_f10_keyword_threshold_consumed():
    """search() 必须接受 keyword_threshold，且写进 SQL 过滤。"""
    from app.core.pgvector_store import PgVectorStore

    sig = inspect.signature(PgVectorStore.search)
    assert "keyword_threshold" in sig.parameters, (
        f"search() 未消费 keyword_threshold，params={list(sig.parameters)}"
    )
    src = inspect.getsource(PgVectorStore.search)
    assert "keyword_threshold" in src
    # 关键词路必须有命中过滤（@@ 或 ts_rank 阈值）
    assert "@@" in src or "ts_rank" in src


def test_f12_agent_tool_passes_retrieval_config():
    """Agent 检索工具必须透传 retrieval_config，否则调参对深度研究无效。"""
    from app.agent.tools import definitions

    src = inspect.getsource(definitions)
    assert "retrieval_config" in src, "Agent 工具未透传 retrieval_config"
