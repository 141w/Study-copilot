# Study Copilot 第二期吸收计划（知识组织与检索调优，交互参照 WeKnora v0.8.0）

> 版本：v1.2（2026-09-28 制定 / 同日实施收尾 / **09-29 OCR 评审加固**）
>
> **工作仓库——要改的就是它**：`/Users/wweiqi/Desktop/update plan/Study-copilot`，代码只落在 `backend/` 与 `frontend/`
> **只读参照——禁止修改、禁止复制其代码**：上述仓库下的 `WeKnora/` 子目录（v0.8.0，commit `ef9cbf4`，MIT）。文中凡以 `WeKnora/` 开头的路径**一律是"去看它怎么做的"**，不是要改的文件。
>
> 本文用途：**交给执行 Agent**。每阶段末尾有可直接粘贴的「执行提示词」。
> **前置**：第一期《WeKnora吸收-UI升级实施计划.md》（v1.3）已收尾，提交 `d411263..71a06d3`。本文是第二期，**不重做第一期范围**。
>
> **验收结论（2026-09-28 实施完成）**：P0 + 阶段一～五（含 Wiki 5.1–5.5）全部交付，共 9 个提交 `c2ad0f0..f285936`。阶段六知识图谱按计划**保持可选、未启动**。门禁收尾（09-29）：后端 **882 passed** / cov 75.5% / ruff 0 / mypy 0；前端 **436 passed** / vue-tsc 0。§15 另记 OCR 四轮评审修复与测试加固。详见 §14–§15。

---

## 0. 给执行 Agent 的硬约束（与第一期相同，违反即返工）

1. **只参照、不复制代码。** 禁止粘贴 `WeKnora/frontend/**` 或 `WeKnora/internal/**` 的源码，禁止新增指向 `WeKnora/` 的 import / 符号链接 / 依赖。
2. **不换组件库、不加构建链。** 继续 Element Plus + TailwindCSS + Vite。TDesign 组件名一律换等价物。
3. **不许改动 `WeKnora/` 目录内容**（只读参照，`.gitignore:116` 已排除）。
4. **每阶段完成 = 代码 + 测试 + 门禁全绿**，命令见 §1.3。不接受"实现完成但测试待补"。
5. **数据库变更必须走 Alembic**，挂当时唯一 head（现为 `c8d9e0f1a2b3`）。**提交前必须跑双 head 检查 + `alembic current == heads`**。
6. **测试用 SQLite、生产用 PostgreSQL**（`tests/conftest.py`）。迁移只用双方言成立的类型；PG 专有表达式不得进 SQLite 覆盖路径。
7. **不确定就停下问**，特别是不可逆数据动作。
8. 行号会漂移，定位以**符号名 + 文件路径**为准。
9. **派发执行提示词时必须原样带上文首「工作仓库 / 只读参照」两行。**

---

## 1. 共享上下文

### 1.1 我们的现状（第一期后）

| 领域 | 现状 |
|---|---|
| 对话 | Agentic RAG + 流式 + 进度双窗 + 引用浮层 + `chunk_id` 透传 + **5.2 追问建议** + 模型胶囊 + 附件 + 断线续流 |
| 文档 | 分块预览、坐标原点区间、切片编辑/版本/回滚、CSV/filePreview |
| 笔记 | 手动/AI 笔记 + 标签 + 语义搜索 |
| 检索 | pgvector 混合（向量+FTS+RRF）、父子块、CrossEncoder 重排；**参数硬编码** |
| 评测 | `backend/evaluation/` CLI harness + `retrieval_probe.py`；**无 UI** |
| 任务 | `TaskPanel` 全屏控制台；**无解析阶段时间线** |
| 记忆 | 五分类长期记忆（WeKnora M3） |
| 缺 | 收藏、文档自动打标、知识 Wiki、图谱、检索调参 UI、起始问题推荐 |

### 1.2 参照文件（只读，禁止修改、禁止复制代码）

