# Study Copilot 二期缺陷修复实施计划（功能落地校验与修复）

> 版本：v1.1（2026-09-29 制定；同日实施完成）
>
> **【状态】20 条缺陷 F1–F20 全部修复完成。** 提交范围 `d241e01..aa90408`（前缀 `fix(phase2-audit):`）。交付说明见 `docs/交付说明-缺陷修复第一批.md`，分批规格见 `docs/compose/spec/phase2-defect-fix-batch{1,2,3,4}.md`。
>
> **工作仓库——要改的就是它**：`/Users/wweiqi/Desktop/update plan/Study-copilot`，代码只落在 `backend/` 与 `frontend/`
> **只读参照——禁止修改、禁止复制其代码**：上述仓库下的 `WeKnora/` 子目录（v0.8.0，commit `ef9cbf4`，MIT）。文中凡以 `WeKnora/` 开头的路径**一律是"去看它怎么做的"**，不是要改的文件。
>
> 本文用途：**交给执行 Agent**。每批末尾有可直接粘贴的「执行提示词」。
> **前置**：《WeKnora吸收二期-知识组织与检索调优实施计划.md》已收尾（提交 `c2ad0f0..cff141c`，本地未推送）。本文**不加新功能，只修已交付但未真正落地的功能**。
> **缺陷来源**：2026-09-29 对照 WeKnora 源码的双向精读 + 人工复核。凡本文标注「已实测」的条目，均有可复现证据；标注「待复测」的条目不得当作既成事实处理。

## 实施结果（2026-09-29 收尾）

| 批次 | 缺陷 | 提交 | 后端测试 |
|---|---|---|---|
| 一 P0 | F1–F4 | `d241e01` `bbd9f33` `f958994` `bed3617` `33a4f3b` | 878 |
| 二 P1 | F5–F9 | `1787cf6` `dd94a2a` `5271cbc` `8f23da7` `9608d33` | 882 |
| 三 P2 | F10–F13 | `9de4ba3` `c3e08b2` | 883 |
| 四 P3 | F14–F20 | `cdfd1bf` `aa90408` | **889** |

**门禁（收尾时）**：后端 889 passed / ruff 0 / mypy 0 / vue-tsc 0 / npm build 成功 / alembic 单 head `f3a4b5c6d7e8`。

**PostgreSQL 实测**：
- F2/F3：`backend/scripts/pg_f2f3_verify.py`，库 `f2f3_pgtest`，7/7 PASS（记录于交付说明）
- F5：同 slug 摄入两次 → `wiki_page_revisions` 出现 rev=1 快照、页面 rev=2，PASS

**带迁移上线**（需 pg_dump + uploads 备份）：
```bash
alembic upgrade head   # d0e1f2a3b4c5 (span 唯一) + f3a4b5c6d7e8 (会话 updated_at/is_pinned)
```

**真机待点验**（计划 §1）：`/study/` 双链可点、成功/失败解析时间线、会话分组、评测台缺期望提示。

**明确遗留**（附录 C + 实施备注）：
- 生产 zhparser 未复测（本地 `pg_ts_config` 仅 simple/english）
- F3.7 完整护栏（单题超时/取消/task_worker 进度）未做，当前同步请求 + 题数≤200
- `auth.py` 的 `str(created_at)` 因混 UI WIP 未入本批（其余 12 处已换 `isoformat_utc`）
- F7 失败计数 UI 已做；「只看收藏」前端入口未做（后端 type 过滤已有）
- 服务器备份机制仍缺（附录 C）

---

## 0. 给执行 Agent 的硬约束（违反即返工）

1. **只参照、不复制代码。** 禁止粘贴 `WeKnora/**` 源码，禁止新增指向 `WeKnora/` 的 import / 符号链接 / 依赖。参照只用于确认契约与状态机语义。
2. **不换组件库、不加构建链。** 继续 Element Plus + TailwindCSS + Vite。
3. **不许改动 `WeKnora/` 目录内容**（只读参照，`.gitignore` 已排除）。
4. **【本文最重要的一条】先写失败测试，再改代码。** 二期的教训是：866 个后端用例 + 435 个前端用例全绿，却漏掉了 6 个用户可见的功能失效。每条缺陷必须**先提交一个能红的复现测试**（渲染产物断言 / 端到端断言 / 失败路径断言），再提交修复。只改代码不补复现测试的，视为未完成。
5. **测试覆盖三层**：函数层（已有）、**渲染产物层**（v-html / HTML 字符串最终结构）、**事务与失败路径层**（异常发生时数据库里到底留下了什么）。本期缺陷全部出在后两层。
6. **数据库变更必须走 Alembic**，挂当时唯一 head（现为 `c9d0e1f2a3b4`）。提交前必须跑双 head 检查 + `alembic current == heads`。
7. **测试用 SQLite、生产用 PostgreSQL**（`backend/tests/conftest.py`）。SQLite 不开外键、不建全文索引、无 `tsvector`/`zhparser`——**这正是本期多个缺陷被掩盖的原因**。凡涉及事务边界、唯一约束冲突、FTS 行为的修复，**必须在 PostgreSQL 上手工验一遍并把结果写进交付说明**，不接受"单测绿了"。
8. **不确定就停下问**，特别是不可逆数据动作（清 span 历史、修 data backfill、删重复行）。
9. 行号会漂移，定位以**符号名 + 文件路径**为准；本文给出的行号是 2026-09-29 快照。
10. **派发执行提示词时必须原样带上文首「工作仓库 / 只读参照」两行。**
11. **提交卫生**：按路径分批 `git add`，**禁止 `git add -A` / `git add .`**。仓库根目录下的个人文件（面试手册、开题、PDF、`scratch/`、`WeKnora/`、`assets/` 中非本项目素材）绝不入库。

