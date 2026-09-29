# Study Copilot 对话与知识库界面升级实施计划（交互参照 WeKnora v0.8.0）

> 版本：v1.3（2026-09-24 制定 / 09-25 验收标注 / 09-25 二次复核补 §13 / **09-28 收尾复核**）
>
> **工作仓库——要改的就是它**：`/Users/wweiqi/Desktop/update plan/Study-copilot`，代码只落在 `backend/` 与 `frontend/`
> **只读参照——禁止修改、禁止复制其代码**：上述仓库下的 `WeKnora/` 子目录（v0.8.0，commit `ef9cbf4`，MIT）。文中凡以 `WeKnora/` 开头的路径**一律是"去看它怎么做的"**，不是要改的文件。
>
> 本文用途：**交给执行 Agent**。每阶段末尾有可直接粘贴的「执行提示词」。
> **验收结论（三次复核，2026-09-28）**：P0 与阶段一～六主体已落地。§12 五处未闭合项中 1/2/4/5 已修，5.2 已补交付；§13 数据事故已处置（备份→清理 stale 10463+dup 150→重跑→前后探针对比，`ready_mismatch=0`，hit@5 保持 100%）。收尾提交 `b65bfb1`、`71a06d3`。**剩余：`rag-stress-corpus.pdf` 源文件缺失、6B/6C 按计划留待迭代。**详见 `docs/compose/spec/weknora-ui-upgrade.md` 与 `backend/evaluation/results/reindex-compare-20260928.md`。

---

## 0. 给执行 Agent 的硬约束（每个阶段都适用，违反即返工）

1. **只参照、不复制代码。** WeKnora 是 MIT，但本计划的意图是用我们自己的技术栈重写交互与数据契约。**禁止**把 `WeKnora/frontend/**` 的 `.vue`/`.ts` 或 `WeKnora/internal/**` 的 `.go` 内容粘贴进 `frontend/` 或 `backend/`，**禁止**新增任何指向 `WeKnora/` 的 import、符号链接或依赖。
2. **不换组件库、不加构建链。** 继续用 Element Plus + TailwindCSS + Vite。参照实现里凡出现 TDesign 组件名（`t-textarea`、`t-popup` 等）一律换成 Element Plus 或原生 + Tailwind 等价物。
3. **不许改动 `WeKnora/` 目录内容**（它是只读参照，且已被 `.gitignore:116` 排除）。唯一例外：本计划中被明确要求读，不写。
4. **每阶段完成的定义 = 代码 + 测试 + 门禁全绿**，门禁命令见 §1.4。不接受"实现完成但测试待补"。
5. **数据库变更必须走 Alembic**，且必须挂在当时的唯一 head 之下。制定本文时 head 为 `d4e5f6a7b8c9`（`add_token_usages`）；**阶段二/三已把链推进为 `d4e5f6a7b8c9 → b7c8d9e0f1a2`（坐标）`→ c8d9e0f1a2b3`（切片版本），当前 head = `c8d9e0f1a2b3`**。后续新迁移一律挂 `c8d9e0f1a2b3`。**本项目曾发生过双 head 导致启动迁移卡死的事故**，提交前必须跑 §1.4 里的双 head 检查。
6. **测试用 SQLite、生产用 PostgreSQL**（`tests/conftest.py:11`）。一切迁移只准用两种方言都成立的朴素类型与 `server_default`；需要加约束时用 `op.batch_alter_table()`；PG 专有表达式（JSONB 操作符、`USING`、`gen_random_uuid()`）不得进入被 SQLite 测试覆盖的路径。并且**每次迁移都要另外对 PostgreSQL 手工跑一遍 `alembic upgrade head`**——测试不跑 alembic，光看测试绿不能证明迁移可用。
7. **不确定就停下问，不要猜需求。** 特别是涉及"是否重新入库全量文档"这类不可逆动作，必须先向用户确认。
8. 行号会漂移。**定位以"符号名 + 文件路径"为准**，本文标注的行号仅供起始参考；对不上时用符号名搜索。
9. **派发任何一则执行提示词时，必须把本文顶部的「工作仓库 / 只读参照」两行原样带在提示词开头。** 本文两类路径混排（本项目 32 处、参照 29 处），只靠"参照只读"四个字不足以让执行方分辨该改谁——这是 v1.0 的交接缺陷，v1.2 起用抬头强制消歧。

---

## 1. 共享上下文

### 1.1 我们的关键文件

| 领域 | 文件 | 说明 |
|---|---|---|
| 切片表 | `backend/app/db/database.py`（`class DocumentChunk`） | 计划制定时仅 `id / document_id / content / embedding / chunk_index / chunk_metadata(JSON) / created_at`。**v1.1 更新：阶段二/三已补 `source_content / char_start / char_end / context_header / is_parent / content_revision / index_status / last_editor_id`（均带 `server_default`）** |
| 分块策略 | `backend/app/core/chunk_strategy.py` | `profile_document()`（画像）、`select_chunking_chain()`（选链）、`validate_chunks()`（五法则校验，**已返回 `(bool, reason)`**）、`enrich_chunk_breadcrumbs()` |
| 分块器 | `backend/app/core/chunker.py` | `FixedChunker` / `SemanticChunker` / `HierarchicalChunker`，父子块用 `metadata.is_parent` 标记 |
| 入库链路 | `backend/app/services/document_service.py` | `_do_process_document()`（约 178-313 行）串起 解析→画像→策略链→校验降级→面包屑→`PgVectorStore.add_chunks()` |
| 切片读取 | `backend/app/services/document_service.py` `get_document()`（约 428-449 行） | **只返回 `{"text", "chunk_metadata"}`**，坐标信息在 metadata 里都不全 |
| 向量检索 | `backend/app/core/pgvector_store.py` | `add_chunks()`、`search()`（约 193 行起：单条 SQL 做 pgvector 余弦 + FTS，RRF 融合；父块用 `chunk_metadata->>'is_parent'` 过滤） |
| 文档接口 | `backend/app/api/document.py` | `POST /{doc_id}/reprocess`（约 112 行）、`POST /{doc_id}/restore`（约 101 行）——**后端已有、前端从未调用** |
| 问答流 | `backend/app/services/chat_service.py` `ask_question_stream()`（约 256 行起） | SSE 事件协议在此产出 |
| 管线 | `backend/app/pipeline/__init__.py` + `pipeline/plugins/*` | 8 段洋葱管线，`PIPELINE_V2_ENABLED` 默认 True（`app/config.py` 约 73 行） |
| 前端聊天控制器 | `frontend/src/views/ChatView.vue`（计划时 1627 行 → **现 1753**，最大文件，改动风险高） | 混合了输入编排、研讨 SSE 解析、markdown 分块缓存、GSAP、滚动管理 |
| 前端消息渲染 | `frontend/src/components/chat/ChatMessageItem.vue`（计划时 787 行 → **现 1117**） | 三层：Agentic 徽章 / CoT 面板 / 正文；4A 双窗收拢加在此处 |
| 前端来源卡 | `frontend/src/components/chat/ChatSourceCards.vue`（计划时 325 行 → **现 444**） | 默认折叠；4B 加了「展开全文」但依赖 chunk_id（见 §12） |
| 前端输入框 | `frontend/src/components/chat/ChatInput.vue` | 纯文本 textarea，`isComposing` 已处理（约 99 行），`props.loading` 拦发送（约 106 行） |
| 前端流状态 | `frontend/src/stores/chat.ts` | `applyEvent()` 消费事件；SSE 用裸 fetch + reader |
| 前端文档页 | `frontend/src/views/DocumentView.vue`（计划时 621 行 → **现 735**） | 切片卡片 + blob 原文预览（PDF/图片/md）+ 分块预览/切片编辑入口 |

