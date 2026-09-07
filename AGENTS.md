# Study Copilot - Root AGENTS.md

This file provides architectural guidance for contributors working on Study Copilot.

## Project Overview

**Study Copilot** is an AI-powered learning assistant built with FastAPI + Vue3. It enables users to upload documents (PDF/DOCX/PPTX), ask questions via RAG (Retrieval-Augmented Generation), generate quizzes automatically, and track learning progress.

### v2 Features
- **Agentic RAG**: 查询路由、上下文感知改写、自适应检索、纠错检索、会话摘要、答案自我反思、Hybrid检索（FAISS+BM25+RRF）
- **笔记系统**: 手动/AI 笔记，标签管理，语义搜索（FAISS向量索引）
- **课程空间**: 按课程组织文档和笔记，课程-文档关联管理
- **内容转换**: 8 种转换类型（摘要/要点/大纲/卡片/思维导图/问答/翻译/解释）
- **URL 导入**: 从网页链接提取内容
- **TTS 语音**: Edge TTS 朗读答案和笔记
- **异步任务**: 批量操作，持久化任务队列（pending 行落库、worker 轮询认领、看门狗超时、重启自动恢复孤儿任务）
- **凭证加密**: Fernet 加密存储 API Key
- **数据库迁移**: Alembic
- **CI/CD**: GitHub Actions
- **代码质量**: Ruff linter + TypeScript + vue-tsc

**Key Values**: Local-first embedding, multi-provider LLM support, Chinese-language optimized, self-hosted.

---

## Current State (2026-09-06)

- **Git**: `master` 分支（全部优化落地，未 push 远端）
- **Tests**: 后端 527 passed (41 测试文件) / 前端 258 passed (28 测试文件) / 覆盖率 72.43% (门禁 65%) / vue-tsc exit 0
- **Ports**: 前端 3000，后端 8000
- **Frontend**: Vue3 + Vite + TypeScript + Pinia + TailwindCSS + GSAP + Element Plus
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16+ + pgvector + sentence-transformers
- **打包**: backend/pyproject.toml（hatchling）+ uv.lock（~484 TOML 条目）；requirements.txt 为兼容层
- **CI**: uv 安装依赖 + ruff lint + mypy 类型门禁（渐进式棘轮配置）+ 覆盖率门禁 65% + 前端 vitest/vue-tsc 全链路
- **可观测性**: 结构化 JSON 日志（生产）/ 文本（开发）+ X-Trace-ID 纯 ASGI 追踪中间件 + /health DB 探测
- **Docker**: 多阶段构建、非 root 运行、healthcheck；.dockerignore 收敛构建上下文

### Recent Changes (2026-08-17 ~ 2026-09-06)

**2026-09-06 批次（AI 互动课堂多模态专属配置与课程乱码根治）：**
1. **课程全链路乱码根治与大纲结构化重塑** (`classroom_service.py` + `classroom_api.py` + `courses.py` + `course.ts` + `CourseCard.vue` + `CourseDetailView.vue` + `CourseListView.vue`)：
   - 后端全部 `json.dumps` 补齐 `ensure_ascii=False`，彻底根除存入 PostgreSQL 数据库的 `\uXXXX` Unicode 转义字符；
   - 修复创建/生成课程接口，`description` 返回大纲纯文本概述（而非 raw 截断 JSON）；
   - 前端新增 `parseCourseDescription` 健壮容错工具函数，解耦大纲 JSON 与简介，展示动态状态徽章；
   - `CourseDetailView.vue` 新增大纲章节目录卡片 Tab，结构化展现学习目标、难度、建议时长与重点标签；编辑弹窗反序列化显示纯文本。
2. **模型设置专属区域（AI 互动课堂与多模态模型设置）** (`ModelConfigView.vue` + `config_service.py` + `config.py` + `image_generator.py`)：
   - **独立图像生成配置**：内置 SiliconFlow (FLUX.1-schnell)、OpenAI DALL-E 3、阿里通义万相 (Wanx) 与自定义 4 种预设；支持 Base URL、Model、画幅比例选择与 Fernet 密文存储；
   - **一键连通性测试**：提供「测试生图接口」按钮（`POST /api/config/test-image`），实时检测画图模型可用性与延迟；
   - **独立课堂教学模型配置**：支持自由切换「复用主模型」或「自定义专属模型」，独立配置专属 Base URL、Model 和 API Key；
   - 数据库模型 `UserLLMConfig` 增设 `extra_config` JSON 字段，实现多模态配置安全落库与掩码脱敏。
