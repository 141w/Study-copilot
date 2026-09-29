"""
RAG Engine for Study Copilot
"""

import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

from app.agent.context import trim_history
from app.config import settings
from app.core import metrics_counters
from app.core.adaptive_retriever import adaptive_retriever
from app.core.answer_reflector import answer_reflector
from app.core.embedder import embedder
from app.core.llm import LLM, build_chat_messages, resolve_completion_max_tokens
from app.core.pgvector_store import PgVectorStore
from app.core.query_router import QueryType, query_router
from app.core.retrieval_grader import retrieval_grader
from app.core.template_manager import render_template
from app.core.tracing import observe_span
from app.core.vector_store import _relevance_sort_key, result_relevance
from app.exceptions import classify_llm_error

# LRU 向量存储缓存上限：每文档索引约 0.5-5 MB，20 上限 ~10-100 MB
_VECTOR_STORE_CACHE_MAX = 20


def _display_relevance(r: dict) -> float:
    """统一的 [0,1] 相关度读取：新字段优先，旧 distance 公式兜底。"""
    rel = result_relevance(r)
    if rel is not None:
        return float(rel)
    return 1.0 / (1.0 + r.get("distance", 1))


def build_source_entry(index: int, r: dict, *, text: str | None = None) -> dict:
    """组装单条来源条目。带稳定 chunk_id 供引用浮层/全文展开回查切片原文。"""
    chunk = r.get("chunk", {})
    page = chunk.get("page", "")
    if page is None:
        page = ""
    elif not isinstance(page, str):
        page = str(page)
    meta = chunk.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    chunk_id = chunk.get("id") or chunk.get("chunk_id") or meta.get("chunk_id") or ""
    return {
        "index": index,
        "chunk_id": chunk_id,
        "document_id": chunk.get("document_id", ""),
        "page": page,
        "source": chunk.get("source", ""),
        "text": text if text is not None else chunk.get("text", ""),
        "relevance_score": _display_relevance(r),
    }


def extract_source_indices(text: str) -> list[int]:
    pattern = r"\[来源(\d+)\]"
    matches = re.findall(pattern, text)
    indices = set()
    for m in matches:
        try:
            indices.add(int(m))
        except ValueError:
            continue
    return sorted(list(indices))


# ── 4A 过程进度收束：阶段窗口元数据 ──────────────────────────────────────
WINDOW_UNDERSTAND = "understand"
WINDOW_RETRIEVE = "retrieve"


def thinking_event(
    step: str,
    detail: str,
    *,
    window: str | None = None,
    duration_ms: int | None = None,
    count: int | None = None,
    doc_count: int | None = None,
    status: str | None = None,
) -> dict:
    """Build a thinking SSE payload, optionally tagged with stage-window metadata."""
    ev: dict = {"type": "thinking", "step": step, "detail": detail}
    if window is not None:
        ev["window"] = window
    if duration_ms is not None:
        ev["duration_ms"] = int(duration_ms)
    if count is not None:
        ev["count"] = int(count)
    if doc_count is not None:
        ev["doc_count"] = int(doc_count)
    if status is not None:
        ev["status"] = status
    return ev


def window_close_event(
    window: str,
    detail: str = "",
    *,
    duration_ms: int | None = None,
    count: int | None = None,
    doc_count: int | None = None,
    status: str = "done",
) -> dict:
    """Closing event for a stage window.

    Hard semantics (4A): every terminate path (error / short-circuit / empty)
    MUST emit one of these so the UI never spins forever.
    """
    label = "问题理解" if window == WINDOW_UNDERSTAND else "检索"
    return thinking_event(
        "window_close",
        detail or f"{label}阶段结束",
        window=window,
        duration_ms=duration_ms,
        count=count,
        doc_count=doc_count,
        status=status,
    )


def result_doc_count(results: list | None) -> int:
    docs: set[str] = set()
    for r in results or []:
        chunk = r.get("chunk") or {}
        did = chunk.get("document_id") or chunk.get("source") or ""
        if did:
            docs.add(str(did))
    return len(docs)


def annotate_retrieve_events(
    events: list[dict],
    *,
    duration_ms: int,
    count: int,
    doc_count: int,
) -> list[dict]:
    """Attach window / duration / result counts to adaptive-retrieve thinking events."""
    for ev in events:
        if ev.get("type") != "thinking":
            continue
        step = str(ev.get("step") or "")
        if step in (
            "strategy_select",
            "adaptive_retrieve",
            "query_decompose",
            "compare_fallback",
            "compare_entities",
            "retrieval_check",
            "retrieval_retry",
        ):
            ev.setdefault("window", WINDOW_RETRIEVE)
        if step == "adaptive_retrieve":
            ev["duration_ms"] = int(duration_ms)
            ev["count"] = int(count)
            ev["doc_count"] = int(doc_count)
        elif "duration_ms" not in ev:
            ev["duration_ms"] = int(duration_ms)
        if step in ("adaptive_retrieve", "retrieval_check") and "count" not in ev:
            ev["count"] = int(count)
            ev["doc_count"] = int(doc_count)
    return events