### 1.2 参照文件（只读，**禁止修改、禁止复制代码**；下列路径全部位于 `WeKnora/` 子目录内，不是要改的目标）

| 用途 | 路径 | 行数 |
|---|---|---|
| **分块预览接口** | `WeKnora/internal/handler/chunker_debug.go` | 292 |
| 分块策略与诊断 | `WeKnora/internal/infrastructure/chunker/`：`strategy.go`(363) `profiler.go`(241) `validator.go`(75) | — |
| 父/子块与坐标不变量 | `WeKnora/internal/infrastructure/chunker/splitter.go`（`Chunk` 结构 26-49、`SplitParentChild` 844-897） | 914 |
| **切片编辑+版本+回滚** | `WeKnora/internal/handler/chunk.go`(462) `internal/application/service/chunk.go`(853) `migrations/versioned/000078_chunk_editing_and_custom_metadata.up.sql`(26) | — |
| **引用标签协议** | `WeKnora/internal/modelcontext/citations.go`(287) | — |
| **引用前端机制** | `WeKnora/frontend/src/utils/citationMarkdown.ts`(316) `directives/stableHtml.ts`(141) `composables/useChatCitationPopover.ts`(261) `components/ChatCitationFloat.vue` | — |
| 来源抽屉 | `WeKnora/frontend/src/components/ChatReferencesDrawer.vue`(604) `utils/referenceSources.ts`(371) | — |
| **过程进度（伪工具事件）** | `WeKnora/internal/application/service/chat_pipeline/progress.go`(306) `internal/types/knowledge_span.go`(117) | — |
| 三态文档视图（切片/合并/预览） | `WeKnora/frontend/src/components/doc-content.vue`(3331) | — |
| 输入框与范围选择 | `WeKnora/frontend/src/components/Input-field.vue`(3844) `components/AttachmentUpload.vue` `components/MentionSelector.vue` | — |
| 按文档覆盖处理参数 | `WeKnora/internal/types/knowledge_process.go`(28) | — |
| 分块参数预览界面 | `WeKnora/frontend/src/views/knowledge/settings/KBChunkingDebug.vue`(725) | — |

### 1.3 三条要照抄的核心机制（其余都是包装）

1. **预览是纯函数式只读接口。** 输入文本 + 分块参数，输出：采用的切法、完整候选链、**每一层被拒的原因**、文档画像、每块带 `start/end` 与面包屑、外加统计（块数、均值、最小/最大、标准差）。不写库、不算向量、有超时和体量上限（它是 64k 字符 / 500 块 / 5 秒）。→ 见 `chunker_debug.go:32-102, 141-148, 248-256`。
2. **正文与上下文分离 + 字符坐标不变量。** `Content` 严格等于原文 `[Start,End)` 切片；面包屑存独立字段，**只在算向量时才拼**（`EmbeddingContent()`）。因为坐标成立，父块可以在子块被编辑后按倒序覆盖重建（倒序是为了让前面的编辑不使后面的坐标失效）→ 见 `service/chunk.go:577-600`。
3. **进度复用工具事件，且必须保证关闭。** 阶段被压成两个伪工具窗口（问题理解 / 检索合并窗），出错时也必须补发 result 事件（哪怕内容是"命中 N 条候选但相关性不足"），否则界面转圈不停 → 见 `progress.go:75-77, 109-171`。

### 1.4 门禁命令（每阶段收尾必须全绿）

```bash
# 后端
cd backend
HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/ -q   # 基线已随阶段推进上浮：现 72 个测试文件 / 741 个测试函数，只许增加不许失败
.venv/bin/python -m ruff check app tests                 # 0 error
.venv/bin/python -m mypy app                             # 0 error
# Alembic 双 head 检查（必须只输出一个 head）
.venv/bin/python -m alembic heads
# 且开发库必须已到 head（v1.2 补：只查 heads 会漏掉"库没升级"）
test "$( .venv/bin/python -m alembic current | tail -1 )" = "$( .venv/bin/python -m alembic heads | tail -1 )"

# 前端
cd frontend
npx vitest run                                           # 基线 47 文件 / 371 用例全绿（注意仍有 6 条 el-* 未解析告警被计为 errors，见 §12）
npx vue-tsc --noEmit
npm run build
```

**2026-09-25 实测**：ruff `All checks passed` / mypy `no issues found in 99 source files` / `alembic heads` 仅 `c8d9e0f1a2b3` / vitest `371 passed` / vue-tsc 0 error。pytest 与 `npm run build` 本轮未执行（审阅态不跑写态命令），其结果以执行方留痕为准。

---

## 2. P0：先修两处既有缺陷（不依赖任何参照实现）

> **状态 ✅ 已完成**（`d411263` `c507346`）。F1 深链统一为 `?doc=`（向后兼容 `document_id`），`DocumentView.vue` 挂载与 query 变化时按 id 选中并滚动，`frontend/tests/views/documentDeepLink.test.js` 断言；F2 选方案 B，`StreamBatcher` 类与那份假测试**一并删除**，全仓 `grep StreamBatcher` 零命中；出题按钮改文案对齐整文档出题行为，名实相符。

### F1 · 来源卡"查看文档"点了没反应