3. **微课生成配图链路贯通** (`course_generator.py`)：
   - 课程生成逻辑无缝集成 `image_generator.py`，根据用户配置的生图模型或系统默认配置，自动为生成课程设计封面图。
4. **全量测试与门禁验证**：
   - 后端新增 `test_classroom_config_roundtrip_and_encryption` 与 `test_image_connectivity_endpoint`；后端测试全通 **527 passed**（覆盖率 72.43%）；前端测试扩充至 **258 passed**，`vue-tsc` 0 errors，`npm run build` 构建成功。

**2026-09-06 批次（后台任务全屏宽屏控制台与差异化任务名称重塑）：**
1. **彻底破除旧版 256px 矮盒与狭窄容器限制** (`TasksView.vue` + `TaskPanel.vue`)：
   - 容器由固定 `max-w-4xl` 升级为现代宽屏自适应布局（`w-full max-w-7xl`），垂直方向破除 `max-h-64` 内部滚动局限，实现全尺寸平铺；
   - 移除 `TasksView.vue` 中冗余重复的标题与底部冲突的 Skeleton/EmptyState，统一由高内聚的 `TaskPanel.vue` 控制台管理。
2. **全功能控制台与状态看板** (`TaskPanel.vue`)：
   - 顶栏增设「全部、进行中、已完成、失败/异常」4 维指标统计卡片，支持一键点击筛选；
   - 增设胶囊式状态筛选 Tab 与实时防抖关键词搜索框（支持匹配文件名、业务标题、任务ID与任务类型）；
   - 增设任务完成态快捷联动动作（文档解析完成支持“查看文档”，测验生成完成支持“前往测验”）。
3. **差异化任务命名与全链路元数据透传安全** (`task_service.py` + `task_worker.py` + `document_service.py` + `TaskPanel.vue`)：
   - **后端元数据字典合并保全**：`update_task` 采用安全合并（`{**existing_result, **result}`），彻底根绝异步完成时冲刷掉初始任务入队时的 `filename`、`doc_id`；
   - **Worker 结果丰富回传**：文档处理任务回传真实文件名，测验生成任务回传关联文档名称列表（`document_names`）；
   - **前端智能多级回退解析**（`getTaskInfo`）：彻底废除千篇一律的枚举类型名，动态组装为《深度学习导论.pdf》· 文档解析与向量化、《现代操作系统》· 智能测验生成；历史数据通过关联文档 Store 自动补充对齐；动态展示切片段数、分块策略、真实耗时与起止时间戳。
4. **全链路自动化测试与类型门禁**：
   - 新增前端单元测试 `frontend/tests/views/TasksView.test.js`（5 passed）；
   - 后端测试通过 **524 passed**（覆盖率 72.95%），前端测试扩充至 **258 passed**，`vue-tsc` 0 errors，`npm run build` 成功。

**2026-09-06 批次（多角色研讨三级菜单发言正文折叠与单行缩略预览）：**
1. **三级菜单（各角色发言实际内容）折叠交互** (`ChatDiscussionItem.vue`)：
   - 角色发言卡片顶栏支持点击折叠/展开，带平滑旋转箭头矢量图标与「收起 / 展开」状态切换；
   - 折叠状态下自动展示单行极简文本缩略预览（自动过滤 Markdown 标记），点击预览亦可快速恢复展开；
   - 流式生成过程中发言气泡强制保持实时展开状态，确保逐字打字动画与脉冲光标完全可见；
   - 一键复制单条发言保持冒泡阻断，互不干扰；
   - 扩充单元测试 `ChatMessageItem.test.js`，前端通过 **253 passed**，`vue-tsc` 0 errors。

**2026-09-06 批次（多角色研讨全链路会话持久化与历史无损复现）：**
1. **多角色研讨全链路会话持久化** (`backend/app/api/chat.py` + `backend/app/services/chat_service.py`)：
   - `DiscussRequest` 增加 `session_id: str | None = None`，支持绑定既有会话或自动生成会话；
   - 用户提问消息即时落库（`role="user"`，计算 embedding 向量化索引支持全局语义搜索）；
   - SSE 讨论流首包即时下发 `{"type": "session", "session_id": "..."}`，对齐常规问答体验；
   - 研讨成果落库（`role="discussion"`）：在 `done` 及异常/客户端断开退出的 `finally` 阶段，将结构化交锋轮次（`discussion_turns`）、发言角色元数据（`personas`）、主持人总结（`summary`）序列化保存于 `messages.sources` 字段中，`content` 存储人类可读 Markdown 纪要兼顾向量检索；
   - `GET /api/chat/history/{session_id}` 接口深度反序列化，提取并返回 `discussionTurns` 与 `summary` 元数据。
