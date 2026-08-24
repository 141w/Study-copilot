# Findings: Study Copilot 全面探索（2026-08-14 会话）

> 历史：v3 升级 9 阶段已于 2026-07-20 完成（见 progress.md 历史记录）。
> 本次为全新探索任务：摸清现状 + 文档与代码一致性核验。

## Phase 1: 仓库总览

### Git 状态（重要发现）
- 分支：master，与 origin/master 同步；仅 2 个提交：
  - c59479e 清理跟踪文件：移除 TODO.md、DESIGN.md；更新 README 为完整文档
  - e2debc3 Initial commit: AI-powered study assistant with RAG Q&A and quiz generation
- **v2/v3 的全部工作（Agentic RAG、笔记、课程、TS 迁移、模板化、测试、CI、docs）均未提交**：
  - 大量 modified（backend 几乎全部 core/api、frontend 多数 views/stores）
  - 大量 untracked（backend/app/services/、backend/app/templates/、backend/tests/、
    alembic/、docs/、.github/、frontend 新组件/类型/composables、open-notebook-main/ 参考项目等）
- ⚠️ 风险：工作区状态即项目全部资产，无任何远端备份。
- ⚠️ untracked 中有运行时产物：backend/study_copilot.db-shm / .db-wal（SQLite WAL 残留，
  与文档宣称的 PostgreSQL 不一致，疑似本地开发曾用 SQLite fallback）；
  backend/.embedding_cache/、frontend/node_modules/ 也在 untracked 列表。

### 顶层结构
- backend/（FastAPI）、frontend/（Vue3）、docs/（0-START-HERE ~ 4-DEVELOPMENT 五节）、
  open-notebook-main/（外部参考项目，非本项目代码）、scripts/（run_all_tests.sh）
- 根级文档/计划：README.md(45KB)、DESIGN.md、OPTIMIZATION_PLAN.md、UPGRADE_PLAN.md、
  CONTRIBUTING.md、README-Docker.md、AGENTS.md、CLAUDE.md
- 运维脚本：start.sh / start.bat / stop.sh / run-tests.sh / deploy-docker.sh / docker-compose.yml

### 根配置
- pyproject.toml：仅 ruff 配置 + pytest asyncio_mode=auto（非打包配置），Python >=3.11
- package.json（根）：薄壳，dev/build 转发到 frontend，start/stop 调 shell 脚本
- docker-compose.yml：postgres:16-alpine + backend(8000) + frontend(nginx, 3000:80)，
  凭据硬编码 study_user/study123（compose 内），JWT/OPENAI 走 ${ENV} 注入
- .env.example：OPENAI_API_KEY/BASE_URL/MODEL、JWT_SECRET_KEY、DATABASE_URL(注释掉的 PG)

### CI（.github/workflows/test.yml）
- 触发分支：push [main, develop]、PR [main] —— ⚠️ 实际分支是 master，CI 触发条件与现状不匹配
- backend job：PG16 service + pytest --cov=app + codecov
- frontend job：Node20 + npm ci + npm test
- 汇总 job all-tests-pass 做门禁
- 模板齐全：bug_report / feature_request / PULL_REQUEST_TEMPLATE

### 测试脚本
- run-tests.sh：简单 pytest 包装
- scripts/run_all_tests.sh：前后端全量 + 汇总；⚠️ 硬编码本机 Python 路径
  /Users/wweiqi/miniconda3/envs/study-c/bin/python（有 fallback 到 PATH pytest）
- stop.sh：按端口 8000/3000 kill —— ⚠️ 前端开发端口文档写 5173，compose 用 3000，存在口径不一

## Phase 2: 后端深探（进行中）

### 结构概览
- app/: api(11 routers) + core(20 模块) + services(10) + db + utils + templates(30 jinja2)
- 源码规模：core+services+api+utils 约 6.3k 行；tests 14 个文件约 3.9k 行
  （test_document_parser 1177 行、test_rag_engine 945 行最大）
- 入口 run.py：uvicorn app.main:app，0.0.0.0:8000；硬编码 NO_PROXY='*'（注释称绕过 VPN 透明代理，本机 hack）
- main.py：lifespan 启动时跑 Alembic 迁移（无 revision 时先 ensure_current_schema 兜底建表）；
  CORS 白名单 5173/3000；11 个 router 全部 prefix=/api；/ 与 /health 探针
- 异常体系：app/exceptions.py（AppError 基类 + 9 个子类 + classify_llm_error 关键词分类器，
  中文用户消息映射）+ exception_handlers.py（4 个全局 handler）—— 设计完整
- 配置：app/config.py pydantic-settings（env_file=.env）；默认 PG URL 硬编码 study_user:study123
- 依赖 requirements.txt：fastapi/uvicorn/sqlalchemy2/asyncpg+aiosqlite/faiss-cpu/
  sentence-transformers/openai/docling/pymupdf/python-docx/pptx/rank-bm25/slowapi/
  pytesseract/alembic + pytest 全家桶（测试依赖混在主 requirements 里）

### 数据层
- database.py：13 个 ORM 模型（User, Document, ChatSession, Message, Quiz, QuizResult,
  UserLLMConfig, CourseSpace, Tag, Note, AsyncTask + note_tags 关联表）；全 String PK（应用层 uuid）
- migrations.py：run_migrations（线程池跑 alembic upgrade head）、get_current_revision、
  get_pending_migrations、stamp_head
- alembic：3 个版本（initial_schema -> add_notes_and_courses -> add_async_tasks），env.py 为异步模板
- 本地残留 study_copilot.db / test.db（SQLite）+ WAL 文件，开发中曾用 SQLite；
  requirements 同时装 aiosqlite+asyncpg

### 已确认 BUG / 问题（后端）
1. database.py:222 ensure_current_schema() 使用 text() 但未 import（sqlalchemy import 块无 text）
   -> 空库首启且无 alembic_version 时 NameError，启动崩溃。