- **事实**：`ChatMessageItem.vue` 的 `openSourceDocument()`（约 416-427 行）push 的查询参数是 `document_id`（约 421 行）；而 `DocumentView.vue` **不读任何文档定位参数**，它只读 `route.query.page` 和 `route.query.q`（约 457-458 行），选中文档靠列表点击。结果：跳转成功、文档没被选中。
- 对照组：反方向是通的——`DocumentView.vue:319` push `/chat?docId=`，`ChatView.vue:1285` 读 `route.query.docId`。
- **要求**：统一为一个参数名（建议 `doc`），在 `DocumentView.vue` 挂载与 query 变化时按该 id 选中文档并滚动到该卡片；文档不存在时给出可见提示而不是静默。
- **验收**：新增前端测试，断言带 `?doc=<id>` 进入文档页后 `selectedDoc.id === <id>`；手工验证从回答里的来源卡点进去能定位。

### F2 · 流式微批缓冲是死代码，且测试测的是不存在的函数

- **事实**：`frontend/src/stores/chat.ts` 定义了 `StreamBatcher` 类（约 14 行起）但**全仓从未实例化**（搜索 `new StreamBatcher` 零命中）；token 是直接追加的。真正防抖动的是 `ChatView.vue` 里的分块缓存 + 尾块重渲（约 574-641 行）。更糟的是 `frontend/tests/stores/chat_stream_batcher.test.ts` **在测试文件里重新实现了一个 src 中不存在的函数**来模拟行为——测试通过但什么都没保障。
- **要求（二选一，不要维持现状）**：
  - 方案 A（推荐）：把 `StreamBatcher` 真正接进 `chat.ts` 的 token 路径，并按其真实行为重写测试；
  - 方案 B：删除 `StreamBatcher` 类，**同时删除那份假测试**，并在 §1.1 的注释里说明抖动控制由 ChatView 的分块缓存承担。
- **验收**：`grep -rn "StreamBatcher" frontend/src frontend/tests` 的结果要么"定义 + 实例化 + 被真实测试"三者齐备，要么完全消失。**不接受**"类在但没人用 + 测试自说自话"的中间态。

### 顺带（同批次，成本极低）

- `DocumentView.vue` 的"基于此段出题"实际调的是整文档出题（约 575-584 行，chunk 被忽略）。要么真正按段落范围出题，要么把按钮文案改成与行为一致。**不许保留名实不符。**

**执行提示词（P0）**
> 在 `/Users/wweiqi/Desktop/update plan/Study-copilot` 修三个既有缺陷：(1) `ChatMessageItem.vue` 的 `openSourceDocument` push `document_id`，但 `DocumentView.vue` 不读任何文档定位参数（只读 page/q），导致跳转后文档不被选中——统一参数名并在 DocumentView 支持按 id 选中+滚动，补一个断言该行为的前端测试；(2) `stores/chat.ts` 的 `StreamBatcher` 类从未被实例化，而 `tests/stores/chat_stream_batcher.test.ts` 在测试文件内部重新实现了一个 src 中不存在的函数——把批处理器真正接入 token 路径并改写测试，或者两者一起删除，不允许保留中间态；(3) `DocumentView.vue` 里"基于此段出题"实际忽略选中的切片按整文档出题——改为按段或改文案，二者取一。不要动组件库、不要新增依赖。收尾跑 §1.4 全部门禁并把结果贴出来。

---

## 3. 阶段一：分块预览接口（最高性价比，后端已经全算过一遍）

> **状态 ✅ 已完成**（`19011a9`）。共享 runner 抽到 `backend/app/core/chunking_pipeline.py::run_chunking_chain`，入库链路改为调用它（`document_service` 净减约 70 行，无逻辑复制）；`POST /api/documents/preview-chunking` 带 64k→413 / 500 块截断 / 5s→504 / `allow_embed=False`，`backend/tests/test_preview_chunking.py` 9 例（含不写库与不调 embedder 断言）；前端 `ChunkPreviewDialog.vue` + 文档页入口。

**为什么第一**：画像、候选链、每层拒绝原因，我们在入库时**已经全部计算并 log 过**（`document_service._do_process_document` 的 for 循环 + `validate_chunks` 返回 `(bool, reason)`）。缺的只是一个不写库、不算向量的只读接口和一个界面。这一件做完，阶段二的参数讨论、阶段四的切片编辑才有讨论对象。

**后端**
- 新增 `POST /api/documents/preview-chunking`，放在 `backend/app/api/document.py`，鉴权与现有上传接口一致。
- 请求体：`{ text: str, chunk_size?: int, chunk_overlap?: int, strategy?: "auto"|"fixed"|"semantic"|"hierarchical" }`。
- 实现：复用 `profile_document()` / `select_chunking_chain()` / `create_chunker()` / `deduplicate_chunks()` / `validate_chunks()` / `enrich_chunk_breadcrumbs()`，把入库循环里那段"逐层尝试 + 记录拒绝原因"抽成一个可复用函数（**要求抽函数而不是复制粘贴**——见下面"重复逻辑"一节）。
- 响应：`{ selected_strategy, chain: [...], rejected: [{strategy, reason}], profile: {total_chars, total_lines, md_heading_total, dominant_heading_level, chinese_chapter_count, ...}, chunks: [{seq, content, page, context_header}], stats: {count, avg_chars, min, max} }`
- 安全阀：文本上限 64k 字符（超出 413）、块数上限 500（超出截断并在 `stats.truncated_to` 标注）、`asyncio.wait_for` 5 秒超时（504）、**不写任何库、不调用 embedder**（加一条断言测试：调用后 `document_chunks` 行数不变、`embedder.embed_texts` 未被调用）。

**前端**
- 在 `DocumentView.vue` 里加一个"分块预览"入口（或独立小视图，避免继续加大 ChatView/DocumentView ——见 §7 重构约束）：粘贴文本或选择已上传文档，右侧展示块卡片流，顶部显示"采用：hierarchical；被拒：semantic（all chunks far below target size）"这样的链与原因，画像字段做成一小排指标卡。参照 `WeKnora/frontend/src/views/knowledge/settings/KBChunkingDebug.vue`。

**验收**：后端新增测试 ≥6 个（正常/超体量/超时/无权限/不写库断言/拒绝链完整）；前端新增测试断言"给定固定画像输入，界面渲染出正确的 selected_strategy 与 rejected 列表"。

**回滚**：纯新增接口与新组件，删路由与组件即可，无迁移。

