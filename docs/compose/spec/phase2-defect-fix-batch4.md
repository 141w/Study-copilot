---
feature: phase2-defect-fix-batch4
status: delivered
updated: 2026-09-29
branch: master
commits: cdfd1bf..cdfd1bf
---

# 二期缺陷修复 · 第四批 F14–F20

## Report

**What was built** — F14 `create_page` 冲突 ConflictError(409)、摄入同 slug 进程内锁；F15 删除软删 + 入站 `[[slug]]` 降级纯文本；F16 巡检覆盖笔记、去掉链接 50 条截断；F17 `ChatSession.updated_at`/`is_pinned`（迁移 `f3a4b5c6d7e8`）+ 置顶排序 + 消息 touch；F18 重命名 ≤80 字、先退出编辑、no-op 不发、Esc；F19 前后端 `normalize_slug` 对齐；F20 去掉未埋点 `index`、`fail_stage` 按 name 去重。

**Verification** — 后端全量 **889 passed**（↑）；wiki/parse/chat 相关 57+ 全绿；ruff/mypy/vue-tsc 0；alembic 单 head `f3a4b5c6d7e8`。

**Journey log** — 1) 软删后 `_get_owned` 必须识别 `__deleted__` 前缀，否则 404 语义丢失。2) 迁移 ID 撞车（`e1f2a3b4c5d6` 已存在）——新迁移先 `alembic heads` 查重。3) F14 一半由并行 OCR 改动覆盖，本批补齐锁与冲突语义。

## Tasks
- [x] F14–F20 全部落地（详见 Report）
- [x] 门禁：889 passed / ruff / mypy / vue-tsc / alembic 单 head