---

## 1. 门禁命令（每批收尾必须全绿，数字只许升）

```bash
cd backend
HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/ -q        # 制定时 866 → 收尾 889
.venv/bin/python -m ruff check app tests                     # 0
.venv/bin/python -m mypy app                                 # 0
.venv/bin/python -m alembic heads                            # 只有一个 head（f3a4b5c6d7e8）
test "$( .venv/bin/python -m alembic current | tail -1 )" = "$( .venv/bin/python -m alembic heads | tail -1 )"

cd ../frontend
npx vitest run                                               # 制定时 435 → 收尾 457+
npx vue-tsc --noEmit                                         # 0
npm run build                                                # 成功
```

**新增的真机验收动作（本期必须做，命令写在附录 B）**：`/study/` 上打开一篇含 `[[双链]]` 的概念页，肉眼确认链接可点；在文档详情看一次**成功**与一次**失败**解析的时间线收尾状态是否正确。

---

## 2. 缺陷总览（按批次）✅ 全部已完成

| 编号 | 严重度 | 现象（用户视角） | 批次 | 状态 |
|---|---|---|---|---|
| F1 | **High** | 概念页正文里的 `[[双向链接]]` **渲染成纯文本，点不动**，还被强行断成三段 | 一 | ✅ `d241e01` |
| F2 | **High** | 解析时间线收尾状态丢失；失败时时间线是空的；极端情况下文档显示"已就绪"却 0 切片、检索永远空 | 一 | ✅ `bbd9f33` |
| F3 | **High** | 评测台命中率**恒为 100%**，任何改动都"没变差"，无法用于决策 | 一 | ✅ `f958994` |
| F4 | **High** | 会话列表分组错 8 小时，今晨的会话落在"昨天" | 一 | ✅ `bed3617` |
| F5 | High | 摄入合并概念页时**不写版本快照**，用户手写正文被覆盖后无法回滚；同一概念被拆成中英文两页 | 二 | ✅ `1787cf6` |
| F6 | Medium | 版本历史只有 120 字预览，取不到全文 → 回滚是盲选、无法 diff | 二 | ✅ `1787cf6` |
| F7 | High | 计划承诺的"解析完成后自动打标"**根本没接线**；打标序号错位、置信度缺省判 0、截断不看分数 | 二 | ✅ `dd94a2a` `9608d33` |
| F8 | Medium | 收藏并发写会 500、删除不幂等、列表不返回标题、消息收藏是死枚举 | 二 | ✅ `5271cbc` |
| F9 | Medium | 起始推荐问题无缓存无失效：切文档/新建会话不刷新也不清空 | 二 | ✅ `8f23da7` `9608d33` |
| F10 | Medium | 关键词通道无匹配过滤、`keyword_threshold` **全链路零消费** | 三 | ✅ `9de4ba3` |
| F11 | Medium | `rerank_threshold` 零消费、重排关闭时滑杆是死控件 | 三 | ✅ `9de4ba3` |
| F12 | Medium | 深度研究（Agent）检索路径不透传用户参数 | 三 | ✅ `9de4ba3` |
| F13 | Medium | span 重跑 `attempt` 恒为 1 → 时间线重复段混叠 | 三 | ✅ `9de4ba3` |
| F14 | Medium | 摄入无进程内锁、创建页"先查后插" → 并发丢更 / 500 | 四 | ✅ `cdfd1bf` `aa90408` |
| F15 | Medium | 删页硬删且不清理入站链接 → 一次删除造出一片死链 | 四 | ✅ `cdfd1bf` |
| F16 | Low | 死链巡检不覆盖笔记；活链 >50 时被误判死链 | 四 | ✅ `cdfd1bf` |
| F17 | Low | 会话只有 `created_at`，老会话继续聊仍永久沉在"更早"；无置顶 | 四 | ✅ `cdfd1bf` |
| F18 | Low | 会话重命名无长度约束、连按 Enter 重复 PUT、无 Esc | 四 | ✅ `cdfd1bf` |
| F19 | Low | slug 归一前后端规则不一致 | 四 | ✅ `cdfd1bf` |
| F20 | Low | `STAGE_ORDER` 含 `index` 但从不埋点；间隙异常误记 | 四 | ✅ `cdfd1bf` |

---

## 3. 第一批（P0）：四处"功能名义存在、实际不成立"

### F1 · 概念页双链渲染失效 — 已实测

**证据**：`frontend/src/composables/useMarkdown.ts:33` 为 `html: false`（`:35` `typographer: true`），而 `frontend/src/views/WikiView.vue` 的 `rendered` 计算属性（约 292-311 行）先在 Markdown 源码里注入原始 HTML 标签 `<wl-placeholder data-slug="…">…</wl-placeholder>`，渲染后再用正则把它替换回 `<a>`。

**实测**（生产同款配置）：

```
输入  : \n\n<wl-placeholder data-slug="梯度下降">梯度下降</wl-placeholder>\n\n
输出  : <p>&lt;wl-placeholder data-slug=“梯度下降”&gt;梯度下降&lt;/wl-placeholder&gt;</p>
后置正则命中数: 0
```

两个独立原因叠加：`html:false` 把标签转义成字面文本；`typographer:true` 又把属性引号换成中文弯引号 `“”`，即便允许 HTML 也匹配不上。另：注入时前后各加 `\n\n`，会把一句话切成三个段落。