**执行提示词（阶段一）**
> 目标：给 Study Copilot 加一个只读的分块预览接口和界面，不改动入库链路的行为。后端在 `backend/app/api/document.py` 新增 `POST /api/documents/preview-chunking`，复用 `app/core/chunk_strategy.py` 的 `profile_document/select_chunking_chain/validate_chunks` 与 `app/core/chunker.py` 的 `create_chunker/deduplicate_chunks`——注意：`backend/app/services/document_service.py` 的 `_do_process_document()` 里已经有一段"遍历策略链、逐层校验、记录拒绝原因"的循环，请把它抽成共享函数供两处调用，禁止复制逻辑。响应必须含 selected_strategy、chain、rejected[{strategy,reason}]、profile 指标、chunks（含 context_header/page）、stats。硬性要求：不写数据库、不调用 embedder（用测试断言这一点）、文本上限 64k、块数上限 500、5 秒超时。前端在文档页加入口，展示采用哪层/哪些层被拒及原因。参照实现只读：`WeKnora/internal/handler/chunker_debug.go` 和 `WeKnora/frontend/src/views/knowledge/settings/KBChunkingDebug.vue`——**照抄交互与响应字段设计，不许粘贴它的代码，组件用 Element Plus + Tailwind 重写**。收尾跑 §1.4 全部门禁。

---

## 4. 阶段二：切片表补"原文副本 + 字符坐标 + 上下文头"（地基，决定后面几个阶段的档次）

> **状态 ✅ 已验收（09-28 补评测对比）**（`1c6c07c` + `a50c42b` + `b65bfb1`）。五列已加（`source_content / char_start / char_end / context_header / is_parent`），迁移链 `d4e5f6a7b8c9 → b7c8d9e0f1a2`，`search()` 的 `is_parent` 过滤已改用真列，向量输入改为 `context_header + content`、落库 `content` 保持干净，坐标不变量有测试。**09-28 补齐 §4.1**：清理存量脏行后重跑，`scripts/retrieval_probe.py` 前后对比 hit@5=100%、重复噪声清零（`evaluation/results/reindex-compare-20260928.md`）。

**为什么必须早做**：坐标只能靠重新入库获得，**无法回填**。它同时是"引用悬浮卡看到精确原文"和"切片编辑后父块重建"两个阶段的前提。现在不给，阶段三只能退化成模糊文本匹配（WeKnora 自己在没有坐标时也是这么将就的）。

**迁移**（新 alembic revision，`down_revision = "d4e5f6a7b8c9"`）

> **方言注意（先读这条再动手）**：本项目的测试跑在 **SQLite**（`tests/conftest.py:11` 的 `sqlite+aiosqlite:///./test.db`），生产跑 PostgreSQL。所以本阶段所有新列必须是两种方言都成立的朴素类型（`TEXT / INTEGER / BOOLEAN` + `server_default`），**不要**在迁移里用 PG 专有语法（`USING`、JSONB 操作符、`gen_random_uuid()`）。若需要给已有表加约束，用 `op.batch_alter_table()`（SQLite 要重建表）。另外测试是靠 ORM 元数据建表、不走 alembic，因此**必须手工跑一次 `alembic upgrade head` 对着 PostgreSQL 验证迁移本身**，否则会出现"测试全绿、真实库迁移失败"。同理，`pgvector_store.search()` 里的 `chunk_metadata->>'is_parent'` 是 PG 专有表达式，改用新列时注意别把它挪进被 SQLite 测试覆盖的通用代码路径。
- `document_chunks` 增列，全部**可空、带默认值**，保证旧行不炸：
  - `source_content TEXT NULL` — 解析器产出的不可变原文（不含面包屑前缀）
  - `char_start INT NULL` / `char_end INT NULL` — 在该文档解析全文中的坐标
  - `context_header TEXT NULL` — 面包屑，单独存，不再焊进 content
  - `is_parent BOOL NOT NULL DEFAULT false` — 把目前藏在 `chunk_metadata->>'is_parent'` 里的标记提升为真列（查询更清晰、可加索引）
- **不动**现有 `content` 列的语义与 `chunk_metadata`（保持向后兼容，旧数据仍可检索）。

**入库链路**
- `chunker.py` 各 chunker 产出时带坐标。当前各策略都在做切片拼接，需要在切分时累计偏移；`FixedChunker` 有句级 overlap，坐标按"块正文实际起止"记录，overlap 部分计入 `char_start` 起点。
- **关键约束**：`content` 必须等于 `source_content[char_start:char_end]`。写一条属性测试随机验证（这是 WeKnora 明确写下来的不变量，也是它后续一切能力的基础）。
- `pgvector_store.add_chunks()`：算向量时用 `context_header + "\n\n" + content`（对齐"匹配用带上下文的、展示用干净原文"），存库的 `content` 保持干净。**注意这会改变向量输入**，因此本阶段附带 §4.1 的重跑要求。

**4.1 重跑全量入库（不可逆动作，必须先向用户确认）**
- 用现成的 `POST /api/documents/{doc_id}/reprocess`（`document_service.reprocess_document()` 已实现清理旧 chunk + 重新入队）。
- 提供脚本 `backend/scripts/reindex_all.py`（本仓已有 `backend/scripts/`），逐用户逐文档串行、失败不中断、打印清单。
- **重跑前必须**：先跑一次检索评测留基线（本仓 `backend/evaluation/` 与 `.github/workflows/retrieval-eval.yml` 已就绪），重跑后再跑一次对比。向量输入变化会移动排序，**没有对比就等于没验证**。
- 若用户暂不重跑：新逻辑只对新上传文档生效，旧文档坐标为空，功能自动降级——所有读坐标的代码路径必须写"坐标为 NULL 时的回退分支"。

**验收**：迁移可上可下（`alembic downgrade -1` 通过）；属性测试证明 content/坐标一致性；评测报告基线 vs 重跑后（召回指标不得劣化超过既有噪声范围）；`alembic heads` 只有一个。

**回滚**：alembic downgrade 掉新列；入库链路回退到旧行为（坐标与 source_content 变 NULL，功能降级但不报错）。

**执行提示词（阶段二）**
> 给 `backend/app/db/database.py` 的 `DocumentChunk` 增列：`source_content`、`char_start`、`char_end`、`context_header`、`is_parent`，写 Alembic 迁移挂在当前唯一 head `d4e5f6a7b8c9` 之后，全部可空或带默认以保证旧行不破。改造 `app/core/chunker.py` 各分块器产出字符偏移，并把当前写进 `metadata.context_header`、以及 `FixedChunker` 直接拼进正文的标题链，改为独立字段——目标不变量：`content == source_content[char_start:char_end]`，写随机属性测试验证。`app/core/pgvector_store.py` 的 `add_chunks()` 改为：向量输入用 `context_header + content`，落库 `content` 保持干净原文。`search()` 里的 `is_parent` 过滤从 JSONB 表达式改用新列。**这一步会改变向量输入，因此完成后先停下来向我报告，不要自行触发全量重跑**；同时确认所有读坐标的路径都有"坐标为 NULL 时降级"分支。参照：`WeKnora/internal/infrastructure/chunker/splitter.go` 的 Chunk 结构与 EmbeddingContent 注释（只读，勿复制）。

