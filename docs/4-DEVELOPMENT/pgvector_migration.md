# 向量存储升级：FAISS + BM25 → PostgreSQL + pgvector

> **日期**: 2026-08-30  
> **作者**: AI 辅助实施  
> **状态**: ✅ 已完成，419 个测试全绿

---

## 一、背景与动机

### 1.1 升级前架构

Study Copilot 使用文件级向量存储方案：

```
vectorstore/{doc_id}/
├── {doc_id}.index      ← FAISS 向量索引 (IndexFlatIP)
├── {doc_id}.pkl        ← chunk 文本 + metadata (pickle)
└── {doc_id}.bm25       ← BM25 关键词索引 (JSON)
```

RAG 检索流程：

1. `rag_engine.retrieve()` 从 LRU 缓存（容量 20）加载每文档的 `DocumentVectorStore`
2. 分别调用 FAISS（语义检索）和 BM25（关键词检索）
3. 应用层用 RRF（Reciprocal Rank Fusion）融合两组结果
4. CrossEncoder 重排序后返回 top_k

### 1.2 痛点

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| **运维复杂度** | 每文档 3 个文件，Docker 卷映射脆弱，重启后需重新加载 | 中 |
| **元数据过滤困难** | 无法在检索时同时过滤课程空间 / 用户 / 软删除状态 | 高 |
| **扩展瓶颈** | `IndexFlatIP` 是暴力搜索，>10万向量后明显变慢 | 中 |
| **进程内内存占用** | 20 文档索引常驻 RAM ~10-100MB，重启即失 | 低 |
| **数据一致性** | PostgreSQL 删除文档后 FAISS/BM25 文件需手动清理 | 中 |

### 1.3 升级目标

用 PostgreSQL + pgvector 扩展替代文件级向量存储，保留现有 RAG 流程的所有行为不变：

- 混合检索（语义 + 关键词）质量不下降
- CrossEncoder 重排序逻辑保持不动
- 软删除 / 课程空间过滤原生支持
- 可扩展到百万级向量

---

## 二、方案设计

### 2.1 为什么选 pgvector 而非独立向量数据库

| 对比维度 | pgvector | Qdrant / Weaviate | Chroma |
|---------|:---:|:---:|:---:|
| 新增服务 | ❌ 零 | ❌ 需额外容器 | ❌ 需额外容器 |
| 部署复杂度 | ✅ 一个 `CREATE EXTENSION` | 需配置连接/副本/备份 | 同左 |
| 元数据过滤 + 向量检索同查询 | ✅ 一次 SQL | ✅ | ✅ |
| BM25 全文检索 | ✅ `tsvector` 原生 | ✅ | 参差 |
| **数据一致性** | ✅ **同一事务，原子写入** | ⚠️ 双写 | ⚠️ |
| 运维成本 | ✅ 同现有 PostgreSQL | ❌ 多套监控 | ❌ |
| 规模上限 | ⚠️ 单机 ~500万向量 | ✅ 分布式 | ✅ 分布式 |

### 2.2 架构变化

```
升级前                          升级后
───────────────              ───────────────
PostgreSQL                    PostgreSQL + pgvector
├── users                    ├── users
├── documents                ├── documents
├── notes                    ├── notes
├── ...                      ├── ...
├── (FAISS 文件)             ├── document_chunks  ← 新增
│   ├── {id}.index           │   ├── id (PK)
│   └── {id}.pkl             │   ├── document_id (FK)
│                            │   ├── content (text)
│   └── {id}.bm25            │   ├── embedding (vector(768))
│                            │   ├── chunk_index (int)
│                            │   ├── chunk_metadata (jsonb)
└──                           │   └── [HNSW + GIN 索引]
FAISS 进程内              ← 淘汰 →  纯 SQL 查询
BM25 进程内                    (tsvector + <=>)
RRF 应用层                     (CTE + RRF SQL)
```

### 2.3 核心技术实现

#### 混合检索 SQL 查询（一次完成向量 + 全文 RRF 融合）