| 能力 | WeKnora 路径 | 规模 |
|---|---|---|
| **推荐起始问题 / 答后追问配置** | `internal/types/custom_agent.go`（`QuestionSuggestionConfig` 299-360）、`internal/application/service/message_suggestion.go`(962)、`internal/handler/message_suggestion.go`(155) | 中 |
| **检索参数配置** | `internal/types/retrieval_config.go`、`frontend/src/views/settings/RetrievalSettings.vue`(287) | 小 |
| **文档自动打标签** | `internal/application/service/knowledge_auto_tag.go`(372)、`frontend/.../BatchTagDialog.vue` | 中 |
| **解析进度时间线** | `internal/types/knowledge_span.go`、`internal/application/service/extract.go`、前端 timeline 组件 | 中-大 |
| **端到端评测** | `internal/handler/evaluation.go`(131)、`internal/application/service/evaluation.go`(476)、`internal/types/evaluation.go` | 中 |
| **知识 Wiki** | `internal/application/service/wiki_ingest*.go`(~13k)、`wiki_page.go`、`frontend/.../wiki/WikiBrowser.vue`(6592) | **极大** |
| **知识图谱** | `internal/application/service/graph.go`、`extract_graph.go`、`internal/types/graph.go`、`extract_graph.go` | **大** |
| **收藏** | `internal/application/service/user_resource_favorite.go`(64)、`internal/types/user_resource_favorite.go` | 小 |
| **会话侧栏** | `frontend/src/components/SessionSidebarRow.vue`、`SessionGroupByDropdown.vue`、`SessionSourceFilter.vue` | 小-中 |
| **批量操作** | `frontend/.../DocumentBatchBar.vue`、`BatchTagDialog.vue` | 小-中 |
| **Prompt 模板选择** | `frontend/src/components/PromptTemplateSelector.vue` | 小 |

### 1.3 门禁命令（每阶段收尾必须全绿）

```bash
cd backend
HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/ -q   # 只许增加不许失败（现 816）
.venv/bin/python -m ruff check app tests                 # 0 error
.venv/bin/python -m mypy app                             # 0 error
.venv/bin/python -m alembic heads                        # 必须只输出一个 head
test "$( .venv/bin/python -m alembic current | tail -1 )" = "$( .venv/bin/python -m alembic heads | tail -1 )"

cd frontend
npx vitest run                                           # 现 410，只许增加
npx vue-tsc --noEmit
npm run build
```

---

## 2. 能力盘点与难度评估（先读表再排期）

按「对学习产品的价值 × 实现成本」排序。难度 S/M/L/XL 为综合估计（含测试）。

| # | 能力 | 对学习产品的价值 | 难度 | 依赖 | 状态 |
|---|---|---|---|---|---|
| A | **推荐起始问题**（空态/新会话引导） | 冷启动即用，用户第一眼 | **S** | 无（复用 5.2 的 LLM 通道） | ✅ `c2ad0f0` |
| B | **收藏 / 书签**（文档、笔记、消息） | 学习资料回看 | **S** | 无 | ✅ `c2ad0f0` |
| C | **会话侧栏增强**（重命名、来源筛选、分组） | 多会话学习管理 | **S** | 无 | ✅ `c2ad0f0` |
| D | **检索参数在线调节**（top_k / 阈值 / RRF 权重） | 调参可见可试，教学与自用 | **M** | 无 | ✅ `4e79c92` |
| E | **文档自动打标签**（从已有标签池匹配） | 文档库组织；笔记已有标签 | **M** | 标签池 | ✅ `f12c9e5` |
| F | **解析进度时间线**（阶段 span + 耗时 + 失败原因） | 大文档"卡在哪一步"可诊断 | **M-L** | 任务表已有 | ✅ `c2059d8` |
| G | **端到端评测 UI**（题集 → 召回/生成指标） | 验证学习质量，闭环调参 | **M** | D（调参）+ 现有 harness | ✅ `81c04ba` |
| H | **知识 Wiki**（概念页 + 双向链接 + 版本） | 学习资料结构化，**价值最高** | **XL** | E/F 可选 | ✅ 5.1–5.5 `c8eeddf`…`f285936` |
| I | **知识图谱**（实体关系抽取 + 可视化） | 概念关联理解 | **L-XL** | H 可选 | ⏸ 未启动（按计划可选） |
| J | 批量操作（多选打标/重解析） | 效率 | **S-M** | E | ✅ 随 E |
| K | 文档自定义元数据 | 边缘 | **S** | 无 | 未做（低优先） |
| L | Prompt 模板选择器 | 调优 | **S** | 无 | 未做（低优先） |
| M | 模型调试器 | 开发者向 | **M** | 无 | 不做（见 §10） |