2. alembic.ini:89 硬编码 PG URL，env.py 未用 DATABASE_URL 环境变量覆盖
   -> 程序化迁移走 app.db.database 的 engine（吃 env），但 alembic command.upgrade 用 ini URL；
   docker 里 db 主机名为 db，与 ini 的 localhost 不符 -> 容器内自动迁移可能连错库。
3. 死代码：RAGEngine._corrective_retrieve 定义后无任何调用（ask/ask_stream 均未走）
   -> retrieval_grader 实际未接入主流程；backend/CLAUDE.md 宣称的 "Step 3 corrective_retrieve" 与代码不符。
4. 死代码：RAGEngine._needs_rewrite 无调用；_rewrite_query 仅被死方法 _corrective_retrieve 调用。
5. 模板孤儿：30 个 jinja2 模板中仅 transformations/ 的 16 个被 render_template 使用；
   rag/ router/ reflector/ decomposer/ retriever/ quiz/ 共 14 个模板无任何代码引用，
   对应模块全部使用内联硬编码 prompt -> "Prompt 模板化" 只完成了一半。
6. alembic versions/__pycache__ 里有 09bdbdf2e796_test_autogenerate.pyc，但源文件已删除（残留）。
7. core/config.py 的 UserConfigMiddleware 是空壳（__call__ 直接透传，未注入任何配置）；
   get_user_llm_config 返回类型标注 dict 但可能返回 None。
8. run.py 全局 NO_PROXY='*' 属本机环境 hack，不宜随仓库分发。

### RAG 实际管线（以代码为准）
ask()/ask_stream():
1. QueryRouter.analyze：规则优先（无文档->direct；闲聊->out_of_scope；总结关键词->summary），
   有历史时一次 LLM 调用同时做意图分类+独立化改写（JSON 输出，宽松解析）
2. AdaptiveRetriever.select_strategy：LLM 选 single/standard/multi_hop/compare
   - multi_hop: decomposer 拆子问题->逐个检索 top3->合并去重取 top5
   - compare: 抽实体->每实体 "entity+query" 检索->合并；失败降级 standard
3. retrieve(): 每文档检索 over-fetch 2x -> distance<=0.85 过滤 -> 前缀去重 ->
   CrossEncoder(ms-marco-MiniLM-L-6-v2) rerank（懒加载，失败降级）-> top_k
4. _build_history_context：>10 条历史时早期摘要+保留最近 5 条
5. generate_answer(_stream) + AnswerReflector.evaluate/refine（流式时先吐 token 再反思，
   失败则发 answer_refined 事件）
- 来源引用：[来源N] 正则抽取 -> filtered_sources
- SSE 事件类型：thinking / sources / token / answer / answer_refined

### 后端补充发现（服务层/API 层）
9. **BUG（高危）：quiz_service.generate_quizzes 使用 core.config.get_user_llm_config，
   返回的 api_key 是 Fernet 密文（未解密）** -> 用户配置了自定义 LLM 后，出题会用密文当 API Key
   导致认证失败。chat_service/transform_service 走的是 config_service.get_llm_config_with_secret（有解密），
   唯独 quiz 走错路径。
10. 文档声称的 POST /api/chat/ask/stream 不存在；实际是 POST /api/chat/ask + body {stream: true}
    返回 SSE（StreamingResponse）。backend/CLAUDE.md API 表有误。
11. 端点路径与文档不符：/api/transform/types 实际为 /api/transform/transformations；
    /api/tts/synthesize 实际为 /api/tts/generate；/api/analysis/record-wrong|knowledge-gaps|progress
    实际为 /api/analysis/wrong|knowledge|progress。
12. requirements.txt 缺少运行时依赖：edge-tts（core/tts.py import）、trafilatura（url_extractor.py）、
    jinja2（template_manager.py）-> 全新环境 pip install -r 后启动即 ImportError。
13. 上传固定使用 RETRIEVAL_TYPE_FAISS；HybridVectorStore/BM25 已实现且有测试，但主流程未启用
    （与 CLAUDE.md "混合检索" 宣称不符；vectorstore 目录里有一个 _bm25 历史残留文件）。
14. BM25VectorStore.search 用 re.findall(r"\w+", query) 分词：中文整句无空格时只产生 1 个 token，
    关键词检索对中文基本失效（若未来启用 hybrid 需注意）。
15. document_service.upload_document 硬编码 "./uploads" 而非 settings.upload_dir（file_handler/tts 用的是 settings）。
16. 限流：自研 IPRateLimiter（内存滑动窗口）挂在 document upload/from-url、chat ask、quiz generate；
    slowapi 在 requirements 里但未使用；DEFAULT_RATE_LIMITS/rate_limit_exceeded_handler 为死代码。
17. 测试 conftest 用 sqlite+aiosqlite 文件库 ./test.db（解释了 backend/test.db 残留）；
    session 级 event_loop fixture 与 pytest-asyncio 0.23+ 的弃用警告风险。
18. /api/config/llm/with-secret 会把解密后的 API Key 明文返回给前端（仅本人 token 可用，但明文出网）。
19. url_extractor.extract_from_url 声明 async 但内部 trafilatura.fetch_url 是同步阻塞调用，会卡事件循环。
20. analysis_service 的"知识点"统计以 document_id 为 topic（无真实知识点抽取）。
21. quiz_service.submit_answer 判题：选择题字母集合比较 + 简答题字符串精确比较（无 LLM 语义判分）。
22. config_service 温度存储约定：DB 存 temperature*10（int 化），读时 /10；写入时兼容 <=1 与 >1 两种输入。
    core/config.get_user_llm_config 也做了 /10 —— 但该函数返回密文 key（见 #9）。

