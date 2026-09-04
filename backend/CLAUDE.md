# Backend CLAUDE.md

Guidance for working on the Study Copilot backend.

## Structure

```
backend/
├── app/
│   ├── api/                          # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── analysis.py               # GET /wrong, GET /knowledge, /progress
│   │   ├── auth.py                    # POST /register, /login, GET/PUT /me, PUT /password, POST /refresh
│   │   ├── chat.py                    # POST /ask (stream:true), GET /history
│   │   ├── config.py                  # GET/POST user LLM config
│   │   ├── courses.py                 # CRUD course spaces, document associations
│   │   ├── document.py                # POST /upload, GET /, DELETE /{id}
│   │   ├── metrics.py                 # Operational metrics (task counts)
│   │   ├── notes.py                   # CRUD notes + tags + semantic search
│   │   ├── openmaic_bridge.py         # OpenMAIC classroom platform REST bridge
│   │   ├── quiz.py                    # POST /generate, /submit, GET /wrong-questions
│   │   ├── tasks.py                   # Async task management
│   │   ├── transform.py               # Content transformation endpoints (8 types)
│   │   │   └── GET /transformations   # List available transformation types
│   │   └── tts.py                     # Text-to-speech synthesis
│   ├── core/                          # Business logic (no HTTP concerns)
│   │   ├── __init__.py
│   │   ├── adaptive_retriever.py      # Adaptive retrieval strategies (4 strategies)
│   │   ├── answer_reflector.py        # Answer quality self-reflection
│   │   ├── chunker.py                 # FixedChunker, SemanticChunker, HierarchicalChunker
│   │   ├── course_generator.py        # Auto-generate course outline + quizzes from docs
│   │   ├── document_bundle.py         # Multi-document packing for LLM context
│   │   ├── document_parser.py         # Factory: Docling/PyMuPDF/python-docx/python-pptx
│   │   ├── embedder.py                # sentence-transformers wrapper with async + caching
│   │   ├── encryption.py              # Fernet credential encryption for API keys
│   │   ├── llm.py                     # OpenAI SDK wrapper with retry/backoff
│   │   ├── logger.py                  # Structured logging with trace-id ContextVar
│   │   ├── persona_discussion.py      # Multi-agent discussion mode (sequential persona chain)
│   │   ├── pgvector_store.py          # Production vector search via PostgreSQL+pgvector
│   │   ├── query_decomposer.py        # Query decomposition + entity extraction
│   │   ├── query_router.py            # Query intent classification + context rewrite
│   │   ├── quiz_generator.py          # LLM-based question generation
│   │   ├── rag_engine.py              # Agentic RAG orchestrator
│   │   ├── rate_limit.py              # 自研滑动窗口 IPRateLimiter
│   │   ├── retrieval_grader.py        # Two-level retrieval quality assessment
│   │   ├── task_worker.py             # Background task enqueue/dequeue/process
│   │   ├── template_manager.py        # Jinja2 template renderer for LLM prompts
│   │   ├── transformations.py         # 8 transformation types (summary/keypoints/outline/flashcards/mindmap/qa/translate/explain)
│   │   ├── tts.py                     # Edge TTS wrapper
│   │   ├── url_extractor.py           # Web content extraction
│   │   └── vector_store.py            # Legacy FAISS/BM25/Hybrid vector indices (per-document)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py                # SQLAlchemy async engine + all ORM models
│   │   ├── migrations.py              # Schema migration helpers (Alembic)
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── trace.py                   # TraceIdMiddleware (X-Trace-ID propagation, structured logs via ContextVar)
│   ├── services/                      # Business orchestration layer
│   │   ├── __init__.py
│   │   ├── analysis_service.py        # analyze_wrong_questions, get_knowledge_stats, get_progress
│   │   ├── auth_service.py            # register, login, refresh_token
│   │   ├── chat_service.py            # ask_question, stream_answer, get_history
│   │   ├── config_service.py          # get_config, update_config
│   │   ├── course_service.py          # Course space management + document associations
│   │   ├── document_service.py        # upload_document, delete_document, list_documents
│   │   ├── note_service.py            # Note CRUD + tagging + semantic search
│   │   ├── openmaic_service.py        # OpenMAIC classroom platform integration
│   │   ├── quiz_service.py            # generate_quiz, submit_quiz, get_wrong_questions
│   │   ├── task_service.py            # Async task queue (create, get_status, list, cancel)
│   │   └── transform_service.py       # Content transformations orchestration
│   ├── utils/
│   │   ├── __init__.py
│   │   └── auth.py                    # Password hashing, JWT creation/validation, get_current_user
│   ├── config.py                      # Pydantic Settings (env vars)
│   ├── exceptions.py                  # Custom exception classes
│   ├── exception_handlers.py          # FastAPI exception handlers
│   └── main.py                        # FastAPI app, middleware, router includes
├── alembic/                           # Database migrations
│   ├── versions/
│   └── env.py
├── tests/                             # Pytest suite (32 test files)
│   ├── conftest.py
│   ├── conftest_async.py
│   ├── conftest_fixtures.py
│   ├── fixtures/
│   ├── test_api.py
│   ├── test_analysis_service.py
│   ├── test_auth.py
│   ├── test_chunker.py
│   ├── test_config_service.py
│   ├── test_course_service.py
│   ├── test_document_parser.py
│   ├── test_document_service.py
│   ├── test_exceptions.py
│   ├── test_hybrid_retrieval_contract.py
│   ├── test_list_pagination.py
│   ├── test_logging_config.py
│   ├── test_metrics.py
│   ├── test_note_indexing.py
│   ├── test_profile.py
│   ├── test_quiz.py
│   ├── test_quiz_generator.py
│   ├── test_quiz_task_e2e.py
│   ├── test_rag_engine.py
│   ├── test_rate_limit.py
│   ├── test_security_headers.py
│   ├── test_soft_delete.py
│   ├── test_task_persistence.py
│   ├── test_task_service.py
│   ├── test_tasks.py
│   ├── test_trace_middleware.py
│   ├── test_transform_service.py
│   ├── test_tts.py
│   ├── test_type_safety_regressions.py
│   └── test_vector_store.py
├── uploads/                           # User-uploaded files (gitignored)
├── vectorstore/                       # FAISS index files (gitignored)
├── alembic.ini
├── requirements.txt
├── run.py                             # Entry point: uvicorn app.main:app
├── pytest.ini
├── Dockerfile
├── entrypoint.sh
└── start.sh
```

