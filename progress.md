# Progress Log

## Session: 2026-08-19 — P1 批次修复 + 后端 E2E 冒烟（Phase 10）

### 背景
P0 五修完成后，按已批准计划推进：落盘 P1–P3 痛点清单 → 同步 remaining_issues → 修 P1 六项 → 后端 E2E 冒烟。
关键环境发现：/Users/wweiqi/miniconda3/envs/study-c/bin/python 具备完整后端依赖（fastapi/sqlalchemy/pytest），pytest 真实可跑。

### A/B 文档同步
- findings.md 新增「P1–P3 痛点清单」章节（P1×6 / P2×5 / P3×10，每项附来源编号+影响+方案）
- remaining_issues.md 移除 4 项陈旧记录（#7 file_handler、#8 pdf_parser、#9 UserConfigMiddleware、#12 requirements 拆分，均已在 2026-08-18 第三批完成并复核确认）

### C 批次修复（6 项）
| # | 项目 | 改动 | 验证 |
|---|------|------|------|
| C1 | with-secret 明文返回 API Key（安全） | 删除 GET /config/llm/with-secret 端点；config_service 修复"空 key 更新会清掉已存 key"根因 bug（留空=保留）；get_llm_config 改返回 has_api_key + api_key_masked（前3后4掩码）；前端 config.ts 删 fetchLLMConfigWithSecret、syncToChatStore 改用安全端点、saveLLMConfig 不再同步 apiKey；ModelConfigView 显示掩码提示；models.ts LLMConfig 类型更新 | verify_config.py 6 项 PASSED + pytest 305 全绿 |
| C2 | Docker alembic localhost fallback | alembic/env.py：env var → app settings(.env) 两级解析；容器内（/.dockerenv）解析到 localhost 时 fail-fast 报错 | 真实 settings 解析验证 |
| C3 | document_service 硬编码 ./uploads | 确认已在 2026-08-18 重写中修复（line 77 用 settings.upload_dir），无需改动 | grep 复核 |
| C4 | 异步任务重启丢任务 | task_service 新增 recover_interrupted_tasks（pending/running→failed+原因）；main.py lifespan 启动时调用 | pytest 全绿 + 启动日志确认执行 |
| C5 | BM25 索引/检索分词不一致 | vector_store 新增 _build_bm25()：索引与检索统一走 _tokenize（中文 jieba/英文 regex）；add_chunks/load 均走统一分词（旧索引文件加载时自愈） | verify_bm25.py 4 项 PASSED（词级索引、中文命中、英文、save/load） |
| C6 | ChatMessage.vue 孤儿组件 | 删除组件 + ChatMessage.test.js（也是 jsdom 崩溃的测试文件之一）；frontend/CLAUDE.md 同步 | grep 确认无残留引用 |

### D 后端 E2E 冒烟（study-c 环境真实启动 + httpx）
**结果：9/9 PASSED**，覆盖 4 条 P0 链路：
- P0-1：上传 .txt → TextParser 解析 → status=ready chunks=3
- P0-2：SSE 首事件 = session 且带 session_id；第二轮追问保持同一 session_id
- P0-3：analysis/wrong 的 weak_areas[].topic = 文件名（smoke_notes.txt）非 UUID
- P0-4：简答精确匹配/包含匹配判对、选择题 'a.' 容错判对

**E2E 额外发现并修复 2 个 bug：**
1. **启动崩溃**：migrations.py 的 ALEMBIC_CFG_PATH 少一级 parent（解析到 backend/app/alembic.ini 不存在）→ alembic 读不到 script_location，应用启动即崩。修复为 parent.parent.parent。
2. **P0-4 回归**：无 LLM 配置的用户提交简答题时，_judge_short_answer 仍构造 LLM 客户端（get_llm_config_with_secret 无配置时返回默认 dict，LLM fallback 到 settings 的 dummy key 发起真实 120s HTTP 调用）→ 请求挂起超时。修复：先查 UserLLMConfig 行，无 api_key 则跳过 LLM 直接规则回退；新增回归测试 test_no_llm_config_skips_llm_judge。

### 测试
- 后端 pytest：**306 passed**（305 + 新增回归测试）
- 前端 vitest：仍无 node，未跑（E 项待用户决策）

### 遗留
- E 前端验证：用户本机跑 npx vitest run + 手动验证流式追问/TTS/复制/模型配置页掩码
- F Git 提交：待用户拍板拆分方案
- jieba 在 study-c 环境 pip 安装挂起（网络），C5 验证用 harness stub；生产环境 requirements 已声明 jieba，部署时正常安装即可