---

## 5. 阶段三：切片在线编辑 + 版本历史 + 回滚

> **状态 ✅ 已交付，不变量语义已定清**（`875f4b7` + `b65bfb1`）。`chunk_revisions` 带 `UNIQUE(chunk_id,revision)`、`content_revision/index_status/last_editor_id` 三列（迁移 `c8d9e0f1a2b3`）、`expected_revision` 不符→409、旧内容快照、`delete_by_chunk_id` + `reindex_chunk`、processing/ready/failed 状态机、失败后"同内容再提交=仅重试重嵌"、回滚实现为一次编辑（可再回滚）、父块按 `char_start` **倒序**覆盖重建，前端拆成 `ChunkEditDialog.vue` / `ChunkRevisionList.vue`。**09-28 定清不变量语义**：坐标=解析原文的**原点区间**；等长编辑维持 `content == source_content[s:e]`，变长后等式不成立属预期（勿为修等式改写 source_content——会使兄弟坐标漂移）；父块重建仍按原点 splice 当前正文。变长路径已补测试。

**前置**：阶段二已完成（否则父块重建无法做，且编辑会破坏坐标一致性）。

**数据模型**
- 新表 `chunk_revisions(id, chunk_id FK, revision INT, content TEXT, editor_id, edited_at, is_enabled BOOL)`，`UNIQUE(chunk_id, revision)`。当前版本仍留在 `document_chunks`，历史表只装被取代的版本。
- `document_chunks` 增列：`content_revision INT DEFAULT 0`、`index_status VARCHAR DEFAULT 'ready'`（`ready|processing|failed`）、`last_editor_id`。
  - **`index_status` 不可省**：重嵌入失败若不落状态，界面就会撒谎（显示已更新但检索仍命中旧内容）。

**服务层**（新增 `backend/app/services/chunk_service.py`，或并入 `document_service` —— 按项目惯例，跨文档级操作放 service，不要塞进 api 层）
- 编辑：乐观并发——请求带 `expected_revision`，不匹配返回 **409**；匹配则把旧内容快照进 `chunk_revisions`、`content_revision += 1`、`index_status = 'processing'`，然后**按 chunk_id 删向量再重嵌**（`pgvector_store` 需要新增 `delete_by_chunk_id` 与 `reindex_chunk` 两个方法），成功后置 `ready`，失败置 `failed` 并把错误返给前端供重试。
- 父块重建：子块被改后，父块的正文用"把编辑过的子块区间按**倒序**覆盖回 `source_content`"重建（倒序防止前面的编辑使后面的坐标失效）。
- 回滚 = 又一次编辑（所以回滚本身也可回滚）。
- 列表接口：`GET /api/documents/{doc_id}/chunks/{chunk_id}/revisions`。

**API**：`PUT/GET /api/documents/{doc_id}/chunks/{chunk_id}`、`POST .../revert`、`GET .../revisions`，注册在 `app/api/document.py`，路由注册到 `main.py`（按根 AGENTS.md 的"加接口"五步）。

**前端**：在 `DocumentView.vue` 的切片卡片上加"编辑 / 历史"，历史面板要能看行级增删并一键回滚。**编辑保存后必须显式显示索引状态**（处理中/就绪/失败+重试）。注意 `DocumentView.vue` 已 621 行，把编辑与历史做成独立组件（`ChunkEditDialog.vue`、`ChunkRevisionList.vue`），不要在原文件里堆。

**验收**：后端测试覆盖 409 冲突、快照写入、回滚可再回滚、重嵌入失败置 failed 且能被重试恢复、父块重建坐标不倒置；前端测试覆盖"索引状态三种显示"与"版本列表渲染"。

**回滚**：新表与新列 downgrade；接口与组件纯新增。

**执行提示词（阶段三）**
> 在阶段二之上实现切片在线编辑与版本回滚。新建 Alembic 迁移（挂当时最新 head）：`document_chunks` 加 `content_revision / index_status / last_editor_id`，新表 `chunk_revisions(chunk_id, revision, content, editor_id, edited_at, is_enabled)` 带 `UNIQUE(chunk_id,revision)`。编辑接口必须实现乐观并发（`expected_revision` 不符返回 409）、把旧内容快照进历史表、把 `index_status` 置 processing、按 chunk_id 删向量后重嵌、成功转 ready / 失败转 failed 且响应里回传状态。父块内容用"按倒序把已编辑子块覆盖回 source_content"的方式重建。回滚实现为一次编辑。前端把编辑与历史做成独立组件，保存后必须显示索引状态（含失败重试）。参照只读：`WeKnora/internal/application/service/chunk.go`（编辑/重建/重索引流程）与 `WeKnora/migrations/versioned/000078_*.sql`（列设计）。完成后跑全部门禁，并单独跑一次检索评测确认编辑后召回跟着变了。

---

## 6. 阶段四：引用与来源呈现升级

> **状态 ✅ 4A/4B 均已闭合**（`9b9040c` `f2a63cc` + `b65bfb1`）。4A：`window_close` 收尾事件在 `query_understand.py` / `corrective_grade.py` 共 10 处发射，thinking 事件带 `duration_ms/count/doc_count`，前端收拢为「问题理解」「检索」双窗，错误路径标 error。4B：前端三机制齐备（占位符换出 / 残缺标记隐藏 / `stableHtml` 原地 morph），悬停浮层 80ms/120ms 防抖 + Teleport。**09-28 补 `chunk_id` 主链路透传**：`pgvector_store.search()` → `build_source_entry` → 全部 `sources_list`（含 pipeline）→ `Source` 契约，「展开全文」可回查切片原文。

拆成两件可独立交付的：

### 4A · 过程进度收束（低成本，先做）
- 保持我们现有的细粒度决策事件（信息量比 WeKnora 高，不要为了对齐而砍），只做三件事：
  1. 把事件**收拢成两个可视窗口**：问题理解、检索（含重排/合并/截断），窗口内可展开看细节；
  2. **每阶段带耗时和结果计数**（后端在 thinking 事件里补 `duration_ms`、`count`、`doc_count`）；
  3. **出错/短路也必须关闭窗口**——这是硬性语义：任何终止路径都要补发一条收尾事件，否则前端转圈不停。参照 `WeKnora/internal/application/service/chat_pipeline/progress.go:75-77`。
