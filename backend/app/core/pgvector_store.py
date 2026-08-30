"""PostgreSQL + pgvector 向量存储实现。

替代原有的文件级 FAISS + BM25 索引：
  - add_chunks(): embed + INSERT INTO document_chunks
  - search(): 单次 SQL 完成向量检索 + 全文检索 + RRF 融合
  - 不再需要 save()/load() 持久化（数据库即持久层）
  - 不再需要 delete() —— 文档删除时级联清除 chunk

usage:
    store = PgVectorStore(user_id=user.id)
    await store.add_chunks(chunks, doc_id)
    results = await store.search(query, doc_ids, top_k=5)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedder import embedder
from app.db import get_db

logger = logging.getLogger(__name__)

# RRF 常数（与 HybridVectorStore._rrf_k 保持一致）
_RRF_K = 60
_VECTOR_WEIGHT = 0.5
_TEXT_WEIGHT = 0.5


class PgVectorStore:
    """PostgreSQL + pgvector 向量存储。

    不继承 BaseVectorStore 以避免 load/save/delete 的空实现误导；
    对外接口与 BaseVectorStore 对齐（add_chunks / search）。
    """

    def __init__(self, user_id: str, dimension: int | None = None):
        self.user_id = user_id
        self.dimension = dimension or settings.embedding_dimension
        self.chunks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 持久化（无操作 —— 数据已存于 DB）
    # ------------------------------------------------------------------

    async def save(self, path: str) -> bool:  # noqa: ARG002 — 兼容 BaseVectorStore 接口
        """数据库自动持久化，无需手动 save。"""
        return True

    async def load(self, path: str) -> bool:  # noqa: ARG002
        """加载由 DB 查询替代；保留接口兼容调用方。"""
        return True

    def delete(self, path: str) -> bool:  # noqa: ARG002
        """chunk 删除通过 SQL ON DELETE CASCADE 自动处理。"""
        return True

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    async def add_chunks(self, chunks: list[dict], doc_id: str, db: AsyncSession | None = None) -> bool:
        """Embed text chunks and batch INSERT INTO document_chunks.

        Args:
            chunks: Text chunk dicts with at least a ``text`` field.
            doc_id: Owner document ID.
            db: Optional existing async DB session.  When supplied, the caller
                is responsible for commit (the test suite passes the test
                session this way).  When omitted, a fresh session is opened
                and committed internally.
        """
        if not chunks:
            return False

        texts = [c["text"] for c in chunks]
        try:
            embeddings = await embedder.embed_texts(texts)
        except Exception as exc:
            logger.error("Embedding failed for doc %s: %s", doc_id, exc)
            raise

        rows: list[dict] = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            meta = {
                k: v
                for k, v in chunk.items()
                if k not in ("text", "id")
            }
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "document_id": doc_id,
                    "content": chunk["text"],
                    "embedding": emb.tolist() if hasattr(emb, "tolist") else list(emb),
                    "chunk_index": i,
                    "chunk_metadata": meta,
                    "created_at": datetime.now(timezone.utc),
                }
            )

        if not rows:
            return False

        # For SQLite tests: serialize complex types to strings
        # (pgvector/JSON handle native types on PostgreSQL)
        if db is not None and db.bind.dialect.name == "sqlite":
            import json as _json
            for row in rows:
                if isinstance(row["embedding"], list):
                    row["embedding"] = _json.dumps(row["embedding"])
                if isinstance(row["chunk_metadata"], dict):
                    row["chunk_metadata"] = _json.dumps(row["chunk_metadata"])
        elif not db:
            # Self-contained path: detect from AsyncSessionLocal
            from app.db.database import AsyncSessionLocal as _ASL
            _bind = _ASL.kw.get("bind")
            if _bind and _bind.dialect.name == "sqlite":
                import json as _json
                for row in rows:
                    if isinstance(row["embedding"], list):
                        row["embedding"] = _json.dumps(row["embedding"])
                    if isinstance(row["chunk_metadata"], dict):
                        row["chunk_metadata"] = _json.dumps(row["chunk_metadata"])

        if db is not None:
            # Caller manages the session/transaction (e.g. test fixtures)
            await db.execute(
                text(
                    "INSERT INTO document_chunks (id, document_id, content, embedding, chunk_index, chunk_metadata, created_at) "
                    "VALUES (:id, :document_id, :content, :embedding, :chunk_index, :chunk_metadata, :created_at)"
                ),
                rows,
            )
            await db.commit()
        else:
            # Self-contained: open + commit internally
            session = await anext(get_db())
            try:
                await session.execute(
                    text(
                        "INSERT INTO document_chunks (id, document_id, content, embedding, chunk_index, chunk_metadata, created_at) "
                        "VALUES (:id, :document_id, :content, :embedding, :chunk_index, :chunk_metadata, :created_at)"
                    ),
                    rows,
                )
                await session.commit()
            finally:
                await session.close()

        self.chunks.extend(chunks)
        logger.debug("Inserted %d chunks for document %s", len(rows), doc_id)
        return True

    # ------------------------------------------------------------------
    # 检索（混合：向量 + 全文 RRF）
    # ------------------------------------------------------------------

    async def search(self, query: str, doc_ids: list[str], top_k: int = 5) -> list[dict[str, Any]]:
        """混合检索：向量相似度 + PostgreSQL 全文搜索，RRF 融合。

        一次 SQL 完成，支持任意 doc_ids 过滤。

        Args:
            query: 用户查询文本。
            doc_ids: 限定检索的文档 ID 列表。
            top_k: 返回结果数。

        Returns:
            按融合分数降序排列的结果列表，每项含 ``chunk``、``relevance``、``retrieval_type``。
        """
        if not doc_ids:
            return []

        q_emb = await embedder.embed_query(query)
        q_emb_list = q_emb.tolist() if hasattr(q_emb, "tolist") else list(q_emb)

        doc_id_array = "{" + ",".join(doc_ids) + "}"

        sql = f"""
        WITH vector_results AS (
            SELECT id, content, chunk_metadata,
                   1.0 / ({_RRF_K} + ROW_NUMBER() OVER (ORDER BY embedding <=> :q_emb::vector)) AS v_score
            FROM document_chunks
            WHERE document_id = ANY(:doc_ids)
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :q_emb::vector
            LIMIT :overfetch
        ),
        text_results AS (
            SELECT id, content, chunk_metadata,
                   1.0 / ({_RRF_K} + ROW_NUMBER() OVER (
                       ORDER BY ts_rank(to_tsvector('zh', content), plainto_tsquery('zh', :query)) DESC
                   )) AS t_score
            FROM document_chunks,
                 plainto_tsquery('zh', :query) AS query
            WHERE document_id = ANY(:doc_ids)
            ORDER BY ts_rank(to_tsvector('zh', content), query) DESC
            LIMIT :overfetch
        ),
        fused AS (
            SELECT
                COALESCE(v.id, t.id) AS id,
                COALESCE(v.content, t.content) AS content,
                COALESCE(v.chunk_metadata, t.chunk_metadata) AS chunk_metadata,
                COALESCE(v.v_score, 0) + COALESCE(t.t_score, 0) AS rrf_score
            FROM vector_results v
            FULL OUTER JOIN text_results t USING (id)
        )
        SELECT id, content, chunk_metadata, rrf_score
        FROM fused
        ORDER BY rrf_score DESC
        LIMIT :top_k
        """

        overfetch = top_k * 2

        db = await anext(get_db())
        try:
            cursor = await db.execute(
                text(sql),
                {
                    "q_emb": str(q_emb_list),
                    "doc_ids": doc_ids,
                    "query": query,
                    "overfetch": overfetch,
                    "top_k": top_k,
                },
            )
            rows = cursor.fetchall()
        finally:
            await db.close()

        if not rows:
            return []

        # 批内归一化：RRF 融合分极小，以本批最高分为基准归一到 [0,1]
        best_score = max(float(r.rrf_score) for r in rows)
        if best_score == 0:
            best_score = 1.0

        results: list[dict[str, Any]] = []
        for row in rows:
            rel = float(row.rrf_score) / best_score
            results.append(
                {
                    "chunk": {
                        "text": row.content,
                        "metadata": row.chunk_metadata or {},
                    },
                    "relevance": max(0.0, min(1.0, rel)),
                    "fused_score": float(row.rrf_score),
                    "retrieval_type": "pgvector_hybrid",
                }
            )

        return results

    def get_chunk_count(self) -> int:
        """Return number of chunks loaded in memory (not total DB count)."""
        return len(self.chunks)
