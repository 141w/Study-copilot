# Study Copilot - Root AGENTS.md

This file provides architectural guidance for contributors working on Study Copilot.

## Project Overview

**Study Copilot** is an AI-powered learning assistant built with FastAPI + Vue3. It enables users to upload documents (PDF/DOCX/PPTX), ask questions via RAG (Retrieval-Augmented Generation), generate quizzes automatically, and track learning progress.

### v2 Features
- **Agentic RAG**: 查询路由、上下文感知改写、自适应检索、纠错检索、会话摘要、答案自我反思
- **笔记系统**: 手动/AI 笔记，标签管理，语义搜索
- **课程空间**: 按课程组织文档和笔记
- **内容转换**: 8 种转换类型（摘要/要点/大纲/卡片/思维导图/问答/翻译/解释）
- **URL 导入**: 从网页链接提取内容
- **TTS 语音**: Edge TTS 朗读答案和笔记
- **异步任务**: 批量操作，后台任务队列
- **凭证加密**: Fernet 加密存储 API Key
- **数据库迁移**: Alembic
- **CI/CD**: GitHub Actions
- **代码质量**: Ruff linter

**Key Values**: Local-first embedding, multi-provider LLM support, Chinese-language optimized, self-hosted.

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

- **[backend/AGENTS.md](backend/AGENTS.md)** — Backend architecture, API structure, core modules
- **[frontend/AGENTS.md](frontend/AGENTS.md)** — Frontend architecture, components, stores

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
4. Add API methods in `frontend/src/services/api.js`

### Run Tests
```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npx vitest run
```
