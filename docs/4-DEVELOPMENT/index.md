# Development Guide

## Development Setup

### Prerequisites

- Python ≥ 3.11 with conda
- Node.js ≥ 18
- PostgreSQL ≥ 16 (or SQLite for local experimentation)
- Git

### Backend Development

```bash
cd backend
conda create -n study-c python=3.11
conda activate study-c
uv pip install -e ".[dev]"
cp .env.example .env  # Configure your environment
python run.py          # Starts uvicorn on port 8000
```

The backend runs at `http://localhost:8000` with hot-reload via `watchfiles` (installed with `uvicorn[standard]`).

> **Note**: The project uses `pyproject.toml` for packaging. Install the editable package with dev extras (`.[dev]`) to get pytest, ruff, and mypy.

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` with Vite HMR. API requests to `/api` are proxied to `http://localhost:8000` via Vite's dev server proxy (`vite.config.js`).

### Running Both (macOS)

```bash
./start.sh   # Starts PostgreSQL, backend, and frontend
./stop.sh    # Stops all services
```

---

## Project Layout

```
backend/
├── app/
│   ├── api/                    # FastAPI route handlers (13 routers)
│   │   ├── auth.py             # POST /register, /login, GET/PUT /me, /password, /refresh
│   │   ├── document.py         # Upload, list, delete, restore documents
│   │   ├── chat.py             # Streaming RAG Q&A, session history, personas, discuss
│   │   ├── quiz.py              # Generate, submit, wrong-questions
│   │   ├── analysis.py          # Wrong answer analysis, knowledge & progress stats
│   │   ├── notes.py             # CRUD notes, tags, semantic search
│   │   ├── courses.py            # CRUD course spaces, document associations, course generation
│   │   ├── transform.py         # 9 content transformation types
│   │   ├── tts.py               # Text-to-speech synthesis
│   │   ├── tasks.py             # Async task queue
│   │   ├── config.py            # LLM provider configuration
│   │   ├── metrics.py            # Operational metrics
│   │   └── classroom_api.py      # AI classroom integration & status self-healing
│   ├── core/                    # Business logic (no HTTP concerns — 24 modules)
│   │   ├── llm.py               # OpenAI SDK wrapper with retry/backoff
│   │   ├── embedder.py          # sentence-transformers wrapper (async + caching)
│   │   ├── pgvector_store.py    # Production vector search via PostgreSQL+pgvector
│   │   ├── vector_store.py      # Legacy FAISS+BM25+RRF (backward compat)
│   │   ├── rag_engine.py        # Agentic RAG orchestrator (5-step pipeline)
│   │   ├── query_router.py      # Intent classification + context rewrite
│   │   ├── adaptive_retriever.py # Adaptive retrieval (4 strategies)
│   │   ├── retrieval_grader.py  # Two-level quality assessment
│   │   ├── query_decomposer.py  # Query decomposition + entity extraction
│   │   ├── answer_reflector.py  # Answer quality self-reflection
│   │   ├── document_parser.py   # Factory: Docling / PyMuPDF / python-docx / python-pptx
│   │   ├── chunker.py           # Fixed / Semantic / Hierarchical chunking
│   │   ├── document_bundle.py   # Multi-doc fair proportional budget allocator
│   │   ├── course_generator.py  # Auto-generate course outline and quizzes from docs
│   │   ├── persona_discussion.py # Multi-agent sequential persona discussion
│   │   ├── quiz_generator.py    # LLM-based question generation
│   │   ├── transformations.py   # 9 transformation types
│   │   ├── encryption.py        # Fernet credential encryption
│   │   ├── tts.py               # Edge TTS wrapper
│   │   ├── url_extractor.py     # Web content extraction
│   │   ├── rate_limit.py        # Sliding-window IP rate limiter
│   │   ├── logger.py            # Structured logging with trace-id ContextVar
│   │   ├── template_manager.py  # Jinja2 template renderer (30 templates)
│   │   └── task_worker.py       # Background task enqueue/dequeue/process
│   ├── services/                # Business orchestration (11 modules)
│   │   ├── auth_service.py
│   │   ├── chat_service.py
│   │   ├── document_service.py
│   │   ├── quiz_service.py
│   │   ├── note_service.py
│   │   ├── course_service.py
│   │   ├── analysis_service.py
│   │   ├── config_service.py
│   │   ├── transform_service.py
│   │   ├── task_service.py
│   │   └── classroom_service.py
│   ├── db/                      # SQLAlchemy async engine, ORM models, Alembic
│   ├── utils/                   # Auth helpers (password hashing, JWT)
│   ├── config.py                # Pydantic Settings (env vars)
│   ├── main.py                  # FastAPI app, middleware, router registration
│   ├── exceptions.py            # Custom exception classes
│   └── exception_handlers.py    # FastAPI exception handlers
├── alembic/                     # Database migrations
├── tests/                      # Pytest suite
├── uploads/                    # User-uploaded files (gitignored)
├── vectorstore/                # FAISS index files (gitignored)
├── .embedding_cache/           # Embedding model cache (gitignored)
├── start.sh / stop.sh          # Dev environment scripts
├── pyproject.toml              # Modern Python packaging + tool config
├── requirements.txt            # Legacy compatibility shim
├── run.py                      # Entry point: uvicorn app.main:app
└── pytest.ini

frontend/
├── src/
│   ├── views/                    # 13 page-level components
│   │   ├── HomeView.vue
│   │   ├── LoginView.vue
│   │   ├── RegisterView.vue
│   │   ├── UploadView.vue
│   │   ├── DocumentView.vue
│   │   ├── ChatView.vue
│   │   ├── NotesView.vue
│   │   ├── QuizView.vue
│   │   ├── AnalysisView.vue
│   │   ├── ModelConfigView.vue
│   │   ├── CourseListView.vue
│   │   ├── CourseDetailView.vue
│   │   ├── TasksView.vue
│   │   └── ProfileView.vue
│   ├── components/              # Reusable UI
│   │   ├── chat/                # ChatHistoryPanel, ChatInput
│   │   ├── common/              # AppHeader, AppSidebar, DocumentPicker, EmptyState
│   │   ├── classroom/           # GenerateClassroomDialog, ClassroomCard
│   │   ├── CopilotBotAvatar.vue
│   │   ├── CourseCard.vue
│   │   ├── NoteCard.vue
│   │   ├── NoteEditor.vue
│   │   ├── TaskPanel.vue
│   │   ├── TransformDialog.vue
│   │   ├── TTSPlayer.vue
│   │   └── UrlImportDialog.vue
│   ├── stores/                 # 11 Pinia stores (TypeScript)
│   │   ├── auth.ts, chat.ts, config.ts, course.ts, document.ts,
│   │   ├── note.ts, classroom.ts, quiz.ts, sidebar.ts, theme.ts, toast.ts
│   ├── services/               # Axios API client + token refresh
│   │   ├── api.ts
│   │   └── authRefresh.ts
│   ├── composables/            # 6 reusable composition functions
│   │   ├── useApi.ts, useMarkdown.ts, useChatExport.ts,
│   │   ├── useFormat.ts, useNoteDraft.ts, useReducedMotion.ts
│   ├── types/                  # TypeScript types
│   │   ├── api.ts, models.ts, markdown-it.d.ts
│   ├── router/                 # Vue Router config with auth guards
│   ├── styles/                 # CSS variables design system + global styles
│   ├── bot/                    # Bot persona runtime
│   └── assets/                 # Static assets
├── tests/                      # Vitest test suite
├── vite.config.js              # Vite config with Element Plus tree-shaking
├── tailwind.config.js          # Layout utilities + CSS variable design tokens
├── tsconfig.json               # TypeScript (progressive migration)
└── package.json
```

