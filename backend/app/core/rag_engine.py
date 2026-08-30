"""
RAG Engine for Study Copilot
"""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

from app.config import settings
from app.core.adaptive_retriever import adaptive_retriever
from app.core.answer_reflector import answer_reflector
from app.core.embedder import embedder
from app.core.llm import LLM
from app.core.pgvector_store import PgVectorStore
from app.core.query_router import QueryType, query_router
from app.core.retrieval_grader import retrieval_grader
from app.core.template_manager import render_template
from app.core.vector_store import result_relevance
from app.exceptions import classify_llm_error

# LRU 向量存储缓存上限：每文档索引约 0.5-5 MB，20 上限 ~10-100 MB
_VECTOR_STORE_CACHE_MAX = 20


def _display_relevance(r: dict) -> float:
    """统一的 [0,1] 相关度读取：新字段优先，旧 distance 公式兜底。"""
    rel = result_relevance(r)
    if rel is not None:
        return float(rel)
    return 1.0 / (1.0 + r.get("distance", 1))


def _relevance_sort_key(r: dict):
    """降序相关度排序键；无新字段的旧结果回退为升序距离。"""
    rel = result_relevance(r)
    if rel is not None:
        return (0, -rel)
    return (1, r.get("distance", float("inf")))


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
        try:
            history_parts = []
            for msg in history[-10:]:
                role_label = "User" if msg.get("role") == "user" else "AI"
                history_parts.append(f"{role_label}: {msg.get('content', '')}")
            history_text = "\n".join(history_parts)
            rewrite_prompt = render_template("rag/query_rewrite.jinja2", history_text=history_text, query=query)
            if user_config:
                llm = LLM(
                    api_key=user_config.get("api_key"),
                    base_url=user_config.get("base_url"),
                    model=user_config.get("model_name"),
                )
            else:
                llm = LLM()
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
        cfg = user_config or {}
        return LLM(
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            model=cfg.get("model_name"),
        )

    async def _build_history_context(self, history: list[dict] | None, llm: LLM) -> list[dict]:
        """构建对话历史上下文：短对话直接用，长对话生成摘要。

        策略：
        - <= 10 条：直接使用完整历史
        - > 10 条：早期历史 → LLM 摘要，最近 5 条完整保留
        """
        if not history or len(history) <= 10:
            return history or []

        early_history = history[:-5]
        recent_history = history[-5:]

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
            return history[-10:]

    # ── Agentic RAG methods ──────────────────────────────────────────

    async def _corrective_retrieve(
        self, doc_ids, query, user_config=None, top_k=5
    ) -> tuple[list[dict], list[dict]]:
        """带纠错的检索流程。

        Returns:
            (retrieved, thinking_events) — 检索结果列表和思考事件列表。
        """
        thinking_events: list[dict] = []

        # 第一次检索
        retrieved = await self.retrieve(doc_ids, query, top_k)
        quality = await retrieval_grader.grade(query, retrieved, user_config)

        thinking_events.append({
            "type": "thinking",
            "step": "retrieval_check",
            "detail": f"检索到 {len(retrieved)} 条结果，质量：{quality.quality}（{quality.reason}，得分 {quality.score:.2f}）",
        })

        if quality.is_good:
            return retrieved, thinking_events

        # 检索质量差 → 改写查询重试一次
        logger.info("Retrieval quality poor (%s), rewriting query...", quality.reason)
        thinking_events.append({
            "type": "thinking",
            "step": "retrieval_retry",
            "detail": f"检索质量不佳（{quality.reason}），正在改写查询重试...",
        })

        rewritten = await self._rewrite_query(query, [], user_config)
        retrieved_retry = await self.retrieve(doc_ids, rewritten, top_k)
        quality_retry = await retrieval_grader.grade(query, retrieved_retry, user_config)

        thinking_events.append({
            "type": "thinking",
            "step": "retrieval_check",
            "detail": f"重试检索到 {len(retrieved_retry)} 条结果，质量：{quality_retry.quality}（{quality_retry.reason}，得分 {quality_retry.score:.2f}）",
        })

        if quality_retry.is_good:
            return retrieved_retry, thinking_events

        # 两次都不行 → 返回空
        return [], thinking_events

    async def _direct_answer(self, query, user_config=None) -> str:
        """不依赖文档，直接用 LLM 回答通用问题。"""
        if user_config:
            llm = LLM(
                api_key=user_config.get("api_key"),
                base_url=user_config.get("base_url"),
                model=user_config.get("model_name"),
            )
        else:
            llm = LLM()

        messages = [
            {"role": "system", "content": "你是一个学习助手。请直接回答用户的问题。"},
            {"role": "user", "content": query},
        ]
        return await llm.chat(messages, temperature=0.7, max_tokens=1024)

    async def _summarize_docs(self, doc_ids, user_config=None) -> dict:
        """检索全部文档内容并生成摘要。返回与 ask() 相同的格式。"""
        # 用通用查询检索全部 chunks
        all_results = await self.retrieve(doc_ids, "文档内容总结", top_k=100)

        if not all_results:
            return {
                "answer": "未找到任何文档内容，请先上传文档。",
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        ctx = self.build_context(all_results, max_context_tokens=12000)

        if user_config:
            llm = LLM(
                api_key=user_config.get("api_key"),
                base_url=user_config.get("base_url"),
                model=user_config.get("model_name"),
            )
        else:
            llm = LLM()

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
        answer = await llm.chat(messages, temperature=0.3, max_tokens=2048)

        sources_list = []
        for i, r in enumerate(all_results[:10]):
            chunk = r.get("chunk", {})
            page = chunk.get("page", "")
            if page is None:
                page = ""
            elif not isinstance(page, str):
                page = str(page)
            sources_list.append({
                "index": i + 1,
                "document_id": chunk.get("document_id", ""),
                "page": page,
                "source": chunk.get("source", ""),
                "text": chunk.get("text", ""),
                "relevance_score": _display_relevance(r),
            })

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

    async def retrieve(self, doc_ids, query, top_k=5):
        """Retrieve relevant chunks via pgvector hybrid search (vector + FTS RRF).

        Replaces the old per-document FAISS search with a single SQL query
        that combines cosine similarity and full-text search.
        """
        store = self._get_pg_vector_store()
        all_results = await store.search(query, doc_ids, top_k * 2)

        if not all_results:
            return []

        # Relevance filtering (batch-normalized scores from PgVectorStore)
        all_results = [r for r in all_results if result_relevance(r) is not None and result_relevance(r) > 1e-6]

        # Sort by relevance descending before dedup (ensures stable ordering)
        all_results.sort(key=_relevance_sort_key)

        # Deduplicate chunks with similar text content before reranking
        all_results = self.deduplicate_results(all_results)

        # CrossEncoder reranking (kept unchanged — application-layer semantic rerank)
        reranker = self._ensure_reranker()
        if reranker and len(all_results) > 0:
            try:
                texts = [r.get("chunk", {}).get("text", "") for r in all_results]
                pairs = [[query, t] for t in texts]
                scores = reranker.predict(pairs)
                for i, score in enumerate(scores):
                    all_results[i]["reranker_score"] = float(score)
                all_results.sort(key=lambda x: x.get("reranker_score", float("-inf")), reverse=True)
            except Exception as e:
                logger.warning(f"Reranking failed, using original order: {e}")

        return all_results[:top_k]

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
        if not self._reranker_loaded:
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

    def build_context(self, chunks, max_context_tokens: int = 3000):
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

    async def generate_answer(self, query, context, sources_text="", history=None, llm_config=None):
        system_prompt = render_template("rag/main_qa_system.jinja2")
        user_prompt = f"参考文档：\n{context}\n\n来源列表：\n{sources_text}\n\n问题：{query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if llm_config:
            llm = LLM(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model_name"),
            )
        else:
            llm = LLM()
        try:
            if llm_config:
                temperature = llm_config.get("temperature", 0.7)
                max_tokens = llm_config.get("max_tokens")
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
        system_prompt = render_template("rag/main_qa_system.jinja2")
        user_prompt = f"参考文档：\n{context}\n\n来源列表：\n{sources_text}\n\n问题：{query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if llm_config:
            llm = LLM(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model_name"),
            )
            temperature = llm_config.get("temperature", 0.7)
            max_tokens = llm_config.get("max_tokens")
        else:
            llm = LLM()
            temperature = 0.7
            max_tokens = None
        try:
            async for token in llm.chat_stream(
                messages, temperature=temperature, max_tokens=max_tokens
            ):
                yield token
        except Exception as e:
            # 流式场景同样映射为类型化错误，避免裸 500 中断 SSE
            raise classify_llm_error(e) from e

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
                logger.info("[RAG] Retrieval %s (%s), attempting corrective...",
                            quality.quality, quality.reason)
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

        ctx = self.build_context(retrieved)
        sources_text = self.build_sources_text(retrieved)
        history_context = await self._build_history_context(history, llm)
        answer = await self.generate_answer(
            final_query, ctx, sources_text, history_context, llm_config=user_config
        )

        # 答案反思：评估答案质量，不合格则重新生成
        try:
            evaluation = await answer_reflector.evaluate(
                final_query, ctx, answer, llm
            )
            if not evaluation.get("pass", True):
                logger.info("[RAG] Answer reflection failed (%s), refining...", evaluation.get("reason"))
                answer = await answer_reflector.refine(
                    final_query, ctx, answer,
                    evaluation.get("suggestions", ""), llm,
                )
        except Exception as e:
            logger.warning("[RAG] Reflection error for '%s': %s", query[:30], e)

        used_indices = extract_source_indices(answer)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            chunk_text = chunk.get("text", "")
            page = chunk.get("page", "")
            if page is None:
                page = ""
            elif not isinstance(page, str):
                page = str(page)
            sources_list.append(
                {
                    "index": i + 1,
                    "document_id": chunk.get("document_id", ""),
                    "page": page,
                    "source": chunk.get("source", ""),
                    "text": chunk_text,
                    "relevance_score": _display_relevance(r),
                }
            )

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

    async def ask_stream(self, doc_ids, query, history=None, user_config: dict | None = None):
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
            yield {
                "type": "answer",
                "content": "这个问题超出了我的知识范围，请问一些与学习相关的问题。",
            }
            return

        if route == QueryType.DIRECT_ANSWER:
            # 流式直接回答（不走检索）
            messages = [
                {"role": "system", "content": "你是一个学习助手。请直接回答用户的问题。"},
                {"role": "user", "content": final_query},
            ]
            async for token in llm.chat_stream(messages):
                yield {"type": "token", "content": token}
            return

        if route == QueryType.SUMMARY:
            # 流式总结：检索全部文档，流式生成摘要
            all_results = await self.retrieve(doc_ids, "文档内容总结", top_k=100)
            if not all_results:
                yield {"type": "answer", "content": "未找到任何文档内容，请先上传文档。"}
                return
            ctx = self.build_context(all_results, max_context_tokens=12000)
            sources_text = self.build_sources_text(all_results)
            sources_list = []
            for i, r in enumerate(all_results[:10]):
                chunk = r.get("chunk", {})
                sources_list.append({
                    "index": i + 1,
                    "document_id": chunk.get("document_id", ""),
                    "page": str(chunk.get("page", "")),
                    "source": chunk.get("source", ""),
                    "text": chunk.get("text", ""),
                    "relevance_score": _display_relevance(r),
                })
            yield {"type": "sources", "sources": sources_list, "filtered_sources": sources_list}
            async for token in self.generate_answer_stream(
                "请总结文档内容", ctx, sources_text, llm_config=user_config
            ):
                yield {"type": "token", "content": token}
            return

        # ── Step 2: RAG 路径（自适应检索 + 答案反思） ──
        # final_query 已在 Step 1 中由 analyze() 处理好
        strategy = await adaptive_retriever.select_strategy(final_query, llm)
        logger.info("[RAG] Adaptive strategy selected: %s", strategy.value)

        retrieved, thinking_events = await adaptive_retriever.retrieve_adaptive(
            doc_ids, final_query, strategy, self, user_config
        )

        # 先输出思考过程
        for event in thinking_events:
            yield event

        # Step 3: Corrective retrieval — grade quality, retry if poor
        if retrieved:
            quality = await retrieval_grader.grade(final_query, retrieved, user_config)
            if not quality.is_good:
                logger.info(
                    "[RAG] Stream retrieval %s (%s), attempting corrective...",
                    quality.quality, quality.reason,
                )
                yield {
                    "type": "thinking",
                    "step": "retrieval_retry",
                    "detail": f"检索质量不佳（{quality.reason}），正在改写查询重试...",
                }
                corrected, _ = await self._corrective_retrieve(
                    doc_ids, final_query, user_config, top_k=5
                )
                if corrected:
                    retrieved = corrected
                    logger.info("[RAG] Stream corrective improved: %d chunks", len(corrected))

        if not retrieved:
            yield {
                "type": "answer",
                "content": "文档中没有找到与您问题相关的内容，请尝试换个方式提问。",
            }
            return

        ctx = self.build_context(retrieved)
        sources_text = self.build_sources_text(retrieved)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            chunk_text = chunk.get("text", "")
            page = chunk.get("page", "")
            if page is None:
                page = ""
            elif not isinstance(page, str):
                page = str(page)
            sources_list.append(
                {
                    "index": i + 1,
                    "document_id": chunk.get("document_id", ""),
                    "page": page,
                    "source": chunk.get("source", ""),
                    "text": chunk_text,
                    "relevance_score": _display_relevance(r),
                }
            )

        yield {"type": "sources", "sources": sources_list, "filtered_sources": sources_list}

        # 流式生成答案，收集完整答案用于反思
        answer_parts = []
        history_context = await self._build_history_context(history, llm)
        async for token in self.generate_answer_stream(
            final_query, ctx, sources_text, history_context, llm_config=user_config
        ):
            answer_parts.append(token)
            yield {"type": "token", "content": token}

        # 答案反思：评估答案质量，不合格则重新生成
        full_answer = "".join(answer_parts)
        try:
            evaluation = await answer_reflector.evaluate(
                final_query, ctx, full_answer, llm
            )
            if not evaluation.get("pass", True):
                logger.info("[RAG] Answer reflection failed (%s), refining...", evaluation.get("reason"))
                yield {"type": "thinking", "step": "reflection_fail",
                       "detail": f"答案质量不佳（{evaluation.get('reason', '')}），正在重新生成..."}
                refined = await answer_reflector.refine(
                    final_query, ctx, full_answer,
                    evaluation.get("suggestions", ""), llm,
                )
                yield {"type": "answer_refined", "content": refined}
            else:
                yield {"type": "thinking", "step": "reflection_pass",
                       "detail": "答案质量检查通过"}
        except Exception as e:
            logger.warning("[RAG] Reflection error for '%s': %s", query[:30], e)

rag_engine = RAGEngine()
