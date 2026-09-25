---
feature: weknora-ui-upgrade
status: delivered
updated: 2026-09-25
branch: master
commits: 902997f..a50c42b
---

# WeKnora 吸收 · UI/检索体验升级

## Report

**What was built** — 计划 P0 与阶段一～六主体：来源深链统一 `?doc=`、StreamBatcher 死代码清理、只读分块预览 API+界面、切片坐标/原文副本/迁移与全量重跑、切片在线编辑+版本回滚、进度双窗收束+window_close、引用悬停浮层与来源展开、输入框范围/模型胶囊、断线续流与会话附件、filePreview/CSV 嗅探。全部为自研 Vue3 + Element Plus + Tailwind 与 FastAPI 重写，未粘贴 WeKnora 代码。

**Verification** — 后端 `pytest tests/` **754 passed**（cov 74.7%）/ ruff / mypy / `alembic heads` 仅 `c8d9e0f1a2b3`。前端 `vitest` **371 passed** / `vue-tsc` 0 / `vite build` 通过。迁移 `b7c8d9e0f1a2` / `c8d9e0f1a2b3` 已对 PostgreSQL 做 upgrade/downgrade 验证。全量重跑 `scripts/reindex_all.py`：ok=14 fail=14（失败均为缺文件/空文档/离线 embedding，非代码缺陷）。

**Journey log**
- StreamBatcher 采用计划方案 B 删除；假测试一并清除。
- `run_chunking_chain` 供入库与预览共用；semantic 在预览中跳过 embedder。
- `content_revision/index_status/is_parent` 必须 `server_default`，否则 raw INSERT 触发 SQLite NOT NULL。
- 深链契约 `?doc=`（兼容 `document_id`）；生产方 ChatMessageItem / NoteViewer / TaskPanel。
- 4B 引用浮层与 5.5/5.6 由并行子任务交付；4B 曾遇 API 中断，文件已落盘并通过门禁。

## [S1] Problem
Study Copilot 对照 WeKnora v0.8.0 的 UI/检索体验缺口（详见根目录 `WeKnora吸收-UI升级实施计划.md`）。

## [S2] Design
P0：深链 `?doc=`、删 StreamBatcher、出题文案。  
一：`run_chunking_chain` + `POST /preview-chunking` + `ChunkPreviewDialog`。  
二：`source_content/char_*/context_header/is_parent` + 坐标不变量 + reindex 脚本。  
三：`chunk_revisions` + 乐观并发 / 父块重建 / 回滚。  
四A：进度双窗 + `duration_ms` + `window_close` 硬关闭。  
四B：citation 占位符 / 残缺标记 / stableHtml + 悬停浮层。  
五：ScopeChips / ModelChip、断线续流、会话附件、停止保半成品。  
六：filePreview（CSV/TSV/类型嗅探）。  
约束：不换组件库、不粘贴 WeKnora/、不新增依赖。

## [S3] Out of Scope
目录树、多租户 RBAC、FAQ 录入、IM/MCP、技能沙箱、Wiki、知识图谱、TDesign 迁移（计划 §9）。Excel 重表格与三态全文视图仅完成嗅探/CSV，可再迭代。

## Tasks
- [x] T1: P0 深链/StreamBatcher/出题文案 (covers: S2)
- [x] T2: 阶段一分块预览 (covers: S2)
- [x] T3: 阶段二坐标地基+重跑 (covers: S2)
- [x] T4: 阶段三切片编辑+版本 (covers: S2)
- [x] T5: 阶段四A 进度收束 (covers: S2)
- [x] T6: 阶段四B 引用浮层 (covers: S2)
- [x] T7: 阶段五输入框/续流/附件 (covers: S2)
- [x] T8: 阶段六 filePreview (covers: S2)
- [x] T9: 全量门禁与验收 (covers: S2; depends: T1-T8)
