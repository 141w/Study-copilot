"""自研检索方案评测：生产路径 pgvector 混合检索（向量 + 全文 + RRF）。

两种配置：
- hybrid:        PgVectorStore.search() 直接检索（生产单条 SQL：向量 + 全文 RRF 融合）
- hybrid-rerank: RAGEngine.retrieve()（search + 相关性过滤 + 去重 + CrossEncoder rerank）

依赖真实 PostgreSQL + pgvector 实例（默认 postgresql+asyncpg://eval@127.0.0.1:55432/evaldb，
可用环境变量 DATABASE_URL 覆盖）。入库走 PgVectorStore.add_chunks（内部 embed，
与生产一致）；由于 search() 结果不回传行 id，原始 chunk id 通过
chunk_metadata.eval_id 回传。

已知环境限制：评测实例无 zhparser，_get_fts_config 会降级为 simple 配置，
中文全文通道近乎失效——hybrid 分数反映的是向量主导的 RRF；生产部署
（zhparser 就绪）下词法通道会贡献更多召回。
"""

from __future__ import annotations

import os

from evaluation.datasets.base import EvalDataset

EVAL_USER_ID = "eval-user"
_SCHEMA_READY = False
_INGESTED: set[str] = set()


def doc_id_for(ds: EvalDataset) -> str:
    """数据集在 PG 中的文档 id（同一数据集重跑幂等）。"""
    return f"eval-{ds.name}"


async def _ensure_schema() -> None:
    """建全部业务表（幂等）并写入最小化 eval 用户行。"""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    from sqlalchemy import text as _text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db import Base, engine

    # 静音 SQL echo：.env DEBUG=True 时 app 引擎 echo 全量 SQL，评测日志会爆炸
    engine.sync_engine.echo = False

    eval_engine = create_async_engine(os.environ["DATABASE_URL"])
    async with eval_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # _Vector.get_col_spec 在 create_all 路径下拿不到 dialect kw，embedding
        # 列会建成 TEXT；生产经 Alembic 迁移建 vector(768)。评测环境显式
        # ALTER 对齐生产 schema（幂等：已是 USER-DEFINED(vector) 则跳过）。
        res = await conn.execute(
            _text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'document_chunks' AND column_name = 'embedding'"
            )
        )
        if res.scalar() != "USER-DEFINED":
            await conn.execute(
                _text(
                    "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768) "
                    "USING embedding::vector"
                )
            )
        await conn.execute(
            _text(
                "INSERT INTO users (id, username, email, password_hash, is_active, created_at) "
                "VALUES (:id, :u, :e, :p, true, now()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": EVAL_USER_ID, "u": "eval", "e": "eval@local", "p": "eval-not-a-hash"},
        )
    await eval_engine.dispose()
    _SCHEMA_READY = True


async def ensure_document_row(doc_id: str, filename: str) -> None:
    """确保 documents 行存在并清空该 doc 的旧 chunk（幂等，供各评测复用）。

    document_chunks.document_id 有 FK 约束，直接 add_chunks 前必须先建行。
    """
    from sqlalchemy import text as _text

    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(
            _text(
                "INSERT INTO documents (id, user_id, filename, file_path, status, chunk_count, "
                "file_size, created_at) VALUES (:id, :uid, :fn, '', 'completed', 0, 0, now()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": doc_id, "uid": EVAL_USER_ID, "fn": filename},
        )
        await db.execute(_text("DELETE FROM document_chunks WHERE document_id = :d"), {"d": doc_id})
        await db.commit()


async def _ensure_ingested(ds: EvalDataset, doc_id: str) -> None:
    """把数据集语料写入 PG（同数据集重跑先清旧 chunk，保证幂等）。"""
    if doc_id in _INGESTED:
        return
    from sqlalchemy import text as _text

    from app.core.pgvector_store import PgVectorStore
    from app.db import AsyncSessionLocal

    await _ensure_schema()

    async with AsyncSessionLocal() as db:
        await db.execute(
            _text(
                "INSERT INTO documents (id, user_id, filename, file_path, status, chunk_count, "
                "file_size, created_at) VALUES (:id, :uid, :fn, '', 'completed', :cc, 0, now()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": doc_id, "uid": EVAL_USER_ID, "fn": ds.name, "cc": len(ds.corpus)},
        )
        await db.execute(_text("DELETE FROM document_chunks WHERE document_id = :d"), {"d": doc_id})
        await db.commit()

    store = PgVectorStore(user_id="eval")
    chunks = [{"text": text, "eval_id": cid} for cid, text in ds.corpus.items()]
    await store.add_chunks(chunks, doc_id, db=None)
    _INGESTED.add(doc_id)


async def retrieve_hybrid(
    ds: EvalDataset,
    queries: dict[str, str],
    top_k: int,
) -> dict[str, list[str]]:
    """hybrid：PgVectorStore.search()（向量 + 全文 RRF，生产 SQL 路径）。"""
    from app.core.pgvector_store import PgVectorStore

    doc_id = doc_id_for(ds)
    await _ensure_ingested(ds, doc_id)
    store = PgVectorStore(user_id="eval")

    run: dict[str, list[str]] = {}
    for qid, q in queries.items():
        results = await store.search(q, [doc_id], top_k=top_k)
        run[qid] = [r["chunk"].get("metadata", {}).get("eval_id", "") for r in results]
    return run


async def retrieve_hybrid_rerank(
    ds: EvalDataset,
    queries: dict[str, str],
    top_k: int,
) -> dict[str, list[str]]:
    """hybrid-rerank：RAGEngine.retrieve()（+ 相关性过滤/去重/CrossEncoder rerank）。"""
    # 循环导入规避：app.core.rag_engine(L12 import app.agent.context) 与
    # app.agent.tools.definitions(L12 import rag_engine 实例) 互为依赖，
    # 若 rag_engine 先进入初始化会死在 definitions 的实例导入上。先完整
    # 加载 app.agent 包（让 definitions 侧先进入循环）再导入 RAGEngine。
    import app.agent  # noqa: F401
    from app.core.rag_engine import RAGEngine

    doc_id = doc_id_for(ds)
    await _ensure_ingested(ds, doc_id)
    engine = RAGEngine()

    run: dict[str, list[str]] = {}
    for qid, q in queries.items():
        results = await engine.retrieve([doc_id], q, top_k=top_k)
        run[qid] = [r["chunk"].get("metadata", {}).get("eval_id", "") for r in results]
    return run
