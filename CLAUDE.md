# Study Copilot - Root CLAUDE.md

This file provides architectural guidance for contributors working on Study Copilot.

## Project Overview

**Study Copilot** is an AI-powered learning assistant built with FastAPI + Vue3. It enables users to upload documents (PDF/DOCX/PPTX), ask questions via RAG (Retrieval-Augmented Generation), generate quizzes automatically, and track learning progress.

### v3 Features (Current)
- **TypeScript**: 渐进式 TypeScript 迁移，stores 全面 TS，views/composables 渐进覆盖
- **组件复用**: Element Plus (el-button, el-card, el-input 等通用组件); Base 通用组件待实现
- **Prompt 模板化**: Jinja2 模板管理 27 个 LLM prompt (7 个子目录)
- **设计系统**: 完整的 CSS 变量系统（间距、字体、颜色、组件样式）
- **Composables**: useApi、useMarkdown 等可复用逻辑
- **主题系统**: Light/Dark 主题切换，CSS 变量驱动
- **响应式布局**: 移动端适配，自适应侧边栏，用户菜单
- **表单组件**: BaseInput、BaseSelect、BaseTextarea 统一交互
- **数据组件**: BaseTable（排序/分页）、BaseList（加载/空状态）

### v2 Features
- **Agentic RAG**: 查询路由、上下文感知改写、自适应检索（4种策略）、纠错检索、会话摘要、答案自我反思
- **混合检索**: FAISS语义检索 + BM25关键词检索 + RRF融合
- **笔记系统**: 手动/AI 笔记，标签管理，语义搜索
- **课程空间**: 按课程组织文档和笔记
- **内容转换**: 8 种转换类型（摘要/要点/大纲/卡片/思维导图/问答/翻译/解释）
- **URL 导入**: 从网页链接提取内容
- **TTS 语音**: Edge TTS 朗读答案和笔记
- **异步任务**: 批量操作，后台任务队列
- **凭证加密**: Fernet 加密存储 API Key
- **数据库迁移**: Alembic
- **代码质量**: Ruff linter

**Key Values**: Local-first embedding, multi-provider LLM support, Chinese-language optimized, self-hosted.

---

## Three-Tier Architecture

