# 检索评测对比 — 全量清理 + 重跑（2026-09-28）

> 对应计划 §4.1 / §12-3 / §13.2：向量输入变更与索引清理后的排序对比。
> 口径：`scripts/retrieval_probe.py`（应用语料探针，非学术 harness）。
> 产物：`probe-before-20260928.json` / `probe-after-20260928.json`。

## 数据侧处置

| 指标 | 清理前 | 清理后（含重跑） |
|---|---|---|
| `document_chunks` 总行数 | 10680 | **1804** |
| `char_start IS NULL` 旧行 | 10463 | 0（子块坐标在 metadata，见备注） |
| 带坐标行 | 217 | 478 父块 + 子块 |
| ready 文档行数 vs `chunk_count` 不一致 | 12 篇 | **0 篇** |
| 最严重单篇（eGMP QMS） | 记录 1754 / 实际 8770（约 5 份副本） | **1754 == 1754**（单副本） |

处置步骤：
1. `pg_dump -t document_chunks` 备份 → `backups/document_chunks_pre_cleanup_20260928.sql`（3.1GB）
2. `scripts/cleanup_duplicate_chunks.py --apply`：删 stale 10463 + 重复 150，resync 12 篇 `chunk_count`
3. `scripts/reindex_all.py` 重建（`_do_process_document` 已先删后建，幂等）：ok=16 / fail=12

失败 12 篇归因：`rag-stress-corpus.pdf` 源文件丢失（真实语料，待单独修）+ 11 篇空测试残留 `t.txt`/`entangle.txt`（内容不足）。

## 探针对比（n=15 查询，top_k=5）

| 指标 | before | after | 说明 |
|---|---|---|---|
| hit_rate@1 | 1.000（14/14） | **0.933（14/15）** | 唯一 @1 丢失：`第四组-学习层次八类方法.pptx` 查询被大文档 eGMP 抢到第 1，本文仍居第 2 |
| hit_rate@5 | 1.000 | **1.000（15/15）** | 右文档始终在 top-5 |
| top3 排序变化 | — | 6/9 共有查询 | 向量输入变更 + 去重后属预期 |
| 重复行占据 top | 是（如 3 条同文副本挤满 top3） | **否**（unique_chunks = k） | 本次清理的核心收益 |

### 结论

1. **索引健康**：行数不变量 `ready_mismatch=0`，/health 的 `chunk_count_sync` 应为 `ok`。
2. **召回未劣化**：hit@5 保持 100%；hit@1 的 1 例偏差是语料体量失衡（1754 块大文档 vs 6 块 pptx），不是排序崩坏。
3. **重复噪声消除**：清理前 top-k 被同内容副本占据，RRF 融合被放大；清理后每条命中都是不同切片。
4. **学术 harness 基线**（cmedqa/mmarco）本轮未跑——需 HF 数据集 + 独立评测 PG，可另排期；本次对比用应用语料探针回答「我的文档排序有没有坏」这一问题。

## 遗留

- `rag-stress-corpus.pdf` 源文件缺失（`uploads/f1a3f4aa-.../e24dbb11-....pdf`），需从备份或原作者处恢复后单独 reprocess。
- 11 篇空 `t.txt` 测试残留建议 soft-delete / purge，避免占用列表与重跑时间。
- hierarchical 子块列级 `char_start/char_end` 为 NULL（坐标在 `chunk_metadata`），与阶段二「列级坐标」设计有偏差；父块已带列级坐标，编辑/浮层链路按父块与 metadata 回退可用。若要子块也上列级坐标，需再改 `chunker.py` 属增强项。
