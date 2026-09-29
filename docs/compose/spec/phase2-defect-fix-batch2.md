---
feature: phase2-defect-fix-batch2
status: delivered
updated: 2026-09-29
branch: master
commits: 1787cf6..8f23da7
---

# 二期缺陷修复 · 第二批 F5–F9

> 需求源：`WeKnora吸收二期-缺陷修复实施计划.md` §4。硬约束同 §0（先红测试、查库断言、PG 手测、禁 `git add -A`）。
>
> **工作仓库**：`/Users/wweiqi/Desktop/update plan/Study-copilot`（`backend/` + `frontend/`）
> **只读参照**：`WeKnora/`（禁止复制代码）。

## Report

**What was built** — F5 摄入合并先写 `WikiPageRevision` 快照再抬 revision，提示词注入已有 slug/title 并要求优先复用，合并受 `MAX_CONTENT` 约束超限记 error；F6 新增 `GET /{page_id}/revisions/{revision}` 返回全文，前端历史抽屉行级 LCS diff，无快照显式报错；F7 自动打标 idx 改 1-based、confidence 缺省视为 1、按分数降序截断、`<document>` 围栏、解析完成后入队 `document_auto_tag` 任务（失败回传、不阻断 ready）、批量 `begin_nested` 隔离；F8 收藏插入幂等（撞唯一约束取既有行）、删除幂等 200、列表 join 标题 + 分页、`message` 移出白名单、文档软删清收藏；F9 起始问题 sessionStorage 缓存 + 请求去重 + 切文档失效 + 失败重试入口 + `document_ids` 上限 20 + 上下文含摘要首段。

**Verification** — 后端全量（排除 WIP）**882 passed**（较第一批 878 ↑）；前端 455 passed（+3 F9），2 个 `ModelChip.test.js` 失败属无关 UI WIP；`ruff`/`mypy`/`vue-tsc` 0。F5 PostgreSQL 快测 **PASS**（`wiki_page_revisions` 出现 rev=1 快照、页面 rev=2）。

**Journey log** — 1) 旧测试把 0-based 序号写进断言，修 1-based 时必须同步改测试（原断言是在固化 bug）。2) F5 第二轮摄入若摘录相同则不触发合并——测试须喂不同摘录才能复现「必须写快照」。3) SQLite 不开外键，F5 快照在 PG 上同样成立。4) `message` 收藏是死枚举，删白名单比补 UI 更诚实。

## [S1] Problem

1. **F5 摄入不写快照**：合并已有页时 `existing.revision += 1` 但不写 `WikiPageRevision`，用户手写正文被覆盖后无法回滚；提示词不给已有 slug/title → 中英文同概念拆成两页；合并绕过 `MAX_CONTENT`。
2. **F6 版本历史取不到全文**：只有列表接口（120 字预览），无 `GET /{page_id}/revisions/{revision}` → 回滚是盲选、无 diff。
3. **F7 自动打标未接线 + 静默错位**：解析完成后不入队打标；候选 0-based 而模型按 1 数 → 整体错位；`confidence` 缺省判 0 被丢弃；截断不看分数；批量失败毒化会话；LLM 异常 `return []` 前端看不出失败。
4. **F8 收藏**：先查后插并发 500、删除不幂等、列表无标题、`message` 是死枚举。
5. **F9 起始问题无缓存**：每次必调模型，切文档不刷新也不清空，刷新页面重烧。

## [S2] Design

### F5 摄入快照 + slug 复用
- 合并路径先写被取代版本快照，再改内容、抬 revision。
- 提示词注入当前用户 `slug + title` 清单，明确要求优先复用已有 slug。
- 合并受 `MAX_CONTENT` 约束，超限记 error 不静默截断。

### F6 版本全文 + diff
- `GET /{page_id}/revisions/{revision}` 返回该版全文。
- 前端历史抽屉行级 LCS diff（新增绿/删除红）。
- 无快照显示「该版本无快照」。

### F7 自动打标接线
- 解析成功后入队 `document_auto_tag`（失败不阻断 ready，结果回传）。
- 序号 **1-based**；confidence 缺省视为 1、>1 自动归一；先按分数降序再截断。
- 批量 `begin_nested()` 隔离；`skip_if_tagged`；`<document>` 围栏。

### F8 收藏
- 插入撞唯一约束回滚后取既有行（幂等）；删除幂等 200。
- 列表 join 标题 + `type` 过滤 + 分页。
- `message` 移出白名单；文档软删清理收藏行。

### F9 起始问题
- `hash(document_ids)` sessionStorage 缓存；文档集合变化即失效。
- 请求去重；失败显示重试入口。
- `document_ids` 长度 ≤20；上下文扩到文件名 + 摘要首段。

## [S3] Out of Scope
- 第三/四批（F10–F20）
- 摄入语义追平（整页改写、可撤回过期内容）
- 消息操作栏星标（选了删枚举而非补 UI）
- 自动 A/B 对比

## Tasks
- [x] T1: Spec — acceptance: 覆盖 F5–F9 设计与验收 (covers: S1, S2)
- [x] T2: F5 先红测试 — acceptance: 同 slug 重跑两次 `wiki_page_revisions` 有第 1 版快照；改前失败 (covers: S2 F5; depends: T1)
- [x] T3: F5 修复 — acceptance: 合并写快照+校验；提示词注入 slug 表；MAX_CONTENT 超限记 error (covers: S2 F5; depends: T2)
- [x] T4: F6 先红测试 + 实现 — acceptance: GET revisions/{rev} 返回全文；回滚可再回滚；无快照显示明确文案 (covers: S2 F6; depends: T3)
- [x] T5: F7 先红测试 — acceptance: idx=1 命中候选第 1 项；省略 confidence 仍采纳；乱序保留高分；改前失败 (covers: S2 F7; depends: T1)
- [x] T6: F7 接线 + 打标修复 — acceptance: 解析后入队；1-based；批量隔离；失败回传 (covers: S2 F7; depends: T5)
- [x] T7: F8 收藏 — acceptance: 并发不 500；删除幂等；列表有标题；删文档收藏消失 (covers: S2 F8; depends: T1)
- [x] T8: F9 起始问题缓存 — acceptance: 切文档重生成；同文档不二调；失败有重试 (covers: S2 F9; depends: T1)
- [x] T9: 门禁 + 交付说明 — acceptance: 后端 882 passed（数字↑）；F5 PG 手测 PASS (covers: S2; depends: T3, T4, T6, T7, T8)

# 二期缺陷修复 · 第二批 F5–F9

> 需求源：`WeKnora吸收二期-缺陷修复实施计划.md` §4。硬约束同 §0（先红测试、查库断言、PG 手测、禁 `git add -A`）。
>
> **工作仓库**：`/Users/wweiqi/Desktop/update plan/Study-copilot`（`backend/` + `frontend/`）
> **只读参照**：`WeKnora/`（禁止复制代码）。

