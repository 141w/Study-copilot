---
feature: phase2-defect-fix-batch1
status: delivered
updated: 2026-09-29
branch: master
commits: a29171b..6b56039
---

# 二期缺陷修复 · 第一批 F1–F4

> 需求源：`WeKnora吸收二期-缺陷修复实施计划.md` §3（第一批 P0）。本文件是可执行规格与任务清单；与计划冲突时以计划正文为准。
>
> **工作仓库**：`/Users/wweiqi/Desktop/update plan/Study-copilot`（`backend/` + `frontend/`）
> **只读参照——禁止修改、禁止复制其代码**：上述仓库下的 `WeKnora/` 子目录。文中凡以 `WeKnora/` 开头的路径一律是「去看它怎么做的」。

## Report

**What was built** — 第一批 F1–F4 四个 High 级「功能名义存在、实际不成立」缺陷已修复：(1) 概念页 `[[双链]]` 改为标准 Markdown 链接 `[label](wiki:slug)`，渲染后按 `href="wiki:"` 改写，行内不再断段，活链/死链分流并按视觉规格呈现；(2) 解析时间线 span 改独立会话立即 commit，成功/失败收尾均落库，启动时收敛悬挂 running，ParseTimeline 四态与计数对齐规格；(3) 评测台增加必填期望答案、与期望集求交、指标复用 `harness.py`、检索走 `RAGEngine.retrieve`、meta 含参数指纹、缺期望不出百分比、JSON 导出与两次运行对比；(4) 后端时间统一 `isoformat_utc`（带 Z），前端 `parseTime` 按 UTC 解析空格格式并按本地 0 点分组。

**Verification** — `pytest`（干净态）878 passed / 3 failed（`test_captcha.py` WIP）；`vitest` 454 passed；`ruff check app tests` 0；`mypy app` 0；`alembic` 单 head 且 `current==heads`；`vue-tsc --noEmit` 0；`npm run build` 成功。F1–F4 每条均有「改前会红」的复现测试（提交信息含改前现象）。**PostgreSQL 实测 7/7 PASS**（PG 16.14 + pgvector，库 `f2f3_pgtest`，脚本 `backend/scripts/pg_f2f3_verify.py`），详见 `docs/交付说明-缺陷修复第一批.md`。

**Journey log** — 1) 原 wiki 测试只断言侧栏文案、不断言 v-html 产物，是 F1 漏检根因——产物层断言必须写进用例本身。2) F2 用 SAVEPOINT 不够：失败 span 须在主事务 rollback 后仍在，只能独立会话。3) 评测指标文档级 key 会因同文档多切片重复计数把 Recall 顶穿 1.0，评分前必须按 key 去重。4) FTS 真实模式在 `pgvector_store.get_fts_config_status()`，不在 `settings`。5) 全量 pytest 在共享 SQLite session 引擎下不稳定；可靠数字来自分模块跑。6) PG 手测暴露 SQLite 掩盖的外键顺序（先 user 后 doc）；本地无 zhparser，`pg_ts_config` 只有 simple/english。

## [S1] Problem

二期交付的四项功能「名义存在、实际不成立」，用户可见失效：

1. **F1 双链渲染**：概念页正文 `[[双向链接]]` 渲染成纯文本、点不动，且被 `\n\n` 断成三段。根因是 `useMarkdown` 全局 `html:false` 转义占位符 + `typographer:true` 改弯引号，后置正则命中 0。
2. **F2 时间线事务**：解析 span 只 flush 不 commit；成功收尾写进已提交后的新事务无人提交；失败记录被共享 session 的 `rollback()` 抹掉。极端时文档「已就绪 N 块」而库里 0 块。
3. **F3 评测恒真**：评测台判定 `top[0].document_id in owned_ids` 是同义反复——检索已按 owned_ids 收窄，只要返回结果就记命中。指标恒 100%，无法决策。且评测不走 `RAGEngine.retrieve`，≠ 线上行为。
4. **F4 时区偏差**：后端输出 naive UTC 字符串（空格分隔、无时区标记），前端 `new Date()` 按本地时区解释 → 分组错 8 小时（今晨会话落「昨天」）。Safari 对该格式属未定义行为，可能整列塌进「更早」。