## Key Patterns

### Async Everything
All database operations and I/O must be `async`. Use `await` with SQLAlchemy async sessions and `asyncio.to_thread` for CPU-bound tasks (Docling, encoding).

### Dependency Injection
Use FastAPI's `Depends()` for auth and database sessions:
```python
from app.utils.auth import get_current_user

@router.get("/")
async def list_items(user = Depends(get_current_user)):
    ...
```

### RAG Pipeline Flow (Agentic)

```
User Query
  → Step 1: QueryRouter.analyze() — intent classification + context rewrite (one LLM call)
      ├─ Rules: chitchat/summary/no-docs → fast path
      └─ LLM: classify intent + rewrite with history context
      → QueryType: rag_qa / direct / summary / out_of_scope
  → Step 2: AdaptiveRetriever.select_strategy() — strategy selection via LLM
      ├─ SINGLE: simple fact, top-1
      ├─ STANDARD: standard Q&A, top-5 + rerank
      ├─ MULTI_HOP: decompose → multi-retrieval → merge
      └─ COMPARE: entity extraction → per-entity retrieval → merge
  → Step 3: corrective_retrieve() — quality grading + retry if poor
      ├─ RetrievalGrader.grade() — rule + LLM two-level assessment
      └─ If bad: rewrite query and retry once
  → Step 4: _build_history_context() — session summary for long conversations
      ├─ <= 10 messages: use full history
      └─ > 10 messages: summarize early, keep recent 5
  → Step 5: generate_answer() + AnswerReflector — generate + self-reflect
      ├─ Evaluate: based-on-docs, no-fabrication, citation-reasonableness, completeness
      └─ If failed: refine with suggestions
  → Stream Response (token + thinking + answer_refined events)
```

Key files:
- `rag_engine.py` — main orchestrator, RAGPipeline
- `query_router.py` — intent + rewrite (QueryRouter, QueryType, QueryAnalysis)
- `adaptive_retriever.py` — strategy selection (AdaptiveRetriever, RetrievalStrategy)
- `retrieval_grader.py` — quality assessment (RetrievalGrader, RetrievalQuality)
- `query_decomposer.py` — decompose + entity extraction (QueryDecomposer)
- `answer_reflector.py` — self-reflection (AnswerReflector)