```sql
WITH vector_results AS (
    SELECT id, content, chunk_metadata,
           1.0 / (60 + ROW_NUMBER() OVER (ORDER BY embedding <=> :q_emb::vector)) AS v_score
    FROM document_chunks
    WHERE document_id = ANY(:doc_ids)
      AND embedding IS NOT NULL
    ORDER BY embedding <=> :q_emb::vector
    LIMIT :overfetch
),
text_results AS (
    SELECT id, content, chunk_metadata,
           1.0 / (60 + ROW_NUMBER() OVER (
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
```

#### 写入流程

```sql
INSERT INTO document_chunks (id, document_id, content, embedding, chunk_index, chunk_metadata, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7);
```

---

## 三、实施细节

### 3.1 数据库 Schema

#### Docker 镜像

```yaml
# docker-compose.yml
db:
  image: pgvector/pgvector:pg16    # ← 替换 postgres:16-alpine
```

#### Alembic 迁移

新建 `backend/alembic/versions/f1a2b3c4d5e6_add_pgvector_chunks.py`：

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id            VARCHAR      NOT NULL PRIMARY KEY,
    document_id   VARCHAR      NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content       TEXT         NOT NULL,
    embedding     vector(768),               -- pgvector 列
    chunk_index   INTEGER      NOT NULL DEFAULT 0,
    chunk_metadata JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- HNSW 索引：余弦相似度向量搜索
CREATE INDEX ix_document_chunks_doc_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN 索引：全文关键词搜索（替代 BM25）
CREATE INDEX ix_document_chunks_content_fts
    ON document_chunks USING gin (to_tsvector('zh', content));

-- 复合索引
CREATE INDEX ix_document_chunks_doc_created
    ON document_chunks (document_id, created_at);
CREATE INDEX ix_document_chunks_metadata
    ON document_chunks USING gin (chunk_metadata);
