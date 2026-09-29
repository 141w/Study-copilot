---
feature: phase2-defect-fix-batch3
status: delivered
updated: 2026-09-29
branch: master
commits: 9de4ba3..9de4ba3
---

# 二期缺陷修复 · 第三批 F10–F13

> 需求源：`WeKnora吸收二期-缺陷修复实施计划.md` §5。F10/F11/F12 同热路径一次做完。

## Report

**What was built** — F10 关键词通道补 `@@` 命中过滤 + `keyword_threshold`（ts_rank）消费，默认 0=旧行为；F11 `rerank_threshold` 在 rerank 阶段生效，面板补 `keyword_threshold`/`rerank_threshold`，重排关闭时滑杆置灰并提示，`vector_threshold`/`embedding_top_k` 文案说明作用域（融合后归一分、仅问答路径）；F12 Agent `knowledge_search` 透传 `retrieval_config`（引擎注入）；F13 重解析 `attempt` 递增 + `(document_id, attempt, name)` 唯一约束迁移 `d0e1f2a3b4c5`。

**Verification** — `test_retrieval_params_f10.py` 2 条 + `test_parse_spans.py` F13 1 条 + `test_rag_engine.py`/`test_agent_tools.py` 全绿；ruff/mypy/vue-tsc 0；alembic 单 head `d0e1f2a3b4c5`。

**Journey log** — 1) `keyword_threshold` 此前只在 config 默认表出现，检索路径零消费——参数面板上有控件不等于后端生效。2) Agent 工具由引擎统一注入受信参数，避免模型覆盖。3) attempt 用 `max(attempt)+1` 简单递增，配合唯一约束防重复行。

## [S1] Problem
见 Report。计划 §5 缺陷表 F10–F13。

## [S2] Design
- F10：`text_results` 加 `to_tsvector @@ plainto_tsquery`；`keyword_threshold>0` 时再加 `ts_rank >=` 过滤。
- F11：`rag_engine.retrieve` 在 rerank 后按 `reranker_score >= rerank_threshold` 过滤；UI 文案与置灰按计划视觉规格。
- F12：`engine.py` 在 `knowledge_search` 的 args 注入 `retrieval_config=cfg.get("retrieval")`。
- F13：`next_attempt()` = `max(attempt)+1`；迁移加唯一约束。

## [S3] Out of Scope
- 第四批 F14–F20
- zhparser 生产复测（本地 `pg_ts_config` 仅 simple/english）
- `top_k<=10` 门、RRF 默认 1.0/1.0（计划明确不改）

## Tasks
- [x] T1: F10 关键词过滤 + keyword_threshold 消费 (covers: S2 F10)
- [x] T2: F11 死参数与文案 (covers: S2 F11)
- [x] T3: F12 Agent 透传 (covers: S2 F12)
- [x] T4: F13 attempt 递增 + 唯一约束迁移 (covers: S2 F13)
