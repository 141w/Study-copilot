# Development Guide

## Development Setup

### Prerequisites

- Python ≥ 3.11 with conda
- Node.js ≥ 18
- PostgreSQL ≥ 16
- Git

### Backend Development

```bash
cd backend
conda create -n study-c python=3.11
conda activate study-c
pip install -r requirements.txt "pydantic[email]"
cp .env.example .env  # Configure your environment
python run.py          # Start without auto-reload
```

The backend runs at `http://localhost:8000` with hot-reload enabled.

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` with Vite HMR.

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
│   ├── api/              # FastAPI route handlers
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── document.py   # Document CRUD
│   │   ├── chat.py       # RAG Q&A endpoints
│   │   ├── quiz.py       # Quiz endpoints
│   │   ├── analysis.py   # Analytics endpoints
│   │   ├── notes.py      # Notes CRUD + tags
│   │   ├── courses.py    # Course spaces CRUD
│   │   ├── transform.py  # Content transformation
│   │   ├── tts.py        # Text-to-speech
│   │   ├── tasks.py      # Async task management
│   │   └── config.py     # LLM config endpoints
│   ├── core/             # Business logic
│   │   ├── encryption.py       # Fernet credential encryption
│   │   ├── tts.py              # Edge TTS wrapper
│   │   ├── url_extractor.py    # Web content extraction
│   │   ├── transformations.py  # Content transformation engine
│   │   ├── document_parser.py  # PDF/DOCX/PPTX parsing
│   │   ├── chunker.py          # Text chunking strategies
│   │   ├── vector_store.py     # FAISS operations
│   │   ├── rag_engine.py       # RAG pipeline
│   │   ├── quiz_generator.py   # AI quiz generation
│   │   ├── llm.py              # LLM client wrapper
│   │   └── embedder.py         # Embedding model
│   ├── db/               # SQLAlchemy models & config
│   ├── utils/            # Auth helpers, file handling
│   ├── config.py         # Pydantic Settings
│   └── main.py           # FastAPI app factory
│   ├── services/         # Business orchestration
│   │   ├── note_service.py
│   │   ├── course_service.py
│   │   ├── transform_service.py
│   │   └── task_service.py
├── tests/                # Pytest test suite
├── uploads/              # User files (gitignored)
└── vectorstore/          # FAISS indices (gitignored)

frontend/
├── src/
│   ├── views/            # Page-level components
│   │   ├── NotesView.vue
│   │   ├── CourseListView.vue
│   │   ├── CourseDetailView.vue
│   │   └── TasksView.vue
│   ├── components/       # Reusable UI components
│   │   ├── NoteEditor.vue
│   │   ├── NoteCard.vue
│   │   ├── CourseCard.vue
│   │   ├── TTSPlayer.vue
│   │   ├── TaskPanel.vue
│   │   ├── TransformDialog.vue
│   │   ├── UrlImportDialog.vue
│   │   ├── common/       # Header, Sidebar, Toast
│   │   └── chat/         # Chat message/input
│   ├── stores/           # Pinia state stores
│   │   ├── note.js
│   │   ├── course.js
│   │   ├── sidebar.js
│   ├── services/         # Axios API client
│   ├── router/           # Vue Router config
│   └── styles/           # Global CSS
├── tests/                # Vitest test suite
└── package.json
```

---

## Common Development Tasks

### Add a New API Endpoint

1. Create or edit a router in `backend/app/api/`
2. Define the Pydantic request/response models
3. Add the business logic in `backend/app/core/`
4. Register the router in `backend/app/main.py`
5. Add tests in `backend/tests/`

```python
# backend/app/api/my_feature.py
from fastapi import APIRouter, Depends
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
async def list_items(user = Depends(get_current_user)):
    # Implementation
    pass
```

### Add a New Frontend View

1. Create the view in `frontend/src/views/`
2. Add route in `frontend/src/router/`
3. Create a Pinia store if needed in `frontend/src/stores/`
4. Add API calls in `frontend/src/services/api.js`

### Modify the RAG Pipeline

Key files:
- `backend/app/core/rag_engine.py` — Main RAG logic
- `backend/app/core/chunker.py` — Text splitting
- `backend/app/core/vector_store.py` — FAISS operations
- `backend/app/core/embedder.py` — Embedding model

### Add a New Embedding Model

1. Update `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION` in `.env`
2. Ensure the model is compatible with `sentence-transformers`
3. Re-upload documents to regenerate vector indices

---

## Code Standards

### Backend (Python)
- Follow PEP 8
- Use type hints on all function signatures
- Async functions for all database and I/O operations
- Pydantic models for request/response validation
- Docstrings on public functions
- Use Ruff for linting and formatting (`ruff check .`, `ruff format .`)

### Frontend (JavaScript/Vue)
- Vue 3 Composition API (`<script setup>`)
- Pinia for state management (no Vuex)
- TailwindCSS for styling (no custom CSS unless necessary)
- ESLint + Prettier for formatting

---

## Database

The project uses SQLAlchemy 2.0 with async PostgreSQL.

### Models
Defined in `backend/app/db/database.py`. Key tables:
- `users` — User accounts
- `documents` — Uploaded documents
- `chunks` — Text chunks from documents
- `conversations` — Chat sessions
- `messages` — Chat messages
- `quizzes` — Generated quizzes
- `quiz_results` — User answers and scores
- `user_llm_configs` — Per-user LLM settings
- `course_spaces` — Course spaces for organizing content
- `notes` — User notes (manual + AI generated)
- `tags` — Note tags
- `note_tags` — Note-tag association table
- `async_tasks` — Background task queue

### Migrations
The database schema is created automatically on startup via SQLAlchemy's `create_all`. For production, use Alembic:

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Debugging

### Backend
- Logs output to stdout with Python `logging`
- Set `DEBUG=True` in `.env` for verbose output
- Use `http://localhost:8000/docs` to test endpoints interactively

### Frontend
- Vue DevTools browser extension
- Vite dev server shows compilation errors in-browser
- Check browser console for API errors (Axios interceptors log them)

### Common Issues

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Activate conda env: `conda activate study-c` |
| `Connection refused` to DB | Start PostgreSQL: `brew services start postgresql@16` |
| Embedding model download hangs | Use VPN or set HF mirror: `export HF_ENDPOINT=https://hf-mirror.com` |
| Port 8000 in use | `lsof -i :8000` then `kill <PID>` |
| CORS errors | Check `backend/app/main.py` CORS middleware config |