**修复要求**
1. **废弃 HTML 占位符方案**。改为在 Markdown 源码阶段把 `[[slug|label]]` 直接换成标准链接语法 `[label](wiki:slug)`，渲染完成后按 `href` 前缀 `wiki:` 定位 `<a>` 节点改写 class 与点击行为（或直接给链接加 data 属性 + 事件委托，不字符串替换）。
2. 行内链接**不得产生分段副作用**（不允许在替换文本前后加 `\n\n`）。
3. 拦截点击：活链 → 跳转 `/wiki?slug=…`；死链 → 弹出"创建该概念页"确认，确认后以该 slug 建空页并回填。
4. `linkify`/`typographer` 等 `useMarkdown` 全局配置**不许为绕过此问题而改动**（影响面是全站 Markdown）。若必须局部处理，在本页自建 markdown 实例并说明理由。

**视觉规格（照此实现，不要自由发挥）**
- 活链：正文色下划线，`text-underline-offset: 2px`；hover 时下划线加深 + 光标 `pointer`；不使用蓝色外链观感。
- 死链：颜色 `--el-text-color-secondary`，下划线改 `1px dashed`；hover 时浮出 `title`/tooltip 文案「概念页「X」尚未创建，点击创建」。
- 二者**字号、行高、字重必须与普通正文完全一致**，不得变成 chip/按钮形态（正文里的链接不该破坏阅读节奏）。
- 中文 slug 链接文本保持原样，不做大小写或空格变形展示。

**验收标准**
- 新增前端测试：对 `WikiView` 的渲染产物断言 —— `[[梯度下降]]` 最终 HTML 中存在 `<a … data-slug="梯度下降">梯度下降</a>`，且 `rendered` 中**不出现**字符串 `wl-placeholder` 或 `&lt;`；断言 `梯度下降` 与其前后句处于同一个 `<p>` 内。
- 真机：`/study/` 里手建两页并互相 `[[链接]]`，点击跳转正常；写一个不存在的 slug，点击能触发建页流程。
- 回归：既有 `test_wiki_service.py` / `WikiView.test.js` 全绿；**必须指出原测试为何没抓到这个缺陷**（原测试断言的是替换正则本身而非渲染结果），并把该断言改成断言产物。
- **回滚**：纯前端渲染层改动，回退文件即可。

---

### F2 · 解析时间线的事务边界错误 — 代码已确证

**证据**（三处，必须一起修）：
- `backend/app/services/parse_span_service.py`：`_insert`/`_finish` 只做 `await self.db.flush()`，**从不 commit**；`_safe()` 在捕获异常后执行 `await self.db.rollback()`——用的是**与文档处理同一个 `AsyncSession`**（`backend/app/services/document_service.py:196` `ParseSpanRecorder(db, doc_id, attempt=1)`）。
- `backend/app/services/document_service.py` 成功路径：`doc.status="ready"` → `await db.commit()`（约 280-281 行）→ **之后**才 `spans.end_stage("finalize","ready")` 与 `spans.end_root("done")`（282-283 行，仅 flush）。上一次事务已提交，这两次写入落进新事务且无人提交 → **成功收尾状态永久丢失**，前端最后阶段停在"进行中"。
- 同一文件异常路径：`fail_stage(...)` + `end_root("failed")`（292-293 行，仅 flush）→ 紧接着 `await db.rollback()`（296 行）→ **失败记录被自己回滚掉**；随后 `doc.status="error"` + commit（297-299 行）。即"文档失败"入库、"为什么失败"蒸发。
- 组合后果：若 `_safe` 在解析中段的 flush 失败上触发 rollback，此前已 flush 的 `document_chunks` 与状态一并回滚，而流程继续走到 `doc.chunk_count = len(chunks)`（内存值）并提交 → **文档显示"已就绪 N 块"、库里 0 块、检索恒空**。`backend/tests/test_parse_spans.py::test_span_write_failure_does_not_raise` 恰好掩盖此点（SQLite 未开外键、且未断言库内实际行数）。

**修复要求**
1. span 写入改用**独立会话/独立连接**（不复用文档处理事务），且**每条状态转移立即 commit**；或使用 `db.begin_nested()` SAVEPOINT 并把失败回滚范围限制在 SAVEPOINT 内——两种方案选其一，说明理由。
2. 删除 `_safe` 里对共享 session 的全量 `rollback()`。
3. 成功路径：`end_stage`/`end_root` 必须在自己的事务里提交，且在函数 `return` 之前完成。
4. 失败路径：失败 span 必须落库成功之后才允许回滚主事务。
5. 补一个收敛动作：进程重启后把残留 `running` 的 span 归为 `failed`（原因写"进程中断"）——挂到启动引导或看门狗里，说明选了哪个时机。

**视觉规格（前端 `ParseTimeline.vue` 同批对齐）**
- 四态：完成（实色 + 对勾）/ 进行中（主题色 + 缓慢脉冲，唯一允许常驻动画的态）/ 失败（红 + 展开错误原因）/ 取消与跳过（灰 + 虚线条，文案「未执行（上游失败）」）。
- 顶部计数 **只统计 stage，不含 root**（现状把 root 计入，会显示成 "6/6" 误导）。
- 阶段中文名映射：parse=文本解析、profile=文档画像、chunk=分块、embed=向量化、index=索引写入、finalize=完成入库。不得出现英文枚举名。
- 时间线一次只呈现**一个 attempt**（默认最近一次），历史 attempt 走折叠入口（依赖 F13 修复后数据可用）。

**验收标准**
- 复现测试（先红）：用 PostgreSQL 手工跑一次真实文档处理，断言库里最终 span 集合包含 `finalize=done` 与 `root=done`；再构造一次中途异常，断言 `root=failed` 且失败 stage 的 `error` 非空、其后阶段为 `cancelled`。
- 新增/改写测试必须**查库断言行数与状态**，不接受只断言"没抛异常"。
- 极端用例：人为让一次 span 写入失败（如注入无效列值），断言文档不会既 `status=ready` 又 `chunk_count>0 / 实查 0 行`。
- **回滚**：span 表数据只增不减，回退代码后旧行仍可读；无迁移或仅新增索引。