2. **前端无缝会话绑定与历史反序列化呈现** (`ChatView.vue` + `chat.ts` + `ChatDiscussionItem.vue`)：
   - `handleDiscuss` 请求透传 `currentSession`，接收 `session` 事件自动绑定会话状态，流式完成触发侧边栏会话列表智能无感刷新；
   - `chatStore.fetchHistory` 在加载历史消息时自动归一化映射 `discussionTurns`；
   - 历史消息以 `role="discussion"` 渲染时，完整复现三级折叠菜单与独立主持人总结卡片。
3. **全链路测试套件扩充与类型门禁**：
   - 新增后端测试 `backend/tests/test_discuss_persistence.py`（3 个测试用例，全通）；
   - 扩充前端 `chat.test.js` 与 `ChatMessageItem.test.js`；
   - 后端测试通过 **524 passed**（覆盖率 72.97%），前端通过 **252 passed**，`vue-tsc` 0 errors。

**2026-09-06 批次（多角色研讨三级可折叠流式菜单与第二轮空内容根因自愈修复）：**
1. **彻底消除连续 Assistant 协议冲突与 API 早停** (`persona_discussion.py` + `llm.py`)：重构多轮多角色 Prompt 结构为标准的单轮 `system`（人设）+ `user`（包含结构化的【圆桌研讨历史记录】与当前轮次互辩任务），彻底摒弃先前堆叠连续 `assistant` 消息导致的大模型 API 早停与第二轮偶发空内容漏洞；增设空流自动降级重试与保底见解机制。
2. **三级可折叠流式菜单交互体系** (`ChatDiscussionItem.vue`)：
   - **一级菜单（研讨过程折叠总容器）**：标题栏展示「多角色研讨过程」与轮次统计，支持一键折叠收纳数千像素的交锋记录，流式生成中自动保持展开；
   - **二级菜单（轮次面板 Round Accordion）**：按轮次自动归类（「第 1 轮 · 初始立论与破题」、「第 2 轮 · 深度互辩与交锋」），展示参会角色徽章与状态，当前吐字轮次智能展开；
   - **三级菜单 / 内容（角色讨论正文与逐字打字流式）**：矢量图标、主题色标签、呼吸打字光标（`animate-pulse`），无论何种折叠状态均平滑接收 `persona_chunk` 流式输出，支持单条发言一键复制；
   - **独立主持人总结成果卡片**：沉淀于一级讨论容器下方，即使折叠研讨过程，核心共识与学习建议依然醒目可见。
3. **真实端到端验证与测试全绿**：通过阶跃星辰（StepFun）`step-3.7-flash` 模型实测 2 轮（4 次发言 + 1 次总结，10,000+ 字）流式输出，第二轮零空内容；前端 245 passed（26 个测试文件），后端单测 8 passed，`vue-tsc` 0 errors。

**2026-09-06 批次（多角色研讨 Peer Context 深度互辩与逐字流式时序流升级）：**
1. **实现 Peer Context 互辩机制** (`persona_discussion.py`)：新增 `build_peer_context_section()`，提取前序同伴发言核心论点，强制要求后续角色从自身人设视角进行深度回应、反驳、举反例或痛点追问，彻底消除各自作答的割裂感。
2. **逐 Token 打字流式推进** (`persona_discussion.py` + `llm.py`)：实现 `_stream_llm_response()` 与 `llm.chat_stream()` 逐 token 产出，扩展 SSE 细粒度事件流（`persona_start` ➔ `persona_chunk` ➔ `persona_speak` ➔ `summary_start` ➔ `summary_chunk` ➔ `summary` ➔ `done`），全过程字字可见、打字机动效呈现。
3. **会议时序流视图（Timeline Round Flow）** (`ChatDiscussionItem.vue` + `ChatView.vue` + `chat.ts`)：
   - 彻底废除按角色静态聚合的旧模式，重构为按发言发生时序自然排列的圆桌会议流，标注「第 N 轮 · 初始立论 / 互辩交锋」；
   - 增设当前活跃发言角色状态条（`currentSpeaker`），动态展示头像、构思状态与脉冲动画；
   - 逐字输出期间显示流式打字光标（Blinking Cursor），主持人总结卡片同步支持逐 token 归纳流式输出；
   - 前后端测试全量绿灯：后端 519 passed（覆盖率 72.10%），前端 241 passed，`vue-tsc` 0 errors。