### 后端补充发现（死代码与基础设施）
23. **异步任务系统是"空壳"**：task_service.create_task/update_task 无任何调用方；
    没有后台任务队列/worker，文档上传与出题均为同步执行。tasks API 只能 list/get/cancel，
    永远不会产生任务记录。CLAUDE.md 宣称的"异步任务：批量操作，后台任务队列"未落地。
24. utils/file_handler.py 整体未被使用（document_service 自己实现了保存逻辑）；
    且其 validate_file_type 只允许 .pdf（与支持的 docx/pptx 矛盾，幸好无人调用）。
25. api/__init__.py 只 re-export 5 个旧 router（auth/chat/document/quiz/analysis），
    新增 6 个 router 未加入（main.py 直接 import，不影响运行，但 __init__ 已过时）。
26. core/__init__.py 仍从 pdf_parser 导出 pdf_parser 单例；document_parser.py 内又有自己的
    PDFParser 实现（Docling 版）—— 两套 PDF 解析并存，pdf_parser.py 疑似旧版残留。
27. analysis /wrong 是 POST 但无请求体（纯触发分析）。
28. courses API 无"文档关联"端点（CLAUDE.md 声称 courses 管理 document associations，
    实际 CourseSpace 只关联 notes；Document 表无 course 外键）。
29. notes API 无语义搜索端点（CLAUDE.md 声称 notes semantic search；note_service 无 embedding 代码）。
30. tts/generate 直接返回 FileResponse 音频；生成的 mp3 永不清理（uploads/tts 累积）。
31. auth /login 用 OAuth2PasswordRequestForm（form-data，非 JSON）——前端需用 URLSearchParams。

## Phase 3: 前端深探

### 结构概览
- 13 views / 10 stores（auth,chat,config,course,document,note,quiz,sidebar,theme,toast）/
  12 common 组件 + 7 feature 组件 + 2 chat 组件 / 2 composables / 2 types 文件
- Vue SFC 总量约 6.9k 行；最大 ChatView.vue 618 行
- 构建：Vite 5.2 + @vitejs/plugin-vue；dev server 端口 **3000**（vite.config.js），
  /api 代理到 localhost:8000 —— 文档（root CLAUDE.md/AGENTS.md、frontend CLAUDE.md 的 Running 节）
  写 5173，与实际不符（stop.sh 的 3000 反而对）
- 样式：TailwindCSS 3.4 + variables.css 设计系统（CSS 变量，dark 主题由 theme.ts 切 .dark 类）；
  tailwind.config.js 有自定义 brand 色板（magenta/orange/dark/lavender）
- 测试：vitest 4.1 + jsdom，6 个测试文件（components 2 + stores 3 + setup）
- TS 迁移现状：9/35 个 SFC 用 lang="ts"；stores 6 TS + 4 JS；**typescript/vue-tsc 未安装**
  （package.json 无此依赖，node_modules 也没有）→ CLAUDE.md 的 "npx vue-tsc --noEmit" 无法执行

### 已确认 BUG / 问题（前端）
F1. **config.ts 字段名不匹配**：fetchLLMConfig/syncToChatStore 读 data.model，但后端返回 model_name
    → localStorage llmModel 恒为 undefined，chatStore.config.modelName 被置 undefined。
    （ModelConfigView 本身用 model_name 是对的；types/models.ts 的 LLMConfig 也错写成 model。）
F2. **config.ts 温度双重乘 10**：saveLLMConfig 前端先 *10，后端 config_service 又对 <=1 的值 *10，
    但前端传的是已 *10 的值（>1）→ 后端按原值存。实际链路恰好"负负得正"？
    —— 细查：前端 payload.temperature = round(t*10)（如 7）；后端判断 >1 直接 round(7)=7 入库；
    读取时 /10 = 0.7。链路正确但约定脆弱，注释与实现分散在两端，极易回归。
F3. **course.js 三个文档关联方法调用不存在的后端端点**（/courses/{id}/documents GET/POST、
    /courses/{id}/documents/{docId} DELETE）→ CourseDetailView 的"课程文档" tab 必然报错、
    移除文档按钮必然失败。后端根本没有这些路由。
F4. **笔记契约全面不匹配**（前后端字段名不一致）：
    - 前端发 {tags: [...], course_id}；后端 NoteCreate/NoteUpdate 期望 {tag_names, course_space_id}
      → 创建/编辑笔记时标签与课程归属被静默丢弃（Pydantic 忽略未知字段）
    - 后端返回 tags: [{id,name,created_at}] 对象数组；前端 note.js/NoteCard/NotesView 按字符串数组处理
      （n.tags.includes(tag)、tagSet.add(t)、:key="tag" 直接渲染对象）→ 标签过滤失效、渲染 [object Object]
    - note.js filteredNotes 按 n.course_id 过滤，后端字段是 course_space_id → 课程过滤恒空
    - NoteCard 显示 note.course_name，后端从不返回该字段
F5. **auth.ts 登录用 FormData + multipart/form-data**：后端 OAuth2PasswordRequestForm 需要
    application/x-www-form-urlencoded；axios 发 multipart 时 FastAPI 解析 form 字段的行为依赖
    python-multipart，实测 multipart 也能解析（FastAPI Form 支持 multipart），风险中等但非标准用法。
F6. chat.js 的 SSE 用裸 fetch 手写解析（无 EventSource），手动处理 buffer/abort —— 实现完整，
    但 401 时不走 api.ts 的自动刷新（fetch 不带 interceptor）。
F7. types/models.ts 多处与后端不符：Note.note_type 'manual'|'ai'（后端 'markdown'|'plain'）、
    ChatSession 有 document_id（后端无）、Quiz.questions 数组（后端 Quiz 是单题模型）、
    Source.page 类型 number（后端 string）、LLMConfig.model（应为 model_name）。
    类型定义形同虚设（strict:false 且多数消费方是 JS）。