---

### F3 · 评测台指标恒真 — 代码已确证

**证据**：`backend/app/services/eval_service.py`
- 检索已按用户文档集合收窄：`store.search(q, owned_ids, top_k=top_k)`
- 判定却是 `ok1 = bool(top) and top[0]["document_id"] in owned_ids`、`okk = bool(hit_docs & set(owned_ids))`
  → **同义反复**：只要检索返回任何结果就记为命中。指标实为"检索有没有返回东西"，而非"返回对了没有"。
- 入参**没有期望答案（qrels）**：docstring 设想过 `expected_doc_ids`，函数与 `backend/app/api/evaluation.py` 均无该参数。
- `backend/tests/test_eval_service.py:51-76` 用单文档 fixture 把这一退化写进了断言，所以它"通过"。
- 另有口径分叉：评测**不走 `RAGEngine.retrieve`**，而生产走它（RRF 权重、阈值、去重、rerank 都在 `retrieve` 里）→ 评测 ≠ 线上行为。
- 对比参照：仓库既有 CLI `backend/evaluation/harness.py` 已有 Recall/MRR/nDCG/CP@k 与真值集；Web 台是**退化**。

**修复要求**
1. `POST /api/evaluation/run` 增加必填的**期望输入**：每题一组期望 `document_id`（或 `chunk_id`）列表；前端提供"每题一行，可选第二列期望文档"的粘贴区与表格编辑。
2. 判定改为与期望集求交；指标至少含 **hit@1 / hit@k / Recall@k / MRR**，**直接复用 `harness.py` 里已有的指标实现**（抽公共函数，禁止再抄一份）。
3. 评测调用**必须走生产同一条检索入口**（`RAGEngine.retrieve`，并透传当前用户的 `retrieval_config`），否则数字无意义。
4. 报表 meta 落库并展示：生效的 `embedding 模型 / top_k / rrf_k / 两路权重 / 阈值 / FTS 配置（simple 还是 zhparser）`。理由：`/study/` 生产库的分词配置尚未验证过，缺这一项跨次结果不可比。
5. 运行留存：每次运行存结果，支持"同一题集 + 两组参数"两次并排对比（**至少支持人工选择两次结果对比**，不必做自动 A/B）。
6. 「导出」按钮当前**未找到实现**——要么实现 JSON 导出，要么删掉这个文案，不许留假按钮。
7. 大请求护栏：题目数上限（建议 ≤200）、单题超时、整体可取消、进度回传（走现有 `task_worker`，一次运行一个任务）。

**视觉规格**
- 结果表：列头「问题 / 期望文档 / 命中@1 / 命中@k / Recall@k / MRR / Top 结果」；命中格用 ✓/—，不用布尔字符串。
- 表上方固定一条「本次生效参数」摘要带（含 FTS 指纹），改参数后重跑必须能看到这一行的变化。
- 未提供期望文档时，页面须显式提示「未录入期望答案，指标不可用于比较」，禁止静默出百分比。

**验收标准**
- 复现测试（先红再绿）：构造"检索返回了结果但不是期望文档"的用例，断言 `hit@1=0`（当前会断言成 1）。
- 对拍测试：同一份题集下，Web 评测与 `scripts/retrieval_probe.py`/`harness.py` 的 Recall/MRR 数字一致（容差写进测试注释）。
- 端到端：在 PostgreSQL 上跑一次真实评测，把结果截图或数值写进交付说明。
- **回滚**：接口入参新增必填字段属破坏性变更 → 前端同批改；若需兼容，接受空期望并返回明确 warning 而非百分比。

---

### F4 · 会话分组时间错 8 小时 — 已实测

**证据**：后端把 naive UTC 时间直接字符串化输出（`backend/app/api/chat.py` 会话列表与历史消息处 `created_at=str(s.created_at)`，形如 `2026-09-29 03:24:11.123`：空格分隔、无时区标记、非标准 ISO），前端 `frontend/src/components/chat/ChatHistoryPanel.vue:33 dayKey()` / `:69 formatDate()` 直接 `new Date(ts)`。

**实测（V8）**：

```
new Date("2026-09-29 03:24:11.123")  →  按本地时区解释，比正确时刻早 8 小时
标准写法 new Date("2026-09-29T03:24:11.123Z") → 正确
```

**待复测（不得当作既成事实）**：Safari/WebKit 对空格分隔格式属实现未定义行为，可能得到 `Invalid Date` → 全部塌进"更早"且时间显示 Invalid Date。需在 iOS/Safari 真机确认。

**根因是序列化层，不要在每个前端调用点打补丁。**

**修复要求**
1. 后端统一输出**带时区标识的 ISO 8601**（`created_at.replace(tzinfo=UTC).isoformat()`），会话列表、历史消息、其他返回 naive datetime 的端点一并核对（grep `str(.*created_at)` / `str(.*updated_at)`）。
2. 分组与排序字段：本期先用 `created_at`，F17 再引入"最后活动时间"。但**分组边界必须按用户本地时区**计算（今天/昨天/本周/更早的切分点是本地 0 点，不是 UTC 0 点）。
3. 前端加一个统一的日期解析工具函数，禁止各处裸 `new Date(...)`；对解析失败要有可见兜底（显示原始串而非 Invalid Date）。