**关键判断**：A/B/C 三件合计不到两天，性价比最高；D→G 是"检索质量可观测闭环"；H 是独立产品能力（约等于把笔记系统升级成概念 Wiki），必须单独排期，不要塞进小阶段。

---

## 3. P0：三件低垂果实（互不依赖，可并行）

### A · 推荐起始问题（Starter Suggestions）

> 参照：`QuestionSuggestionConfig.Starters`（`custom_agent.go:321-327`）、`message_suggestion.go`（`ensure` 复用同一配置快照避免重复生成）。

**现状**：5.2 已做「答后追问」；**空态 / 新会话首屏**没有引导问题。

**要求**
- 后端：`POST /api/chat/suggest-starters`，入参 `{ document_ids?: [], n=3 }`；有文档时基于文档摘要生成，无文档时用课程/通用学习引导语。
- **复用 5.2 的 LLM 通道与解析容错**（`_parse_suggestion_list`），计入 `usage_service`；把 `_parse_suggestion_list` 与模板渲染抽到可复用函数，**禁止复制**。
- 前端：`ChatView` 空态渲染 3 个可点起始问题（无消息时显示）；点击即发送。
- 配置：`n` 可关（设置里关掉后不再显示），默认开。

**验收**：后端测试（有文档/无文档/LLM 失败降级）；前端测试（空态渲染、点击发送、关闭后不渲染）。

**回滚**：纯新增，删路由与组件即可。

### B · 收藏 / 书签

> 参照：`user_resource_favorite.go`（resource_type 白名单 + 非空校验，service 极薄）。

**要求**
- 表 `user_favorites(id, user_id, resource_type, resource_id, created_at)`，`UNIQUE(user_id, resource_type, resource_id)`；`resource_type ∈ {document, note, message}`。
- API：`GET/POST/DELETE /api/favorites`，按 type 过滤列表。
- 前端：文档卡 / 笔记卡 / 消息操作栏加星标；`AnalysisView` 或侧栏加「我的收藏」入口（可先做文档+笔记，消息收藏 P1）。

**验收**：后端 CRUD + 去重；前端星标态切换与列表。

### C · 会话侧栏增强

> 参照：`SessionSidebarRow.vue`（内联重命名）、`SessionGroupByDropdown.vue`、`SessionSourceFilter.vue`。

**要求**
1. **内联重命名**：双击会话标题可编辑，回车保存（API 已有 `PUT /history/{id}`）。
2. **来源筛选**：按「全部 / 深度研究 / 多角色研讨」过滤（我们没有 Web/IM/嵌入来源，映射到 mode）。
3. **按时间分组**：今天 / 昨天 / 更早（纯前端分组，无 API）。

**验收**：前端测试覆盖重命名、筛选、分组渲染。

**P0 执行提示词（A+B+C）**
> 工作仓库：`/Users/wweiqi/Desktop/update plan/Study-copilot`，只改 `backend/` 与 `frontend/`；其下 `WeKnora/` 是只读参照，禁止修改、禁止复制代码。任务：做三件小交互。(1) 起始问题：后端 `POST /api/chat/suggest-starters` 用 LLM 按所选文档（或无文档通用）生成 3 条空态引导问题，复用 `chat_service._parse_suggestion_list` 与 usage 记账（抽公共函数，禁止复制 5.2 逻辑）；前端 ChatView 空态显示可点芯片，点击即发送，设置可关。(2) 收藏：新表 `user_favorites`（user_id+type+id 唯一，type∈document/note/message），API GET/POST/DELETE，文档卡与笔记卡加星标与收藏列表入口。(3) 会话侧栏：标题双击内联重命名、按 mode 筛选、按今天/昨天/更早分组。每项补测试。收尾跑 §1.3 全部门禁并贴结果。不要动组件库、不要新增依赖。

---

## 4. 阶段一：检索参数在线调节（可观测调参闭环的起点）

