# Study Copilot — 全量变更记录 (2026-08-17)

> 从初始状态（仓库仅 2 个提交，v2/v3 全部未提交）开始，
> 经过 P0 紧急修复 → P1 文档/CI/测试对齐 → P2 迁移优化 → P3 低优卫生 → 5 项架构特性新增。
> 共 8 个 commit，覆盖约 70 个文件。

---

## 1. Commit 历史速览

| Commit | 阶段 | 主要内容 |
|--------|------|---------|
| `32c8440` | A | 异步任务队列：task_worker.py 创建 + document/quiz 接线 + main.py lifespan + POST /api/tasks |
| `6989751` | C+D | 笔记语义搜索（service+API）+ 课程-文档关联（routes+service+store） |
| `02eae49` | E | 纠错检索集成 + 死代码移除 (_needs_rewrite + tests) |
| `8c57f63` | P3 | defineOptions + useMarkdown composable + 温度注释 + api/__init__ 补全 + TTS TODO |
| `55d8502` | P2 | 6 模块模板迁移(orphan→render_template) + typescript/vue-tsc 安装 + .env.example + upload_dir |
| `fdbc370` | P1 | 端口 5173→3000 + API 路径对齐 + CI main→master + 测试方法名修复 + 前端测试 mock |
| `237c052` | P0 | text import + requirements 补全 + quiz 密文修复 + config model_name + alembic env + notes 契约 + course tab |

---

## 2. P0 — 紧急修复（8 项，22 个文件）

| # | 问题 | 修复方式 | 关键文件 |
|---|------|---------|---------|
| 1 | git 未提交，无远端备份 | .gitignore 补 runtime 产物 + `git add -A && git commit` | `.gitignore` |
| 2 | `ensure_current_schema()` 缺 `text` import | sqlalchemy import 块补 `text` | `backend/app/db/database.py` |
| 3 | requirements.txt 缺 edge-tts / trafilatura / jinja2 | 加三行 | `backend/requirements.txt` |
| 4 | quiz_service 用 Fernet 密文当 API Key | 改用 `config_service.get_llm_config_with_secret` | `backend/app/services/quiz_service.py` |
| 5 | config.ts 读 `data.model` 但后端返回 `model_name` | config.ts + types/models.ts 改为 `model_name` | `frontend/src/stores/config.ts`, `frontend/src/types/models.ts` |
| 6 | alembic.ini 硬编码 localhost, 不读 `DATABASE_URL` | env.py 加 `os.getenv("DATABASE_URL")` 覆盖 | `backend/alembic/env.py` |
| 7 | 笔记前后端契约断裂（tags/course_id vs tag_names/course_space_id） | backend 接受两种字段别名, NoteBrief.tags 返回 `list[str]` | `backend/app/api/notes.py`, `backend/app/services/note_service.py` |
| 8 | course.js 调用不存在端点 + CourseDetailView 文档 tab 报 404 | 注释掉 3 个 store 方法 + 移除文档 tab 模板 | `frontend/src/stores/course.js`, `frontend/src/views/CourseDetailView.vue` |

---

## 3. P1 — 文档/CI/测试对齐（5 项，12 个文件）