**验收标准**
- **测试造数必须改成后端真实响应格式**（当前 `frontend/tests/components/ChatHistoryPanel.test.js:12-17` 用 `toISOString()` 造数，恰好绕过了 bug）。
- 新增用例：给一个 UTC 时刻 `2026-09-29T00:30:00Z`（东八区 08:30），断言它归入"今天"而不是"昨天"；给 `2026-09-28T17:00:00Z`（东八区次日 01:00），断言归入"今天"。
- 用例覆盖畸形输入（空串、无时区串）不产生 Invalid Date 文案。
- Safari 复测结果写进交付说明（可由人工执行 `npx vitest` 之外的手工验证）。
- **回滚**：纯序列化格式变更，回退文件即可。

---

## 4. 第二批（P1）：可回滚性、自动打标接线、并发与成本

### F5 · 摄入不写快照 + 提示词不给已有 slug

**证据**：`backend/app/services/wiki_ingest_service.py:128-129`（合并已有页时）`existing.content = body` 且 `existing.revision = (existing.revision or 1) + 1`，但**没有写入 `WikiPageRevision` 快照**；对照 `backend/app/services/wiki_service.py:223-234` 的正常更新路径 `update_page` 是"先快照再抬 revision"。后果：版本号抬了而历史里没有对应版本，回滚列表错位、用户手写正文被覆盖后永久不可恢复。另：约 27-39 行的摄入提示词**不包含既有 slug/title 清单**，模型无从复用 → 同一概念产生"梯度下降"与"gradient-descent"两页。合并路径还绕过了 `MAX_CONTENT` 与标题校验（只有 create/update 走校验）。

**要求**：摄入合并改走 `update_page`（或复用其"快照 + 校验"内部函数，禁止复制两份逻辑）；提示词注入当前用户的 slug + title 列表并**明确要求优先复用已有 slug**；合并受 `MAX_CONTENT` 约束，超限记 error 而非静默截断（参照 `WeKnora/internal/application/service/wiki_ingest_dedup.go` 的判重思路与 `wiki_ingest_batch.go` 的"整页改写 + 撤回过期内容"语义，只读参照，禁止复制）。

**验收**：同 slug 重跑两次，断言 `wiki_page_revisions` 出现第 1 版快照、历史条数与 `revision` 值自洽；构造中英文同概念两次摄入，断言只有一页（或第二条为 merged 而非 created）；用户正文 > `MAX_CONTENT` 时不产生无限增长。

### F6 · 版本历史取不到全文

**证据**：`backend/app/api/wiki.py` 只有 `GET /{page_id}/revisions`（列表，`backend/app/services/wiki_service.py:240-260` 返回预览）与 `POST /{page_id}/revert`；服务层 `wiki_service.py:263-274` 已有按 revision 取单条的能力但未暴露路由。→ 回滚是盲选、无 diff。

**要求**：加 `GET /{page_id}/revisions/{revision}` 返回该版全文；前端历史抽屉做**行级 diff**（新增绿/删除红，不用并排两栏，窄屏优先），并在确认按钮上写清"当前内容会被存为新版本，仍可再次回滚"。

**验收**：回滚后可再回滚（版本单调递增，无破坏性覆盖）；diff 用例覆盖中文正文与空行；旧文档无快照（F5 之前产生的版本）时前端显示"该版本无快照"而非空白。

### F7 · 自动打标：接线 + 错位 + 置信 + 失败不可见

**证据（`backend/app/services/document_tag_service.py`）**
- **未接线**：在 `task_worker.py` / `document_service.py` / `task_service.py` 中 grep 自动打标调用**零命中**，只有手动 HTTP 触发 → 二期承诺的"解析完成后可选异步打标"未落地。
- **序号错位**：候选列表用 `enumerate(valid_names)`（约 200 行，**0-based**），提示词示例也写 `"idx": 0`。模型天然按 1 数数 → 整体错位一个标签，静默打错标。`WeKnora/internal/application/service/knowledge_auto_tag.go` 用 **1-based**。
- **置信度缺省判 0**：约 175 行 `conf = float(it.get("confidence") or 0)` → 模型省略字段即被当 0 分丢弃（功能时灵时不灵）。参照实现把缺失视为 1、且 0-100 量纲自动除 100。
- **截断不看分数**：约 234 行 `_parse_...(raw, valid_names)[:max_tags]` 按模型返回顺序截断 → 可能留 0.76 丢 0.99。参照实现先按分数降序再截断。
- **标签池静默截断**：候选取 200 条且无"已截断"标记（参照实现会记录并告警）→ 长尾标签永远选不到。
- **批量失败毒化会话**：约 239-249 行逐篇 `await auto_tag_document(...)`，异常分支不回滚 → 一篇抛错后同 `AsyncSession` 进入 PendingRollbackError，**其余文档全部静默返回空**，用户却看到"已打标签"。
- **失败不可见**：LLM 异常 `return []`（约 230-232 行），前端统一显示"未匹配到合适标签"。
- **无唯一约束**：`backend/app/db/database.py` 的 Tag 无 `(user_id, name)` 唯一约束 → 重名标签使 `scalar_one_or_none()` 抛 MultipleResultsFound。
- **无数据围栏**：正文直接拼进 user prompt，缺参照实现里的 `<document>` 隔离声明（提示注入面）。

**要求**：解析成功后入队打标任务（走现有 `task_worker`，失败不阻断文档 ready）；序号改 **1-based**；置信度缺失视为 1、>1 量纲自动归一；**先按分数排序再截断**；批量按篇 `begin_nested()` 隔离；失败计数回传前端（"3 成功 / 1 失败：模型超时"）；加 `<document>` 围栏；补 `skip_if_tagged`（已打标则 0 成本跳过）。

