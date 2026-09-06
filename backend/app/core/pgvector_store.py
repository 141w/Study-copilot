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

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedder import embedder
from app.db import AsyncSessionLocal
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

# RRF 常数（与 HybridVectorStore._rrf_k 保持一致）
_RRF_K = 60
_VECTOR_WEIGHT = 0.5
_TEXT_WEIGHT = 0.5

_cached_fts_config: str | None = None


async def _get_fts_config(db: AsyncSession) -> str:
    """探测 PostgreSQL 是否支持 'zh' 全文配置；若不支持则平滑降级为 'simple'。"""
    global _cached_fts_config
    if _cached_fts_config is not None:
        return _cached_fts_config
    try:
        res = await db.execute(text("SELECT 1 FROM pg_ts_config WHERE cfgname = 'zh'"))
        if res.scalar():
            _cached_fts_config = "zh"
            return "zh"
    except Exception as exc:
        logger.debug("pg_ts_config probe failed or not postgres: %s", exc)
    logger.info("PostgreSQL 'zh' full-text configuration not detected; falling back to 'simple'")
    _cached_fts_config = "simple"
    return "simple"

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
        """Embed + insert using raw SQL with vector cast."""
        if not chunks:
            return False

        texts = [c["text"] for c in chunks]
        try:
            embeddings = await embedder.embed_texts(texts)
        except Exception as exc:
            logger.error("Embedding failed for doc %s: %s", doc_id, exc)
            raise

        import json as _json

        # H-1 预检：模型实际输出维度必须与配置一致。列维度（768）在建表时固化，
        # 切换 BGE-M3(1024) 等模型时若不预检，INSERT 会在 DB 层报晦涩的
        # 22023 "expected 768 dimensions" —— 这里提前给出明确中文指引。
        if len(embeddings) > 0:
            sample = embeddings[0]
            actual_dim = len(sample) if hasattr(sample, "__len__") else int(getattr(sample, "shape", [0])[0])
            if actual_dim != self.dimension:
                raise ValidationError(
                    f"Embedding 维度不匹配：模型输出 {actual_dim} 维，"
                    f"但配置/数据库列为 {self.dimension} 维。请检查 .env 的 "
                    f"EMBEDDING_MODEL 与 EMBEDDING_DIMENSION 是否一致；切换模型"
                    f"需迁移数据库列并重新处理全部文档。"
                )

        rows: list[dict] = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            meta = {k: v for k, v in chunk.items() if k not in ("text", "id")}
            emb_list = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "document_id": doc_id,
                    "content": chunk["text"],
                    "embedding": _json.dumps(emb_list),
                    "chunk_index": i,
                    "chunk_metadata": _json.dumps(meta),
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )

        if not rows:
            return False

        sql = text(
            "INSERT INTO document_chunks "
            "(id, document_id, content, embedding, chunk_index, chunk_metadata, created_at) "
            f"VALUES (:id, :document_id, :content, CAST(:embedding AS vector({self.dimension})), :chunk_index, :chunk_metadata, :created_at)"
        )

        if db is not None:
            batch_size = 100
            for start_idx in range(0, len(rows), batch_size):
                await db.execute(sql, rows[start_idx : start_idx + batch_size])
            await db.commit()
        else:
            async with AsyncSessionLocal() as session:
                batch_size = 100
                for start_idx in range(0, len(rows), batch_size):
                    await session.execute(sql, rows[start_idx : start_idx + batch_size])
                await session.commit()

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

        async with AsyncSessionLocal() as db:
            fts_cfg = await _get_fts_config(db)

        sql = f"""
        WITH vector_results AS (
            SELECT id, document_id, content, chunk_metadata,
                   1.0 / ({_RRF_K} + ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:q_emb AS vector))) AS v_score
            FROM document_chunks
            WHERE document_id = ANY(:doc_ids)
              AND embedding IS NOT NULL
              AND (chunk_metadata->>'is_parent' IS NULL OR chunk_metadata->>'is_parent' != 'true')
            ORDER BY embedding <=> CAST(:q_emb AS vector)
            LIMIT :overfetch
        ),
        text_results AS (
            SELECT id, document_id, content, chunk_metadata,
                   1.0 / ({_RRF_K} + ROW_NUMBER() OVER (
                       ORDER BY ts_rank(to_tsvector('{fts_cfg}', content), plainto_tsquery('{fts_cfg}', :query)) DESC
                   )) AS t_score
            FROM document_chunks,
                 plainto_tsquery('{fts_cfg}', :query) AS query
            WHERE document_id = ANY(:doc_ids)
              AND (chunk_metadata->>'is_parent' IS NULL OR chunk_metadata->>'is_parent' != 'true')
            ORDER BY ts_rank(to_tsvector('{fts_cfg}', content), query) DESC
            LIMIT :overfetch
        ),
        fused AS (
            SELECT
                COALESCE(v.id, t.id) AS id,
                COALESCE(v.document_id, t.document_id) AS document_id,
                COALESCE(v.content, t.content) AS content,
                COALESCE(v.chunk_metadata, t.chunk_metadata) AS chunk_metadata,
                COALESCE(v.v_score, 0) + COALESCE(t.t_score, 0) AS rrf_score
            FROM vector_results v
            FULL OUTER JOIN text_results t USING (id)
        )
        SELECT id, document_id, content, chunk_metadata, rrf_score
        FROM fused
        ORDER BY rrf_score DESC
        LIMIT :top_k
        """

        overfetch = max(top_k * 3, 20)

        async with AsyncSessionLocal() as db:
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

        if not rows:
            return []

        # 批内归一化：RRF 融合分极小，以本批最高分为基准归一到 [0,1]
        best_score = max(float(r.rrf_score) for r in rows)
        if best_score == 0:
            best_score = 1.0

        results: list[dict[str, Any]] = []
        for row in rows:
            rel = float(row.rrf_score) / best_score
            meta = row.chunk_metadata or {}
            if isinstance(meta, str):
                # JSONB 列通常已反序列化；防御驱动直接返回字符串的场景
                try:
                    meta = json.loads(meta)
                except Exception:  # noqa: BLE001 - 保留可显示部分
                    meta = {}
            results.append(
                {
                    "chunk": {
                        # 扁平字段与 legacy vector_store 保持同一契约：
                        # rag_engine 从顶层读取 page/source/document_id
                        # 构建来源卡（此前嵌套在 metadata 里，来源卡页码恒空）
                        "text": row.content,
                        "page": meta.get("page", ""),
                        "source": meta.get("source", ""),
                        "document_id": row.document_id,
                        "metadata": meta,
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