F8. ModelConfigView 的"适配度评分"是 Math.random 假数据（UI 装饰），configHistory 恒为空数组
    （从未写入）—— 死 UI。
F9. ChatView 内联了自己的 MarkdownIt 实例，未复用 composables/useMarkdown.js（重复实现）。
F10. document.ts uploadDocument 返回类型标 Document，实际后端返回 DocProcessResponse
    （含 message、无 created_at/file_size）；且 documents.unshift 的响应对象缺字段。
F11. TasksView/TaskPanel 轮询 /tasks，但后端从不产生任务（见后端 #23）→ 页面永远空。
F12. App.vue keep-alive include ['QuizView','ChatView','AnalysisView']：script setup 组件无显式 name，
    依赖 @vitejs/plugin-vue 从文件名推断组件名（推断成立则生效）。脆弱点：一旦改名/换打包器即失效，
    建议 defineOptions({ name })。（更正：Vue SFC 编译器会按文件名推断，非必然失效）

## Phase 4: 文档与部署核对

### docs/ 结构（9 个 md，1435 行）
- 0-START-HERE / 1-INSTALLATION / 2-ARCHITECTURE / 3-API-REFERENCE(596行) / 4-DEVELOPMENT(+testing.md)
- 另有 3 个规划/对比文档：AGENTIC_RAG_PLAN.md、CONTEXT_OPTIMIZATION_PLAN.md、comparison-with-open-notebook.md
- README.md 1117 行，内容最全（功能表、架构、API、模块详解、FAQ、changelog）

### 文档错误清单（docs/README 与代码不符）
D1. docs/0-START-HERE 与 4-DEVELOPMENT 称前端跑在 5173 —— 实际 vite.config.js 固定 3000。
D2. docs/3-API-REFERENCE：login 写成 JSON body（实际 form-data）；register/upload 标 201
    （FastAPI 默认 200）；upload 响应示例含 created_at（实际 DocProcessResponse 无此字段）。
D3. README API 表：
    - /api/chat/ask/stream 不存在（实际 /chat/ask + stream:true）
    - /api/notes/search 语义搜索不存在（后端无此实现）
    - /api/notes/tags/all 重复列了两行
    - /api/tts/synthesize 应为 /api/tts/generate
    - courses/{id} GET 声称"含文档和笔记"，实际只返回课程字段
    - 缺 /api/documents/from-url、/api/config/llm PUT
D4. backend/CLAUDE.md API 表同样有 ask/stream、transform/types、tts/synthesize、
    analysis record-wrong/knowledge-gaps 等错误路径（见后端 #10/#11）。
D5. root CLAUDE.md 声称 "15 Pinia stores"，实际 10 个；"8 shared + 7 feature components"，
    实际 common 12 + feature 7 + chat 2。frontend/CLAUDE.md 结构树列了不存在的 stores/analysis.js。
D6. docs/4-DEVELOPMENT 称 run.py "Start with auto-reload"，实际 reload=False。

### 部署
- backend/Dockerfile：python:3.11-slim + build-essential/libpq-dev；CMD uvicorn（无 gunicorn/workers）
- frontend/Dockerfile：node:20-alpine 构建 → nginx:alpine 托管；nginx.conf 有 SPA fallback + /api 代理 backend:8000
  - ⚠️ nginx proxy_read_timeout 60s：SSE 流式问答超过 60s 会被 nginx 断开（长答案风险）
- docker-compose：db/backend/frontend 三服务；backend 依赖 db healthy；
  ⚠️ backend 容器内 alembic.ini 指向 localhost:5432（见后端 #2），自动迁移会失败
- start.sh：macOS 一键启动，硬依赖 ~/miniconda3 + conda env study-c；FRONTEND_PORT=3000
- CI：.github/workflows/test.yml 触发于 main/develop，仓库实际分支 master → push 不会触发 CI

## Phase 5: 交叉验证与测试运行结果

### 数量核对（CLAUDE.md 声称 vs 实际）
| 项目 | 声称 | 实际 | 结论 |
|------|------|------|------|
| 后端 routers | 11 | 11 | ✅ |
| Pinia stores | 15 | 10 | ❌ 虚报 |
| views | 13 | 13 | ✅ |
| common 组件 | 12 | 12 | ✅ |
| feature 组件 | 7 | 7 | ✅ |
| Jinja2 模板 | 30 | 30 | ✅（但 14 个是孤儿） |
| services | 10 | 10 | ✅ |
| core 模块 | - | 20 | - |
| 后端测试文件 | - | 13 | - |
| 前端测试文件 | - | 5 | - |

### 测试实际运行结果（2026-08-14，conda env study-c / Python 3.11.15）
**后端 pytest**：
- 171 passed, 6 failed, 1 个测试导致进程挂起
- 6 个失败全部是 test_rag_engine.py 的 deduplicate 测试：
  测试调用 engine._deduplicate_results()，但代码中方法名是 deduplicate_results()（无下划线前缀）
  → 测试与代码不同步（方法被重命名后测试未更新）
- 挂起测试：TestRAGEngineAsync::test_retrieve_calls_store_search
  原因：retrieve() 内部调用 _ensure_reranker() 会真实加载 CrossEncoder 模型
  （cross-encoder/ms-marco-MiniLM-L-6-v2），测试未 mock 该路径 → 模型加载阻塞/超时
- 结论：CI 的 backend-tests job 会失败（pytest 非零退出）

**前端 vitest**：
- 3 个 store 测试文件通过（13 tests passed）
- 2 个组件测试文件（ChatMessage.test.js、UploadView.test.js）加载失败：
  axios 在 jsdom 环境下因路径含空格（update plan）触发 "Invalid URL"
  → 环境问题（目录名含空格）+ axios isURLSameOrigin 的已知行为
- 结论：CI 的 frontend-tests job 也会失败（vitest 非零退出）