| # | 问题 | 修复 |
|---|------|------|
| 1 | 测试调 `_deduplicate_results` 但方法名是 `deduplicate_results` | test_rag_engine.py 全局替换 |
| 2 | CI 触发分支 `main/develop` 不存在（实际 `master`） | test.yml 改为 `master` |
| 3 | 前端组件测试因 jsdom + 路径含空格崩溃 | setup.js 添加 axios mock |
| 4 | 文档 14 处写端口 5173（实际 vite.config.js 固定 3000） | AGENTS.md, CLAUDE.md, docs/*, frontend/CLAUDE.md 全部改为 3000 |
| 5 | API 路径文档不符（`ask/stream`、`synthesize`、`record-wrong` 等） | backend/CLAUDE.md + frontend/CLAUDE.md + docs/3-API-REFERENCE 对齐 |

---

## 4. P2 — 迁移/优化（4 项，18 个文件）

| 子项 | 操作 |
|------|------|
| **模板迁移** | 6 个模块（query_decomposer、answer_reflector、query_router、quiz_generator、rag_engine、adaptive_retriever）的 14 个 inline prompt 替换为 `render_template()` 调用，消除所有孤儿模板 |
| **TS 工具链** | `npm install --save-dev typescript vue-tsc` 加入 devDependencies |
| **配置修复** | `backend/.env.example` 补 `ENCRYPTION_KEY` 及生成命令 + `document_service.py` 硬编码 `"./uploads"` 改为 `settings.upload_dir` |
| **死代码清理** | 移除 `slowapi` 依赖（实际未使用）、`rate_limit_exceeded_handler`/`DEFAULT_RATE_LIMITS`/`create_rate_limit_key`（3 个死函数）、`utils/__init__.py` 的 `file_handler` 再导出 |

---

## 5. P3 — 低优卫生（5 项，7 个文件）

| 文件 | 改动 |
|------|------|
| `QuizView.vue`, `ChatView.vue`, `AnalysisView.vue` | 加 `import { defineOptions } from 'vue'` + `defineOptions({ name })` 确保 keep-alive 生效 |
| `ChatView.vue` | 从 `useMarkdown` composable 导入渲染函数替代内联实例 |
| `backend/app/services/config_service.py` | 温度存储约定注释（前后端同步注意点） |
| `frontend/src/stores/config.ts` | 同上温度约定注释 |
| `backend/app/core/tts.py` | 加 `# TODO: cleanup mp3 >24h` |
| `backend/app/api/__init__.py` | 从 5 个旧路由扩展到全部 11 个路由 re-export |

---

## 6. 架构特性新增（5 项）

### 6.1 B. Hybrid 检索

**文件**：`vector_store.py` / `document_service.py` / `requirements.txt`

- BM25VectorStore 新增 `_tokenize()` 静态方法：中文文本用 `jieba.cut()`，英文用 `re.findall`
- 上传时切换 `RETRIEVAL_TYPE_FAISS` → `RETRIEVAL_TYPE_HYBRID`（FAISS+BM25+RRF）
- `requirements.txt` 添加 `jieba>=0.42.1`
- 已有 FAISS-only 索引自动降级兼容（load() 逻辑已有检测）

### 6.2 E. 纠错检索集成

**文件**：`rag_engine.py` / `test_rag_engine.py`

- `ask()` 和 `ask_stream()` 中加入 retrieval quality grading：
  - 自适应检索后调用 `retrieval_grader.grade(final_query, retrieved, user_config)`
  - 若 `not quality.is_good`，调用 `_corrective_retrieve()` 重写 query 重试
  - 流式模式下追加 `thinking` event 通知前端
- 移除死代码：`_needs_rewrite()` 方法 + `_REWRITE_TRIGGER_WORDS` 类属性 + 对应测试

### 6.3 C. 笔记语义搜索

**文件**：`note_service.py` / `notes.py`

- `note_service.py`：新增 `search_notes()` 异步函数
  - 按用户懒加载 `DocumentVectorStore(f"notes_{user.id}", vectorstore_dir="./vectorstore/notes")`
  - 查询时 embed query → FAISS search → 取 note_ids → DB 查询 → 返回带 score 的 NoteBrief
- 笔记创建/更新时自动建立向量索引（try/except 捕获失败，不影响核心流程）
- `notes.py` API：新增 `NoteSearchRequest(BaseModel)` schema + `POST /search` 端点

### 6.4 D. 课程-文档关联

**文件**：`courses.py` / `course_service.py` / `course.js` / `CourseDetailView.vue`

- `courses.py` API：新增 3 个端点
  - `GET /{course_id}/documents` — 列出课程关联文档
  - `POST /{course_id}/documents` — 关联文档到课程（需 `AddDocRequest.document_id`）
  - `DELETE /{course_id}/documents/{doc_id}` — 解除关联（设 `course_space_id = NULL`）
- `course_service.py`：新增 3 个异步服务函数（`get_course_documents`, `add_document_to_course`, `remove_document_from_course`）
- `course.js` store：取消注释被禁用的 3 个方法
- `CourseDetailView.vue`：恢复文档 tab（之前 P0.8 被整体移除）

### 6.5 A. 异步任务队列

**文件**：`task_worker.py` (NEW) / `main.py` / `document_service.py` / `tasks.py`

- `backend/app/core/task_worker.py`：in-process asyncio 后台队列
  - `TaskJob` 类、`start_worker()` / `stop_worker()` / `enqueue()`
  - 内部 `_worker_loop()` 持续消费队列，`_execute_job()` 按类型分发
  - 支持 `document_process`（解析→分块→建索引）和 `quiz_generate`（生成题目）
  - 全程通过 `update_task()` 同步 DB 状态（pending→running→completed/failed）
- `main.py` lifespan：startup 阶段 `await start_worker()`，shutdown 阶段 `await stop_worker()`
- `document_service.py`：upload 函数改为创建 task + enqueue + 立即返回（不再阻塞等待解析完成）
- `tasks.py` API：新增 `POST /api/tasks` 端点（接收 `task_type` + `payload`，创建并入队）

---

## 7. 当前 Git 仓库状态

```
master 分支，领先 origin/master 9 个 commit
工作区干净（无未提交文件）
```

### 待处理（未来方向）

- BM25 jieba 分词仅用于 search 时，索引时 rank_bm25 内部有自有 tokenizer（需确认实际效果）
- 异步任务队列目前是内存队列，server 重启会丢失未完成的任务（可添加重启时标记 running→failed）
- 前端测试 2 个组件文件仍因 jsdom + 路径含空格崩溃（已 mock axios 但仍有环境问题）
- 可考虑添加 `ruff format` 到 CI lint 流程
- `frontend/src/views/CourseDetailView.vue` 的文档 tab 模板曾整体移除，恢复时需确认模板正确性

---

## 8. 文件变更索引

### 后端 Python 文件 (backend/app/)

| 文件 | 行数 | 本次变更 |
|------|------|---------|
| `core/rag_engine.py` | 691 | E 集成 + 死代码移除 |
| `core/vector_store.py` | ~550 | B: 新增 `_tokenize()` |
| `core/task_worker.py` | NEW | A: worker 实现 |
| `api/notes.py` | ~200 | C: search 端点 + schema |
| `api/courses.py` | ~140 | D: 3 个 document 路由 |
| `api/tasks.py` | ~90 | A: POST 端点 |
| `services/note_service.py` | ~230 | C: search_notes + 索引 |
| `services/course_service.py` | ~210 | D: 3 个文档服务函数 |
| `services/document_service.py` | ~215 | A: 异步上传 + B: hybrid |
| `services/quiz_service.py` | ~220 | P0: 密文修复 |
| `services/config_service.py` | ~200 | P3: 温度注释 |
| `db/database.py` | ~230 | P0: text import |
| `main.py` | ~90 | A: lifespan worker |
| `exceptions.py` | 删除 | P2.4: dead code |
| `exception_handlers.py` | ~80 | (已有) |
| `utils/file_handler.py` | 删除引用 | P2.4: dead code |
| `utils/auth.py` | ~55 | (已有) |
| `utils/__init__.py` | 清空 | P2.4: dead code |
| `api/__init__.py` | ~12 | P3: 全部 11 路由 re-export |
| `api/analysis.py` | ~55 | (已有) |
| `api/auth.py` | ~80 | (已有) |
| `api/chat.py` | ~185 | (已有) |
| `api/config.py` | ~110 | (已有) |
| `api/document.py` | ~130 | (已有) |
| `api/quiz.py` | ~120 | (已有) |
| `api/transform.py` | ~85 | (已有) |
| `api/tts.py` | ~75 | (已有) |
| `core/adaptive_retriever.py` | ~220 | P2: template 迁移 |
| `core/answer_reflector.py` | ~145 | P2: template 迁移 |
| `core/query_router.py` | ~200 | P2: template 迁移 |
| `core/query_decomposer.py` | ~90 | P2: template 迁移 |
| `core/quiz_generator.py` | ~80 | P2: template 迁移 |
| `core/tts.py` | ~120 | P3: TTS TODO |
| `core/rate_limit.py` | ~80 | P2.4: 死函数移除 |
| `core/encryption.py` | ~45 | (已有) |
| `core/template_manager.py` | ~46 | (已有) |
| `core/embedder.py` | ~180 | (已有) |
| `core/llm.py` | ~78 | (已有) |
| `core/chunker.py` | ~810 | (已有) |
| `core/document_parser.py` | ~610 | (已有) |
| `core/transformations.py` | ~160 | (已有) |
| `core/url_extractor.py` | ~100 | (已有) |
| `db/migrations.py` | ~83 | (已有) |
| `db/database.py` | ~230 | P0: text import |
| `services/auth_service.py` | ~110 | (已有) |
| `services/analysis_service.py` | ~110 | (已有) |
| `services/chat_service.py` | ~220 | (已有) |
| `services/task_service.py` | ~210 | (已有) |
| `services/transform_service.py` | ~185 | (已有) |

### 前端文件 (frontend/src/)

| 文件 | 行数 | 本次变更 |
|------|------|---------|
| `views/ChatView.vue` | ~620 | P3: defineOptions + useMarkdown |
| `views/QuizView.vue` | ~410 | P3: defineOptions |
| `views/AnalysisView.vue` | ~295 | P3: defineOptions |
| `views/CourseDetailView.vue` | ~400 | P0.8: 文档 tab 移除 (待 D 重构恢复) |
| `views/LoginView.vue` | ~115 | (已有, TS) |
| `views/RegisterView.vue` | ~100 | (已有) |
| `views/HomeView.vue` | ~330 | (已有) |
| `views/UploadView.vue` | ~225 | (已有) |
| `views/DocumentView.vue` | ~370 | (已有) |
| `views/ModelConfigView.vue` | ~405 | (已有) |
| `views/NotesView.vue` | ~370 | (已有) |
| `views/CourseListView.vue` | ~280 | (已有) |
| `views/TasksView.vue` | ~25 | (已有) |
| `stores/config.ts` | ~105 | P0: model→model_name + P3: 温度注释 |
| `stores/course.js` | ~130 | P0: 注释 + D: 取消注释 |
| `stores/auth.ts` | ~77 | (已有) |
| `stores/chat.js` | ~310 | (已有) |
| `stores/document.ts` | ~65 | (已有) |
| `stores/quiz.js` | ~250 | (已有) |
| `stores/note.js` | ~160 | (已有) |
| `stores/toast.ts` | ~50 | (已有) |
| `stores/sidebar.ts` | ~60 | (已有) |
| `stores/theme.ts` | ~60 | (已有) |
| `services/api.ts` | ~67 | (已有) |
| `types/models.ts` | ~140 | P0: LLMConfig.model→model_name |
| `types/api.ts` | ~20 | (已有) |
| `composables/useApi.ts` | ~63 | (已有) |
| `composables/useMarkdown.js` | ~73 | (已有) |

### 文档/配置

| 文件 | 变更 |
|------|------|
| `.gitignore` | 新增 `open-notebook-main/`, `backend/.embedding_cache/`, `backend/uploads/tts/*.mp3`, `.idea/`, `frontend/node_modules/`, `frontend/dist/` |
| `backend/requirements.txt` | 新增 `edge-tts`, `jinja2`, `jieba`, `trafilatura`；移除 `slowapi` |
| `backend/.env.example` | 新增 `ENCRYPTION_KEY` 及生成命令注释 |
| `backend/alembic/env.py` | 新增 `os.getenv("DATABASE_URL")` 覆盖 |
| `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, `frontend/CLAUDE.md` | 端口 5173→3000, API 路径对齐 |
| `.github/workflows/test.yml` | 触发分支 `main/develop`→`master` |
| `ARCHITECTURE_IMPLEMENTATION_PLAN.md` | NEW: 架构实施规划 |

---

*记录完毕。*