**2026-09-06 批次（多角色研讨端到端链路自愈与全状态可视化）：**
1. **模型配置健壮对齐** (`persona_discussion.py` + `llm.py`)：修复 `persona_discussion` 从 `user_llm_config` 读取模型名时使用 key `"model"` 导致获取为 `None` 并回落 `.env` 模型（导致阶跃星辰 StepFun 等自定义服务商报 404 拒绝）的问题；`LLM.from_config` 与 `persona_discussion` 统一对齐兼顾兼容 `model_name` 与 `model`。
2. **请求校验与角色解析自愈** (`chat.py`)：将 `PersonaConfig` 的 `name` 设为可选，自动根据 `role`/`id` 从预置库或用户自定义角色库补全角色名、矢量图标、主题色与人设提示词，彻底解决缺少 `name` 引发 422 验证失败的问题。
3. **前端多角色讨论全状态可视化** (`ChatDiscussionItem.vue` + `ChatView.vue` + `chat.ts`)：
   - 彻底修复此前讨论卡片只循环渲染 `personas`，导致一旦发生错误或进入总结时消息空白无反应的隐蔽缺陷；
   - 增设醒目的错误状态告警卡片，直观呈现错误详情，不再静默吞并；
   - 增设各角色发言前的筹备动效等待卡片；
   - 增设独立的主持人「讨论总结」卡片，以墨绿色专业学习卡片渲染主要共识、关键分歧与学习建议；
   - 前端测试套件扩充至 240 passed，后端扩充至 517 passed。

**2026-09-06 批次（研讨角色同源 SVG 矢量图标全面统一）：**
1. **统一 SVG 矢量图标来源** (`frontend/src/components/icons/index.ts`)：全面废弃 Emoji 字符（`🧑‍🏫`、`🎓`、`🌱`、`📝`、`💬`、`✨` 等），改用本项目统一维护的 Reicon Outline 24×24 矢量图标库，包含 `User`、`GraduationCap`、`ChatLineRound`、`EditPen`、`Brain`、`Lightning`、`TrendCharts`、`MagicStick`、`Reading`、`Promotion`、`ChatDotSquare` 等 16 套专业学习与研讨意象。
2. **后端核心模型与事件解构** (`persona_discussion.py` + `database.py` + `chat.py`)：预置角色库 avatar 统一调整为 SVG 图标标识名，事件流中携带 `color` 主题色与图标标识，自定义角色 `CustomPersona` 字段与验证对齐支持图标名。
3. **前端 UI 沉浸式演进** (`PersonaManageDialog.vue` + `ChatDiscussionItem.vue` + `ChatView.vue`)：管理弹窗内置 16 款高频 SVG 药丸点选网格与主题色联动预览；多角色讨论消息气泡支持图标与角色色同步渲染；讨论下拉树移除 Emoji 统一显示 SVG 矢量图标。
4. **测试与类型安全**：后端 513 passed（覆盖率 72.32%）；前端 232 passed（25 测试文件），`vue-tsc` 0 errors。

**2026-09-06 批次（自定义角色多端云同步）：**
1. **自定义角色数据库持久化** (`database.py` + `alembic` 迁移 `e8f9a0b1c2d3_add_custom_personas.py`)：新增 `custom_personas` 表，按 `user_id` 严格隔离，支持角色名称、矢量图标、主题色、自定义 Prompt 人设（跨设备/换浏览器登录同一账号自动同步）。
2. **角色完整 CRUD API 与流式讨论接入** (`chat.py` + `auth.py`)：实现 `GET/POST/PUT/DELETE /api/chat/personas`，`GET` 智能合并官方预置与用户自定义角色；`POST /api/chat/discuss` 自动根据 `id`/`role` 查询数据库补全未传的自定义人设提示词。
3. **前端交互与管理弹窗** (`PersonaManageDialog.vue` + `ChatView.vue`)：在讨论模式顶栏增加「管理研讨角色」入口与下拉树快捷项；提供预置与自定义双列表、快捷图标选择器、调色板点选器与 3 款快速人设灵感模板；创建后自动选中参与研讨。