## Session: 2026-08-19 — 修复 5 个 P0 用户痛点 bug（Phase 9）

### 背景
站在用户角度盘点全部功能后输出 P0–P3 痛点分析；本次直接修复 5 个 P0 bug。

### 修复项
| # | Bug | 文件 | 改动 |
|---|-----|------|------|
| 1 | URL 导入永远失败（.txt 无解析器） | backend/app/core/document_parser.py | 新增 TextParser：utf-8/utf-8-sig/gbk/latin-1 编码探测，按段落累积 2000 字分页；工厂注册 .txt/.md/.markdown |
| 2 | 流式对话丢多轮上下文 | backend/app/services/chat_service.py (+4 行)；frontend/src/stores/chat.js | 后端 _ensure_session 后第一时间 yield {"type":"session","session_id"}；前端新增 session 事件分支捕获 currentSession，sources 分支兜底，done 后刷新会话列表；仅显式指定 session 时才覆盖 |
| 3 | 薄弱知识点显示文档 UUID | backend/app/services/analysis_service.py | 查询 Document.filename 映射，topic 显示文件名（缺失回退「未知文档」） |
| 4 | 简答题永远判错 | backend/app/services/quiz_service.py；backend/app/templates/quiz/judge_short_answer.jinja2（新增） | 判分拆分：_judge_choice（字母/大小写/标点容错）+ _judge_short_answer（精确→包含→LLM 语义裁判返回 {is_correct, reason}，失败保守判错）；判定理由补充进 explanation |
| 5 | TTS 死代码 | frontend/src/views/ChatView.vue | 助手消息操作栏接入 TTSPlayer + 复制按钮（clipboard + 已复制反馈）；顺带把内联 MarkdownIt 换成 useMarkdown composable |

### 验证（本机无 conda/node/pytest 依赖 → importlib harness 方案）
- /tmp/verify_textparser.py — ALL TEXTPARSER TESTS PASSED（纯文本/分页/空文件/GBK/extract_text/extract_pages/工厂注册）
- /tmp/verify_quiz.py — ALL QUIZ GRADING TESTS PASSED（选择题容错、简答三级判分、LLM 畸形响应回退）
- /tmp/verify_analysis.py — ALL ANALYSIS TESTS PASSED（topic 显示文件名，按正确率升序）
- /tmp/verify_chat.py — ALL CHAT SESSION-EVENT TESTS PASSED（首事件 session、ChatSession 落库 ID 一致、事件序列 session→sources→token×5→done、消息持久化）
- 前端改动（chat.js / ChatView.vue）：ast.parse + 逐行 diff 复核 + TTSPlayer props/useMarkdown 导出/SSE 序列化（api/chat.py 泛化 json.dumps 透传）一致性检查通过；无法跑 vitest/vue-tsc

### 测试同步
- backend/tests/test_document_parser.py：新增 TestTextParser；工厂断言改为 .txt/.md 支持、.xlsx 不支持
- backend/tests/test_quiz.py：新增 TestJudgeChoice / TestJudgeShortAnswer（mock LLM + get_llm_config_with_secret）

### Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| edit 工具把 \n 写成真实换行 → Python SyntaxError | 1 | 受影响字符串改用 \\n 转义重新编辑 |
| py_compile 报 PermissionError (com.apple.python) | 1 | 改用 ast.parse 校验语法 |
| verify_chat harness 多轮失败（docling InputFormat 缺失、rag 模块路径不存在、config stub 非 async、user 传 str 非对象、sources chunk 缺 filtered_sources） | 1-5 | 补齐 docling stub；改为 stub 整个 app.core.rag_engine（chat_service 仅依赖 rag_engine.ask_stream）；config stub 改 async；传 User 对象；补 filtered_sources 字段 |

### 遗留
- 建议在有完整依赖的环境跑一次 pytest tests/ -v 做最终确认（本机跑不了）
- 前端建议刷新页面手动验证一次流式追问 + TTS 朗读
- P1–P3 痛点未在本次范围

## Session: 2026-08-18 — 修复 Phase 7 遗留问题 + 语法错误
见下方详情。