- 历史回放：刷新后这些阶段状态要能从已存的 sources/thinking 里重新合成（我们现在已经存 thinking，核对是否有耗时字段即可）。

### 4B · 引用可交互升级（中成本，依赖阶段二）
- 现状已不错：`[来源N]` 会被渲染成可点徽章（`ChatView._applySourceBadges` 约 596-600 行）并滚动高亮来源卡（`ChatView.vue` 约 643-658 行）。
- 升级目标：**悬停即出该切片原文预览的浮层** + **来源抽屉里就地展开全文**。
- 必须照抄的三个机制（否则会在流式过程中出鬼影或闪断）：
  1. **占位符换出再还原**：把引用标记替换成不会被 Markdown 解析器破坏的占位符，解析完再还原 → `citationMarkdown.ts:204-225`；
  2. **隐藏半截标记**：流式中末尾出现残缺标记时先藏起来 → 同文件 `:18-32`；
  3. **原地 DOM morph 而非重设 innerHTML**，避免悬浮卡因重渲染被卸载 → `directives/stableHtml.ts`。
- 悬停/点击防抖：入 80ms、出 120ms 宽限（检查两处元素是否都非 hover 才关）→ `useChatCitationPopover.ts:139-178`。浮层用 `Teleport` 到 body + `getBoundingClientRect` 定位 + 视口夹取。
- **是否改用标签协议（`<kb chunk_id=.../>`）**：这是 WeKnora 让引用与 UUID 解耦的做法（`internal/modelcontext/citations.go`）。**本计划建议先不换**——我们的 `[来源N]` 加"序号→UUID 映射表"已经能用，换协议的收益要在模型稳定性上验证。列为可选实验项：若要试，先在评测里做 A/B，比较引用错指率。
- 后端需要补：来源条目里带**稳定的 chunk_id**（现在给的是文档级信息 + 序号），以及一个"按 chunk_id 取原文"的轻接口（阶段三已有 chunk 详情接口，可复用）。

**验收**：前端测试覆盖"流式中途出现残缺标记不闪现原始符号"、"悬停出浮层且点击进抽屉"、"阶段窗口在错误路径下被关闭"；手工验证长回答连续流式时悬浮卡不闪断。

**执行提示词（阶段四）**
> 分两步做。4A：把聊天里的 RAG 阶段事件在**前端**收拢为"问题理解""检索"两个可展开窗口，保留现有细粒度信息作为窗口内明细；后端在对应事件里补 `duration_ms` 与结果计数；并强制实现"任何异常/短路/无结果路径都必须补发一条关闭事件"，为这条语义写测试。4B：给引用标记加悬停浮层（显示该切片原文与页码）和来源抽屉就地展开。前端必须实现三个机制：引用标记先换成占位符再跑 markdown 解析、解析后还原；流式期间隐藏残缺标记；用原地 DOM 更新指令而不是 innerHTML 替换。悬浮层用 Teleport + rect 定位，入 80ms / 出 120ms 防抖。后端把来源条目补上稳定 chunk_id（复用阶段三的切片详情接口取原文），**暂不更换 `[来源N]` 引用协议**，如要更换先与我讨论并做引用错指率的 A/B。参照只读：`WeKnora/frontend/src/utils/citationMarkdown.ts`、`directives/stableHtml.ts`、`composables/useChatCitationPopover.ts`、`components/ChatReferencesDrawer.vue`、`internal/application/service/chat_pipeline/progress.go`。**不许粘贴其代码**，用 Element Plus + Tailwind + 我们现有的 markdown-it 重写。

---

## 7. 阶段五：输入框升级（用户最想要的第二件）

> **状态 ✅ 5.1～5.6 全部交付**（`1c6c07c` `d9ddc1f` + `e090c32` + `71a06d3`）。5.1 ScopeChips 胶囊 + 课程维度 + IME 守卫；5.2 **追问建议已补**（`POST /api/chat/suggest-followups` + 回答下可点芯片，计入用量）；5.3 **模型胶囊已接线**（`@select` → `modelOverride` → `llm_config`，`ModelChip` 读真实 `context_window`）；5.4 停止保半成品；5.5 断线续流；5.6 附件仅 uploading 禁发。

按性价比排，前三件互不依赖，可并行：

| 项 | 内容 | 前端改动点 | 后端依赖 | 成本 |
|---|---|---|---|---|
| 5.1 胶囊化范围选择 | 把"文档勾选行"升级成输入框上方的胶囊行；空文本时退格弹出最后一个胶囊；候选可 `@` 唤起并**增加课程维度** | `ChatInput.vue`、`DocumentPicker.vue` → 新组件 `ScopeChips.vue` | 无（复用现有 doc_ids + 课程关联接口） | 低 |
| 5.2 追问建议 | 每条回答下渲染 3 条可点建议，点击即发送 | `ChatMessageItem.vue` + `ChatView.vue` | 新增"为某条回答生成建议问题"接口（一次 LLM 调用，**要计入用量统计** `usage_service`） | 中 |
| 5.3 模型胶囊 | 输入条上直接切模型，显示当前上下文窗口余量；记住上次选择 | `ChatInput.vue`（现在只有跳到 `/model-config` 的链接） | 已有配置接口；需返回模型上下文上限 | 低 |
| 5.4 停止语义确认 | 停止=中断 + 服务端标记，部分回答干净落库 | 已有（`chat.ts` AbortError 分支保留部分回答） | 复核 SSE 中断后落库路径 | 低 |
| 5.5 断线续流 | 刷新后若最后一条是"未完成"，重连继续收流 | `ChatView` 挂载逻辑 + `chat.ts` | **需要服务端支持按消息重放/续流**，成本最高，放最后 | 高 |
| 5.6 聊天附件 | 图片/文档临时上传，两阶段状态；**只有"上传中"禁发**，解析可后台继续 | `ChatInput.vue` 新增附件行 | 需要"会话级临时附件"接口 + 解析状态查询 | 中-高 |

**IME 坑（5.1 必修）**：检测 `@` 触发前必须判断输入法组合态（`compositionstart/end`），否则中文输入过程中会误弹选择器。我们已经处理过 Enter 的 `isComposing`（`ChatInput.vue:99`），同样的守卫要加到 `@` 检测上。