### 综合结论
1. 项目功能实现度高（v2/v3 特性基本落地），但"最后一公里"质量缺失：
   - 测试套件红（后端 6 失败 + 1 挂起；前端 2 文件崩溃）
   - CI 配置指向不存在的分支（main），实际从未跑过
   - 全部工作未提交 git
2. 文档与代码存在系统性漂移（API 路径、端口、数量、功能宣称）
3. 前后端契约在 notes/courses/config 三个模块上断裂（字段名不匹配、端点不存在）
4. 多个宣称的功能为空壳：异步任务队列、笔记语义搜索、课程-文档关联、纠错检索

## 待验证问题清单（已全部核对完毕）
1. 数据库：默认配置为 PostgreSQL（config.py 默认 URL + docker-compose PG16）；
   但本地残留 study_copilot.db/test.db（SQLite）说明开发中曾用 SQLite；
   测试 conftest 固定用 sqlite+aiosqlite。生产路径是 PG，无运行时 fallback 逻辑。
2. CI 触发分支 main/develop vs 实际分支 master → 已确认：CI 永远不会被触发。
3. 前端端口：vite.config.js 固定 3000（dev 与 compose 一致）；文档写 5173 是错的。
4. 数量核对：routers 11✅ / views 13✅ / 模板 30✅ / stores 实际 10（声称 15）❌。
5. open-notebook-main/（6.5MB，外部参考项目 lfnovo/open-notebook）：
   仅作为 v2/v3 升级的参考素材，建议移出仓库或加入 .gitignore（目前 untracked）。

---

## Phase 7: 重点问题二次核验（2026-08-18）

> 目的：对上一轮“面向用户分析”中提到的关键问题，逐项回到代码层做二次验证，
> 区分“仍真实存在”“已修复/不成立”“部分成立”三类。

### 7.1 笔记前后端契约（仍部分成立，过滤断裂）

- **创建/更新别名映射已补齐**：后端 `backend/app/api/notes.py` 的 `NoteCreate`/`NoteUpdate`
  已同时接受 `course_id` 与 `course_space_id`、`tags` 与 `tag_names`，
  并在视图层做 `csid = data.course_space_id or data.course_id` 这类别名归一化。
- **返回格式已部分统一**：列表接口返回 `NoteBrief`，其中 `tags` 是字符串数组；
  详情接口返回 `NoteResponse`，其中 `tags` 是对象数组（含 `id/name/created_at`）。
- **仍真实存在的问题**：
  - 前端 `frontend/src/stores/note.js` 的 `filteredNotes` 按 `n.course_id` 过滤，
    但列表返回字段为 `course_space_id` → **课程筛选失效**。
  - 前端 `frontend/src/views/CourseDetailView.vue` 的 `courseNotes` 也按 `n.course_id === courseId` 过滤，
    同样会漏掉课程归属的笔记。
  - 标签过滤依赖 `n.tags.includes(tag)`，若后端返回 `NoteResponse` 对象数组而非字符串数组，
    前端渲染/过滤会异常；当前列表虽用 `NoteBrief` 规避，但契约仍脆弱。

### 7.2 模型配置同步到聊天 Store（仍真实存在）

- **现象**：用户保存 LLM 配置后，聊天侧可能仍使用旧模型名或空模型。
- **原因**：`frontend/src/stores/config.ts` 的 `syncToChatStore` 读的是 `config.model`，
  但后端 `backend/app/services/config_service.py` 返回的是 `model_name`。
- **代码位置**：
  - `frontend/src/stores/config.ts:91,96`
  - `backend/app/services/config_service.py:153`

### 7.3 异步任务系统（仍真实存在，空壳）

- **现象**：任务页永远为空；上传文档、生成测验不会产生任务记录。
- **原因**：`task_worker.py` 的 worker、enqueue、execute job 骨架已接线，
  但 `document_service.upload_document` 与 `quiz_service.generate_quizzes`
  都是同步执行，没有调用 `enqueue` 创建任务。
- **代码位置**：
  - `backend/app/services/document_service.py:45-153`
  - `backend/app/services/quiz_service.py:22-96`
  - `backend/app/core/task_worker.py:41-99`

### 7.4 课程文档关联端点（已修复/不成立）

- **上一轮结论**：课程-文档关联端点不存在。
- **本次核实**：`backend/app/api/courses.py` 第120行后确实混入了
  `GET/POST/DELETE /{course_id}/documents`；`backend/app/services/course_service.py`
  也有 `get_course_documents`、`add_document_to_course`、`remove_document_from_course`。
- **结论**：端点**已存在**，但代码格式混乱（同一文件内出现类似压缩/粘贴的乱码片段）。

### 7.5 quiz 调用未解密 api_key（已修复）

- **上一轮结论**：`quiz_service.generate_quizzes` 使用 `get_user_llm_config`，
  返回 Fernet 密文，导致自定义 LLM 认证失败。
- **本次核实**：`backend/app/services/quiz_service.py:57` 实际调用的是
  `get_llm_config_with_secret(db, user)`，会先解密再返回。
- **结论**：**已修复**，不再成立。

### 7.6 BM25 中文分词（已修复）

- **上一轮结论**：BM25 搜索用 `re.findall(r"\w+", query)`，中文整句无空格时只产生 1 个 token。
- **本次核实**：`backend/app/core/vector_store.py:246-255` 已有 `_tokenize`，
  检测到中文会走 `jieba.cut(text)`，仅非中文或未安装 jieba 时才回退到正则。
- **结论**：**已修复**，不再成立。

### 7.7 混合检索未启用（已修复）

- **上一轮结论**：上传固定使用 `RETRIEVAL_TYPE_FAISS`，Hybrid/BM25 未启用。
- **本次核实**：`backend/app/services/document_service.py:124`
  明确使用 `DocumentVectorStore(doc_id, retrieval_type=DocumentVectorStore.RETRIEVAL_TYPE_HYBRID)`。