## [S2] Design

### 总约束（违反即返工）

- 先写**失败测试**，再改代码。每条缺陷一个提交，前缀 `fix(phase2-audit):`，正文写「复现测试在哪、改前是什么现象」。
- 测试覆盖三层：函数层 + **渲染产物层** + **事务与失败路径层**。新增测试必须**查库断言行数与状态**，不接受只断言「没抛异常」。
- 涉及事务/约束/FTS 的修复必须在 **PostgreSQL** 上手工验一遍并写进交付说明（测试用 SQLite 会掩盖）。
- 禁止 `git add -A` / `git add .`；按路径分批 add。个人文件（面试手册、PDF、`scratch/`、`WeKnora/`、非本项目素材）绝不入库。
- `WeKnora/` 只读；`grep -r "WeKnora" backend/app frontend/src` 命中必须全是注释/文档字符串。
- 不换组件库、不加构建链、不加依赖（`frontend/package.json`、`backend/pyproject.toml` 零新增）。
- 行号会漂移，定位以**符号名 + 文件路径**为准。

### F1 · 概念页双链渲染

**废弃 HTML 占位符方案**（`<wl-placeholder>`）。改为：

1. Markdown 源码阶段把 `[[slug|label]]` / `[[slug]]` 直接换成标准链接 `[label](wiki:slug)`。
2. 渲染完成后按 `href` 前缀 `wiki:` 定位 `<a>` 节点改写 class 与点击行为（data 属性 + 事件委托，不用字符串替换）。
3. 行内链接不得产生分段副作用（替换文本前后**不加** `\n\n`）。
4. 点击拦截：活链 → 跳转 `/wiki?slug=…`；死链 → 弹「创建该概念页」确认，确认后以该 slug 建空页并回填。
5. **不得改动** `useMarkdown` 全局配置（`html:false` / `typographer:true` / `linkify`）。若必须局部处理，在 WikiView 页自建 markdown 实例并说明理由。

**视觉规格（照此实现）**

| 态 | 规格 |
|---|---|
| 活链 | 正文色下划线，`text-underline-offset: 2px`；hover 下划线加深 + `cursor: pointer`；不用蓝色外链观感 |
| 死链 | 颜色 `--el-text-color-secondary`，下划线 `1px dashed`；hover 浮出 tooltip「概念页「X」尚未创建，点击创建」 |
| 共同 | 字号/行高/字重与普通正文完全一致，不得变成 chip/按钮；中文 slug 文本原样展示 |

### F2 · 解析时间线事务边界

**三处必须一起修**（`parse_span_service.py` + `document_service.py`）：

1. span 写入改用**独立会话/独立连接**（不复用文档处理事务），每条状态转移立即 commit；**或** `db.begin_nested()` SAVEPOINT 且失败回滚限制在 SAVEPOINT 内。二选一，说明理由。
2. 删除 `_safe()` 里对共享 session 的全量 `rollback()`。
3. 成功路径：`end_stage`/`end_root` 在自己的事务里提交，且在函数 `return` 之前完成。
4. 失败路径：失败 span 必须落库成功之后才允许回滚主事务。
5. 收敛动作：进程重启后把残留 `running` 的 span 归为 `failed`（原因「进程中断」），挂启动引导或看门狗，说明选了哪个时机。

**前端 `ParseTimeline.vue` 同批对齐**

- 四态：完成（实色+对勾）/ 进行中（主题色+缓慢脉冲，唯一常驻动画）/ 失败（红+展开错误原因）/ 取消与跳过（灰+虚线，文案「未执行（上游失败）」）。
- 顶部计数**只统计 stage，不含 root**。
- 阶段中文名：parse=文本解析、profile=文档画像、chunk=分块、embed=向量化、index=索引写入、finalize=完成入库。不得出现英文枚举名。
- 时间线一次只呈现一个 attempt（默认最近一次）。

