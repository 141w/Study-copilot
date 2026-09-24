---
feature: weknora-ui-upgrade
status: in-progress
updated: 2026-09-25
branch: master
commits: # leave empty while in progress
---

# WeKnora 吸收 · UI/检索体验升级

## Report

## [S1] Problem
Study Copilot 对照 WeKnora v0.8.0 的 UI/检索体验缺口：来源跳转失灵、流式微批是死代码、分块无法预览、切片无坐标/编辑/版本、引用浮层与输入框胶囊等交互待补。完整计划见根目录 `WeKnora吸收-UI升级实施计划.md`（只读参照实现在 `WeKnora/`，禁止粘贴代码）。

## [S2] Design
### 已交付 P0
1. 来源深链统一 `?doc=`（兼容 `document_id`）。
2. StreamBatcher 死代码删除（方案 B）。
3. 出题按钮文案对齐整文档出题。

### 已交付 阶段一 · 分块预览
- 共享 `run_chunking_chain`（`app/core/chunking_pipeline.py`）：策略链 + 校验降级 + 拒绝原因；入库与预览共用。
- `POST /api/documents/preview-chunking`：只读；`selected_strategy / chain / rejected / profile / chunks / stats`；64k→413、500 截断、5s→504；`allow_embed=False` 时 semantic 跳过并记原因。
- 前端 `ChunkPreviewDialog` + 文档页入口；展示采用层级、拒绝原因、画像指标与块卡片。

## [S3] Out of Scope
坐标迁移、切片编辑版本、引用浮层、输入框胶囊、附件与断线续流（计划阶段二～六）。全量重新入库（需用户确认）。

## Tasks
- [x] T1: F1 统一 `?doc=` 深链并补测试 — acceptance: 带 `?doc=<id>` 挂载后选中该文档 (covers: S2)
- [x] T2: F2 删除 StreamBatcher 与假测试 — acceptance: grep 零命中 (covers: S2)
- [x] T3: 出题按钮文案与行为一致 — acceptance: 「基于本文出题」 (covers: S2)
- [x] T5: 共享策略链 runner — acceptance: 入库与预览调用同一函数 (covers: S2)
- [x] T6: preview-chunking API + 7+ 测试（含无权限/截断/超时/不写库） — acceptance: 计划 §3 矩阵 (covers: S2)
- [x] T7: ChunkPreviewDialog 界面 — acceptance: 渲染 chain/rejected/画像/块 (covers: S2)
- [x] T8: 门禁 — acceptance: pytest/ruff/mypy/alembic heads + vitest/vue-tsc/build 全绿 (covers: S2; depends: T5, T6, T7)