### Document Parsing
Factory pattern in `document_parser.py`:
- PDF text → Docling (preserves tables/layout, smart OCR for scanned)
- PDF > 30 pages → PyMuPDF (memory safe)
- Scanned PDF < 10 pages → Docling OCR, >= 10 pages → error
- DOCX → python-docx
- PPTX → python-pptx

### Vector Store (Hybrid Retrieval)

Two implementations coexist:
- **Production**: `pgvector_store.py` — PostgreSQL+pgvector async vector search (embedding + DB-backed)
- **Legacy**: `vector_store.py` — file-based FAISS + BM25 + RRF (per-document, backward compat)
  - `FAISSVectorStore` — cosine similarity via IndexFlatIP (normalized vectors)
  - `BM25VectorStore` — Okapi BM25 keyword retrieval via rank_bm25
  - `HybridVectorStore` — RRF (Reciprocal Rank Fusion) combining FAISS + BM25
  - `DocumentVectorStore` — per-document wrapper, auto-detects format on load

### Chunking
Three chunker types in `chunker.py`:
- `FixedChunker` — 512 tokens, sentence-boundary overlap, Markdown-aware
- `SemanticChunker` — embedding-based boundary detection with real threshold
- `HierarchicalChunker` — parent-child structure (coarse + fine)

### Error Handling
Custom exceptions in `exceptions.py`. FastAPI exception handlers registered in `exception_handlers.py`.

### Logging
Structured logging via `logger.py`:
- `setup_logging(debug=bool)` — configures log level + format
- Trace-id propagation via `X-Trace-ID` header + ContextVar (ASGI middleware in `app/middleware/trace.py`)
- All log lines include `[trace_id]` prefix for distributed tracing

### Templates
28 Jinja2 prompt templates in `app/templates/`, rendered via `template_manager.py`:
- Subdirectories: `rag/` (3), `quiz/` (3), `reflector/` (2), `retriever/` (1), `router/` (1), `decomposer/` (2), `transformations/` (16)

### ORM Models (`app/db/database.py`)

No separate `app/models/` directory; all ORM models are defined in `app/db/database.py`.

| Model | Table | Key Fields |
|-------|-------|-----------|
| `User` | `users` | id, username, email, password_hash, is_active, created_at |
| `Document` | `documents` | id, user_id, course_space_id, filename, file_path, status, chunk_count, file_size, vectorstore_path, deleted_at (soft delete) |
| `ChatSession` | `chat_sessions` | id, user_id, title, created_at |
| `Message` | `messages` | id, session_id, role, content, sources, embedding (vector), created_at |
| `Quiz` | `quizzes` | id, document_id, question_type, question, options, answer, explanation, created_at |
| `QuizResult` | `quiz_results` | id, quiz_id, user_id, user_answer, is_correct, submitted_at |
| `UserLLMConfig` | `user_llm_configs` | id, user_id, provider, api_key, base_url, model_name, temperature, max_tokens, embedding_model, embedding_dimension, created_at, updated_at |
| `CourseSpace` | `course_spaces` | id, user_id, name, description, color, created_at, updated_at |
| `Tag` | `tags` | id, user_id, name, created_at |
| `Note` | `notes` | id, user_id, course_space_id, title, content, note_type, is_pinned, deleted_at (soft delete), created_at, updated_at |
| `AsyncTask` | `async_tasks` | id, user_id, task_type, status, progress, result, error, created_at, completed_at |
| `DocumentChunk` | `document_chunks` | id, document_id, content, embedding (vector), chunk_metadata (JSON), chunk_index, created_at |
| `note_tags` | association table | note_id, tag_id |

Also: no `app/schemas/` directory; Pydantic schemas are defined inline in each router.

### Services Layer
Each service orchestrates core modules for a single domain:
- Manages SQLAlchemy `AsyncSession` transactions
- Transforms between API schemas and DB models
- Handles cross-cutting concerns (logging, error mapping)

## Environment Variables