**2026-09-05 批次（AI 互动课堂原生架构与多文档布包融合）：**
1. **多文档布包公平预算** (`document_bundle.py`)：实现 `allocateDocumentTextBudgets` 算法，两阶段分配（基础 1500 字符 + 按未满足需求比例分配剩余预算 + 标点/换行边界安全截断）。
2. **多智能体讨论模式** (`persona_discussion.py` + `chat.py`)：内置 4 套标准角色预设（苏老师 `teacher`、学霸 `thinker`、求知同学 `curious`、归纳助手 `notetaker`），新增 `GET /api/chat/personas`，`POST /api/chat/discuss` 支持动态人设配置与 `rag_snippets` / `full_docs` 上下文模式。
3. **双通道状态轮询与自愈** (`classroom_api.py` + `classroom_service.py`)：新增 `GET /api/classroom/{job_id}/status`，在轮询发现任务完成时主动从课堂引擎拉取产物并同步占位课程与测验，杜绝单纯依赖 Webhook 造成的单点失效。
4. **配图开关与课程生成**：课堂创建请求与前端弹窗支持 `enable_image_generation`（AI 图像生成配图），`POST /api/courses/generate` 支持本地大纲与测验生成。
5. **数据库模式演进**：Alembic 迁移 `b9a8c7d6e5f4_quiz_document_id_nullable.py` 将 `quizzes.document_id` 设为可空，支持课程级跨文档测验沉淀。
6. **前端体验增强**：ChatView 增加多智能体讨论人设多选下拉与上下文切换；GenerateClassroomDialog 增加配图开关；`classroom.ts` 增加 `pollJobStatus` 轮询与自动缓存失效机制。
7. **测试与类型安全**：后端新增 `test_persona_discussion.py`、`test_document_bundle.py`、`test_classroom_integration.py`、`test_course_generator.py`，全量测试扩充至 490 passed（覆盖率 72.52%）；前端全量 227 passed（24 测试文件），`vue-tsc` 0 errors。

**2026-08-30 批次：**
1. 测试扩展：`test_analysis_service.py`（+15）+ `test_transform_service.py`（+20），覆盖率 71.76%
2. M-4: temperature ×10 隐式约定消除（migration + config_service 清理 + 测试修正）
3. F-M3 补齐：`note.ts` SWR 30s 缓存 + CUD 失效，+4 缓存测试
4. 文档清理：6 份过时文件移至 archive_docs/（UPGRADE_PLAN/OPTIMIZATION_CHECKLIST/CHANGELOG 等）
5. 测试总览更新：README/docs testing.md 同步 420 用例清单

**2026-08-17 批次（P0~P3）：**
1. **P0 紧急修复** (237c052): git 提交、text import、requirements 补全、quiz 密文修复、config model_name 对齐、alembic env、notes 前后端契约、course tab 404
2. **P1 对齐** (fdbc370): 端口 5173→3000 (14 处)、API 路径纠错、CI main→master、测试方法名同步、前端 mock
3. **P2 迁移** (55d8502): 6 模块模板迁移（14 orphan→render_template）、typescript+vue-tsc、.env.example + upload_dir、死代码清理
4. **P3 卫生** (8c57f63): defineOptions、useMarkdown composable、温度注释、api__init__ 补全、TTS TODO
5. **E 纠错** (02eae49): retrieval_grader 接入 ask/ask_stream、移除 _needs_rewrite 死代码
6. **C+D 特性** (6989751): 笔记语义搜索（service+API）、课程-文档关联（routes+service+store）
7. **A 异步** (32c8440): task_worker.py、main.py lifespan 接线、document_service 异步化、POST /api/tasks
8. **B Hybrid** (part of 02eae49/55d8502): vector_store.py 新增 _tokenize()，支持 jieba 中文分词 + BM25+FAISS+RRF

### Outstanding Items
- uv.lock 需在依赖变更后手动运行 `cd backend && uv lock` 再生
- 真机验证状态（2026-08-27）：后端 15/15 冒烟全通，RAG 端到端返回带 `[来源N]`
  引用的真实生成内容；用户配置默认值已修复为回落 settings.openai_model，
  .env 的 OPENAI_MODEL（siliconflow）经直连与 SDK 双路实测有效
- 本地测试环境（2026-08-27 起）：backend/.venv 已补齐全量依赖（含 faiss/docling/sentence-transformers），
  `HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/` 可本地全量跑；注意 .venv 由 conda Python 3.13 创建，
  类型检查目标版本由 pyproject `python_version = "3.11"` 钉住（与 Docker 一致）
