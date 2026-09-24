---
feature: weknora-ui-upgrade
status: delivered
updated: 2026-09-24
branch: master
commits: 902997f..HEAD
---

# WeKnora 吸收 · UI/检索体验升级

## Report

**What was built** — P0 三处缺陷修复：来源卡「打开原文」与文档深链统一为 `?doc=`（兼容旧 `document_id`），DocumentView 按 id 选中文档并滚动卡片、缺失时 toast；删除未使用的 StreamBatcher 与自造逻辑的假测试（方案 B）；出题按钮改为「基于本文出题」以匹配整文档出题行为。

**Verification** — 前端 `vitest run` 325 passed（含 5 条深链/文案测试）；`vue-tsc --noEmit` PASS；`npm run build` PASS。后端 `pytest tests/` 719 passed（cov 74%）；`ruff check` PASS；`mypy app` PASS；`alembic heads` 仅 `d4e5f6a7b8c9`。

**Journey log**
- StreamBatcher 在 HEAD 已不被引用，采用计划方案 B 直接删除假测试，避免无真实调用方的微批改造。
- 深链生产方统一为 `?doc=`（ChatMessageItem / NoteViewer / TaskPanel）；兼容读 `document_id` 并有测试。
- 残留：无 document_id 时仍写 `query.filename`，DocumentView 未消费该键（既有同类缺陷，未在 P0 扩 scope）。
- 门禁失败根因是学习活动 UTC 日期与 `timezone.utc` 写法，已改为 `datetime.UTC` 并与库内朴素 UTC 对齐。

## [S1] Problem
Study Copilot 对照 WeKnora v0.8.0 的 UI/检索体验缺口：来源跳转失灵、流式微批是死代码、分块无法预览、切片无坐标/编辑/版本、引用浮层与输入框胶囊等交互待补。完整计划见根目录 `WeKnora吸收-UI升级实施计划.md`（只读参照实现在 `WeKnora/`，禁止粘贴代码）。

## [S2] Design
按计划分阶段交付。本轮实施 **P0 三处既有缺陷**：

1. **F1 来源深链参数统一**：`ChatMessageItem.openSourceDocument` 与 `DocumentView.applyDeepLinkFromRoute` 统一用 `?doc=<id>`（兼容读取 `document_id`）。进入文档页按 id 选中并定位；不存在时 toast 可见提示。
2. **F2 StreamBatcher 死代码**：采用方案 B——删除未实例化的 `StreamBatcher` 类与测试文件内自造逻辑；抖动控制由 `ChatView` 分块缓存承担（计划允许二选一，B 风险更低且满足「三者齐备或完全消失」）。
3. **出题按钮名实一致**：`generateQuiz` 仍按整文档出题，按钮文案改为「基于本文出题」。

约束：不换组件库、不动 `WeKnora/`、不新增依赖。

## [S3] Out of Scope
分块预览、坐标迁移、切片编辑版本、引用浮层、输入框胶囊、附件与断线续流（计划阶段一～六，另轮排期）。全量重新入库（需用户确认）。

## Tasks
- [x] T1: F1 统一 `?doc=` 深链并补测试 — acceptance: 带 `?doc=<id>` 挂载后选中该文档；ChatMessageItem 跳转 query 含 `doc` 而非仅 `document_id` (covers: S2)
- [x] T2: F2 删除 StreamBatcher 与假测试 — acceptance: `grep StreamBatcher frontend/src frontend/tests` 零命中 (covers: S2)
- [x] T3: 出题按钮文案与行为一致 — acceptance: 按钮显示「基于本文出题」且仍生成整文档测验 (covers: S2)
- [x] T4: 门禁 — acceptance: 后端 pytest/ruff/mypy/alembic heads + 前端 vitest/vue-tsc/build 全绿 (covers: S2; depends: T1, T2, T3)