**执行提示词（阶段五 5.1/5.3）**
> 升级 Study Copilot 的聊天输入框。(1) 把现在的文档勾选改造成输入框上方的"范围胶囊行"：选中项以胶囊显示在 textarea 上方、可单个删除，textarea 为空时按退格弹出最后一个胶囊，并增加"课程"这一维度作为范围（课程-文档关联接口已存在）。支持在光标处输入 `@` 唤起候选弹层，弹层按 知识库/文档/课程 分组、可键盘上下回车选择；**`@` 检测必须先判断输入法组合态**（参照 `ChatInput.vue` 里 Enter 已做的 `isComposing` 守卫）。(2) 在输入条右侧加"模型胶囊"：直接切换当前会话使用的模型、显示该模型的上下文窗口余量、把选择记到 localStorage，不再只跳转到 `/model-config`。约束：不要引入新依赖、不要换组件库、把新交互拆成独立组件而不是继续加大 `ChatView.vue`（它已 1627 行）。每项都要补前端测试：胶囊退格弹出、IME 组合态不误弹、模型选择持久化。参照只读：`WeKnora/frontend/src/components/Input-field.vue` 的 mention→chip 与 model chip 部分（3844 行，只看相关段落），**禁止复制代码**。

---

## 8. 阶段六：文档预览与长列表（收尾项，可独立排期）

> **状态 ✅ 6A 部分交付，6B/6C 明确未做**（`f2a63cc`）。`utils/filePreview.ts` 已按扩展名 + MIME + 轻量嗅探（PK zip→xlsx）分派类型，CSV/TSV 走表格渲染；Excel 重表格与三态全文视图按 `docs/compose/spec/weknora-ui-upgrade.md` §S3 记为"可再迭代"，6.3 虚拟滚动维持"观察后再做"。

- **6.1 Excel/CSV 在线预览**：我们已有 PDF/图片/Markdown 的 blob 预览（`DocumentView.vue` 约 230-284 行），补表格渲染。参照 `WeKnora/frontend/src/utils/filePreview.ts` 的分类思路（按嗅探类型分派），但**要评估新增依赖的重量**再决定。
- **6.2 三态文档视图**（切片 / 合并全文 / 原文预览 一个视图内切换）：依赖阶段二的坐标。没有坐标就只能做文本重叠加容差猜测（WeKnora 自己承认这是将就，见 `doc-content.vue:567-587`）。
- **6.3 虚拟滚动**：观察后再做。我们目前分页够用；WeKnora 也只在 wiki 浏览器用了它，聊天主列表没上。

---

## 9. 明确不做（被问到就给理由，别默默实现）

| 不做 | 理由 |
|---|---|
| 目录树 | 课程空间已经占据"组织资料"这一轴，两套并存的层级会让信息架构打架 |
| 多工作区 / 成员 / RBAC / 审计 | 单用户本地产品，属于参照项目的企业侧形态 |
| FAQ 问答对库的录入管理界面 | 参照实现里那一块约 5650 行，是为团队协作设计的；我们用测验功能替代 |
| IM 渠道、网站嵌入挂件、分享令牌 | 发布形态不同 |
| 解析阶段时间线全家桶（含 attempt 历史、子 span 表） | 我们只有三个阶段、单用户、已有任务表与 SSE；粗粒度状态加每阶段起止即可覆盖八成效用。若将来真要做，硬前提是先给文档加 attempt 计数 |
| 技能沙箱、Wiki 自动生成、知识图谱、多向量库抽象 | 根 AGENTS.md「第三方归属」与该产品的吸收账本里已列为"明确不做" |
| Element Plus → TDesign | 全量 UI 重写，收益只有观感 |

---

## 10. 里程碑、依赖与工作量

```
P0 (F1/F2 缺陷)  ──► 阶段一 分块预览 ──► 阶段二 坐标与原文副本 ──┬─► 阶段三 切片编辑/版本
                                         （含全量重跑，需确认）   ├─► 阶段四B 引用浮层
                                                                 └─► 阶段六B 三态文档视图
        阶段四A 进度收束 ──（独立，可与上面并行）
        阶段五 输入框升级 ──（5.1/5.3/5.4 独立并行；5.5 断线续流、5.6 附件 各自独立且最贵）
        阶段六A Excel 预览 ──（独立）
```

| 阶段 | 规模 | 风险 | 不可逆动作 | 验收状态（2026-09-28） |
|---|---|---|---|---|
| P0 | S | 低 | 无 | ✅ `d411263` `c507346` |
| 一 分块预览 | M | 低 | 无 | ✅ `19011a9` |
| 二 坐标地基 | M | **中-高**（改变向量输入） | **全量重跑入库** | ✅ `1c6c07c` `a50c42b` `b65bfb1` — 清理+重跑+前后探针对比已补 |
| 三 切片编辑 | L | 中（重嵌入一致性） | 无（可 downgrade） | ✅ `875f4b7` `b65bfb1` — 不变量语义定清（原点区间）+ 变长测试 |
| 四A 进度收束 | S | 低 | 无 | ✅ `9b9040c` |
| 四B 引用浮层 | M | 中（流式渲染易出鬼影） | 无 | ✅ `f2a63cc` `b65bfb1` — `chunk_id` 主链路已透传 |
| 五 输入框 | M（5.5/5.6 各 L） | 低-中 | 无 | ✅ `1c6c07c` `d9ddc1f` `e090c32` `71a06d3` — 5.1～5.6 全交付 |
| 六 预览与三态 | M | 低 | 无 | ✅ 6A（CSV/嗅探）；6B/6C 按计划留待迭代 |

**关键路径**：阶段二。它是唯一"只能靠重跑获得、且越晚越贵"的一步，也是三件功能的地基。若资源有限，做完 P0 + 阶段一 + 阶段四A 就已经覆盖"用户看得见、成本最低"的三处改进。

---

## 11. 全程验证清单（最后一个 Agent 或我来收尾时用）

> 2026-09-28 三次复核勾对（09-25 首核记录保留要点）。

1. ✅ **门禁全量实测（09-28）**：后端 `pytest` 816 passed / cov 74.94% / ruff 0 / mypy 0（104 文件）；`alembic current == heads == c8d9e0f1a2b3`；前端 `vitest` 410 passed / `vue-tsc` 0 / `npm run build` 通过。
2. ✅ **坐标不变量**：等式在等长编辑下成立；变长路径已补测试并定清语义（原点区间，等式条件成立）。
3. ✅ `test_preview_chunking.py` 含"调用后 `document_chunks` 行数不变 + `embedder.embed_texts` 未被调用"断言。
4. ✅ 后端 `test_progress_windows.py` 5 例 + 前端「错误路径下阶段窗口必须关闭」等用例。
5. ✅ **前后评测对比已补（09-28）**：`evaluation/results/probe-before/after-20260928.json` + `reindex-compare-20260928.md`（hit@5=100%，重复噪声清零）；`backend/evaluation/` 已入库。
6. ✅ `WeKnora/` 被 `.gitignore:116` 排除且未被 force-add。
7. ✅ `grep -rn "WeKnora/" frontend/src backend/app` 零命中；同名前端文件均为自研重写。