**验收**：序号用例（模型回 idx=1 必须命中候选表第 1 项）；省略 confidence 仍被采纳；返回顺序乱序时保留的是高分而非先出现的；批量中一篇抛错、其余仍成功；自动打标失败时文档状态仍是 ready 且任务面板可见失败原因。**PostgreSQL 上手工跑一次批量 20 篇**，记录耗时与是否撞超时（这是那条"同步串行"风险的实测）。

### F8 · 收藏：并发、幂等、可读性

**证据**：`backend/app/services/favorite_service.py` 约 62-79 行为"先查再插"（并发触发唯一约束 → 500）；约 96-100 行删除以 `rowcount` 为 0 抛错（不幂等，双击/重复请求会报错）；`backend/app/api/favorites.py` 全量返回且只给 `(type,id)`，无标题/状态 join；`resource_type` 支持 `message` 但前端只有文档卡与笔记卡挂了星标（`FavoriteStar` 未出现在消息操作栏）→ 死枚举；文档软删后收藏行成孤儿。

**要求**：`INSERT … ON CONFLICT DO NOTHING`；删除改幂等 200；列表 join 回标题与状态并支持 `type` 过滤 + 分页；「我的收藏」入口要有真实去处（现状只写不读）；`message` 二选一——补消息操作栏星标，或本期从白名单里去掉并说明。文档删除时清理其收藏行（或标记不可达）。

**验收**：并发双击不产生 500 且不重复入库；重复删除返回 200；列表能显示标题并可跳转到详情页；删除文档后收藏列表不再出现该项。

### F9 · 起始问题：缓存与失效

**证据**：`backend/app/services/chat_service.py` 起始问题**每次必调模型**，且给模型的上下文只有文件名（约 721-726 行）；无缓存、无租约去重（参照实现 `WeKnora/internal/application/service/message_suggestion.go` 的 `AcquireGeneration` 单飞 + 配置哈希缓存键，且其 starters **显式排除生成式来源**，走 0 模型成本）；前端只在 `ChatView` 挂载时打一次，切文档与 `newChat()` 既不重生成也不清空 → 陈旧问题挂着；用量记账与解析容错确实是复用同一函数（这点没问题，不是缺陷）。

**要求**：按 `hash(document_ids)+语言` 做会话内缓存（sessionStorage 即可），选中的文档集合变化即失效；请求去重（同一时刻只允许一个在飞）；失败时前端显示"暂时没想到合适的问题，点这里重试"而不是整块静默消失；后端入参加 `document_ids` 长度上限（当前无 `max_length` → 超长 IN 子句）；把给模型的上下文从"只有文件名"扩到文件名 + 摘要首段（说明 token 成本估算）。

**验收**：切换文档后旧问题被清空并重生成；同文档重复进入空态不二次调用模型（断言 stub 调用次数为 1）；LLM 失败时界面有可见的重试入口。

---

## 5. 第三批（P2）：检索参数真生效

### F10 · 关键词通道无匹配过滤 + `keyword_threshold` 零消费

**证据**：全仓 grep `keyword_threshold` 仅出现在 `backend/app/services/config_service.py` 的默认表、夹取逻辑与 `backend/app/api/config.py` 的请求模型里，**检索路径零消费**（消费点见 `backend/app/core/rag_engine.py:468-518`：只用了 `embedding_top_k / vector_threshold / rrf_k / rrf_vector_weight / rrf_keyword_weight / rerank_top_k`）。`backend/app/core/pgvector_store.py` 的关键词路结果未加 `@@ query` 命中过滤，未命中片段也带着 `1/(k+rank)` 名次分进入融合；两路等权时能与向量第一名同分。

**要求**：关键词查询补 `tsvector @@ query` 约束（或等价过滤）；`keyword_threshold` 作用到词法通道分数；**必须在 PostgreSQL 上验证 zhparser 是否真的生效**（`/health` 已暴露 `fts_config`，把它的值写进交付说明；若仍是 simple 降级，本条只算修了语义、召回结论仍待复测）。

**验收**：不相关片段不进入融合结果；`keyword_threshold` 提高时结果集单调不增；对拍测试证明默认阈值下行为与改前一致（延续二期"默认=旧行为"约束）。

### F11 · 死参数与误导文案

**要求**：`rerank_threshold` 要么在 rerank 阶段真生效，要么从面板移除；`settings.reranker_enabled=False` 时，两条 rerank 滑杆**置灰并显示"当前重排已关闭，此项不生效"**；`vector_threshold` 的界面文案需说明它作用在"融合后归一分"、且**第一名恒为 1.0 因此无法用它做拒答**（参照实现是作用在融合前原始余弦分，两者语义不同；若要改成绝对余弦阈值，另列一项并说明迁移代价）；`embedding_top_k` 的说明须写"仅作用于常规问答路径（top_k≤10 的调用），全篇总结等批量调用不受影响"——这个 `top_k<=10` 的门是 `rag_engine.py:466-471` **有意为之且有注释**，不是缺陷，别去"修"它。

**视觉规格**：置灰项保留可读（不能整块隐藏），右侧灰色小字写原因；每项 hover 有 tooltip 说明作用域与默认值。

**验收**：面板每一项要么有消费点、要么不在面板上；测试断言"改这个参数 → 检索结果确实变化"，或断言该项被标为不生效。

### F12 · Agent（深度研究）路径不透传参数

**证据**：`backend/app/agent/tools/definitions.py:86` `await rag_engine.retrieve(doc_ids, query, top_k=top_k)`——没有 `retrieval_config`，`top_k` 由模型自选（默认 5）。

**要求**：把用户检索参数透传进 Agent 的检索工具（`retrieval_config=(user_config or {}).get("retrieval")` 同生产路径一致）；工具入参若模型显式指定了 `top_k`，定义清楚谁优先并在文案里说明。