- **结论**：**已启用**，不再成立。

### 7.8 流式问答缺少纠错检索（仍真实存在）

- **现象**：非流式问答在检索质量差时会改写查询重试；流式问答没有该逻辑。
- **原因**：`rag_engine.ask` 在 retrieve 后调用 `retrieval_grader.grade`，
  质量差时进入 `_corrective_retrieve`；但 `ask_stream` 缺少该步骤。
- **代码位置**：
  - `backend/app/core/rag_engine.py:468-483`（`ask` 有 corrective）
  - `backend/app/core/rag_engine.py:612-625`（`ask_stream` 缺失 corrective）

### 7.9 TTS 音频文件无清理（仍真实存在）

- **现象**：每次 TTS 生成都在 `uploads/tts/` 下落 mp3，永不清洗。
- **原因**：`backend/app/core/tts.py:18` 有 TODO，但未实现清理逻辑。
- **代码位置**：`backend/app/core/tts.py:18,101-102`

---

## 最新综合结论（2026-08-18 核实后）

1. **仍真实存在且影响用户的问题**：
   - 笔记按课程筛选失效（字段名 `course_id` vs `course_space_id`）
   - 模型配置同步到聊天 Store 时读错字段（`model` vs `model_name`）
   - 异步任务系统空壳（worker 已接线但无生产者）
   - 流式问答缺少纠错检索（召回质量不稳定）
   - TTS 文件长期堆积
2. **已修复/不成立的问题**：
   - quiz 调用未解密 api_key
   - BM25 中文分词
   - 混合检索未启用
3. **部分成立的问题**：
   - 笔记前后端契约：创建/更新别名已补齐，但**过滤字段名仍断裂**
   - 课程文档关联端点：已存在，但代码格式混乱
---

## Phase 8: 2026-08-18 — 修复成果汇总

> 基于 Phase 7 二次核验结论 + 修复后的实测验证。

### 修复列表

#### 致命语法错误（6 后端 + 2 前端 + requirements.txt）
| 文件 | 问题 | 修复 |
|------|------|------|
| query_router.py | 模板迁移后缩进错误 | 修正缩进 |
| query_decomposer.py | 模板迁移碎片 + 引用不存在属性 | 删除碎片，定义 TEMPLATE 路径常量 |
| answer_reflector.py | 同上 | 同上 |
| api/tasks.py | 残留分隔线 `──────────────────────────` | 删除 |
| api/courses.py | 文档关联端点压缩到一行 | 重写为格式化的代码 |
| services/course_service.py | 3 个函数压缩到一行 | 重写为格式化代码 |
| stores/course.js | 残留注释文本在 return 对象中 | 重写为干净代码 |
| CourseDetailView.vue | 孤儿代码片段 `toast.error('移除失败')}` | 删除；同时恢复文档 Tab |
| requirements.txt | 字面 `\n` 字符串 | 拆为两行 |

#### Phase 7 功能修复
| 问题 | 修复方式 |
|------|----------|
| 7.1 笔记课程过滤断裂 | note.js + CourseDetailView + NotesView 使用 `course_space_id` |
| 7.2 config.ts 读错字段 | `config.model` → `config.model_name` (2 处) |
| 7.3 异步任务空壳 | 文档上传真异步 + 测验生成创建任务记录；补齐 `_do_process_document/_do_generate_quiz` |
| 7.4 courses.py 代码混乱 | 重写为格式化代码；定义 CourseDocResponse Schema |
| 7.8 ask_stream 缺纠错检索 | 新增 corrective 步骤（与 ask() 对称） |
| 7.9 TTS 不清理 | 实现 `cleanup_old_audio`，生成时带节流调用 |

#### 配套改动
- **Document 模型**：新增 `course_space_id` 字段 + FK(SET NULL) + 索引 + 迁移
- **types/models.ts**：Note.note_type 类型修正，LLMConfig 已验证，Source.page→string，Quiz 单题模型
- **test_rag_engine.py**：移除 6 个 `_needs_rewrite` 测试（方法已删）；修复 "upload" 断言 → 中文；修复 CrossEncoder 挂起；修复 rewrite 测试为新架构
- **test_rate_limit.py**：补回已删的 `create_rate_limit_key` 函数
- **setup.js**：修复 api mock 路径（`../services/api` → `@/services/api`），解决 jsdom+空格路径崩溃
- **rate_limit.py**：补回 `create_rate_limit_key` 辅助函数

### 测试结果
- **后端**：288 passed, 0 failed (0.99s)
- **前端**：5 test files, 21 passed (1.03s)

### 仍然存在的问题
- vue-tsc 因 typescript exports 不兼容报错（环境问题，非代码问题）
- NO_PROXY hack (run.py)，未改动
- Chat SSE 401 不刷新 (F6)，预存在设计局限
- ModelConfigView 假评分 (F8)，预存 UI 装饰
- 文档（CLAUDE.md/docs/）与代码存在系统性漂移（预存，未全部修复）

---

## Phase 9: 修复 5 个 P0 用户痛点 bug（2026-08-19 会话）

### 背景
用户视角功能盘点 + P0–P3 痛点分析后，直接修复 5 个 P0 bug。对应 findings 中的既有发现：
- #21（quiz 简答精确匹配）、#20（analysis topic 用 document_id）、#14 关联（TTS 死代码/ChatMessage 孤儿）、
  URL 导入链路断裂（url_extractor 落 .txt 但解析器工厂不支持）、流式多轮上下文断裂。

