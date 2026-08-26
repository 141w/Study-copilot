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

## Current State (2026-08-17)

- **Git**: `master` 分支，领先 origin 9 个 commit，工作区干净
- **Changelog**: `CHANGELOG_2026-08-17.md`（8 commit，约 70 文件）
- **Ports**: 前端 3000，后端 8000
- **Frontend**: Vue3 + Vite + TypeScript + Pinia + TailwindCSS + GSAP
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16+ + FAISS + sentence-transformers
- **打包**: backend/pyproject.toml（hatchling）+ uv.lock（192 包锁定）；requirements.txt 为兼容层
- **CI**: uv 安装依赖 + ruff lint + 覆盖率门禁 65% + 前端 vue-tsc/build/vitest 全链路
- **可观测性**: 结构化 JSON 日志（生产）/ 文本（开发）+ X-Trace-ID 纯 ASGI 追踪中间件 + /health DB 探测
- **Docker**: 多阶段构建、非 root 运行、healthcheck；.dockerignore 收敛构建上下文

### Recent Changes (2026-08-17)

1. **P0 紧急修复** (237c052): git 提交、text import、requirements 补全、quiz 密文修复、config model_name 对齐、alembic env、notes 前后端契约、course tab 404
2. **P1 对齐** (fdbc370): 端口 5173→3000 (14 处)、API 路径纠错、CI main→master、测试方法名同步、前端 mock
3. **P2 迁移** (55d8502): 6 模块模板迁移（14 orphan→render_template）、typescript+vue-tsc、.env.example + upload_dir、死代码清理
4. **P3 卫生** (8c57f63): defineOptions、useMarkdown composable、温度注释、api__init__ 补全、TTS TODO
5. **E 纠错** (02eae49): retrieval_grader 接入 ask/ask_stream、移除 _needs_rewrite 死代码
6. **C+D 特性** (6989751): 笔记语义搜索（service+API）、课程-文档关联（routes+service+store）
7. **A 异步** (32c8440): task_worker.py、main.py lifespan 接线、document_service 异步化、POST /api/tasks
8. **B Hybrid** (part of 02eae49/55d8502): vector_store.py 新增 _tokenize()，支持 jieba 中文分词 + BM25+FAISS+RRF

### Outstanding Items
- test_document_service.py 依赖 faiss/docling 导入链，本地轻量环境跑不了，由 CI 全量验证
- uv.lock 需在依赖变更后手动运行 `cd backend && uv lock` 再生

### Resolved Since 2026-08-17（详见 remaining_issues.md）
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
│ - FAISS vector indices (per-user files)      │
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