Key `.env` settings:
```
# OpenAI / LLM
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=2048
OPENAI_TEMPERATURE=0.7

# Embedding
EMBEDDING_MODEL=shibing624/text2vec-base-chinese
EMBEDDING_DIMENSION=768
HF_ENDPOINT=https://hf-mirror.com        # Optional: HF mirror
HF_HUB_OFFLINE=1                          # Optional: offline mode

# JWT Auth
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql+asyncpg://...

# File Upload
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800                    # 50MB

# FAISS Vector Store
VECTORSTORE_DIR=./vectorstore
TOP_K=5

# Encryption
ENCRYPTION_KEY=...                        # Fernet key for API key encryption

# App
APP_NAME=Study Copilot
APP_VERSION=1.0.0
DEBUG=True
```

## Running

```bash
cd backend
conda activate study-c
python run.py              # Starts uvicorn on port 8000
pytest tests/ -v           # Run tests
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, returns access + refresh tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user info |
| PUT | `/api/auth/me` | Update current user profile (username/email) |
| PUT | `/api/auth/password` | Change password (requires old password) |
| POST | `/api/documents/upload` | Upload document (PDF/DOCX/PPTX) |
| POST | `/api/documents/from-url` | Import document from URL |
| GET | `/api/documents` | List user's documents |
| GET | `/api/documents/{id}` | Get document detail |
| DELETE | `/api/documents/{id}` | Delete document (soft, restorable) |
| POST | `/api/documents/{id}/restore` | Restore soft-deleted document |
| POST | `/api/chat/ask` | Non-streaming RAG Q&A |
| POST | `/api/chat/ask` (stream:true) | Streaming RAG Q&A (SSE) |
| GET | `/api/chat/history` | List chat sessions |
| GET | `/api/chat/history/{id}` | Get session messages |
| PUT | `/api/chat/history/{id}` | Update session title |
| DELETE | `/api/chat/history/{id}` | Delete session |
| POST | `/api/quiz/generate` | Generate quiz from document |
| POST | `/api/quiz/submit` | Submit quiz answers |
| GET | `/api/quiz/result-history` | Get quiz result history |
| GET | `/api/quiz/wrong-questions` | Get wrong questions for review |
| GET | `/api/analysis/wrong` | Analyze wrong answers |
| GET | `/api/analysis/knowledge` | Get knowledge stats |
| GET | `/api/analysis/progress` | Get learning progress |
| GET | `/api/notes` | List notes (with filters) |
| POST | `/api/notes` | Create note |
| GET | `/api/notes/{id}` | Get note detail |
| PUT | `/api/notes/{id}` | Update note (including tags) |
| DELETE | `/api/notes/{id}` | Delete note (soft, restorable) |
| POST | `/api/notes/{id}/restore` | Restore soft-deleted note |
| POST | `/api/notes/search` | Semantic note search |
| GET | `/api/notes/tags/all` | List all tags |
| DELETE | `/api/notes/tags/{tag_id}` | Delete a tag |
| POST | `/api/courses` | Create course space |
| GET | `/api/courses` | List course spaces |
| GET | `/api/courses/{id}` | Get course detail |
| PUT | `/api/courses/{id}` | Update course space |
| DELETE | `/api/courses/{id}` | Delete course space |
| GET | `/api/courses/{id}/documents` | List documents associated with a course |
| POST | `/api/courses/{id}/documents` | Associate documents with a course |
| DELETE | `/api/courses/{id}/documents/{doc_id}` | Remove a document association |
| POST | `/api/transform` | Transform content (8 types) |
| GET | `/api/transform/transformations` | List available transformation types |
| POST | `/api/tts/generate` | Synthesize speech from text |
| GET | `/api/tts/voices` | List available TTS voices |
| POST | `/api/tasks` | Create an async task |
| GET | `/api/tasks` | List user's tasks (filterable by status) |
| GET | `/api/tasks/{id}` | Get task status |
| DELETE | `/api/tasks/{id}` | Cancel task |
| GET | `/api/config/llm` | Get user's LLM config |
| POST | `/api/config/llm` | Update user's LLM config |
| PUT | `/api/config/llm` | Update user's LLM config |
| POST | `/api/integrations/openmaic/classroom` | Initiate OpenMAIC classroom generation |
| GET | `/api/integrations/openmaic/classrooms` | List generated classrooms |
| POST | `/api/integrations/openmaic/webhook` | OpenMAIC callback endpoint |
| GET | `/` | App info |
| GET | `/health` | Health check |
| GET | `/api/metrics` | Operational metrics (task counts by status) |
