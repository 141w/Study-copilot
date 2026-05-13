"""
RAG Engine for Study Copilot
"""
from typing import List, Dict, Any, Optional
from app.core.vector_store import DocumentVectorStore
from app.core.llm import LLM
from app.config import settings
import re
import pickle
import os
import asyncio


def extract_source_indices(text: str) -> List[int]:
    pattern = r'\[来源(\d+)\]'
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
        self._vector_store_cache = {}
        self._reranker = None
        
    async def retrieve(self, doc_ids, query, top_k=5):
        all_results = []
        for doc_id in doc_ids:
            store = await self._get_vector_store(doc_id)
            results = await store.search(query, top_k)
            all_results.extend(results)
        all_results.sort(key=lambda x: x.get("distance", float("inf")))
        return all_results[:top_k]

    async def _get_vector_store(self, doc_id):
        if doc_id not in self._vector_store_cache:
            store = DocumentVectorStore(doc_id)
            await store.load()
            self._vector_store_cache[doc_id] = store
        return self._vector_store_cache[doc_id]

    def build_context(self, chunks):
        parts = []
        for i, r in enumerate(chunks):
            chunk = r.get("chunk", {})
            txt = chunk.get("text", "")
            page = chunk.get("page", "")
            source = chunk.get("source", "")
            attrs = f'index="{i + 1}"'
            if page:
                attrs += f' page="{page}"'
            if source:
                attrs += f' file="{source}"'
            parts.append(f"<source {attrs}>\n{txt}\n</source>")
        return "\n\n".join(parts)

    def build_sources_text(self, retrieved):
        parts = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            txt = chunk.get("text", "")
            page = chunk.get("page", "")
            source = chunk.get("source", "")
            preview = txt[:80] + "..." if len(txt) > 80 else txt
            source_id = f"来源{i+1}"
            if page:
                source_id += f" (第{page}页)"
            if source:
                source_id += f" - {source}"
            parts.append(f"[{source_id}]: {preview}")
        return "\n".join(parts)

    async def generate_answer(self, query, context, sources_text="", history=None, llm_config=None):
        num_sources = sources_text.count("\n") + 1 if sources_text else 0
        prompt = f"""Answer based on the provided documents. Cite sources as [来源1], [来源2], etc.
        
Documents:
{context}

Sources:
{sources_text}

Question: {query}
Answer:"""

        messages = [{"role": "user", "content": prompt}]
        if llm_config:
            llm = LLM(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model_name")
            )
            temperature = llm_config.get("temperature", 0.7)
            max_tokens = llm_config.get("max_tokens")
            answer = await llm.chat(messages, temperature=temperature, max_tokens=max_tokens)
        else:
            llm = LLM()
            answer = await llm.chat(messages)
        return answer, []

    async def generate_answer_stream(self, query, context, sources_text="", history=None, llm_config=None):
        num_sources = sources_text.count("\n") + 1 if sources_text else 0
        prompt = f"""Answer based on the provided documents. Cite sources as [来源1], [来源2], etc.
        
Documents:
{context}

Sources:
{sources_text}

Question: {query}
Answer:"""

        messages = [{"role": "user", "content": prompt}]
        if llm_config:
            llm = LLM(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model_name")
            )
            temperature = llm_config.get("temperature", 0.7)
            max_tokens = llm_config.get("max_tokens")
            async for token in llm.chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
                yield token
        else:
            llm = LLM()
            async for token in llm.chat_stream(messages):
                yield token

    async def ask(self, doc_ids, query, history=None, user_config: Optional[dict] = None):
        final_query = query
        if history and isinstance(history, list) and len(history) > 0:
            try:
                history_parts = []
                for msg in history:
                    role_label = "User" if msg.get("role") == "user" else "AI"
                    history_parts.append(f"{role_label}: {msg.get('content', '')}")
                history_text = "\n".join(history_parts)
                rewrite_prompt = f"""Rewrite this follow-up question as a standalone query based on the history.
History: {history_text}
Question: {query}
Rewritten:"""
                if user_config:
                    llm = LLM(
                        api_key=user_config.get("api_key"),
                        base_url=user_config.get("base_url"),
                        model=user_config.get("model_name")
                    )
                else:
                    llm = LLM()
                rewrite_messages = [{"role": "user", "content": rewrite_prompt}]
                rewritten_query = await llm.chat(rewrite_messages, temperature=0.0, max_tokens=256)
                rewritten_query = rewritten_query.strip()
                if rewritten_query:
                    final_query = rewritten_query
            except Exception as e:
                print(f"Query rewrite failed: {e}")

        retrieved = await self.retrieve(doc_ids, final_query, self.top_k * 2)
        if not retrieved:
            return {
                "answer": "Please upload documents first.",
                "sources": [],
                "used_source_indices": [],
                "context_used": False,
            }

        ctx = self.build_context(retrieved)
        sources_text = self.build_sources_text(retrieved)
        truncated_history = history[-10:] if history and len(history) > 10 else history
        answer = await self.generate_answer(final_query, ctx, sources_text, truncated_history, llm_config=user_config)
        used_indices = extract_source_indices(answer)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            chunk_text = chunk.get("text", "")
            page = chunk.get("page", "")
            if page is not None and not isinstance(page, str):
                page = str(page)
            sources_list.append({
                "index": i + 1,
                "document_id": chunk.get("document_id", ""),
                "page": page,
                "source": chunk.get("source", ""),
                "text": chunk_text,
                "relevance_score": 1.0 / (1.0 + r.get("distance", 1)),
            })

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

    async def ask_stream(self, doc_ids, query, history=None, user_config: Optional[dict] = None):
        final_query = query
        if history and isinstance(history, list) and len(history) > 0:
            try:
                history_parts = []
                for msg in history[-10:]:
                    role_label = "User" if msg.get("role") == "user" else "AI"
                    history_parts.append(f"{role_label}: {msg.get('content', '')}")
                history_text = "\n".join(history_parts)
                rewrite_prompt = f"""Rewrite this follow-up question as a standalone query.
History: {history_text}
Question: {query}
Rewritten:"""
                if user_config:
                    llm = LLM(
                        api_key=user_config.get("api_key"),
                        base_url=user_config.get("base_url"),
                        model=user_config.get("model_name")
                    )
                else:
                    llm = LLM()
                rewrite_messages = [{"role": "user", "content": rewrite_prompt}]
                rewritten_query = await llm.chat(rewrite_messages, temperature=0.0, max_tokens=256)
                rewritten_query = rewritten_query.strip()
                if rewritten_query:
                    final_query = rewritten_query
            except Exception as e:
                print(f"Query rewrite failed: {e}")

        retrieved = await self.retrieve(doc_ids, final_query, self.top_k * 2)
        if not retrieved:
            yield {"type": "answer", "content": "Please upload documents first."}
            return

        ctx = self.build_context(retrieved)
        sources_text = self.build_sources_text(retrieved)

        sources_list = []
        for i, r in enumerate(retrieved[:10]):
            chunk = r.get("chunk", {})
            chunk_text = chunk.get("text", "")
            page = chunk.get("page", "")
            if page is not None and not isinstance(page, str):
                page = str(page)
            sources_list.append({
                "index": i + 1,
                "document_id": chunk.get("document_id", ""),
                "page": page,
                "source": chunk.get("source", ""),
                "text": chunk_text,
                "relevance_score": 1.0 / (1.0 + r.get("distance", 1)),
            })

        yield {"type": "sources", "sources": sources_list, "filtered_sources": sources_list}

        truncated_history = history[-10:] if history and len(history) > 10 else history
        async for token in self.generate_answer_stream(final_query, ctx, sources_text, truncated_history, llm_config=user_config):
            yield {"type": "token", "content": token}


rag_engine = RAGEngine()