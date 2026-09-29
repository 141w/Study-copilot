---
feature: phase2-defect-fix-batch2
status: in-progress
updated: 2026-09-29
branch: master
commits: # fill at delivery
---

# 二期缺陷修复 · 第二批 F5–F9

> 需求源：`WeKnora吸收二期-缺陷修复实施计划.md` §4。硬约束同 §0（先红测试、查库断言、PG 手测、禁 `git add -A`）。
>
> **工作仓库**：`/Users/wweiqi/Desktop/update plan/Study-copilot`（`backend/` + `frontend/`）
> **只读参照**：`WeKnora/`（禁止复制代码）。

## Report

## [S1] Problem

1. **F5 摄入不写快照**：合并已有页时 `existing.revision += 1` 但不写 `WikiPageRevision`，用户手写正文被覆盖后无法回滚；提示词不给已有 slug/title → 中英文同概念拆成两页；合并绕过 `MAX_CONTENT`。
2. **F6 版本历史取不到全文**：只有列表接口（120 字预览），无 `GET /{page_id}/revisions/{revision}` → 回滚是盲选、无 diff。
3. **F7 自动打标未接线 + 静默错位**：解析完成后不入队打标；候选 0-based 而模型按 1 数 → 整体错位；`confidence` 缺省判 0 被丢弃；截断不看分数；批量失败毒化会话；LLM 异常 `return []` 前端看不出失败。
4. **F8 收藏**：先查后插并发 500、删除不幂等、列表无标题、`message` 是死枚举。
5. **F9 起始问题无缓存**：每次必调模型，切文档不刷新也不清空，刷新页面重烧。

## [S2] Design

### F5 摄入快照 + slug 复用
- 合并路径改走 `update_page` 或复用其「快照 + 校验」内部逻辑（禁止复制两份）。
- 提示词注入当前用户 `slug + title` 清单，明确要求优先复用已有 slug。
- 合并受 `MAX_CONTENT` 约束，超限记 error 不静默截断。
- 参照 `WeKnora/internal/application/service/wiki_ingest_dedup.go` 判重思路（只读）。

### F6 版本全文 + diff
- 加 `GET /{page_id}/revisions/{revision}` 返回该版全文。
- 前端历史抽屉行级 diff（新增绿/删除红，窄屏优先）。
- 确认按钮写清「当前内容会被存为新版本，仍可再次回滚」。
- 旧文档无快照时显示「该版本无快照」。

### F7 自动打标接线
- 解析成功后入队打标任务（`task_worker`，失败不阻断 ready）。
- 序号 **1-based**；confidence 缺省视为 1、>1 自动归一；先按分数降序再截断。
- 批量按篇 `begin_nested()` 隔离；失败计数回传「3 成功 / 1 失败」。
- `<document>` 围栏；`skip_if_tagged`。

### F8 收藏
- `INSERT … ON CONFLICT DO NOTHING`；删除幂等 200。
- 列表 join 标题/状态 + `type` 过滤 + 分页。
- `message` 二选一：补消息星标或从白名单去掉（本期去掉并说明）。
- 文档删除时清理收藏行。

### F9 起始问题
- `hash(document_ids)+语言` 会话内缓存（sessionStorage）；文档集合变化即失效。
- 请求去重（同一时刻只允许一个在飞）；失败显示重试入口。
- `document_ids` 加长度上限；上下文扩到文件名 + 摘要首段。

## [S3] Out of Scope
- 第三/四批（F10–F20）
- 摄入语义追平（整页改写、可撤回过期内容）
- 自动 A/B 对比、BLEU/ROUGE
- 多租户 / Redis 锁

## Tasks
- [ ] T1: Spec — acceptance: 覆盖 F5–F9 设计与验收 (covers: S1, S2)
- [ ] T2: F5 先红测试 — acceptance: 同 slug 重跑两次 `wiki_page_revisions` 有第 1 版快照；改前失败 (covers: S2 F5; depends: T1)
- [ ] T3: F5 修复 — acceptance: 合并走快照+校验；提示词注入 slug 表；MAX_CONTENT 超限记 error (covers: S2 F5; depends: T2)
- [ ] T4: F6 先红测试 + 实现 — acceptance: GET revisions/{rev} 返回全文；回滚可再回滚；无快照显示明确文案 (covers: S2 F6; depends: T3)
- [ ] T5: F7 先红测试 — acceptance: idx=1 命中候选第 1 项；省略 confidence 仍采纳；乱序保留高分；改前失败 (covers: S2 F7; depends: T1)
- [ ] T6: F7 接线 + 打标修复 — acceptance: 解析后入队；1-based；批量隔离；失败回传 (covers: S2 F7; depends: T5)
- [ ] T7: F8 收藏 — acceptance: 并发不 500；删除幂等；列表有标题可跳转；删文档收藏消失 (covers: S2 F8; depends: T1)
- [ ] T8: F9 起始问题缓存 — acceptance: 切文档重生成；同文档不二调；失败有重试 (covers: S2 F9; depends: T1)
- [ ] T9: 门禁 + 交付说明 — acceptance: 全绿数字只升；F5/F7 PG 手测记录 (covers: S2; depends: T3, T4, T6, T7, T8)