> 参照：`internal/types/retrieval_config.go`（EmbeddingTopK / VectorThreshold / KeywordThreshold / RerankTopK / RerankThreshold / RRFK / RRFVectorWeight / RRFKeywordWeight）、`RetrievalSettings.vue`（滑杆 + 保存）。

**为什么值得做**：我们的 `top_k`、RRF `k`、相关度阈值目前写死在 `pgvector_store` / `rag_engine`。学习场景常要"更宽召回做综述 / 更窄召回做精读"，参数应在界面可调并立刻生效。

**要求**
- 表 `user_retrieval_configs`（或并入 `user_llm_configs.extra_config`——**优先扩展已有 JSON 列，少建表**）：字段对齐参照的 8 项，给合理默认（top_k=5, rerank_top_k=5, rrf_k=60, vector_weight=0.7）。
- API：`GET/PUT /api/config/retrieval`（管理员=当前用户即可）。
- 接线：`pgvector_store.search()` / `rag_engine.retrieve()` 读取用户配置覆盖默认值；**坐标为默认时行为必须与现状 bit 级一致**（回归测试）。
- 前端：`ModelConfigView` 或设置区加「检索参数」面板（滑杆 + 数值显示 + 重置默认）；旁挂"用最近一次探针跑一把"的快捷按钮（可选）。

**验收**：
1. 默认值下现有检索测试全绿（行为不变）。
2. 改 top_k 后 search 返回条数跟着变的测试。
3. 前端滑杆持久化 + 刷新后回显。

**风险**：中——改检索热路径。必须有"默认配置 = 旧行为"的对拍测试。

**执行提示词（阶段一）**
> 工作仓库与只读参照抬头见上。任务：给检索加用户级在线参数。把 EmbeddingTopK / VectorThreshold / KeywordThreshold / RerankTopK / RerankThreshold / RRFK / RRFVectorWeight / RRFKeywordWeight 存进用户配置（优先 `user_llm_configs.extra_config`  JSON 扩展，避免新表），提供 `GET/PUT /api/config/retrieval`。`pgvector_store.search` 与 `rag_engine.retrieve` 读取用户配置覆盖默认；**必须写"默认配置下检索行为与改前一致"的回归测试**。前端在模型设置区加滑杆面板（参照 `WeKnora/frontend/src/views/settings/RetrievalSettings.vue` 的交互，禁止复制代码，用 Element Plus）。收尾跑 §1.3 门禁。

---

## 5. 阶段二：文档自动打标签 + 批量操作

> 参照：`knowledge_auto_tag.go`（confidence ≥ 0.75、只从已有标签池选、不新建、不覆盖人工标签、候选按序号而非 UUID 以省 token）、`BatchTagDialog.vue` / `DocumentBatchBar.vue`。

**要求**
- 标签池：把现有 `tags` 表从"仅笔记"扩展到"笔记+文档"（或 `tag_scope` 字段）；文档详情显示标签。
- 自动打标：文档解析完成后（或手动触发）异步任务——取文档前 N 字 + 用户标签列表，LLM 输出匹配标签（序号引用），阈值过滤，**只增量关联、不删人工标签**。
- 批量：文档列表多选 → 批量打标签（自动预选公共标签）/ 批量删除；任务走现有 `task_worker`。

**验收**：自动打标不创建新标签、不覆盖人工标签；批量 API 与 UI；异步失败不阻断文档 ready。

**难度**：M。LLM 调用 + 任务编排 + 列表多选 UI。

**执行提示词（阶段二）**
> 抬头见上。任务：文档自动打标签。标签体系扩展到文档；解析完成后可选异步打标——LLM 只从用户已有标签池按序号挑选，confidence 阈值过滤，只增量关联（不新建、不覆盖人工标签）；参照 `WeKnora/internal/application/service/knowledge_auto_tag.go` 的契约（只读）。前端文档列表支持多选与批量打标签（`BatchTagDialog` 交互）。任务进现有 task_worker。补测试：阈值过滤、人工标签保留、批量结果。

---

## 6. 阶段三：解析进度时间线（Span）