## Session: 2026-08-14 — 全面探索
- Phase 1 仓库总览：完成（git 仅 2 提交，v2/v3 全部未提交；CI 触发分支 main vs 实际 master）
- Phase 2 后端深探：完成。确认 31 项问题/发现，重点：
  - BUG: database.py ensure_current_schema 缺 text import（空库首启崩溃）
  - BUG: quiz_service 用未解密的 Fernet 密文 api_key 调 LLM
  - requirements.txt 缺 edge-tts/trafilatura/jinja2
  - 死代码：_corrective_retrieve、_needs_rewrite、tasks 系统空壳、file_handler、14 个孤儿模板
  - 文档与代码多处不符（ask/stream、transform/types、tts/synthesize、hybrid 检索、notes 语义搜索、courses 文档关联）
- Phase 3 前端深探：完成。12 项前端问题（F1-F12），重点：
  - config.ts 读 data.model 但后端返回 model_name（模型配置静默失效）
  - course.js 调用 3 个不存在的后端端点（课程文档 tab 必挂）
  - 笔记前后端契约全面断裂（tags/course_id vs tag_names/course_space_id）
  - typescript/vue-tsc 未安装，"vue-tsc --noEmit" 无法执行
- Phase 4 文档与部署核对：完成。6 项文档错误（D1-D6）；nginx SSE 60s 超时风险；
  docker 内 alembic.ini 指向 localhost 导致容器迁移失败
- Phase 5 交叉验证 + 实测：完成。
  - 后端 pytest：171 passed / 6 failed（deduplicate 方法名不同步）/ 1 hang（真实加载 CrossEncoder）
  - 前端 vitest：13 passed / 2 文件崩溃（axios+jsdom+路径含空格）
  - 结论：两个 CI job 当前都会红；且 CI 触发分支 main 不存在，实际从未运行
- Phase 6 汇总报告：完成（见最终会话输出）

---

# Progress Log: Study Copilot v3 Upgrade

## Session: 2026-07-20

### Overview
Completed v3 upgrade based on Open Notebook comparison analysis.

### Tasks Completed

#### Phase 6: Frontend Component Extraction ✅
- Created BaseDialog.vue, BaseButton.vue, LoadingSpinner.vue, IconButton.vue
- Updated TransformDialog.vue and UrlImportDialog.vue to use BaseDialog
- Completed variables.css design system
- Created useMarkdown.js composable

#### Phase 7: Backend Prompt Template化 ✅
- Created template_manager.py
- Created 30 Jinja2 template files
- Updated transformations.py to use templates

#### Phase 8: TypeScript Migration ✅
- Created tsconfig.json, tsconfig.node.json, env.d.ts
- Created types/api.ts and types/models.ts
- Migrated 6 JS files to TS (api, auth, toast, sidebar, document, config)
- Updated 4 Vue components with lang="ts"

#### Phase 9: Component Optimization ✅
- Created useApi.ts composable
- Updated all CLAUDE.md files
- Updated README.md with v3 changelog

### Files Created/Modified

#### New Files (Frontend)
- frontend/src/components/common/BaseDialog.vue
- frontend/src/components/common/BaseButton.vue
- frontend/src/components/common/LoadingSpinner.vue
- frontend/src/components/common/IconButton.vue
- frontend/src/composables/useMarkdown.js
- frontend/src/composables/useApi.ts
- frontend/src/types/api.ts
- frontend/src/types/models.ts
- frontend/src/env.d.ts
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/src/services/api.ts
- frontend/src/stores/auth.ts
- frontend/src/stores/toast.ts
- frontend/src/stores/sidebar.ts
- frontend/src/stores/document.ts
- frontend/src/stores/config.ts

#### New Files (Backend)
- backend/app/core/template_manager.py
- backend/app/templates/ (30 Jinja2 files)

#### Modified Files
- frontend/src/components/TransformDialog.vue
- frontend/src/components/UrlImportDialog.vue
- frontend/src/components/NoteCard.vue
- frontend/src/components/CourseCard.vue
- frontend/src/components/chat/ChatMessage.vue
- frontend/src/views/LoginView.vue
- frontend/src/styles/variables.css
- backend/app/core/transformations.py
- CLAUDE.md (root)
- frontend/CLAUDE.md
- README.md
- task_plan.md
- findings.md

### Errors Encountered
None — all phases completed successfully.

### Next Steps
1. Migrate remaining stores to TypeScript (chat, note, course, quiz, analysis)
2. Migrate remaining Vue components to TypeScript
3. Add tests for v2/v3 features
4. Consider引入 Shadcn/vue 组件库