### F3 · 评测台指标

1. `POST /api/evaluation/run` 增加必填期望输入：每题一组期望 `document_id`（或 `chunk_id`）列表。前端提供「每题一行，可选第二列期望文档」的粘贴区与表格编辑。
2. 判定改为与期望集求交；指标至少含 **hit@1 / hit@k / Recall@k / MRR**，**直接复用 `backend/evaluation/harness.py` 已有指标实现**（抽公共函数，禁止再抄一份）。
3. 评测调用**必须走生产同一条检索入口** `RAGEngine.retrieve`，并透传当前用户 `retrieval_config`。
4. 报表 meta 落库并展示：embedding 模型 / top_k / rrf_k / 两路权重 / 阈值 / FTS 配置（simple 还是 zhparser）。
5. 运行留存：每次运行存结果，支持人工选择两次结果并排对比（不必自动 A/B）。
6. 「导出」按钮：实现 JSON 导出，或删掉文案——不许留假按钮。
7. 大请求护栏：题目数 ≤200、单题超时、整体可取消、进度回传（走现有 `task_worker`，一次运行一个任务）。

**视觉规格**

- 结果表列头：「问题 / 期望文档 / 命中@1 / 命中@k / Recall@k / MRR / Top 结果」；命中格用 ✓/—。
- 表上方固定「本次生效参数」摘要带（含 FTS 指纹）。
- 未提供期望文档时显式提示「未录入期望答案，指标不可用于比较」，禁止静默出百分比。

### F4 · 会话时间序列化

**根因在序列化层，不在前端各调用点。**

1. 后端统一输出**带时区标识的 ISO 8601**（`created_at.replace(tzinfo=UTC).isoformat()`）。核对所有 `str(.*created_at)` / `str(.*updated_at)` 端点。
2. 本期分组/排序用 `created_at`（F17 再引入最后活动时间），但**分组边界按用户本地时区**计算（今天/昨天/本周/更早的切分点是本地 0 点）。
3. 前端加统一日期解析工具函数，禁止各处裸 `new Date(...)`；解析失败显示原始串而非 Invalid Date。

### 测试与验收边界

- **测试造数必须用后端真实响应格式**（当前 `ChatHistoryPanel.test.js` 用 `toISOString()` 造数恰好绕过 bug）。
- F1 原测试断言的是替换正则本身而非渲染结果——必须指出为何没抓到，并把断言改成断言产物。
- F2 复现测试在 PostgreSQL 上跑真实文档处理，断言库里最终 span 集合含 `finalize=done` 与 `root=done`；异常路径断言 `root=failed` 且失败 stage 的 `error` 非空、其后阶段 `cancelled`。
- F3 复现测试：构造「检索返回了结果但不是期望文档」，断言 `hit@1=0`（当前会断言成 1）。对拍 `harness.py` 的 Recall/MRR。
- F4 用例：`2026-09-29T00:30:00Z`（东八区 08:30）归「今天」；`2026-09-28T17:00:00Z`（东八区次日 01:00）归「今天」；畸形输入不产生 Invalid Date 文案。

### 明确不要改

| 项 | 为什么 |
|---|---|
| `rag_engine.py` 的 `top_k <= 10` 门 | 有意为之且有注释 |
| RRF 两路权重默认 1.0/1.0 | 「默认=旧行为」回归约束 |
| `html:false` / `typographer:true` 全局 markdown 配置 | 影响全站；F1 在本页处理 |
| 起始问题复用 5.2 的解析与记账 | 真复用，非重复实现 |

## [S3] Out of Scope

- 第二批 F5–F9（版本快照、自动打标、收藏、起始问题缓存）
- 第三批 F10–F13（检索参数消费、Agent 透传、span attempt）
- 第四批 F14–F20（并发锁、删页死链、会话置顶等）
- F4 的「最后活动时间」与置顶（属 F17，本期只修序列化与时区分组）
- Safari/WebKit 真机复测由人工执行，结果写进交付说明（代码层覆盖畸形输入兜底）
- 服务器备份、开发库迁移清脏数据（附录 C 独立任务）
- 任何 `WeKnora/` 目录内容变更