> 参照：`internal/types/knowledge_span.go`（root / stage / subspan / generation；pending/running/done/failed/skipped/cancelled——**failed 与 cancelled 语义要分开**）、`extract.go`、前端 Langfuse 风格时间线。

**现状**：`TaskPanel` 只有任务级状态；大 PDF 解析卡住时看不出卡在哪一阶段。

**要求**
- 表 `document_parse_spans(id, document_id, attempt, parent_span_id, kind, name, status, started_at, ended_at, error)`；阶段集与我们解析链对齐（parse / profile / chunk / embed / index），**不要抄 WeKnora 的 5 阶段名**。
- `document_service._do_process_document` 各阶段埋点（start/end/fail）；失败置 failed，上游失败下游置 cancelled。
- 前端：文档详情加「解析时间线」折叠面板（阶段条 + 耗时 + 可展开子 span）；无 span 的旧文档降级为任务状态。

**验收**：阶段失败时对应 span 为 failed、其后为 cancelled；时间线渲染；旧文档无 span 不崩。

**风险**：M-L——要在解析热路径写库，注意别拖慢入库；span 写入用批量/独立 session。

**执行提示词（阶段三）**
> 抬头见上。任务：文档解析进度时间线。新表存 span（root/stage/subspan + pending/running/done/failed/skipped/cancelled，failed 与 cancelled 语义分开，参照 `WeKnora/internal/types/knowledge_span.go` 只读）。在 `_do_process_document` 各阶段埋点；阶段名用我们的 parse/profile/chunk/embed/index，不要抄 WeKnora 五阶段。前端文档详情加折叠时间线（阶段条+耗时+失败原因）。span 写入不得显著拖慢入库（独立事务/批量）。补测试：失败→cancelled 链、旧文档降级。

---

## 7. 阶段四：端到端评测 UI（检索+生成可视化）

> 参照：`evaluation.go` / `EvaluationService`（corpus/queries/answers/qrels/arels；召回命中 + BLEU/ROUGE）。

**现状**：`backend/evaluation/` 是 CLI harness；用户看不到「我这篇文档 + 这些问题 → 召回如何」。

**要求**
- 后端：`POST /api/evaluation/run`——入参 `{ document_ids, questions[], expected? }`；内部调用现有 `retrieval_probe` / `RAGEngine.retrieve`，产出 hit@k、MRR、可选生成答案与引用核对；**一次运行一次任务**（`task_worker`），结果落 `async_tasks.result` 或独立表。
- 前端：设置/分析区「评测台」——粘贴或上传问题列表 → 运行 → 表格结果（问题 / hit@1 / hit@5 / top 结果）+ 导出 JSON。
- 与阶段一联动：评测台展示当前检索参数，改参后可重跑对比。

**验收**：固定题集的指标可复现；与 `scripts/retrieval_probe.py` 数字一致（对拍测试）。

**难度**：M。UI 是新的，但底层已有 harness。

**执行提示词（阶段四）**
> 抬头见上。任务：端到端评测台。`POST /api/evaluation/run` 接收 document_ids + 问题列表，用现有检索链路跑 hit@k / top 结果（对拍 `scripts/retrieval_probe.py` 口径），异步任务落库。前端「评测台」页面：贴问题 → 跑 → 表格 + 导出，并展示当前检索参数（与阶段一联动）。补测试：指标口径与探针一致。

---

## 8. 阶段五：知识 Wiki（独立大项，单独排期）

> 参照：`wiki_ingest.go`(3238)、`wiki_page.go`、`wiki_linkify.go`、`wiki_lint.go`、`wiki_ingest_taxonomy.go`、`WikiBrowser.vue`(6592)、`WikiRevisionDrawer.vue`。**这是 WeKnora 里对学习产品价值最高、也最重的一块。**

**核心机制（要照抄的三点，其余是包装）**

1. **摄入即摘要+链接**：文档/笔记进 Wiki 时由 Agent 抽概念页（slug 稳定），正文里自动 `[[slug]]` 双向链接；同 slug 用 reduce 锁做读-改-写合并（`withSlugLock`），防并发丢更。
2. **人可编辑 + 版本历史**：页面可在浏览器编辑，逐版本快照、行级 diff、一键回滚——与我们阶段三的切片版本同构，可复用 `chunk_revisions` 的乐观并发模式。
3. **索引页 / 分类法**：`wiki_ingest_taxonomy.go` 维护目录与索引页，层级不深、宁可平铺（我们第一期已否决文件夹树，Wiki 的"目录"是**概念索引**不是文件树）。