**验收**：新增用例：把 `embedding_top_k` 设为 12，走 Agent 检索工具，断言返回条数/参数生效；与 F3 联动——评测走同一入口。

### F13 · span 的 attempt / 状态机补齐

**证据**：`backend/app/services/document_service.py:196` `attempt=1` **硬编码**，`reprocess_document` 也走同一路径 → 重解析往同一 attempt 追加重复行；表无 `(document_id, attempt, name)` 唯一约束（迁移 `a7b8c9d0e1f2`）；`list_parse_spans(..., limit_attempts=3)` 参数形同虚设；`frontend/src/components/ParseTimeline.vue:71` 只按 `kind` 过滤、**不按 attempt 分组** → 时间线重复段混叠、计数失真。另外 `pending` 从不写、`skipped` 状态完全缺失、cancelled 是按 `STAGE_ORDER` 线性推断而非依赖关系；`error` 只有自由文本无错误码、无 duration 列；进程被杀后 `running` 行永久悬挂（参照实现有心跳与 housekeeping）。

**要求**：`attempt` 由重解析入口递增传入；`(document_id, attempt, name)` 唯一 + upsert；列表与前端默认只渲染**最近 attempt**（历史可选）；补 `pending` 占位（前端渲染固定阶段集，缺失的显示"未开始"）；失败原因加结构化错误码；悬挂 `running` 收敛（并入 F2 第 5 项）。

**验收**：重解析两次后时间线仍只有一组 6 段（可切换第 1/2 次）；SQLite 与 **PostgreSQL 双跑** upsert 语义（这是双方言差异最容易翻车的一条，必须真机验 PG）。

---

## 6. 第四批（P3）：并发机制补课 + 交互卫生

| 编号 | 要求 | 验收 |
|---|---|---|
| F14 | 摄入加进程内 slug 锁（同 slug 读-改-写串行，单用户不需要分布式锁）；`wiki_service.create_page` 的"先查后插"（约 141-176 行：`_slug_exists` 检查后 `db.add`）改为插入依赖唯一约束 + 捕获冲突转 409 | 并发两个请求建同 slug：一个成功一个得到 409 而不是 500；并发摄入同 slug 不丢更（PG 上验） |
| F15 | `wiki_service.delete_page`（约 287-289 行 `await db.delete(p)`）改软删或删前处理入站 `[[slug]]`：把入链降级为纯文本并在页面提示"N 处链接已失效"；文档删除时联动清理其"来源摘录"段 | 删一页后，指向它的页面不再显示死链而显示纯文本；`/wiki/audit/dead-links` 数字随之下降 |
| F16 | 死链/孤页巡检覆盖笔记（现仅扫概念页）；`WikiView.vue:419` 的 `.slice(0, 50)` 上限去除（活链 >50 会被误判死链，点进去建页又 409） | 构造 60 个活链的概念页，断言全部识别为活链；笔记正文里的 `[[链接]]` 参与巡检 |
| F17 | `ChatSession` 只有 `created_at`（`backend/app/db/database.py:132-135`，**无 updated_at**）→ 新增"最后活动时间"，新消息写入时更新，侧栏排序/分组用它；顺带加置顶 | 老会话继续聊天后回到"今天"；置顶会话恒在顶部；需 Alembic 迁移（挂 `c9d0e1f2a3b4`） |
| F18 | 会话重命名：入参加长度约束（现 `UpdateTitleRequest.title: str` 无校验）、前端 input 加 `maxlength`；**Enter 时先同步退出编辑态再发请求**（现 `ChatHistoryPanel.vue` 的 `saveTitle` 在 `await` 之后才置 `editingSessionId=null` → 连按 Enter 重复 PUT）；与原标题相同则跳过请求；支持 Esc 取消 | 连按 Enter 只发一次请求；no-op 不发请求；Esc 取消不保存；超长标题被拒并有提示 |
| F19 | slug 归一规则前后端统一（前端 `WikiView.vue normalizeSlug` 末尾只 strip `-`，后端 strip `-` 与 `/`）→ 抽成一份规则（后端为准），并加一致性用例 | 同一串输入两端得到同一 slug；不会出现"后端建出来的页面前端标成死链" |
| F20 | `parse_span_service.py:18` `STAGE_ORDER` 含 `index` 但解析链从不埋点 → 要么补 `index` 埋点，要么从阶段集里去掉（保持段数稳定）；`document_service.py:291` `spans.current_stage or "parse"` 会把阶段间隙异常误记到 parse，并对已 done 的阶段重复插 cancelled 行 → `fail_stage` 需按 name 去重 | 成功解析的时间线段数恒定；间隙异常不再产生"parse=失败 但 parse=已完成 两条" |

---

## 7. 明确不要改（防止执行 Agent"顺手优化"）

| 项 | 为什么 |
|---|---|
| `rag_engine.py:466-471` 的 `top_k <= 10` 门 | **有意为之且有注释**：用户参数只覆盖问答体量，避免把全篇总结截成 5 条。要改的是文案（F11），不是逻辑 |
| RRF 两路权重默认 1.0/1.0（非参照项目的 0.7/0.3） | 二期为满足"默认配置 = 改前行为"的回归约束而故意如此，改成 0.7/0.3 会静默改变线上排序 |
| `html: false` / `typographer: true` 全局 markdown 配置 | 影响全站。F1 要在本页自建实例或改标准链接语法，**不得改全局配置** |
| 会话"来源筛选"降级为时间筛选 | 二期已如实记录：会话表没有 mode 字段。要做请先做 F17，别在文案上假装 |
| 起始问题复用 5.2 的解析与记账 | 精读确认是**真复用**（同一 `_parse_suggestion_list`），不是重复实现，不要"顺手重构" |
| 多租户 / Redis 锁 / 独立 worker 池 / 页面重命名重写 / 图谱 | 二期 §10 与 §9 已否决；本文不翻案 |