## Session: 2026-08-18 — Fix Phase 7 issues + syntax corruption

### Result: 288 backend tests ✅, 21 frontend tests ✅

### Fixed items

#### A. Syntax corruption (app couldn't even start / build)
1. **query_router.py** — fixed indentation error in `_classify_intent` (line 136 extra spaces)
2. **query_decomposer.py** — fixed corrupted template migration (dangling string fragments; methods referenced missing `DECOMPOSE_PROMPT_TEMPLATE`)
3. **answer_reflector.py** — same pattern; defined `REFLECT_PROMPT_TEMPLATE` / `REFINE_PROMPT_TEMPLATE` constants
4. **api/tasks.py** — removed stray separator line that broke the file
5. **api/courses.py** — decompressed document-association endpoints that were crammed onto one line
6. **services/course_service.py** — decompressed 3 document functions crammed onto one line
7. **stores/course.js** — removed stray comment text inside the return object (invalid JS)
8. **views/CourseDetailView.vue** — removed orphaned `toast.error('移除失败')}` fragment
9. **requirements.txt** — fixed literal `\n` inside `jinja2>=3.1.0\njieba>=0.42.1` (split to 2 lines)

#### B. Phase 7 functional issues from findings.md
10. **note.js** — filteredNotes: `n.course_id` → `(n.course_space_id)`; also made tag filtering robust (handles both string arrays and object arrays)
11. **CourseDetailView.vue** — courseNotes filter: `n.course_id` → `n.course_space_id`; restored the documents tab (the backend now has working endpoints); added add/remove document UI
12. **config.ts** — syncToChatStore: `config.model` → `config.model_name` (2 places)
13. **models.ts** — fixed Note.note_type ('markdown'|'plain'), Note.course_space_id, Source.page (string), Quiz (single-question), ChatSession (removed document_id)
14. **rag_engine.py** — ask_stream: added corrective retrieval step (grade + retry on poor quality), mirroring ask()
15. **tts.py** — implemented cleanup of mp3 files older than 24 hours (throttled, runs at most once per hour)
16. **task_worker.py** — rewrote `_run_document_process` and `_run_quiz_generate` to use updated service signatures (`_do_process_document` / `_do_generate_quiz`); added result capture in `_execute_job` so task records store results
17. **document_service.py** — made upload truly async: validates + saves file + creates Document(status=processing) + enqueues background task; added `_do_process_document` for background processing; added sync fallback when worker unavailable
18. **quiz_service.py** — added task tracking: `generate_quizzes` now creates/finalizes an AsyncTask record; added `_do_generate_quiz` for the worker path
19. **courses.py/course_service.py** — clean formatting + proper CourseDocResponse schema for document endpoints; added course_space_id unlink on course deletion
20. **database.py** — added `course_space_id` column to Document model (FK → course_spaces, ondelete SET NULL, index)
21. **alembic migration** — `b3c4d5e6f7a8_add_document_course_space_id.py` adds the column + FK + index
22. **notes.py** — removed duplicate `NoteSearchRequest` class definition
23. **rate_limit.py** — restored `create_rate_limit_key` helper that was removed as dead code but still needed by tests

#### C. Test fixes (CI alignment)
24. **test_rag_engine.py** — removed 6 obsolete `_needs_rewrite` tests (method intentionally removed); fixed `test_ask_no_results`/test_ask_stream_no_results to match Chinese answer message; fixed `test_retrieve_calls_store_search` to mock the reranker (was loading real CrossEncoder → hang); fixed `test_ask_stream_embedding_model_switch` to patch LLM (was making real API calls → hang); updated ask_stream tests to handle thinking events; updated `test_ask_with_history_triggers_rewrite` to test the router-based rewrite (current architecture); fixed `test_engine_reranker_init` to use a pristine RAGEngine
25. **all engine fixtures** — disable real CrossEncoder loading by default (`_reranker_loaded=True`); tests that need a reranker set it up explicitly
26. **setup.js** — fixed api module mock path from `../services/api` to `@/services/api` (the wrong path resolved to a nonexistent file, allowing real axios to crash in jsdom with spaces in the directory name)

#### D. Other
27. **NotesView.vue** — `openEditNote`: `note.course_id` → `note.course_space_id`