**范围裁剪（相对 WeKnora）**
- **做**：单用户、文档+笔记双源摄入、概念页 CRUD、`[[链接]]` 解析与死链提示、版本回滚、简单搜索。
- **不做**：多租户空间、Wiki 独立 Worker 池（用现有 `task_worker`）、Redis 分布式锁（单用户进程内锁即可）、多语言 lint、与文件夹树联动。

**建议切法（避免一口吃成胖子）**
| 子阶段 | 内容 | 难度 |
|---|---|---|
| 5.1 | 数据模型 + 手动建概念页 + Markdown 渲染 `[[slug]]` | M |
| 5.2 | 从文档/笔记摄入（LLM 抽概念 + 链接） | L |
| 5.3 | 索引/分类页 + 全局搜索 + 死链检查 | M |
| 5.4 | 版本历史 + 回滚（复用切片版本模式） | M |
| 5.5 | 浏览器内编辑（可选，用现有 markdown 编辑） | S-M |

**验收（每子阶段独立门禁）**：摄入幂等（同文档重跑不复制页）；链接可点；版本可回滚；旧笔记/文档未摄入时 Wiki 不报错。

**风险**：**XL**。务必子阶段切片交付，每片可回滚。第一期之后我们有 5.2 追问与笔记系统，Wiki 的 LLM 提示词要与之对齐风格。

**执行提示词（5.1 起）**
> 抬头见上。任务：知识 Wiki 5.1——数据模型与手动概念页。新表 wiki_pages（slug 唯一、title、content、revision），Markdown 渲染支持 `[[slug]]` 链接跳转与死链标灰；提供 CRUD API；前端 Wiki 浏览页（列表+正文+面包屑）。**不要**在本阶段做摄入。参照 `WeKnora/internal/types/wiki_page.go` 与 `frontend/.../wiki/WikiBrowser.vue` 的交互结构（只读，禁止复制代码）。门禁见 §1.3。

---

## 9. 阶段六：知识图谱（可选，仅当 Wiki 已稳）

> 参照：`graph.go`（PMI + 关系强度加权、间接关系衰减、并发实体抽取）、`extract_graph.go`。

**只做最小闭环**：从已摄入 Wiki 概念页抽实体-关系三元组 → 存表 → 力导向图可视化 → 点击节点跳概念页。**不做**：GraphRAG 检索增强（那是另一条产品线，评测成本高）、多文档跨库图谱。

**难度**：L-XL。建议只有在 5.x 全绿且用户明确要"概念关联图"时再启动。

---

## 10. 明确不做（被问到就给理由，别默默实现）

| 不做 | 理由 |
|---|---|
| RBAC / 多租户 / 审计日志 / 邀请 | 单用户本地产品 |
| IM 渠道、网站嵌入 Widget、Chrome 插件、小程序 | 发布形态不同 |
| 技能沙箱（Docker/E2B/Cube）、ClawHub | 第一期 §9 已否决 |
| 数据源同步（Notion/飞书/语雀/RSS） | 我们是上传+URL 导入 |
| 多向量库抽象（ES/Milvus/…） | 钉死 pgvector |
| FAQ 问答对库录入管理 | 用测验功能替代 |
| 文件夹树 | 课程空间已占组织轴（第一期 §9） |
| 模型调试器、OIDC、密钥轮换 | 开发者/企业向 |
| GraphRAG 检索增强 | 评测成本高，先有图谱可视化再说 |

---

## 11. 里程碑、依赖与工作量

```
P0（A 起始问题 + B 收藏 + C 会话侧栏）── 独立并行，约 2 天
        │
        ▼
阶段一 检索调参 ──► 阶段四 评测 UI（调参可对比）
        │
        ▼
阶段二 自动打标签 + 批量
        │
        ▼
阶段三 解析时间线
        │
        ▼
阶段五 Wiki（5.1→5.5 切片）──► 阶段六 图谱（可选）
```

