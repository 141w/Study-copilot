-- Embedding 迁移：text2vec-base-chinese(768) -> bge-small-zh-v1.5(512)
--
-- ⚠️ 激活前置条件（未满足前禁止执行，见 docs/compose/spec/rag-retrieval-optimization.md Phase 4）：
--   1. 真实用户 query 抽样验证 bge-small-zh 不劣化（公开数据集是代理指标）
--   2. 全量重建向量任务已就绪（本脚本会清空旧向量，重建前检索质量为空窗期）
--   3. 配置同步：EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5 / EMBEDDING_DIMENSION=512
--
-- 执行方式（每条在事务中，可逐表灰度）：
--   psql -d study_copilot -f backend/scripts/embedding_migration_bge_small_zh.sql
--
-- 回滚：本脚本为破坏性（DROP 旧向量列）。回滚 = 重新执行 768 版本迁移 +
--   全量重建（预案：重建任务可重复入队）。建议迁移前 pg_dump document_chunks。

\set ON_ERROR_STOP on

BEGIN;

-- 1. document_chunks（RAG 检索主表）
ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;
ALTER TABLE document_chunks ADD COLUMN embedding vector(512);

COMMIT;

BEGIN;

-- 2. messages（会话消息语义搜索）
ALTER TABLE messages DROP COLUMN IF EXISTS embedding;
ALTER TABLE messages ADD COLUMN embedding vector(512);

COMMIT;

BEGIN;

-- 3. notes（笔记语义搜索）
ALTER TABLE notes DROP COLUMN IF EXISTS embedding;
ALTER TABLE notes ADD COLUMN embedding vector(512);

COMMIT;

-- 4. 索引（如有 HNSW/IVFFlat 索引需一并重建；当前 schema 以 migrations 为准，
--    若无显式向量索引可跳过本节）
-- CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
--   ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- 5. 迁移后必做：触发全量重建（对每个文档重新向量化）。
--    复用文档处理管线（document_service + 异步任务队列）：
--    - 若有 reprocess 入口：逐文档入队重建任务
--    - 若无：临时补一个重建任务类型（遍历 documents 表，删除旧 chunk 后重跑管线）
--    重建完成前检索命中率将显著下降（向量为空），建议低峰期执行或维护双列灰度。

SELECT 'migration done: embedding columns now vector(512); re-vectorization required' AS status;