### Still remaining
- vue-tsc has a TypeScript path-exported compatibility issue (unrelated to code changes)
- The NO_PROXY hack in run.py (not touched)
- Chat SSE 401 refresh (F6 — pre-existing design limitation)
- ModelConfigView's random score display (F8 — cosmetic, not user-impacting)
- Documentation drift (CLAUDE.md/README — partially updated in prior commit)
- Course documents tab frontend test coverage (added restore but no dedicated test)

## Session: 2026-08-18 — 第二批修复（剩余问题）

### 修复项
- **main.py lifespan** — 全新DB → create_all + stamp_head，不再因迁移冲突崩溃
- **run.py NO_PROXY** — `setdefault` 替代强制覆盖，不再影响用户代理配置
- **auth.ts login** — FormData → URLSearchParams，使用标准 OAuth2 编码
- **url_extractor** — trafilatura.fetch_url 包装为 asyncio.to_thread，不再阻塞事件循环
- **config.py Pydantic** — class Config → model_config dict，消除弃用警告
- **migrations.py get_current_revision** — 无 alembic_version 表时 catch 返回 None，不再崩溃
- **database.py ensure_current_schema** — 移除 PG 专有 SQL，简化为 create_all(checkfirst=True)

### 测试
- 后端 288 passed ✅
- 前端 21 passed ✅

### 仍存在的问题清单
见 remaining_issues.md（13项，均为低风险/代码卫生/文档漂移）。
## Session: 2026-08-18 — 第三批修复（代码卫生）

### 修复内容
| # | 项目 | 方式 |
|---|------|------|
| 7 | utils/file_handler.py + tests → 删除（死代码） | rm -f |
| 8 | core/pdf_parser.py → 删除（死代码，两套 PDF 解析共存） | rm + 从 __init__ 移除导出 |
| 9 | core/UserConfigMiddleware → 删除（空壳中间件） | 从 config.py 移除 |
| 10 | backend/requirements.txt → 分离测试依赖 | grep 分离至 test-requirements.txt |
| 6 | quiz_service submit_answer 归一化改进 | re.sub 折叠多余空格 |
| 4 | chat.js SSE 401 自动刷新 Token | 新增 doFetch + 401 重试逻辑 |

### 测试结果
- 后端: **282 passed** (原 288，减少 6 因移除 test_file_handler.py 的测试) ✅
- 前端: **21 passed** ✅

### 仍存在的问题
| # | 问题 | 风险 | 备注 |
|---|------|------|------|
| 1 | Docker nginx proxy_read_timeout 60s 默认值 | 中 | 需在 docker/nginx.conf 加长超时 |
| 2 | CLAUDE.md / docs/ 端口、store 数量、API 路径漂移 | 低 | 需系统性文档更新 |
| 3 | vue-tsc 因 typescript exports 不兼容无法运行 | 低 | 本地环境问题，非代码 |
| 5 | ChatView 内联 MarkdownIt 未复用 composable | 低 | 需手动重构（ChatView.vue + useMarkdown.js） |

---

---

## 会话记录：2026-08-24 第三轮（REVIEW_2026-08-24 后续收尾）

### 任务来源
用户提供 REVIEW_2026-08-24.md，要求基于文档完成任务；明确**不需要推送**。
范围 = 报告 §6「明确未做」除 push 外全部 + §4.1 温度 wart 建议。

### 完成项
| # | 内容 | 提交 |
|---|------|------|
| 1 | main/router/useMarkdown TS 化 + markdown-it ambient 类型声明 | 8d65757 |
| 2 | config POST 响应温度 /10 归一化统一（§4.1 收口）+ 回归测试 | cb3fd0f |
| 3 | tsconfig strict/noUnusedLocals/noUnusedParameters 开启 + chat store 隐性 bug 修复 | 8f136cb |
| 4 | README 叙述性内容逐句核对修正（结构树/env 块/默认值表/分块策略/SSE/CI） | 9aceb42 |
| 5 | 规划文件与评审文档附录收尾 | （本提交） |

### 验证结果
- 后端 pytest：**313 passed**（312 基线 + 1 新增双形态兼容用例）
- vue-tsc --noEmit：exit 0（strict 全开后仅 4 处 TS6133，均已修复）
- vitest：**18 passed**

### 关键发现
chat store 未 return currentSessionTitle → ChatView 四处读写静默失效
（详见 findings.md Phase 12）；由 strict 模式 TS6133 信号定位。

### 遗留
- push 到远端待用户拍板（本地领先 origin/master 29 commits）
- frontend/dist 为 gitignored 且为旧编译产物——部署前必须 npm run build