```
┌──────────────────────────────────────────────┐
│          Frontend (Vue3 + Vite)              │
│          frontend/ @ port 3000               │
├──────────────────────────────────────────────┤
│ - 13 views (Home, Login, Register, Upload, Document, Chat, Quiz, Analysis, ModelConfig, CourseList, CourseDetail, Notes, Tasks) │
│ - 10 Pinia stores                             │
│ - 12 common components + 9 feature components │
│ - TailwindCSS + GSAP styling                  │
│ - Axios HTTP client with JWT interceptors    │
└──────────────────┬───────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼───────────────────────────┐
│          Backend (FastAPI)                   │
│          backend/ @ port 8000                │
├──────────────────────────────────────────────┤
│ - 13 REST API routers (auth/chat/config/courses/document/metrics/notes/quiz/tasks/transform/tts/analysis)
│ - Agentic RAG (Router + Adaptive + Corrective + Reflection) │
│ - Vector search via PostgreSQL+pgvector (production)  │
│ - Multi-provider LLM abstraction (OpenAI SDK)│
│ - JWT authentication (access + refresh)      │
│ - 10 service orchestration modules (analysis, auth, chat, config, course, document, note, quiz, task, transform)               │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│          Data Layer                          │
├──────────────────────────────────────────────┤
│ - PostgreSQL 16+ + pgvector extension (production vector search) │
│ - Legacy: FAISS + BM25 + RRF file-based (backward compat) │
│ - File storage (uploads/)                    │
│ - Alembic migrations                         │
└──────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend (`backend/`)
- **Framework**: FastAPI 0.109+
- **Language**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (async mode)
- **Database**: PostgreSQL 16+ with asyncpg
- **Vector Search**: FAISS (IndexFlatIP for cosine similarity)
- **Keyword Search**: rank-bm25 (Okapi BM25)
- **Hybrid Search**: RRF (Reciprocal Rank Fusion)
- **Embeddings**: sentence-transformers (text2vec-base-chinese / BGE-M3) with local caching
- **Document Parsing**: Docling (with OCR), PyMuPDF, python-docx, python-pptx
- **LLM**: OpenAI SDK (OpenRouter / OpenAI / Anthropic / Gemini / custom)
- **Auth**: JWT via python-jose + passlib (bcrypt)
- **Validation**: Pydantic v2 + pydantic-settings
- **Migrations**: Alembic
- **Testing**: pytest + pytest-asyncio + pytest-cov

### Frontend (`frontend/`)
- **Framework**: Vue 3.4 (Composition API with `<script setup lang="ts">`)
- **Language**: TypeScript (渐进式迁移，JS/TS 共存)
- **Build Tool**: Vite 5.2
- **State**: Pinia 2.1
- **Routing**: Vue Router 4.3 (lazy-loaded, auth guards)
- **Styling**: TailwindCSS 3.4 + CSS Variables 设计系统
- **HTTP**: Axios 1.6 with JWT interceptors + auto-refresh
- **Rendering**: markdown-it 14.1 + highlight.js 11.9
- **Animations**: GSAP 3.15
- **Testing**: Vitest 4.1 + Vue Test Utils 2.4 + Testing Library
- **UI Library**: Element Plus 2.14 (auto-imported via unplugin-vue-components)

### 通用组件 (`frontend/src/components/common/`)
- `AppHeader.vue` — 全局头部导航（支持主题切换、移动端菜单、用户下拉）
- `AppSidebar.vue` — 侧边栏导航（响应式，移动端遮罩，文档列表）

> **Note**: Base 通用组件（BaseDialog、BaseButton、BaseInput、BaseSelect、BaseTable 等）在当前架构中改为使用 Element Plus 组件直接实现，无需重新实现。（v3 Feature 组件复用已迁移至 Element Plus。）

### Composables (`frontend/src/composables/`)
- `useApi.ts` — 统一 API 请求处理（错误处理、toast 通知）
- `useMarkdown.ts` — Markdown 渲染（markdown-it 封装）
- `useChatExport.ts` — 聊天导出 Markdown 构建（buildChatMarkdown, formatDate）

### Backend Internal Modules (`backend/app/`)

#### Core (`app/core/` — 23 modules)
| Module | Responsibility |
|--------|---------------|
| `llm.py` | OpenAI SDK wrapper with retry/backoff |
| `embedder.py` | sentence-transformers wrapper (async + caching) |
| `rag_engine.py` | Agentic RAG orchestrator (5-step pipeline) |
| `query_router.py` | Intent classification + context rewrite |
| `adaptive_retriever.py` | Adaptive retrieval strategy selection (4 strategies) |
| `retrieval_grader.py` | Two-level retrieval quality assessment |
| `query_decomposer.py` | Query decomposition + entity extraction |
| `answer_reflector.py` | Answer quality self-reflection |
| `document_parser.py` | Factory: Docling / PyMuPDF / python-docx / python-pptx |
| `chunker.py` | Fixed / Semantic / Hierarchical chunking |
| `quiz_generator.py` | LLM-based question generation |
| `transformations.py` | 8 transformation types (summary/keypoints/outline/flashcards/mindmap/qa/translate/explain) |
| `encryption.py` | Fernet credential encryption |
| `tts.py` | Edge TTS wrapper |
| `url_extractor.py` | Web content extraction |
| `rate_limit.py` | Sliding-window IPRateLimiter |
| `logger.py` | Structured logging with trace-id ContextVar |
| `template_manager.py` | Jinja2 template renderer for LLM prompts |
| `task_worker.py` | Background task enqueue/dequeue/process |
| `pgvector_store.py` | **Production** vector search via PostgreSQL+pgvector |
| `vector_store.py` | Legacy FAISS/BM25/Hybrid file-based (backward compat) |

#### Services (`app/services/` — 10 modules)
| Module | Responsibility |
|--------|---------------|
| `analysis_service.py` | Wrong answer analysis, knowledge stats, progress |
| `auth_service.py` | Register, login, refresh_token |
| `chat_service.py` | Ask question, stream answer, history management |
| `config_service.py` | Get/create/update LLM config |
| `course_service.py` | Course CRUD, document associations |
| `document_service.py` | Upload, delete, list, get documents |
| `note_service.py` | Notes CRUD, tagging, semantic search |
| `quiz_service.py` | Quiz generation, submission, history |
| `task_service.py` | Async task CRUD, cancel, recover interrupted |
| `transform_service.py` | Content transformation orchestration |

#### Other
- **Middleware**: `trace.py` — TraceIdMiddleware (X-Trace-ID propagation, structured logs via ContextVar)
- **Utils**: `auth.py` — Password hashing (bcrypt), JWT create/decode, get_current_user
- **Templates**: 27 .jinja2 prompt files across 7 directories (rag/, quiz/, reflector/, retriever/, router/, decomposer/, transformations/)
- **No `schemas/` directory**: Pydantic schemas defined inline in each router
- **No `models/` directory**: ORM models defined in `app/db/database.py`

---
## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | PostgreSQL+pgvector (production); FAISS+BM25+RRF (legacy, backward compat) | pgvector: no extra service, SQL-native; legacy kept for migration path |
| Keyword Search | BM25 (rank-bm25) | Complements semantic search with exact matching |
| Hybrid Retrieval | RRF fusion (legacy file-based); pgvector IVFFlat (production) | Best of both worlds; no reranking needed for fusion |
| Embedding | Local SBERT models | Privacy, no API cost, Chinese support |
| Streaming | SSE (fetch + ReadableStream) | Standard HTTP, no WebSocket complexity |
| LLM abstraction | OpenAI-compatible API | Swap providers without code changes |
| Auth | JWT (access + refresh) | Standard, works with SPA, auto-refresh |
| Document parsing | Docling + PyMuPDF fallback | Best-in-class extraction with safe fallback |
| Chunking | Markdown-aware + semantic + hierarchical | Preserves document structure, supports all use cases |
| Prompt Management | Jinja2 templates | 易于维护、版本控制、A/B 测试 |
| Frontend Types | TypeScript (渐进式) | 类型安全、IDE 提示、减少运行时错误 |
| Component Design | Element Plus 通用组件 | UI 一致、维护成本低、无需自建基础组件 |
| Theme System | CSS Variables + Dark mode | 用户体验、系统级适配、易于扩展 |
| Responsive | Mobile-first + 断点适配 | 移动端体验、自适应布局 |
| Form Components | Element Plus Input/Select/InputNumber | 统一交互、表单验证、可访问性 |

---

## Component References

- **[backend/CLAUDE.md](backend/CLAUDE.md)** — Backend architecture, API structure, core modules, RAG pipeline
- **[frontend/CLAUDE.md](frontend/CLAUDE.md)** — Frontend architecture, components, stores, routing

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
1. Create router in `backend/app/api/`
2. Add Pydantic models for request/response
3. Add service function in `backend/app/services/`
4. Add core logic in `backend/app/core/` if needed
5. Register router in `backend/app/main.py`
6. Add tests in `backend/tests/`

### Add a New Frontend View
1. Create view in `frontend/src/views/` (使用 `<script setup lang="ts">`)
2. Add route in `frontend/src/router/` (lazy-loaded)
3. Create Pinia store in `frontend/src/stores/` if needed (使用 TypeScript)
4. Add API methods in `frontend/src/services/api.ts` or use store directly
5. Define types in `frontend/src/types/models.ts` if needed
6. Add tests in `frontend/tests/`

### Add a New LLM Prompt
1. Create Jinja2 template in `backend/app/templates/<module>/`
2. Use `from app.core.template_manager import render_template`
3. Call `render_template("template_path.jinja2", **variables)`

### Add a New Frontend Component
1. Create component in `frontend/src/components/`
2. Use `<script setup lang="ts">` syntax
3. Define props with `defineProps<{ ... }>()`
4. Use existing Element Plus components when possible (`<el-button>`, `<el-dialog>`, etc.) — auto-imported, no manual import needed
5. Import types from `frontend/src/types/models.ts`

### Run Tests
```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npx vitest run

# TypeScript type check
cd frontend && npx vue-tsc --noEmit
```

### Database Migrations
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```