---

## 12. 验收结论与未闭合项（2026-09-25 记 / **2026-09-28 收尾**）

**主体已落地**：P0 与阶段一～六；后端 816 测试函数（计划基线 634），前端 410 用例（基线 298）。计划 §9「明确不做」的边界守住了，没有偷跑目录树、多租户、TDesign 迁移。

### 原五处未闭合项 —— 现状

| # | 项 | 现状 | 收尾 |
|---|---|---|---|
| 1 | 主链路缺 `chunk_id` | ✅ **已修** | `pgvector_store.search()` 透传 `id/chunk_id`；`build_source_entry` 统一 6 处 `sources_list` + pipeline；`Source` 契约补字段（`b65bfb1`） |
| 2 | 5.3 模型胶囊是装饰 | ✅ **已修** | `@select` → `modelOverride` → `llm_config`；`ModelChip` 读真实 `context_window`（`e090c32`） |
| 3 | 阶段二重跑无前后对比 | ✅ **已补** | 清理脏行后重跑，`retrieval_probe.py` 前后对比：hit@5=100%、重复噪声清零、`ready_mismatch=0`（`b65bfb1`） |
| 4 | 坐标不变量条件成立 | ✅ **语义定清** | 坐标=**原点区间**；等长编辑维持等式，变长后不成立属预期；补变长路径测试（不置 NULL——否则打断父块重建 splice） |
| 5 | 进度文档口径 | ✅ **已同步** | 本文件 v1.3 + `docs/compose/spec/weknora-ui-upgrade.md` 均更新为 09-28 口径 |

**补交付**：5.2 追问建议（`71a06d3`）——原先记为"未做"，现已实现。

### 顺带记录（非计划缺陷）

- §7 要求"不要继续加大 ChatView / ChatMessageItem"，实际 `ChatView.vue` 1627→1774、`ChatMessageItem.vue` 787→1118。对话框类都按要求拆了独立组件。
- vitest 有 `Failed to resolve component: el-*` 告警（已知噪声，不影响结论）。

---

## 13. 数据事故与处置（2026-09-25 发现 / **2026-09-28 已处置**）

**结论**：代码从未需要回退；数据侧事故已清。

### 13.1 本地库未升级到最新迁移 → ✅ 已修

`alembic current == alembic heads == c8d9e0f1a2b3`，阶段三在真实库上可用。§1.4 门禁已补「`current` 必须等于 `heads`」。

### 13.2 全量重跑未删旧行 → 索引重复爆炸 → ✅ 已处置

**根因已堵**（`e090c32`）：`_do_process_document()` 先删该文档旧 chunk 再重建，`reindex_all` 幂等。

**存量已清**（2026-09-28，`b65bfb1`）：

| 步骤 | 结果 |
|---|---|
| 备份 `document_chunks` | `backups/document_chunks_pre_cleanup_20260928.sql`（3.1GB） |
| `cleanup_duplicate_chunks.py --apply` | 删 stale 10463 + dup 150，resync 12 篇 `chunk_count` |
| `reindex_all.py` 重跑 | ok=16 / fail=12 |
| 不变量 | `ready_mismatch=0`；eGMP 大文档 8770 行(约5副本) → **1754 单副本** |
| 前后探针对比 | hit@5 保持 100%；top-k 重复副本清零（`evaluation/results/reindex-compare-20260928.md`） |

**fail=12 归因**：11 篇空 `t.txt`/`entangle.txt` 测试残留（**已 purge**）+ `rag-stress-corpus.pdf` 源文件丢失（**仍待恢复**）。

### 13.3 处置清单勾对

1. ✅ `alembic upgrade head`
2. ✅ `_do_process_document` 先删后建（比改脚本更彻底）
3. ✅ 一次性清理 stale + 重复行（先备份）
4. ✅ 重跑 + 前后评测对比
5. ⚠️ error 文档：残留已 purge；**`rag-stress-corpus.pdf` 待恢复源文件后 reprocess**
6. ✅ `/health` 增加 `chunk_count_sync` 常驻哨兵

---

## 14. 2026-09-28 收尾记录

**提交**：`b65bfb1`（计划收尾：chunk_id / 坐标语义 / 健康哨兵 / 清理与评测）、`71a06d3`（5.2 追问建议）。

**门禁实测**：后端 816 passed / cov 74.94% / ruff 0 / mypy 0 / alembic 单 head 且库在 head；前端 410 passed / vue-tsc 0 / build 通过。

**剩余**：
1. 恢复 `rag-stress-corpus.pdf` 源文件（`uploads/f1a3f4aa-.../e24dbb11-....pdf`）后单独 reprocess
2. 6B 三态全文视图 / 6C 虚拟滚动（计划明确留待迭代）
3. hierarchical 子块列级坐标（增强项，现坐标在 metadata）

**执行提示词（13.1 + 13.2）**
> 工作仓库：`/Users/wweiqi/Desktop/update plan/Study-copilot`，只改 `backend/` 与 `frontend/`；其下 `WeKnora/` 是只读参照，禁止修改、禁止复制代码。任务：修复全量重跑造成的索引重复。步骤——(1) 对本地 PostgreSQL 执行 `cd backend && .venv/bin/python -m alembic upgrade head`，并确认 `alembic current` 与 `alembic heads` 一致；(2) 修改 `backend/scripts/reindex_all.py`：每篇文档在重建前必须先删除其现有的 `document_chunks` 行，**复用 `app/services/document_service.py` 中 `reprocess_document()` 已有的删除逻辑，不要复制 SQL**；脚本结束时逐文档核对"实际行数 == documents.chunk_count"并打印不一致清单；(3) 写一个一次性清理脚本，删除 `char_start IS NULL` 的历史行与按 `(document_id, content)` 判定的重复行，执行前先备份 `document_chunks`，并支持只处理单篇文档的 dry-run 模式；(4) 清理后用修好的脚本重跑一次全量，重跑前与重跑后各出一份同口径检索评测报告并对比；(5) 新增一条不变量检查（`/health` 或测试）：每篇文档的 `document_chunks` 实际行数必须等于 `documents.chunk_count`。当前实测基线：ready 文档实际 9830 行 vs 记录 1802，其中 9613 行无坐标。完成后把六个数字（清理前后行数、重跑 ok/fail、评测对比结论）报给我。