---

## Common Development Tasks

### Add a New API Endpoint

1. Add a router in `backend/app/api/` (or extend an existing one)
2. Define Pydantic request/response models inline
3. Add business logic in `backend/app/services/`
4. Register router in `backend/app/main.py`
5. Add tests in `backend/tests/`

```python
# backend/app/api/my_feature.py
from fastapi import APIRouter, Depends
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
async def list_items(user=Depends(get_current_user)):
    return []
```

### Add a New Frontend View

1. Create in `frontend/src/views/` using `<script setup lang="ts">`
2. Add lazy-loaded route in `frontend/src/router/` with auth guard
3. Create a Pinia store if needed in `frontend/src/stores/`
4. Define types in `frontend/src/types/` if needed

### Modify the RAG Pipeline

Key files:
- `backend/app/core/rag_engine.py` — Main 5-step orchestrator
- `backend/app/core/query_router.py` — Intent classification + rewrite
- `backend/app/core/adaptive_retriever.py` — Retrieval strategy selection
- `backend/app/core/retrieval_grader.py` — Quality assessment
- `backend/app/core/chunker.py` — Text splitting strategies
- `backend/app/core/vector_store.py` — Legacy FAISS/BM25/Hybrid

### Add a New Jinja2 Prompt Template

Place `.jinja2` files in `backend/app/templates/<module>/`, then render via:

```python
from app.core.template_manager import render_template
result = render_template("rag/my_template.jinja2", var="value")
```

### Add a Document Parser Type

Extend `backend/app/core/document_parser.py` (factory pattern). Supported types: PDF (Docling/PyMuPDF), DOCX, PPTX.

---

## Testing

### Backend (pytest)

```bash
cd backend
pytest tests/ -v          # All tests
pytest tests/test_chunker.py -v  # Single file
```

Configured via `pytest.ini`. Uses `pytest-asyncio` for async tests, `pytest-cov` for coverage.

### Frontend (Vitest)

```bash
cd frontend
npx vitest run            # All tests
npx vitest                # Watch mode
```

### TypeScript Type Check

```bash
cd frontend
npx vue-tsc --noEmit
```

---

## Linting & Formatting

### Backend

```bash
cd backend
ruff check .              # Lint + auto-fix
ruff check . --fix        # Auto-fix violations
ruff format .             # Format code
```

Configured via `[tool.ruff]` in `pyproject.toml`. Line length: 100, target: Python 3.11.

Enforce type annotations with mypy:

```bash
cd backend
mypy app/
```

### Frontend

```bash
cd frontend
npm run lint              # ESLint
npm run lint:fix          # ESLint auto-fix
npm run format            # Prettier (write)
npm run format:check      # Prettier (verify only)
```

---

## Database

### Models

All ORM models are in `backend/app/db/database.py`. Key tables:

| Table | Model | Purpose |
|-------|-------|---------|
| `users` | `User` | Accounts |
| `documents` | `Document` | Uploaded files (soft-delete via `deleted_at`) |
| `document_chunks` | `DocumentChunk` | Chunked content with embeddings |
| `chat_sessions` | `ChatSession` | Conversations |
| `messages` | `Message` | Chat messages |
| `quizzes` | `Quiz` | Generated questions |
| `quiz_results` | `QuizResult` | User answers |
| `user_llm_configs` | `UserLLMConfig` | Per-user LLM settings |
| `course_spaces` | `CourseSpace` | Course organization |
| `notes` | `Note` | User notes (soft-delete) |
| `tags` / `note_tags` | `Tag` / assoc | Note tagging |
| `async_tasks` | `AsyncTask` | Background task queue |

### Migrations

Alembic migrations live in `backend/alembic/`. Schema is auto-created on dev startup via SQLAlchemy `create_all`.

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

---

## Debugging

### Backend

- Logs output to stdout with `[trace_id]` prefix (structured via ContextVar).
- Set `DEBUG=True` in `.env` for verbose output.
- Interactive docs at `http://localhost:8000/docs` (Swagger UI).
- No email sending in the backend (CLAUDE.md compliance).
- All async; `asyncio.to_thread` for CPU-bound work (Docling, FAISS encoding).

### Frontend

- Vue DevTools browser extension.
- Vite dev server shows compilation errors inline.
- Check browser console for Axios interceptor logs.

### Common Issues

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Activate conda env: `conda activate study-c` |
| `Connection refused` to DB | Start PostgreSQL: `brew services start postgresql@16` |
| Embedding model download hangs | Set HF mirror: `export HF_ENDPOINT=https://hf-mirror.com` |
| Port 8000 in use | `lsof -i :8000` then `kill <PID>` |
| CORS errors | Check `backend/app/main.py` CORS middleware |
| Token expired | Frontend auto-refreshes via `services/authRefresh.ts` |

---

## Design System

CSS variables in `frontend/src/styles/variables.css` drive the entire theme. Light/dark mode toggles the `data-theme` attribute on `<html>`. Element Plus component styles are overridden via `frontend/src/styles/element-plus-theme.css`. TailwindCSS is used for layout primitives only; semantic styling goes through CSS variables.

Key tokens (no hard-coded values in components):

- Colors: `--color-primary`, `--bg-primary`, `--text-primary`, etc.
- Spacing: `--spacing-xs` through `--spacing-2xl`
- Radius: `--radius-xs` (6px) through `--radius-2xl` (24px)
- Typography: `--font-size-sm`, `--font-size-base`, `--font-size-lg`, etc.