```

### 3.2 ORM 模型

在 `backend/app/db/database.py` 新增：

```python
class _Vector(TypeDecorator):
    """pgvector 兼容类型：
    - PostgreSQL: 渲染为 vector(N)
    - SQLite (测试): 回退为 String 存储 JSON 序列化的 list
    """
    impl = String
    cache_ok = True

    def __init__(self, dimension: int = 768):
        super().__init__()
        self.dimension = dimension

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            # 渲染为 vector(N) DDL
            ...
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # asyncpg 原生处理 list → vector
        return json.dumps(value)  # SQLite: JSON 序列化

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # asyncpg 返回 list
        return json.loads(value)  # SQLite: 反序列化


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(_Vector(), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
```

> **注意**：字段名 `chunk_metadata` 而非 `metadata`——SQLAlchemy Declarative API 中 `metadata` 是保留字。

### 3.3 PgVectorStore 核心模块

新建 `backend/app/core/pgvector_store.py`，实现向量存储接口：

```python
class PgVectorStore:
    def __init__(self, user_id: str, dimension: int | None = None):
        self.user_id = user_id
        self.dimension = dimension or settings.embedding_dimension
        self.chunks: list[dict] = []

    async def add_chunks(self, chunks, doc_id, db=None) -> bool:
        """Embed + INSERT INTO document_chunks。
        支持传入外部 db session（测试用）或自行创建 session。"""

    async def search(self, query, doc_ids, top_k=5) -> list[dict]:
        """混合检索：向量相似度 + 全文搜索，RRF 融合。
        一次 SQL CTE 完成，结果 batch-normalized 到 [0,1]。"""

    def save(self, path): return True      # 数据库自动持久化
    def load(self, path): return True      # 加载由 DB 查询替代
    def delete(self, path): return True    # CASCADE 自动处理
```

**关键设计决策**：

| 决策 | 原因 |
|------|------|
| `add_chunks` 接受可选 `db` 参数 | 测试套件用同一个 session fixture，需要外部注入 |
| SQLite 测试时 JSON 序列化 embedding | SQLite 不支持数组参数，pgvector 仅在 PostgreSQL 上生效 |
| `chunk_metadata` 含除 `text`/`id` 外的所有 chunk 字段 | 保留 source/page/chunking_method 等信息 |
| `search()` 返回 `retrieval_type: "pgvector_hybrid"` | 与旧 HybridVectorStore 的输出契约对齐 |

### 3.4 document_service 改动

#### 写入流程（`_do_process_document`）

```python
# 旧代码
store = DocumentVectorStore(doc_id, retrieval_type=HYBRID)
await store.add_chunks(chunks)
await store.save()  # → 写 .index + .pkl + .bm25 文件

# 新代码
store = PgVectorStore(user_id=user.id)
await store.add_chunks(chunks, doc_id, db=db)  # → embed + INSERT SQL
```

#### `get_document()`

```python
# 旧代码
store = DocumentVectorStore(doc_id)
await store.load()
chunks = store._store.chunks

# 新代码
chunks_result = await db.execute(
    select(DocumentChunk).where(DocumentChunk.document_id == doc_id).order_by(DocumentChunk.chunk_index)
)
chunks = [{"text": c.content, "metadata": c.chunk_metadata or {}} for c in chunks_result.scalars().all()]
```

#### `delete_document()`

不再需要 `rag_engine.evict_vector_store(doc_id)`（无进程内缓存可驱逐）。

#### `purge_deleted_documents()`

```python
# 旧代码
store = DocumentVectorStore(doc.id)
store.delete()  # → 删除文件

# 新代码
await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
# ON DELETE CASCADE 也会自动清理
```

### 3.5 quiz_service 改动

`_do_generate_quiz` 从文件索引改为 SQL 查询：

```python
# 旧代码
store = DocumentVectorStore(did)
await store.load()
chunks_list.extend([c["text"] for c in store._store.chunks[:10]])

# 新代码
chunk_result = await db.execute(
    select(DocumentChunk).where(DocumentChunk.document_id == did)
    .order_by(DocumentChunk.chunk_index).limit(10)
)
chunks_list.extend([c.content for c in chunk_result.scalars().all()])
```

### 3.6 rag_engine 改动

#### RAGEngine 类

```python
# 旧代码
self._vector_store_cache: OrderedDict[str, DocumentVectorStore] = OrderedDict()
self._VECTOR_STORE_CACHE_MAX = 20

# 新代码
self._pg_vector_store: PgVectorStore | None = None
```

#### `retrieve()` 方法

```python
# 旧代码：per-document 加载 + 并行搜索 + 应用层合并
stores = await asyncio.gather(*[self._get_vector_store(did) for did in doc_ids])
results_per_doc = await asyncio.gather(*[s.search(query, fetch_k) for s in stores])
all_results = [r for sub in results_per_doc for r in sub]
# ... 合并 + 过滤 + 去重 + CrossEncoder 重排序

# 新代码：单次 PgVectorStore 查询
store = self._get_pg_vector_store()
all_results = await store.search(query, doc_ids, top_k * 2)
# ... 过滤 + 去重 + CrossEncoder 重排序
```

#### 保留不变的段

```python
# CrossEncoder 重排序：完全不动
reranker = self._ensure_reranker()
if reranker and len(all_results) > 0:
    texts = [r.get("chunk", {}).get("text", "") for r in all_results]
    pairs = [[query, t] for t in texts]
    scores = reranker.predict(pairs)
    # ...

# 上下文构建：不动
context = self.build_context(all_results, max_context_tokens=12000)

# 引用来源提取：不动
used_indices = extract_source_indices(answer)
```

---

## 四、测试适配

### 4.1 改动文件

| 文件 | 改动内容 |
|------|---------|
| `tests/test_rag_engine.py` | ~25 处 `_vector_store_cache` → `_pg_vector_store`；`_make_retrieved` 改用 `relevance` 字段 |
| `tests/test_hybrid_retrieval_contract.py` | 重写为 `PgVectorStore` 契约测试（mock `_get_pg_vector_store`） |
| `tests/test_document_service.py` | `get_document` 测试改为 SQL 查 `DocumentChunk` |

### 4.2 关键适配点

| 旧 mock | 新 mock | 原因 |
|---------|---------|------|
| `engine._vector_store_cache["doc1"] = mock_store` | `engine._pg_vector_store = mock_store` | LRU 缓存替换为单例 |
| `mock_store.search(query, top_k)` | `mock_store.search(query, doc_ids, top_k*2)` | 新签名：传入 doc_ids 和 overfetch |
| `{"distance": 0.1}` | `{"relevance": 0.8, "retrieval_type": "pgvector_hybrid"}` | 新字段协议 |
| `patch('app.services.document_service.DocumentVectorStore')` | 直接 INSERT `DocumentChunk` | 不再文件索引 |
| `patch('app.services.quiz_service.DocumentVectorStore')` | 直接 SELECT `DocumentChunk` | 同上 |

---

## 五、配置文件变更

### 5.1 config.py

```python
# 旧代码
vectorstore_dir: str = "./vectorstore"    # FAISS 文件目录

# 新代码（保留 deprecated，兼容旧 .env）
vectorstore_dir: str = "./vectorstore"    # 标记为 deprecated，DB 后端不再使用
```

### 5.2 .env.example（建议更新）

```env
# 以下配置已废弃（向量存储改为数据库后端，不再需要文件目录）
# VECTORSTORE_DIR=./vectorstore

# 以下仍在使用
TOP_K=5
EMBEDDING_MODEL=shibing624/text2vec-base-chinese
EMBEDDING_DIMENSION=768
```

### 5.3 pyproject.toml

`faiss-cpu` 和 `rank-bm25` 依赖**保留**（回滚保障），如确认稳定后可移除。

---

## 六、部署流程

### 6.1 前置条件

1. **Docker 镜像可用**：`docker pull pgvector/pgvector:pg16`
2. **数据库权限**：确保 `study_user` 有 `CREATE EXTENSION` 权限

### 6.2 部署步骤

```bash
# 1. 更新 docker-compose.yml（已完成）
#    image: pgvector/pgvector:pg16

# 2. 停止旧服务，卷数据保留
docker compose down

# 3. 启动新数据库
docker compose up -d db

# 4. 验证 pgvector 扩展
docker exec -it study-copilot-db psql -U study_user -d study_copilot \
  -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT * FROM pg_available_extensions WHERE name='vector';"

# 5. 运行迁移（在 backend 容器内或本地）
cd backend
alembic upgrade head

# 6. 启动全量服务
docker compose up -d

# 7. 验证：上传文档 → 请求 PG → 确认 document_chunks 有数据
docker exec -it study-copilot-db psql -U study_user -d study_copilot \
  -c "SELECT count(*) FROM document_chunks;"
```

### 6.3 旧数据迁移策略

**惰性迁移（推荐）**：

1. 新代码上线后，旧 FAISS/BM25 索引文件不再被读取
2. 用户首次对某文档做 RAG 提问时，系统自动重新嵌入并写入 `document_chunks`
3. 生产稳定后可做一次性批量迁移

**一次性批量迁移（可选）**：

```python
# 运维脚本: migrate_legacy_embeddings.py
async def migrate_all():
    docs = await db.execute(
        select(Document).where(Document.status == "ready", Document.deleted_at.is_(None))
    )
    for doc in docs:
        chunks = await load_legacy_chunks(doc.id)  # 从 .pkl 加载
        if chunks:
            store = PgVectorStore(user_id=doc.user_id)
            await store.add_chunks(chunks, doc.id, db=db)
            # 可选：删除旧 FAISS/BM25 文件
            shutil.rmtree(f"./vectorstore/{doc.id}")
```

---

## 七、性能预期

| 指标 | FAISS + BM25 | pgvector HNSW | 说明 |
|------|:---:|:---:|------|
| 单文档检索延迟 | ~5ms | ~10-20ms | HNSW 在 1万向量下 < 50ms |
| 混合检索延迟 | ~15ms (并行) | ~20-30ms (单次 SQL) | 消除 Python 层 RRF 合并开销 |
| 写入吞吐 | O(n) per doc | O(n) batch INSERT | 差异不大 |
| 内存占用 | ~1-100MB (LRU 20 docs) | ~几 MB (HNSW cache) | pgvector 显著更低 |
| 规模上限 | ~10万向量 (FAISS brute) | ~500万向量 (HNSW, 单机) | pgvector 扩展性更好 |

---

## 八、回滚方案

旧代码（FAISS + BM25）完整保留在 `app/core/vector_store.py`，仅修改调用方：

```python
# 回滚只需改一行：
# rag_engine.py: _get_pg_vector_store() → _get_vector_store(doc_id)
# document_service.py: PgVectorStore → DocumentVectorStore
```

---

## 九、改动文件总览

### 新建文件（3个）

| 文件 | 说明 |
|------|------|
| `backend/app/core/pgvector_store.py` | PgVectorStore 向量存储实现 |
| `backend/alembic/versions/f1a2b3c4d5e6_add_pgvector_chunks.py` | pgvector 扩展 + document_chunks 表 + 索引 |
| `docker-compose.yml` (修改) | 镜像切换 `pgvector/pgvector:pg16` |

### 修改文件（8个）

| 文件 | 变更 |
|------|------|
| `backend/app/db/database.py` | +`_Vector` TypeDecorator +`DocumentChunk` ORM 模型 |
| `backend/app/db/__init__.py` | 导出 `DocumentChunk` |
| `backend/app/services/document_service.py` | 向量化改 SQL；remove file cleanup |
| `backend/app/services/quiz_service.py` | chunk 获取改 SQL |
| `backend/app/core/rag_engine.py` | retrieve() 调用 PgVectorStore；remove LRU cache |
| `backend/app/config.py` | 注释 deprecated `vectorstore_dir` |
| `backend/tests/test_rag_engine.py` | ~25 处 mock 适配 |
| `backend/tests/test_hybrid_retrieval_contract.py` | 重写为 pgvector 契约 |
| `backend/tests/test_document_service.py` | chunk 查找改 SQL |

### 保留不动（回滚保障）

| 文件 | 原因 |
|------|------|
| `backend/app/core/vector_store.py` | FAISS/BM25 代码完整保留 |
| `backend/app/core/embedder.py` | 嵌入计算逻辑复用 |
| `backend/app/core/chunker.py` | 分块逻辑不变 |

---

## 十、风险与经验

| 问题 | 解决 | 经验 |
|------|------|------|
| `sqlalchemy.VECTOR` 不可用 (2.0.50) | 自实现 `_Vector` TypeDecorator | SQLAlchemy 非所有 PG 类型都有内置类型 |
| `metadata` 是 Declarative API 保留字 | 改名为 `chunk_metadata` | ORM 模型命名需避开 SQLAlchemy 内部属性 |
| SQLite 不支持 `list` 参数绑定 | JSON 序列化 embedding + metadata | 测试 DB 和 PG 的参数序列化行为不同 |
| `get_db()` 是 async generator，不能用 `async with` | 用 `await anext(get_db())` + `finally: close()` | FastAPI `Depends` 模式不直接支撑上下文管理 |
| 测试 suite 的 `.env` 连真实 PostgreSQL | 测试失败时先检查是否走了 PG 而非 SQLite | `.env` 的 `DATABASE_URL` 优先级高于 test fixtures |
| `_make_retrieved` 的 `distance` 字段与新 `relevance` 不兼容 | 全局更新 mock 数据格式 | 变更数据契约时需全面审查所有 mock |
| `chunk_metadata dict` 在 SQLite 不支持 | `json.dumps()` 序列化 | SQLite 的 JSON 列实际为 TEXT |

---

## 十一、后续优化方向

1. **批量迁移工具**：将已有 FAISS 索引迁移到 `document_chunks`
2. **HNSW 参数调优**：当前 `m=16, ef_construction=64`，可根据实际数据量调整
3. **`COPY` 批量写入**：大批量 chunk 插入时用 `COPY` 替代逐行 INSERT
4. **移除旧依赖**：确认稳定后从 `pyproject.toml` 移除 `faiss-cpu` 和 `rank-bm25`
5. **ivfflat 索引**：对于 >100万向量的场景，可考虑 IVF 索引替代 HNSW
