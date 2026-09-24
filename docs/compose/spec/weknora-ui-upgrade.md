---
feature: weknora-ui-upgrade
status: in-progress
updated: 2026-09-24
branch: master
commits: # leave empty while in progress
---

# WeKnora 吸收 · UI/检索体验升级

## Report

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
- [ ] T1: F1 统一 `?doc=` 深链并补测试 — acceptance: 带 `?doc=<id>` 挂载后选中该文档；ChatMessageItem 跳转 query 含 `doc` 而非仅 `document_id` (covers: S2)
- [ ] T2: F2 删除 StreamBatcher 与假测试 — acceptance: `grep StreamBatcher frontend/src frontend/tests` 零命中 (covers: S2)
- [ ] T3: 出题按钮文案与行为一致 — acceptance: 按钮显示「基于本文出题」且仍生成整文档测验 (covers: S2)
- [ ] T4: 门禁 — acceptance: 后端 pytest/ruff/mypy/alembic heads + 前端 vitest/vue-tsc/build 全绿 (covers: S2; depends: T1, T2, T3)