- pytest 配置唯一源为 pyproject `[tool.pytest.ini_options]`（pytest.ini 已删除——它会静默遮蔽 pyproject，
  曾导致 loop_scope=session 失效、全量测试跨循环崩溃）；uv 缓存若被沙箱拒写可加 `UV_CACHE_DIR=/tmp/uv-cache`

### Resolved Since 2026-08-17（见 archive_docs/remaining_issues.md 历史记录）
- BM25 索引/检索分词统一 _tokenize()（C5），旧索引加载自愈
- 任务队列持久化：pending 落库 + worker 轮询 + recover_interrupted_tasks 接入 lifespan（C4）
- CourseDetailView 文档 tab、analysis/wrong 方法语义、pytest-asyncio loop_scope 迁移均已完成

---

## Three-Tier Architecture

```
┌──────────────────────────────────────────────┐
│          Frontend (Vue3 + Vite)              │
│          frontend/ @ port 3000               │
├──────────────────────────────────────────────┤
│ - Auth, Document, Chat, Quiz, Analysis views │
│ - Pinia state management                     │
│ - TailwindCSS styling                        │
│ - Axios HTTP client with interceptors        │
└──────────────────┬───────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼───────────────────────────┐
│          Backend (FastAPI)                   │
│          backend/ @ port 8000                │
├──────────────────────────────────────────────┤
│ - REST API + SSE streaming                   │
│ - RAG engine (Agentic: Router + Adaptive + Corrective + Reflection) │
│ - Quiz generator (LLM-powered)              │
│ - JWT authentication                         │
│ - Multi-provider LLM abstraction            │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│          Data Layer                          │
├──────────────────────────────────────────────┤
│ - PostgreSQL (async via asyncpg + SQLAlchemy)│
│ - pgvector (PostgreSQL extension, vector search)│
│ - File storage (uploads/)                    │
└──────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend (`backend/`)
- **Framework**: FastAPI 0.109+
- **Language**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (async mode)
- **Database**: PostgreSQL 16+ with asyncpg
- **Vector Search**: FAISS
- **Embeddings**: sentence-transformers (text2vec-base-chinese / BGE-M3)
- **Document Parsing**: Docling, PyMuPDF, python-docx, python-pptx
- **LLM**: OpenAI SDK (OpenRouter / OpenAI / Anthropic / Gemini / custom)
- **Auth**: JWT via python-jose + passlib (bcrypt)
- **Validation**: Pydantic v2

### Frontend (`frontend/`)
- **Framework**: Vue 3 (Composition API with `<script setup>`)
- **Build Tool**: Vite
- **State**: Pinia
- **Routing**: Vue Router
- **Styling**: TailwindCSS
- **HTTP**: Axios
- **Rendering**: markdown-it + highlight.js
- **Animations**: GSAP
- **Testing**: Vitest

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | FAISS (file-based) | No extra service; simple deployment |
| Embedding | Local SBERT models | Privacy, no API cost, Chinese support |
| Streaming | SSE | Standard HTTP, no WebSocket complexity |
| LLM abstraction | OpenAI-compatible API | Swap providers without code changes |
| Auth | JWT (stateless) | Standard, works with SPA |

---

## Component References

- **[backend/CLAUDE.md](backend/CLAUDE.md)** — Backend architecture, API structure, core modules
- **[frontend/CLAUDE.md](frontend/CLAUDE.md)** — Frontend architecture, components, stores

---

## Documentation

- **[docs/0-START-HERE/](docs/0-START-HERE/index.md)** — Quick start
- **[docs/1-INSTALLATION/](docs/1-INSTALLATION/index.md)** — Detailed installation
- **[docs/2-ARCHITECTURE/](docs/2-ARCHITECTURE/index.md)** — System architecture
- **[docs/3-API-REFERENCE/](docs/3-API-REFERENCE/index.md)** — API endpoints
- **[docs/4-DEVELOPMENT/](docs/4-DEVELOPMENT/index.md)** — Development guide
- **[docs/4-DEVELOPMENT/testing.md](docs/4-DEVELOPMENT/testing.md)** — Testing guide

---

## Common Tasks

### Add a New API Endpoint
1. Create/edit router in `backend/app/api/`
2. Define Pydantic models for request/response
3. Add logic in `backend/app/core/` if needed
4. Register router in `backend/app/main.py`
5. Add tests in `backend/tests/`

### Add a New Frontend View
1. Create view in `frontend/src/views/`
2. Add route in `frontend/src/router/`
3. Create Pinia store in `frontend/src/stores/` if needed
4. Add API methods in `frontend/src/services/api.ts`

### Run Tests
```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npx vitest run
```