### 修复与验证
| # | Bug | 修复 | 验证 |
|---|-----|------|------|
| 1 | URL 导入永远失败 | document_parser.py 新增 TextParser（utf-8/utf-8-sig/gbk/latin-1 探测，段落累积 2000 字分页），工厂注册 .txt/.md/.markdown | verify_textparser.py PASSED |
| 2 | 流式对话丢多轮上下文 | chat_service.py：_ensure_session 后首事件 yield session；chat.js：session/sources 事件捕获 currentSession，done 后刷新会话列表，仅显式 session 才覆盖 | verify_chat.py PASSED（事件序列 session→sources→token×5→done，ChatSession/Message 落库 ID 一致） |
| 3 | 薄弱知识点显示 UUID | analysis_service.py：Document.filename 映射，缺失回退「未知文档」 | verify_analysis.py PASSED |
| 4 | 简答题永远判错 | quiz_service.py：_judge_choice（字母/大小写/标点容错）+ _judge_short_answer（精确→包含→LLM 语义裁判，失败保守判错）；新增 quiz/judge_short_answer.jinja2；判定理由补进 explanation | verify_quiz.py PASSED |
| 5 | TTS 死代码 | ChatView.vue：助手消息操作栏接入 TTSPlayer + 复制按钮；内联 MarkdownIt 换用 useMarkdown | ast.parse + diff 复核 + TTSPlayer props/useMarkdown 导出/SSE 泛化透传一致性检查 |

### 验证方法说明（重要先例）
本机无 conda/node/pytest 依赖（系统 python3 缺 sqlalchemy/fastapi；无 npm）。采用 **importlib 隔离加载真实生产代码 + stub 重依赖** 的 harness（/tmp/verify_*.py，/usr/local/bin/python3.13 执行）：
- stub sqlalchemy（select/where/order_by/scalars 链式 + 模型元类）、docling、app.db/app.exceptions/app.core.rag_engine/app.services.config_service
- chat_service 仅依赖 rag_engine.ask_stream，stub 该单例即可完整跑通 ask_question_stream
- 关键坑：config stub 必须是 async 函数；ask_question_stream 第二参是 User 对象非 id；sources chunk 必须含 filtered_sources 键

### 测试同步
- test_document_parser.py：新增 TestTextParser（纯文本/分页/空/GBK/extract_*）；工厂断言 .txt/.md 支持、.xlsx 不支持
- test_quiz.py：新增 TestJudgeChoice / TestJudgeShortAnswer（mock app.core.llm.LLM + get_llm_config_with_secret）
- 两文件 ast.parse 通过；建议有依赖环境时跑 pytest 最终确认

### 遗留
- 前端改动无法跑 vitest/vue-tsc（无 node），建议手动验证流式追问 + TTS
- P1–P3 痛点未处理（见下方落盘清单）

---

## P1–P3 痛点清单（2026-08-19 落盘，防上下文丢失）

> 来源：Phase 2/3/4 编号发现（#15-31、F1-F12、D1-D6）+ AGENTS.md Outstanding Items + Phase 7/8/9 修复后的剩余项。
> 已修复项不再列入；每项标注来源编号与修复方案。

### P1 — 高优先级（功能/安全/可靠性）

> 状态更新（2026-08-19 Phase 10）：P1-1~P1-5 已全部修复并通过验证（pytest 306 passed + E2E 冒烟 9/9）；P1-6 待用户拍板提交。

| # | 痛点 | 来源 | 影响 | 修复方案 | 状态 |
|---|------|------|------|---------|------|
| P1-1 | **/api/config/llm/with-secret 向前端明文返回解密后的 API Key** | #18 | 安全：Key 明文出网，浏览器扩展/日志可截获 | 删除端点 + 空 key 保留根因修复 + get_llm_config 返回 has_api_key/api_key_masked + 前端适配 | ✅ 已修（C1） |
| P1-2 | **Docker 环境 alembic.ini 默认 localhost:5432** | remaining #2、Phase 4 部署 | 容器未设 DATABASE_URL 时迁移连错库（连到容器自身而非 db 服务），启动失败或静默连错 | alembic/env.py：env var→settings(.env) 两级解析；容器内（/.dockerenv）解析到 localhost 时 fail-fast | ✅ 已修（C2） |
| P1-3 | **document_service 硬编码 "./uploads"** | #15 | 与 settings.upload_dir 不一致；换部署目录时上传文件落错位置、删除找不到文件 | 统一改用 settings.upload_dir | ✅ 确认 2026-08-18 已修（C3） |
| P1-4 | **异步任务内存队列重启丢任务** | #23 残余、AGENTS Outstanding | server 重启后 running/pending 任务永久卡死，前端 TasksView 显示假状态 | task_service.recover_interrupted_tasks（pending/running→failed+原因）+ lifespan 启动接线 | ✅ 已修（C4） |
| P1-5 | **BM25 索引/检索分词不一致** | AGENTS Outstanding | 索引用 rank_bm25 自有 tokenizer（空格切词），检索用 jieba 中文分词 → 中文关键词检索基本失效，hybrid 退化为纯 FAISS | _build_bm25() 统一 _tokenize（中文 jieba/英文 regex）；add_chunks/load 均统一分词，旧索引加载自愈 | ✅ 已修（C5） |
| P1-6 | **Git：全部工作未提交、无远端备份** | Phase 1 | 工作区即项目全部资产，一次误删/磁盘故障即全丢 | 按逻辑拆分 commit（P0 五修、文档、P1 批次分开）；是否 push 由用户决定 | ⏳ 待用户拍板（F） |

### P2 — 中优先级（体验/质量）