| 阶段 | 规模 | 风险 | 不可逆动作 | 验收状态（2026-09-28） |
|---|---|---|---|---|
| P0 A/B/C | S×3 | 低 | 无 | ✅ `c2ad0f0` |
| 一 检索调参 | M | **中**（热路径） | 无 | ✅ `4e79c92`（默认=旧行为回归测试） |
| 二 自动打标 | M | 低-中 | 无 | ✅ `f12c9e5` |
| 三 解析时间线 | M-L | 中（入库写 span） | 无 | ✅ `c2059d8` |
| 四 评测 UI | M | 低 | 无 | ✅ `81c04ba` |
| 五 Wiki 5.1–5.5 | **XL** | 高 | 无 | ✅ `c8eeddf` `21a3490` `9a6e98f` `f285936` |
| 六 图谱 | L-XL | 高 | 无 | ⏸ 未启动（可选） |

**若资源只够一半**：做完 P0 + 阶段一 + 阶段二，已覆盖"用起来顺手、资料好找、检索可调"三件用户最常抱怨的事；Wiki 单独立项。

---

## 12. 全程验证清单（收尾 Agent 用）

> 2026-09-28 实施收尾勾对。

1. ✅ 门禁：pytest **866 passed** / ruff 0 / mypy 0（113 文件）/ alembic 单 head `c9d0e1f2a3b4` 且 `current==heads` / vitest **435 passed** / vue-tsc 0。
2. ✅ `WeKnora/` 只读未改动；`grep WeKnora/` 进 app 零命中。
3. ✅ `frontend/package.json` 无新增依赖。
4. ✅ 每阶段有测试文件；检索「默认=旧行为」回归（`test_retrieval_config.py`）保持绿。
5. ✅ 评测口径与 `scripts/retrieval_probe.py` 一致（`eval_service` 同用 PgVectorStore.search + hit@k）。
6. ✅ `/health` 的 `chunk_count_sync` 哨兵仍在（第一期引入，本轮未破坏）。

---

## 13. 与第一期的边界

| 项 | 第一期 | 第二期 |
|---|---|---|
| 答后追问 | ✅ 5.2 已做 | A 做**起始问题**（空态），不重复 |
| 收藏 | 未做 | B |
| 会话侧栏 | 基础列表 | C 增强 |
| 检索 | 硬编码参数 | D 可调 |
| 打标 | 仅笔记 | E 扩到文档 |
| 解析进度 | 任务级 | F 阶段级 |
| 评测 | CLI | G UI |
| Wiki / 图谱 | 明确不做中的"知识图谱" | H/I 重新立项（图谱从"不做"升为"可选"，因学习场景价值重估） |

**图谱说明**：第一期 §9 把"知识图谱"列为不做；第二期把它降为**阶段六可选**——前提是 Wiki 已交付且用户确实要概念关联。若不想做，整项可删，不影响其他阶段。

---

## 14. 2026-09-28 实施收尾记录

**提交清单（按阶段）**

| 提交 | 阶段 | 交付 |
|---|---|---|
| `c2ad0f0` | P0 | 起始问题 `POST /chat/suggest-starters`；`user_favorites`（迁移 `e5f6a7b8c9d0`）+ 星标；会话时间分组/筛选 |
| `4e79c92` | 一 | `extra_config.retrieval` + `GET/PUT /config/retrieval` + 滑杆面板；默认=旧行为回归 |
| `f12c9e5` | 二 | `document_tags`（迁移 `f6a7b8c9d0e1`）；自动打标（只增不覆盖）+ 批量；列表带 `tag_names` |
| `c2059d8` | 三 | `document_parse_spans`（迁移 `a7b8c9d0e1f2`）；parse/profile/chunk/embed/finalize 埋点 + 时间线 UI |
| `81c04ba` | 四 | `POST /evaluation/run` + 评测台（hit@1/5） |
| `c8eeddf` | 五 5.1 | `wiki_pages`（迁移 `b8c9d0e1f2a3`）；概念页 CRUD + `[[双链]]` + 死链提示 |
| `21a3490` | 五 5.2 | 文档/笔记摄入（LLM 提炼 + 同 slug 合并） |
| `9a6e98f` | 五 5.4 | `wiki_page_revisions`（迁移 `c9d0e1f2a3b4`）；版本历史 + 回滚（回滚=再编辑） |
| `f285936` | 五 5.3 | 全局死链巡检 + 孤页统计 + 索引数据 |