class RAGEngine:
    def __init__(self):
        self.top_k = settings.top_k if hasattr(settings, "top_k") else 5
        self._pg_vector_store: PgVectorStore | None = None
        self._reranker = None
        self._reranker_loaded = False

    async def _rewrite_query(
        self, query: str, history: list[dict], user_config: dict | None = None
    ) -> str:
        """Rewrite a follow-up query into a standalone question using conversation history."""
        # 单轮守卫：没有会话历史时 query 本身就是独立问题，无需改写。
        # 2026-09-19 评测实测：无历史改写对单轮 query 净负收益
        # （R@10 -3.5pt），且每次改写浪费一次 LLM 调用。
        if not history:
            return query
        try:
            history_parts = []
            for msg in trim_history(history, max_messages=10, max_tokens=2000):
                role_label = "User" if msg.get("role") == "user" else "AI"
                history_parts.append(f"{role_label}: {msg.get('content', '')}")
            history_text = "\n".join(history_parts)
            rewrite_prompt = render_template(
                "rag/query_rewrite.jinja2", history_text=history_text, query=query
            )
            llm = LLM.from_config(user_config)
            rewrite_messages = [{"role": "user", "content": rewrite_prompt}]
            rewritten_query = await llm.chat(rewrite_messages, temperature=0.0, max_tokens=256)
            rewritten_query = rewritten_query.strip()
            if rewritten_query:
                return rewritten_query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
        return query

    def _get_llm(self, user_config=None):
        """创建一个 LLM 实例（复用配置）"""
        return LLM.from_config(user_config)

    async def _build_history_context(self, history: list[dict] | None, llm: LLM) -> list[dict]:
        """构建对话历史上下文：短对话直接用，长对话生成摘要。

        策略：
        - <= 10 条：直接使用完整历史
        - > 10 条：早期历史 → LLM 摘要，最近 5 条完整保留
        """
        if not history or len(history) <= 10:
            return trim_history(history, max_messages=10, max_tokens=2000)

        early_history = history[:-5]
        recent_history = trim_history(history[-5:], max_messages=5, max_tokens=1500)

        # 对早期历史生成摘要
        try:
            history_text = "\n".join(
                f"{'用户' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')[:150]}"
                for m in early_history[-15:]  # 最多取 15 条做摘要
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
            logger.info("[RAG] History summarized: %s...", (summary or "")[:80])
            return [
                {"role": "system", "content": f"之前的对话摘要：{summary}"},
                *recent_history,
            ]
        except Exception as e:
            logger.warning("[RAG] History summarization failed: %s, using truncation", e)
            return trim_history(history, max_messages=10, max_tokens=2000)

    # ── Agentic RAG methods ──────────────────────────────────────────

    async def _corrective_retrieve(
        self, doc_ids, query, user_config=None, top_k=5
    ) -> tuple[list[dict], list[dict]]:
        """带纠错的检索流程。

        Returns:
            (retrieved, thinking_events) — 检索结果列表和思考事件列表。
        """
        thinking_events: list[dict] = []
        ret_cfg = (user_config or {}).get("retrieval") or {}

        # 第一次检索
        retrieved = await self.retrieve(doc_ids, query, top_k, retrieval_config=ret_cfg)

        # 配置门控：corrective_retrieval_enabled=False（默认）时跳过评分与
        # 重试，直接返回首次检索结果。2026-09-19 评测实测：grader 触发率 0%
        # （无收益），且每次查询固定多花 2 次 LLM 调用（评分+改写）。
        if not settings.corrective_retrieval_enabled:
            logger.debug("Corrective retrieval disabled by config; skipping grade/retry")
            return retrieved, thinking_events

        quality = await retrieval_grader.grade(query, retrieved, user_config)

        thinking_events.append(
            thinking_event(
                "retrieval_check",
                f"检索到 {len(retrieved)} 条结果，质量：{quality.quality}（{quality.reason}，得分 {quality.score:.2f}）",
                window=WINDOW_RETRIEVE,
                count=len(retrieved),
                doc_count=result_doc_count(retrieved),
            )
        )
        metrics_counters.incr("rag.retrieval_check")
        if quality.is_good:
            metrics_counters.incr("rag.retrieval_good")
            return retrieved, thinking_events

        # 检索质量差 → 改写查询重试一次
        logger.info("Retrieval quality poor (%s), rewriting query...", quality.reason)
        metrics_counters.incr("rag.retrieval_retry")
        thinking_events.append(
            thinking_event(
                "retrieval_retry",
                f"检索质量不佳（{quality.reason}），正在改写查询重试...",
                window=WINDOW_RETRIEVE,
                count=len(retrieved),
                doc_count=result_doc_count(retrieved),
            )
        )

        rewritten = await self._rewrite_query(query, [], user_config)
        retrieved_retry = await self.retrieve(doc_ids, rewritten, top_k, retrieval_config=ret_cfg)
        quality_retry = await retrieval_grader.grade(query, retrieved_retry, user_config)

        thinking_events.append(
            thinking_event(
                "retrieval_check",
                f"重试检索到 {len(retrieved_retry)} 条结果，质量：{quality_retry.quality}（{quality_retry.reason}，得分 {quality_retry.score:.2f}）",
                window=WINDOW_RETRIEVE,
                count=len(retrieved_retry),
                doc_count=result_doc_count(retrieved_retry),
            )
        )

        if quality_retry.is_good:
            return retrieved_retry, thinking_events

        # 两次都不行 → 返回首次检索结果而非空。空结果意味着用户得到
        # 「未找到相关内容」，而首次检索结果再不济也优于什么都没有。
        logger.info(
            "Retrieval quality still poor after retry (%s); returning first results",
            quality_retry.reason,
        )
        return retrieved, thinking_events

    async def _direct_answer(self, query, user_config=None) -> str:
        """不依赖文档，直接用 LLM 回答通用问题。"""
        llm = LLM.from_config(user_config)
        system_prompt = render_template("rag/general_chat_system.jinja2")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        try:
            return await llm.chat(messages, temperature=0.7, max_tokens=1024)
        except Exception as e:
            # 未分类的供应商异常 → 友好的类型化错误（否则表现为裸 500）
            raise classify_llm_error(e) from e

    async def _synthesize_note_doc(self, doc_ids, query, user_config=None) -> dict:
        """根据文档或问题生成结构化学习笔记。"""
        ctx = ""
        sources_list = []
        if doc_ids:
            results = await self.retrieve(
                doc_ids, query, top_k=5, retrieval_config=(user_config or {}).get("retrieval")
            )
            if results:
                ctx = self.build_context(results, max_context_tokens=16000)
                for i, r in enumerate(results[:10]):
                    sources_list.append(build_source_entry(i + 1, r))

        llm = LLM.from_config(user_config)
        prompt = render_template("notes/synthesize_note.jinja2", query=query, context=ctx)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ]
        try:
            answer = await llm.chat(messages, temperature=0.3, max_tokens=2500)
        except Exception as e:
            raise classify_llm_error(e) from e

        return {
            "answer": answer or "",
            "sources": sources_list,
            "used_source_indices": [s["index"] for s in sources_list],
            "filtered_sources": sources_list,
            "intent": "note_taking",
        }

    async def _summarize_docs(self, doc_ids, user_config=None) -> dict:
        """检索全部文档内容并生成摘要。返回与 ask() 相同的格式。"""
        # 用通用查询检索全部 chunks
        all_results = await self.retrieve(
            doc_ids,
            "文档内容总结",
            top_k=100,
            retrieval_config=(user_config or {}).get("retrieval"),
        )

        if not all_results:
            return {
                "answer": "未找到任何文档内容，请先上传文档。",
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        ctx = self.build_context(all_results, max_context_tokens=60000)

        llm = LLM.from_config(user_config)

        messages = [
            {
                "role": "system",
                "content": "你是一个专业的学习助手。请根据提供的文档内容，生成一份结构清晰、重点突出的摘要。",
            },
            {
                "role": "user",
                "content": f"请总结以下文档内容：\n\n{ctx}",
            },
        ]
        try:
            answer = await llm.chat(messages, temperature=0.3, max_tokens=2048)
        except Exception as e:
            # 未分类的供应商异常 → 友好的类型化错误（否则表现为裸 500）
            raise classify_llm_error(e) from e

        sources_list = []
        for i, r in enumerate(all_results[:10]):
            sources_list.append(build_source_entry(i + 1, r))

        return {
            "answer": answer,
            "sources": sources_list,
            "used_source_indices": [],
            "filtered_sources": sources_list,
            "context_used": True,
        }

    def deduplicate_results(self, results: list[dict]) -> list[dict]:
        """Deduplicate chunks with >90% text overlap (first 100 chars match).

        When two chunks overlap, keep the more relevant one
        （统一 [0,1] 相关度比较，兼容旧 distance 语义）。
        """
        if not results:
            return results

        seen_prefixes: dict[str, dict] = {}  # prefix -> best result
        deduped = []

        for r in results:
            text = r.get("chunk", {}).get("text", "")
            prefix = text[:100]
            if not prefix:
                deduped.append(r)
                continue

            score = _display_relevance(r)
            if prefix in seen_prefixes:
                existing = seen_prefixes[prefix]
                if score > _display_relevance(existing):
                    # Replace with the more relevant (higher relevance) result
                    deduped.remove(existing)
                    deduped.append(r)
                    seen_prefixes[prefix] = r
                # else: keep existing, skip this duplicate
            else:
                seen_prefixes[prefix] = r
                deduped.append(r)

        return deduped

    async def retrieve(self, doc_ids, query, top_k=5, retrieval_config: dict | None = None):
        """Retrieve relevant chunks via pgvector hybrid search (vector + FTS RRF).

        Replaces the old per-document FAISS search with a single SQL query
        that combines cosine similarity and full-text search.
        ``retrieval_config`` 可覆盖召回条数 / rrf_k / 权重 / 阈值（阶段一在线调参）。
        """
        cfg = retrieval_config or {}
        # 用户配置只覆盖「常规问答」体量的 top_k（≤10）；总结类 top_k=100 等批量调用保持原样，
        # 否则滑杆会把全篇总结截成 5 条。同理 rerank_top_k 只在问答路径生效。
        user_top = int(cfg.get("embedding_top_k") or 0)
        if user_top and top_k <= 10:
            effective_top = user_top
        else:
            effective_top = top_k
        vector_threshold = float(cfg.get("vector_threshold") or 0.0)
        keyword_threshold = float(cfg.get("keyword_threshold") or 0.0)
        store = self._get_pg_vector_store()
        all_results = await store.search(
            query,
            doc_ids,
            effective_top * 2,
            rrf_k=cfg.get("rrf_k"),
            vector_weight=cfg.get("rrf_vector_weight"),
            keyword_weight=cfg.get("rrf_keyword_weight"),
            keyword_threshold=keyword_threshold,
        )

        if not all_results:
            return []

        # Relevance filtering (batch-normalized scores from PgVectorStore)
        min_rel = max(1e-6, vector_threshold)
        all_results = [
            r for r in all_results if (rel := result_relevance(r)) is not None and rel > min_rel
        ]

        # Sort by relevance descending before dedup (ensures stable ordering)
        all_results.sort(key=_relevance_sort_key)

        # Deduplicate chunks with similar text content before reranking
        all_results = self.deduplicate_results(all_results)

        # CrossEncoder reranking (kept unchanged — application-layer semantic rerank)
        reranker = self._ensure_reranker()
        reranked = False
        if reranker and len(all_results) > 0:
            try:
                texts = [r.get("chunk", {}).get("text", "") for r in all_results]
                pairs = [[query, t] for t in texts]
                scores = reranker.predict(pairs)
                for i, score in enumerate(scores):
                    all_results[i]["reranker_score"] = float(score)
                all_results.sort(key=lambda x: x.get("reranker_score", float("-inf")), reverse=True)
                reranked = True
            except Exception as e:
                logger.warning(f"Reranking failed, using original order: {e}")

        for r in all_results:
            r["reranked"] = reranked

        # F11：rerank_threshold 在 rerank 阶段生效（对 reranker_score 过滤）
        if reranked:
            rr_thr = float(cfg.get("rerank_threshold") or 0.0)
            if rr_thr > 0:
                all_results = [
                    r for r in all_results if float(r.get("reranker_score") or 0) >= rr_thr
                ]

        final_n = effective_top
        rerank_top_k = int(cfg.get("rerank_top_k") or 0)
        if reranked and rerank_top_k and top_k <= 10:
            final_n = rerank_top_k
        return all_results[:final_n]

    def _get_pg_vector_store(self) -> PgVectorStore:
        """Return the singleton PgVectorStore (replaces per-document LRU cache)."""
        if self._pg_vector_store is None:
            self._pg_vector_store = PgVectorStore(user_id="")
        return self._pg_vector_store

    def evict_vector_store(self, doc_id: str) -> None:
        """No-op for pgvector backend (no in-memory cache to evict)."""
        pass

    def clear_vector_stores(self) -> None:
        """No-op for pgvector backend."""
        pass

    def _ensure_reranker(self):
        if self._reranker_loaded:
            return self._reranker
        # 配置门控：reranker_enabled=False 时整体跳过加载（评测实测负增益，见 config 注释）
        if not settings.reranker_enabled:
            logger.debug("Reranker disabled by config (reranker_enabled=False); skipping load")
            self._reranker = None
            self._reranker_loaded = True
            return None
        if True:
            try:
                from sentence_transformers import CrossEncoder

                # 缓存优先（同 embedder BUG-1 修复模式）：避免 HF 联网校验在
                # VPN 黑洞环境下阻塞首问数十秒；本地无缓存则放弃 rerank 降级
                self._reranker = CrossEncoder(
                    "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    local_files_only=True,
                )
                logger.info("CrossEncoder reranker loaded (local cache)")
            except Exception as e:
                logger.warning(f"CrossEncoder 本地缓存不可用，禁用 rerank 降级: {e}")
                self._reranker = None
            finally:
                self._reranker_loaded = True
        return self._reranker

    def build_context(self, chunks, max_context_tokens: int = 64000):
        """Build context string from retrieved chunks with token-aware truncation.

        Estimates token count as len(text)/2 for Chinese text. If the total
        exceeds *max_context_tokens*, drops the lowest-relevance chunks
        (assumed to be at the end of the list after reranking) until under budget.
        """
        # Build per-chunk source blocks
        parts = []
        for i, r in enumerate(chunks):
            chunk = r.get("chunk", {})
            txt = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            # 层级分块感知：若包含父块全文 parent_text，传递完整父块语境给 LLM
            if isinstance(meta, dict) and meta.get("parent_text"):
                txt = meta["parent_text"]
            page = chunk.get("page", "")
            source = chunk.get("source", "")
            attrs = f'index="{i + 1}"'
            if page is not None and page != "":
                attrs += f' page="{page}"'
            if source:
                attrs += f' file="{source}"'
            parts.append(f"<source {attrs}>\n{txt}\n</source>")

        # Token-aware truncation: estimate tokens and drop tail chunks if over budget
        def _estimate_tokens(text: str) -> int:
            return max(1, len(text) // 2)

        total_tokens = _estimate_tokens("\n\n".join(parts))
        if total_tokens > max_context_tokens:
            # Drop chunks from the end (lowest relevance after reranking) until under budget
            while parts and _estimate_tokens("\n\n".join(parts)) > max_context_tokens:
                parts.pop()
            joined = "\n\n".join(parts)
            logger.info(
                f"Context truncated to {len(parts)} chunks "
                f"(~{_estimate_tokens(joined)} tokens, budget={max_context_tokens})"
            )

        return "\n\n".join(parts)

    def build_sources_text(self, retrieved):
        parts = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            txt = chunk.get("text", "")
            page = chunk.get("page", "")
            source = chunk.get("source", "")
            preview = txt[:80] + "..." if len(txt) > 80 else txt
            source_id = f"来源{i + 1}"
            if page:
                source_id += f" (第{page}页)"
            if source:
                source_id += f" - {source}"
            parts.append(f"[{source_id}]: {preview}")
        return "\n".join(parts)

    async def _get_memory_envelope(self, llm_config: dict | None, query: str) -> str:
        """Recall user's long-term memory envelope if user_id is provided."""
        user_id = llm_config.get("user_id") if llm_config else None
        if not user_id:
            return ""
        try:
            from app.db.database import AsyncSessionLocal
            from app.services.memory_service import memory_service

            async with AsyncSessionLocal() as session:
                recalled = await memory_service.recall(user_id, query, session)
                return recalled.prompt_envelope if recalled and recalled.prompt_envelope else ""
        except Exception as e:
            logger.debug("Memory recall error (ignored): %s", e)
            return ""

    async def generate_answer(self, query, context, sources_text="", history=None, llm_config=None):
        ai_style = llm_config.get("ai_style") if llm_config else None
        system_prompt = render_template("rag/main_qa_system.jinja2", ai_style=ai_style)
        memory_envelope = await self._get_memory_envelope(llm_config, query)
        if memory_envelope:
            system_prompt = f"{system_prompt}\n\n{memory_envelope}"
        user_prompt = f"参考文档：\n{context}\n\n来源列表：\n{sources_text}\n\n问题：{query}"
        # Multi-turn: inject history between system and current question
        messages = build_chat_messages(system_prompt, history, user_prompt)
        llm = LLM.from_config(llm_config)
        try:
            if llm_config:
                temperature = llm_config.get("temperature", 0.7)
                max_tokens = resolve_completion_max_tokens(
                    llm.model, llm_config.get("max_tokens")
                )
                answer = await llm.chat(messages, temperature=temperature, max_tokens=max_tokens)
            else:
                answer = await llm.chat(messages)
        except Exception as e:
            # 未分类的供应商异常 → 友好的类型化错误（否则表现为裸 500）
            raise classify_llm_error(e) from e
        return answer

    async def generate_answer_stream(
        self, query, context, sources_text="", history=None, llm_config=None
    ):
        ai_style = llm_config.get("ai_style") if llm_config else None
        system_prompt = render_template("rag/main_qa_system.jinja2", ai_style=ai_style)
        memory_envelope = await self._get_memory_envelope(llm_config, query)
        if memory_envelope:
            system_prompt = f"{system_prompt}\n\n{memory_envelope}"
        user_prompt = f"参考文档：\n{context}\n\n来源列表：\n{sources_text}\n\n问题：{query}"
        messages = build_chat_messages(system_prompt, history, user_prompt)
        llm = LLM.from_config(llm_config)
        temperature = llm_config.get("temperature", 0.7) if llm_config else 0.7
        # chat_stream resolves again; pass explicit safe budget for logging/clarity
        max_tokens = resolve_completion_max_tokens(
            llm.model,
            llm_config.get("max_tokens") if llm_config else None,
            prompt_chars=sum(len(str(m.get("content") or "")) for m in messages),
        )
        try:
            async for chunk in llm.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                include_reasoning=True,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "reasoning":
                        yield chunk
                    else:
                        yield chunk.get("content", "")
                else:
                    yield chunk
        except Exception as e:
            # 流式场景同样映射为类型化错误，避免裸 500 中断 SSE
            raise classify_llm_error(e) from e

    @observe_span(name="rag.ask")
    async def ask(self, doc_ids, query, history=None, user_config: dict | None = None):
        # 检查是否需要切换 Embedding 模型
        if user_config and user_config.get("embedding_model"):
            if user_config["embedding_model"] != embedder.model_name:
                embedder.reload_model(
                    user_config["embedding_model"], user_config.get("embedding_dimension", 768)
                )

        # ── Step 1: 意图理解 + 上下文改写（一次 LLM 调用）──
        llm = self._get_llm(user_config)
        analysis = await query_router.analyze(query, doc_ids, history, llm)
        route = analysis.intent
        final_query = analysis.standalone_query
        logger.info("[RAG] Intent: %s, Query: '%s'", route.value, final_query[:50])

        if route == QueryType.OUT_OF_SCOPE:
            return {
                "answer": "这个问题超出了我的知识范围，请问一些与学习相关的问题。",
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        if route == QueryType.DIRECT_ANSWER:
            answer = await self._direct_answer(final_query, user_config)
            return {
                "answer": answer,
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        if route == QueryType.SUMMARY:
            return await self._summarize_docs(doc_ids, user_config)

        if route == QueryType.NOTE_TAKING:
            return await self._synthesize_note_doc(doc_ids, final_query, user_config)

        # ── Step 2: RAG 路径（自适应检索 + 答案反思） ──
        # final_query 已在 Step 1 中由 analyze() 处理好
        strategy = await adaptive_retriever.select_strategy(final_query, llm)
        logger.info("[RAG] Adaptive strategy selected: %s", strategy.value)

        retrieved, _thinking = await adaptive_retriever.retrieve_adaptive(
            doc_ids, final_query, strategy, self, user_config
        )

        # Step 3: Corrective retrieval — grade quality, retry if poor
        if retrieved:
            quality = await retrieval_grader.grade(final_query, retrieved, user_config)
            if not quality.is_good:
                logger.info(
                    "[RAG] Retrieval %s (%s), attempting corrective...",
                    quality.quality,
                    quality.reason,
                )
                corrected, _ = await self._corrective_retrieve(
                    doc_ids, final_query, user_config, top_k=5
                )
                if corrected:
                    retrieved = corrected
                    logger.info("[RAG] Corrective improved: %d chunks", len(corrected))

        if not retrieved:
            return {
                "answer": "文档中没有找到与您问题相关的内容，请尝试换个方式提问。",
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        ctx_budget = 64000
        if user_config and user_config.get("context_window"):
            ctx_budget = max(4000, min(120000, user_config["context_window"] // 2))
        ctx = self.build_context(retrieved, max_context_tokens=ctx_budget)
        sources_text = self.build_sources_text(retrieved)
        history_context = await self._build_history_context(history, llm)
        answer = await self.generate_answer(
            final_query, ctx, sources_text, history_context, llm_config=user_config
        )

        # 答案反思：评估答案质量，不合格则重新生成
        try:
            evaluation = await answer_reflector.evaluate(final_query, ctx, answer, llm)
            if not evaluation.get("pass", True):
                logger.info(
                    "[RAG] Answer reflection failed (%s), refining...", evaluation.get("reason")
                )
                answer = await answer_reflector.refine(
                    final_query,
                    ctx,
                    answer,
                    evaluation.get("suggestions", ""),
                    llm,
                )
        except Exception as e:
            logger.warning("[RAG] Reflection error for '%s': %s", query[:30], e)

        used_indices = extract_source_indices(answer)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            sources_list.append(build_source_entry(i + 1, r))

        if used_indices:
            filtered_sources = [s for s in sources_list if s["index"] in used_indices]
        else:
            filtered_sources = sources_list

        return {
            "answer": answer,
            "sources": sources_list,
            "used_source_indices": used_indices,
            "filtered_sources": filtered_sources,
            "context_used": True,
        }

    @observe_span(name="rag.ask_stream")
    async def ask_stream(self, doc_ids, query, history=None, user_config: dict | None = None):
        # 检查是否需要切换 Embedding 模型
        if user_config and user_config.get("embedding_model"):
            if user_config["embedding_model"] != embedder.model_name:
                embedder.reload_model(
                    user_config["embedding_model"], user_config.get("embedding_dimension", 768)
                )

        # ── Step 1: 意图理解 + 上下文改写（一次 LLM 调用）──
        llm = self._get_llm(user_config)
        t_intent = time.monotonic()
        analysis = await query_router.analyze(query, doc_ids, history, llm)
        intent_ms = int((time.monotonic() - t_intent) * 1000)
        route = analysis.intent
        final_query = analysis.standalone_query
        logger.info("[RAG] Intent: %s, Query: '%s'", route.value, final_query[:50])

        if route == QueryType.OUT_OF_SCOPE:
            yield thinking_event(
                "intent_analysis",
                f"意图识别：【超出范围】。问题「{final_query[:40]}」与学习场景无关，终止检索。",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
            yield window_close_event(
                WINDOW_UNDERSTAND,
                f"问题理解完成（{intent_ms}ms），短路终止",
                duration_ms=intent_ms,
                status="done",
            )
            yield {
                "type": "answer",
                "content": "这个问题超出了我的知识范围，请问一些与学习相关的问题。",
            }
            return

        if route == QueryType.DIRECT_ANSWER:
            # 流式直接回答（不走检索）
            yield thinking_event(
                "intent_analysis",
                f"意图识别：【通用常识问答】。无需检索文档，由模型直接给出解答：「{final_query}」",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
            yield window_close_event(
                WINDOW_UNDERSTAND,
                f"问题理解完成（{intent_ms}ms），转直接回答",
                duration_ms=intent_ms,
                status="done",
            )
            system_prompt = render_template("rag/general_chat_system.jinja2")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_query},
            ]
            async for token in llm.chat_stream(messages):
                yield {"type": "token", "content": token}
            return

        if route == QueryType.SUMMARY:
            # 流式总结：检索全部文档，流式生成摘要
            yield thinking_event(
                "intent_analysis",
                "意图识别：【全篇知识总结】。正在检索并整合文档全部核心切片...",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
            yield window_close_event(
                WINDOW_UNDERSTAND,
                f"问题理解完成（{intent_ms}ms），转全篇总结",
                duration_ms=intent_ms,
                status="done",
            )
            t_ret = time.monotonic()
            all_results = await self.retrieve(
                doc_ids,
                "文档内容总结",
                top_k=100,
                retrieval_config=(user_config or {}).get("retrieval"),
            )
            ret_ms = int((time.monotonic() - t_ret) * 1000)
            if not all_results:
                yield thinking_event(
                    "adaptive_retrieve",
                    "全篇检索命中 0 条切片",
                    window=WINDOW_RETRIEVE,
                    duration_ms=ret_ms,
                    count=0,
                    doc_count=0,
                    status="empty",
                )
                yield window_close_event(
                    WINDOW_RETRIEVE,
                    f"检索无结果（{ret_ms}ms）",
                    duration_ms=ret_ms,
                    count=0,
                    doc_count=0,
                    status="empty",
                )
                yield {"type": "answer", "content": "未找到任何文档内容，请先上传文档。"}
                return
            yield thinking_event(
                "adaptive_retrieve",
                f"全篇检索完成，命中 {len(all_results)} 条切片",
                window=WINDOW_RETRIEVE,
                duration_ms=ret_ms,
                count=len(all_results),
                doc_count=result_doc_count(all_results),
                status="done",
            )
            yield window_close_event(
                WINDOW_RETRIEVE,
                f"检索完成（{ret_ms}ms）：{len(all_results)} 条切片",
                duration_ms=ret_ms,
                count=len(all_results),
                doc_count=result_doc_count(all_results),
                status="done",
            )
            ctx = self.build_context(all_results, max_context_tokens=60000)
            sources_text = self.build_sources_text(all_results)
            sources_list = []
            for i, r in enumerate(all_results[:10]):
                sources_list.append(build_source_entry(i + 1, r))
            yield {"type": "sources", "sources": sources_list, "filtered_sources": sources_list}
            async for chunk in self.generate_answer_stream(
                "请总结文档内容", ctx, sources_text, llm_config=user_config
            ):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "reasoning":
                        yield {"type": "reasoning", "content": chunk["content"]}
                    elif chunk.get("type") == "token":
                        yield {"type": "token", "content": chunk["content"]}
                    else:
                        yield chunk
                else:
                    yield {"type": "token", "content": chunk}
            return

        if route == QueryType.NOTE_TAKING:
            yield {"type": "intent", "intent": "note_taking"}
            yield thinking_event(
                "intent_analysis",
                f"意图识别：【学习笔记沉淀】。正在提取核心概念与考点，编排结构化笔记：「{final_query}」",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
            yield window_close_event(
                WINDOW_UNDERSTAND,
                f"问题理解完成（{intent_ms}ms），转笔记沉淀",
                duration_ms=intent_ms,
                status="done",
            )
            ctx = ""
            sources_list = []
            note_ret_ms = 0
            note_count = 0
            if doc_ids:
                t_ret = time.monotonic()
                results = await self.retrieve(
                    doc_ids,
                    final_query,
                    top_k=5,
                    retrieval_config=(user_config or {}).get("retrieval"),
                )
                note_ret_ms = int((time.monotonic() - t_ret) * 1000)
                note_count = len(results)
                yield thinking_event(
                    "adaptive_retrieve",
                    f"笔记素材检索完成，命中 {note_count} 条切片",
                    window=WINDOW_RETRIEVE,
                    duration_ms=note_ret_ms,
                    count=note_count,
                    doc_count=result_doc_count(results),
                    status="done" if results else "empty",
                )
                yield window_close_event(
                    WINDOW_RETRIEVE,
                    f"检索完成（{note_ret_ms}ms）：{note_count} 条切片",
                    duration_ms=note_ret_ms,
                    count=note_count,
                    doc_count=result_doc_count(results),
                    status="done" if results else "empty",
                )
                if results:
                    ctx = self.build_context(results, max_context_tokens=16000)
                    for i, r in enumerate(results[:10]):
                        sources_list.append(build_source_entry(i + 1, r))
                    yield {
                        "type": "sources",
                        "sources": sources_list,
                        "filtered_sources": sources_list,
                    }
            else:
                yield window_close_event(
                    WINDOW_RETRIEVE,
                    "未选择文档，跳过检索",
                    count=0,
                    doc_count=0,
                    status="empty",
                )
            yield thinking_event(
                "strategy_select",
                "策略规划：应用标准化知识卡片模板，生成包含核心定义、原理解析、易错陷阱与思考题的结构化笔记。",
                window=WINDOW_UNDERSTAND,
                duration_ms=note_ret_ms,
                count=note_count,
            )
            system_prompt = render_template(
                "notes/synthesize_note.jinja2", query=final_query, context=ctx
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_query},
            ]
            async for chunk in llm.chat_stream(messages, include_reasoning=True):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "reasoning":
                        yield {"type": "reasoning", "content": chunk["content"]}
                    elif chunk.get("type") == "token":
                        yield {"type": "token", "content": chunk["content"]}
                    else:
                        yield chunk
                else:
                    yield {"type": "token", "content": chunk}
            return

        # ── Step 2: RAG 路径（自适应检索 + 答案反思） ──
        # final_query 已在 Step 1 中由 analyze() 处理好
        if final_query != query:
            yield thinking_event(
                "intent_analysis",
                f"意图识别：【文档知识检索】。结合对话历史消除指代，改写为独立提问：「{final_query}」",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
        else:
            yield thinking_event(
                "intent_analysis",
                f"意图识别：【文档知识检索】。问题独立明确：「{final_query}」",
                window=WINDOW_UNDERSTAND,
                duration_ms=intent_ms,
                status="done",
            )
        yield window_close_event(
            WINDOW_UNDERSTAND,
            f"问题理解完成（{intent_ms}ms）",
            duration_ms=intent_ms,
            status="done",
        )

        t_strat = time.monotonic()
        strategy = await adaptive_retriever.select_strategy(final_query, llm)
        strat_ms = int((time.monotonic() - t_strat) * 1000)
        logger.info("[RAG] Adaptive strategy selected: %s", strategy.value)

        t_ret = time.monotonic()
        retrieved, thinking_events = await adaptive_retriever.retrieve_adaptive(
            doc_ids, final_query, strategy, self, user_config
        )
        ret_ms = int((time.monotonic() - t_ret) * 1000)
        retrieve_doc_count = result_doc_count(retrieved)
        annotate_retrieve_events(
            thinking_events,
            duration_ms=strat_ms + ret_ms,
            count=len(retrieved),
            doc_count=retrieve_doc_count,
        )
        for ev in thinking_events:
            if ev.get("step") == "strategy_select":
                ev["duration_ms"] = strat_ms
                ev.setdefault("count", len(retrieved))
                ev.setdefault("doc_count", retrieve_doc_count)

        # 先输出思考过程
        for event in thinking_events:
            yield event

        # Step 3: Corrective retrieval — grade quality, retry if poor
        if retrieved:
            quality = await retrieval_grader.grade(final_query, retrieved, user_config)
            yield thinking_event(
                "retrieval_check",
                quality.detail
                or f"检索到 {len(retrieved)} 条结果，质量评分：{quality.score:.2f}（{quality.reason}）",
                window=WINDOW_RETRIEVE,
                count=len(retrieved),
                doc_count=retrieve_doc_count,
            )
            if not quality.is_good:
                logger.info(
                    "[RAG] Stream retrieval %s (%s), attempting corrective...",
                    quality.quality,
                    quality.reason,
                )
                yield thinking_event(
                    "retrieval_retry",
                    f"检索质量评分偏低（{quality.score:.2f}），正在针对问题核心要点重写查询执行纠错检索...",
                    window=WINDOW_RETRIEVE,
                    count=len(retrieved),
                    doc_count=retrieve_doc_count,
                )
                corrected, _ = await self._corrective_retrieve(
                    doc_ids, final_query, user_config, top_k=5
                )
                if corrected:
                    retrieved = corrected
                    retrieve_doc_count = result_doc_count(retrieved)
                    quality_corrected = await retrieval_grader.grade(
                        final_query, retrieved, user_config
                    )
                    yield thinking_event(
                        "retrieval_check",
                        f"纠错检索完成：{quality_corrected.detail or f'重新召回 {len(corrected)} 条切片，质量评分提升至 {quality_corrected.score:.2f}'}",
                        window=WINDOW_RETRIEVE,
                        count=len(corrected),
                        doc_count=retrieve_doc_count,
                    )
                    logger.info("[RAG] Stream corrective improved: %d chunks", len(corrected))

        # 4A 硬性语义：检索窗口必须关闭（含空结果短路）
        yield window_close_event(
            WINDOW_RETRIEVE,
            f"检索完成（{strat_ms + ret_ms}ms）：{len(retrieved)} 条候选 / {retrieve_doc_count} 篇文档",
            duration_ms=strat_ms + ret_ms,
            count=len(retrieved),
            doc_count=retrieve_doc_count,
            status="done" if retrieved else "empty",
        )

        if not retrieved:
            yield {
                "type": "answer",
                "content": "文档中没有找到与您问题相关的内容，请尝试换个方式提问。",
            }
            return

        ctx_budget = 64000
        if user_config and user_config.get("context_window"):
            ctx_budget = max(4000, min(120000, user_config["context_window"] // 2))
        ctx = self.build_context(retrieved, max_context_tokens=ctx_budget)
        sources_text = self.build_sources_text(retrieved)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            sources_list.append(build_source_entry(i + 1, r))

        yield {"type": "sources", "sources": sources_list, "filtered_sources": sources_list}

        # 流式生成答案，收集完整答案用于反思，同时透传 reasoning 和 token
        answer_parts = []
        history_context = await self._build_history_context(history, llm)
        async for chunk in self.generate_answer_stream(
            final_query, ctx, sources_text, history_context, llm_config=user_config
        ):
            if isinstance(chunk, dict):
                if chunk.get("type") == "reasoning":
                    yield {"type": "reasoning", "content": chunk["content"]}
                elif chunk.get("type") == "token":
                    answer_parts.append(chunk["content"])
                    yield {"type": "token", "content": chunk["content"]}
                else:
                    yield chunk
            else:
                answer_parts.append(chunk)
                yield {"type": "token", "content": chunk}

        # 答案反思：评估答案质量，不合格则重新生成
        full_answer = "".join(answer_parts)
        try:
            evaluation = await answer_reflector.evaluate(final_query, ctx, full_answer, llm)
            score = evaluation.get("score", 90)
            reason = evaluation.get("reason", "")
            analysis_text = evaluation.get("analysis", "")
            if not evaluation.get("pass", True):
                logger.info("[RAG] Answer reflection failed (%s), refining...", reason)
                yield {
                    "type": "thinking",
                    "step": "reflection_fail",
                    "detail": f"事实依据核验未达标（评分 {score}/100，{reason}）：{analysis_text}。改进策略：{evaluation.get('suggestions', '')}，正在触发自我纠错与精炼...",
                }
                refined = await answer_reflector.refine(
                    final_query,
                    ctx,
                    full_answer,
                    evaluation.get("suggestions", ""),
                    llm,
                )
                yield {"type": "answer_refined", "content": refined}
            else:
                yield {
                    "type": "thinking",
                    "step": "reflection_pass",
                    "detail": f"事实依据核验通过（合规评分 {score}/100）：{analysis_text or reason or '核心论述均在参考文档中有可靠依据，未检测到幻觉编造'}",
                }
        except Exception as e:
            logger.warning("[RAG] Reflection error for '%s': %s", query[:30], e)


rag_engine = RAGEngine()