| # | 痛点 | 来源 | 影响 | 修复方案 |
|---|------|------|------|---------|
| P2-1 | **CI 触发分支 main/develop vs 实际 master** | Phase 1、D | CI 从未被触发，测试门禁形同虚设 | .github/workflows/test.yml 触发改 master；顺带验证 CI 配置（PG service、npm ci）可跑 |
| P2-2 | **ChatMessage.vue 孤儿组件** | remaining #14 | 死代码；内含独立 MarkdownIt 实例误导维护者 | TTS 已接入 ChatView，直接删除组件 + 其测试文件 |
| P2-3 | **TasksView 实际可用性未验证** | F11 残余 | 任务系统 2026-08-18 已落地，但前端页面是否真能展示任务未实测 | E2E 冒烟时顺带验证：上传文档 → TasksView 出现任务 → 状态流转 |
| P2-4 | **前端测试本机无法运行** | 环境 | 无 node/npm，vitest/vue-tsc 跑不了，前端回归只能靠人工 | 用户本机跑 npx vitest run；或批准安装 node |
| P2-5 | **14 个孤儿 Jinja2 模板** | Phase 2 | 模板目录虚胖，迁移/审计时误导 | 核对 render_template 调用方，删除确无引用的模板（谨慎：部分可能被 transformations 动态引用） |

### P3 — 低优先级（卫生/文档）

| # | 痛点 | 来源 | 修复方案 |
|---|------|------|---------|
| P3-1 | slowapi 在 requirements 但未使用；DEFAULT_RATE_LIMITS/rate_limit_exceeded_handler 死代码 | #16 | 删除 slowapi 依赖 + 死代码，或正式启用 slowapi |
| P3-2 | conftest session 级 event_loop fixture 弃用风险（pytest-asyncio>=0.23） | #17 | 迁移到 event_loop_policy 或 loop_scope 配置 |
| P3-3 | temperature 存储约定脆弱（前端 *10、后端 >1 直存、读时 /10，约定分散两端） | #22、F2 | 统一为单端转换 + 注释锚点；加回归测试 |
| P3-4 | api/__init__.py 只 re-export 5 个旧 router（实际 11 个） | #25 | 补齐 11 个 router 导出 |
| P3-5 | analysis /wrong 是 POST 但无请求体 | #27 | 改 GET 或加明确请求体 schema |
| P3-6 | ModelConfigView 适配度评分是 Math.random 假数据、configHistory 恒空 | F8 | 删除假 UI 或接真实数据 |
| P3-7 | document.ts uploadDocument 返回类型标 Document，实际是 DocProcessResponse | F10 | 修正类型定义 |
| P3-8 | App.vue keep-alive include 依赖文件名推断组件名 | F12 | 三个 view 加 defineOptions({ name }) |
| P3-9 | open-notebook-main/（6.5MB 外部参考项目）untracked 在仓库 | Phase 1 待验证 #5 | 移出仓库或加 .gitignore |
| P3-10 | 文档残余漂移（D1-D6 大部分已对齐，个别细节待查） | Phase 4 | 随 P1/P2 修复顺带更新 |


---

## Phase 11: P2/P3 全量收尾 + E2E 实测（2026-08-24 会话）

### 修复清单
| # | 内容 | 文件 |
|---|------|------|
| P2-1 | CI 分支确认早已修复（master） | .github/workflows/test.yml |
| P2-5 | 删除 4 个孤儿模板（非 findings 所记 14 个） | router/analyze, rag/history_summary, rag/direct_answer_system, rag/doc_summary_system |
| P2-3 | 新增异步任务 E2E 冒烟脚本并实测 **PASS** | scripts/e2e_tasks_smoke.py（新） |
| P3-1/4/8/9 | 确认早已修复（slowapi/api__init__/defineOptions/.gitignore） | — |
| P3-2 | 删除弃用 event_loop fixture；加 asyncio_default_fixture_loop_scope=session | conftest.py, pyproject.toml |
| P3-3 | 温度约定改为后端单端 ownership：前端直传 0.7，后端内部 ×10/+回归测试 | stores/config.ts, tests/test_config_service.py（新） |
| P3-5 | /analysis/wrong POST→GET（后端+前端+全部文档） | analysis.py, AnalysisView.vue, docs×2, README, backend CLAUDE.md |
| P3-6A | 删除 ModelConfigView 假评分+空历史 UI 及死导入 | ModelConfigView.vue（−89 行） |
| P3-7 | uploadDocument 返回类型对齐实际响应 | document.ts, models.ts(created_at 可选) |
| P3-10 | 文档漂移修正（reload/login form-data/upload 响应/model_name） | docs×2 |

### ⭐ E2E 抓到的生产级 bug（单测无法发现）
`.env` 配 BAAI/bge-m3 但从未下载成功；且**即使模型已缓存**，huggingface_hub
默认联网版本校验在本机代理环境下无限挂起 → 上传任务永远卡 running。
修复：embedder 改缓存优先加载（local_files_only 先行，未命中再联网）；
.env 回退到已缓存的 text2vec-base-chinese/768。

### 追加清理与健壮性
- 死代码删除：core/config.py（get_user_llm_config 密钥陷阱）、utils/file_handler.py、tests/test_file_handler.py、alembic versions/__pycache__
- 任务看门狗：TASK_TIMEOUT_SEC(默认600s) 超时→failed+明确错误（task_worker.py）
- F6 确认早已修复：chat.js 已含 SSE 401 刷新重试（findings 记录过期）

### 验证
pytest 307 ✅ / vitest 18 ✅ / vue-tsc 0 err ✅ / e2e_tasks_smoke PASS ✅

### ⚠️ 注意
.env 切回 768 维模型后，旧 bge-m3(1024维) 索引检索会维度失配，需重新上传对应文档。

### Phase 11 追加（同日第二轮打磨）
- fix(backend): 笔记语义索引缺失修复——create/update/delete_note 后全量重建
  notes_{uid} 索引（此前恒空，搜索永远返回空列表）；+4 单测，pytest 311
- chore(backend): core/__init__.py 清空再导出——无人包级导入，避免冷启动
  急切实例化 FAISS/Embedder 单例
- 记录勘误：url_extractor 阻塞(#19)早已 to_thread 修复；nginx SSE 已是
  600s+buffering off（非 60s）；F6(chat SSE 401 刷新)已实现于 chat.js；
  README 路由表归一化后全覆盖（D3 缺口早轮已补）