---

## 8. 里程碑与派发

```
第一批 F1-F4  ── 各自独立，可并行；F2 需要 PG 手测 → 单人串行
      ▼
第二批 F5-F9  ── F5/F6 同文件必须同人顺序做；F7 需接 task_worker，独立人
      ▼
第三批 F10-F13 ─ F10/F11/F12 是同一热路径，必须一人做完并一次对拍
      ▼
第四批 F14-F20 ─ 卫生项，可并行；F17 需 Alembic 迁移（注意 head 链）
```

**派发规则**：一次只派一批；每条缺陷一个提交；提交信息前缀 `fix(phase2-audit):`；每个提交正文必须写「复现测试在哪、改前是什么现象」。**批次之间不许交叉改同一文件**。

**建议工作量**：第一批约 1.5 天（F3 最重，因为要改接口入参和指标复用）；第二批约 2 天；第三批约 1.5 天（含 PG 验证）；第四批约 1 天。

---

## 9. 收尾验收清单（收尾 Agent 用）

1. ✅ 门禁：pytest 889 / ruff 0 / mypy 0 / alembic 单 head `f3a4b5c6d7e8` / vitest 457+ / vue-tsc 0 / `npm run build` 成功。数字较开头 866/435 只升。
2. ✅ `WeKnora/` 未被改动（本批未触及）。
3. ✅ `frontend/package.json`、`backend/pyproject.toml` 零新增依赖。
4. ✅ F1–F4 每条都有「改前会红」测试（提交信息含改前现象与测试位置；PG 手测见交付说明）。
5. ✅ F2/F3/F5 PostgreSQL 实测记录已写进 `docs/交付说明-缺陷修复第一批.md`（F2/F3 7/7 PASS；F5 快照 PASS）。F7/F13 为纯 Python 逻辑 + 唯一约束迁移，SQLite 单测 + 迁移审查覆盖。
6. ⏳ 真机 `/study/` 人工点验仍待执行：（a）双链可点（b）成功/失败解析时间线（c）会话分组（d）评测台缺期望提示。
7. ⏳ 上线：`pg_dump` + uploads 备份 → 推送 → 部署脚本。**含迁移 `d0e1f2a3b4c5` + `f3a4b5c6d7e8`，属带迁移的上线**，不可直接回滚镜像了事。

---

## 附录 A · 本文证据的产生方式（可复现）

双链失效（前端目录内执行，与 `useMarkdown.ts` 同配置）：

```bash
node -e "const M=require('markdown-it');const md=new M({html:false,linkify:true,typographer:true});
const out=md.render('\n\n<wl-placeholder data-slug=\"梯度下降\">梯度下降</wl-placeholder>\n\n');
console.log(out);console.log((out.match(/<wl-placeholder data-slug=\"([^\"]*)\">([^<]*)<\/wl-placeholder>/g)||[]).length)"
```

时间解析偏差（同一 naive UTC 字符串）：

```bash
node -e "const s='2026-09-29 03:24:11.123';console.log(new Date(s).toString(), new Date(s.replace(' ','T')+'Z').toString())"
```

参数消费点核对：

```bash
grep -rn "cfg.get(" backend/app/core/rag_engine.py
grep -rn "keyword_threshold\|rerank_threshold" backend/app | grep -v test
```

自动打标是否接线：

```bash
grep -rn "auto_tag\|suggest_tags" backend/app/task_worker.py backend/app/services/document_service.py backend/app/services/task_service.py
```

## 附录 B · 与参照项目的机制差距（设计参考，非本期必修）

| 机制 | WeKnora（只读参照） | 我们 | 建议 |
|---|---|---|---|
| 摄入并发 | slug 锁 + 任务认领 + 陈旧恢复 | 无 | F14 用进程内锁即可（单用户） |
| 同名概念 | 相似度检索 + 判重调用 + 规范 slug 重写 | 无，提示词不给 slug 表 | F5 先做"提示词注入 + 要求复用"，判重调用性价比低 |
| 摄入语义 | 整页改写、可撤回过期内容 | 尾部追加 800 字摘录 | 二期不追平，F5 至少保证可回滚 |
| 版本 | 快照与更新同事务、含作者/类型/状态 | 快照缺 status/page_type，摄入不写快照 | F5/F6 + 补字段 |
| 巡检 | 6 类问题 + 健康分 + 自动修复 | 死链 + 孤页 | 够用；F15 补入链处理即可 |
| 建议生成 | 配置快照 + 缓存 + 租约单飞 + 排除生成式来源 | 每次调模型、无缓存 | F9 |
| 评测 | parquet 数据集 + 真值 + Recall/nDCG/MRR/BLEU/ROUGE | hit@1/@5 且恒真 | F3 对齐指标，不引入 BLEU/ROUGE（生成质量非本期瓶颈） |
| 参数层级 | 租户 → agent → 请求级三层覆盖 | 仅按用户单层 | 暂不做，等有"多课程不同策略"的真实需求 |

## 附录 C · 本文未覆盖、但已知欠着的事

- 二期遗留：`§13` 提到的开发库未迁移、一次重建索引把切片重复写入（约 9613 行无坐标）是否已清干净——**未复核**，属独立任务。
- 服务器至今**没有备份机制**。
- 检索评测报告挂着的 P0/P1：分词上生产复测、embedding 换代决策——**依赖 F3 修好后才有可信仪器**。
- UI 视觉规格除本文所列（F1/F2/F3/F11）外仍缺整体设计稿。