**数据库迁移链**：`c8d9e0f1a2b3 → e5f6a7b8c9d0 → f6a7b8c9d0e1 → a7b8c9d0e1f2 → b8c9d0e1f2a3 → c9d0e1f2a3b4`（单 head）。

**与计划的偏差（如实记录）**
1. **检索 RRF 权重默认 1.0/1.0**（非 WeKnora 的 0.7/0.3）——为满足「默认配置 = 改前行为」回归约束，避免静默改变排序。
2. **会话「来源筛选」**映射为时间筛选（全部/今天/昨天/本周/更早）——会话表无 mode 字段，深度研究/研讨筛选未做。
3. **Wiki 5.3 的「分类法索引页」**折成 `wiki_index` 数据接口 + 列表搜索，未做独立目录树页（与第一期「不做文件夹树」一致）。
4. **消息收藏（favorite type=message）**后端已支持，前端星标只挂了文档/笔记。
5. **阶段六图谱**按计划保持可选，未启动。

**测试增量**（相对第一期 816 + 422）
- 后端 +50：favorites 5、tag 8、span 4、eval 4、wiki 14、ingest 7、retrieval 5、starter 3、其余门禁修正
- 前端 +13：favorite/star、batch tag、parse timeline、eval lab、wiki view 3、history panel 3、starter store 3

**剩余可做**
1. 阶段六知识图谱（可选）
2. 消息收藏星标前端入口
3. 文档自定义元数据 / Prompt 模板选择器（计划低优先）

---

## 15. 2026-09-29 OCR 评审收尾（四轮）与工程加固

**背景**：用 `alibaba/open-code-review`（`ocr` CLI，StepFun `step-5-preview`）对两期计划的生产代码做分批评审，共 **~54 条**意见，High/Medium 全部修复。

### 提交

| 提交 | 内容 |
|---|---|
| `cff141c` | 一轮：检索参数接入主路径（High）、滑杆真生效、建议解析不吞正文数字、追问按 id 回写、探针可比性 |
| `8a0e07d` | 二轮：WikiView `[[slug]]` 渲染前占位（High）、slug 前后端归一对齐（High）、ParseTimeline 过滤优先级（High）、摄入 rollback、搜索防抖 |
| `a29171b` | 三轮：切片编辑乐观并发改 DB CAS（409 而非 500）、角标仅收纯数字、代码块不吞引用标记、回滚带 expected_revision |
| `39fea40` | 四轮：span `fail_stage` 幂等（High）、批量打标事务隔离（High）、confidence/排序/name 匹配 |
| `549ad0a` | 测试加固：`_ensure_schema` 防 cov 塌表、`asyncio.run` 改 async 测试 |
| `e452cf7` | 注册算术人机验证链路（收编并行 WIP 的 captcha） |

### OCR 发现的典型缺陷类型（后续做类似功能时当检查单）

1. **并发非原子**：应用层读-改-写乐观锁撞 UNIQUE → 500；改 DB CAS 或捕获 IntegrityError → 409
2. **批量循环共享 session**：单条失败不 rollback → 后续全废；业务错误与 DB 异常要分开处理
3. **前后端归一规则不一致**：slug/数字前缀等，key 对不上就误判死链/错位
4. **在已渲染 HTML 上做正则**：污染 href/code；应先占位再渲染
5. **级联操作不幂等**：外层 except 二次调用重复插记录
6. **sync 测试里 `asyncio.run`**：踩 session 级事件循环，引发 fixture 提前 teardown

### 门禁现状（2026-09-29）

后端 **882 passed** / cov 75.5% / ruff 0 / mypy 0；前端 **436 passed** / vue-tsc 0；
`alembic` 单 head `c9d0e1f2a3b4`；连续两次全量 cov 跑稳定。

**剩余未做**（与 §14 一致）：阶段六图谱、消息收藏前端星标、文档自定义元数据、Prompt 模板选择器。