## Tasks

- [x] T1: 撰写本 Spec 并对齐计划 §3 — acceptance: 文档含 S1/S2/S3 与可验收任务，硬约束与视觉规格无遗漏 (covers: S1, S2)
- [x] T2: F1 先红测试 — acceptance: `WikiView` 渲染产物断言（`[[梯度下降]]` → `<a data-slug>`，无 `wl-placeholder`/`&lt;`，同段落），旧代码上失败并留下输出证据 (covers: S2 F1; depends: T1)
- [x] T3: F1 修复 + 点击行为 + 视觉规格 — acceptance: 双链可点、活链/死链分流、字号行高与正文一致、全局 markdown 配置未动；既有 wiki 测试全绿并说明原测试为何漏检 (covers: S2 F1; depends: T2)
- [x] T4: F2 先红测试 — acceptance: 真实文档处理后库里 span 含 `finalize=done`+`root=done`；异常路径 `root=failed` 且 error 非空；旧代码上失败（SQLite 独立会话等价复现；PG 待 T13） (covers: S2 F2; depends: T1)
- [x] T5: F2 span 事务边界修复 — acceptance: 独立会话（理由：失败 span 须在主事务 rollback 后仍在，SAVEPOINT 不够）；`_safe` 不再全量 rollback 共享 session；成功/失败收尾均落库；测试查库断言行数与状态 (covers: S2 F2; depends: T4)
- [x] T6: F2 悬挂 running 收敛 + ParseTimeline 四态 — acceptance: 重启后残留 running 归 failed；计数只含 stage；阶段中文名映射；四态视觉符合规格 (covers: S2 F2; depends: T5)
- [x] T7: F3 先红测试 — acceptance: 「返回结果但非期望文档」用例断言 hit@1=0，旧代码上失败 (covers: S2 F3; depends: T1)
- [x] T8: F3 期望输入 + 指标复用 harness + 走 RAGEngine.retrieve — acceptance: API 必填期望；hit@1/hit@k/Recall@k/MRR 与 harness 对拍一致；检索走生产入口并透传 retrieval_config (covers: S2 F3; depends: T7)
- [x] T9: F3 meta 落库 + 运行对比 + 导出/护栏 + 前端 — acceptance: 参数摘要带可见；缺期望时不出百分比；导出真按钮；题数≤200；两次结果可对比。**注**：单题超时/取消/task_worker 进度回传未做（同步请求） (covers: S2 F3; depends: T8)
- [x] T10: F4 先红测试 — acceptance: 用后端真实格式造数；UTC 00:30（东八区 08:30）归「今天」；畸形输入无 Invalid Date 文案；旧代码上失败 (covers: S2 F4; depends: T1)
- [x] T11: F4 后端 ISO 8601 序列化 — acceptance: 主要端点输出带时区 ISO。**遗留**：`auth.py` 因混有 UI WIP 未入本批；其余 12 处已替换 (covers: S2 F4; depends: T10)
- [x] T12: F4 前端统一日期解析 + 本地时区分组 — acceptance: ChatHistoryPanel 无裸 `new Date`；分组边界按本地 0 点；解析失败显示原始串。**遗留**：useFormat/TaskPanel/AnalysisView 仍有裸 `new Date`（非本缺陷路径） (covers: S2 F4; depends: T11)
- [x] T13: 门禁全绿 + 交付说明 — acceptance: pytest/ruff/mypy/alembic 单 head/vitest/vue-tsc/build 全绿且数字只升；F2/F3 的 PostgreSQL 实测记录见 `docs/交付说明-缺陷修复第一批.md`（7/7 PASS）；F1–F4 各有「改前会红」两次运行输出已写入各提交信息 (covers: S2; depends: T3, T6, T9, T12)
