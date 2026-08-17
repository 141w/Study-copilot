# Backend CLAUDE.md

Guidance for working on the Study Copilot backend.

## Structure

```
backend/
├── app/
│   ├── api/                    # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── auth.py             # POST /register, /login, GET /me, POST /refresh
│   │   ├── document.py         # POST /upload, GET /, DELETE /{id}
│   │   ├── chat.py             # POST /ask (stream:true), GET /history
│   │   ├── quiz.py             # POST /generate, /submit, GET /wrong-questions
│   │   ├── analysis.py         # POST /wrong, GET /knowledge, /progress
│   │   ├── notes.py            # CRUD notes + tags + semantic search
│   │   ├── courses.py          # CRUD course spaces, document associations
│   │   ├── transform.py        # Content transformation endpoints (8 types)
│   │   ├── tts.py              # Text-to-speech synthesis
│   │   ├── tasks.py            # Async task management
│   │   └── config.py           # GET/POST user LLM config
│   ├── core/                   # Business logic (no HTTP concerns)
│   │   ├── __init__.py
│   │   ├── config.py           # Default config constants
│   │   ├── llm.py              # OpenAI SDK wrapper with retry/backoff
│   │   ├── embedder.py         # sentence-transformers wrapper with async + caching
│   │   ├── vector_store.py     # FAISS/BM25/Hybrid vector indices (per-document)
│   │   ├── rag_engine.py       # Agentic RAG orchestrator
│   │   ├── query_router.py     # Query intent classification + context rewrite
│   │   ├── adaptive_retriever.py # Adaptive retrieval strategies
│   │   ├── retrieval_grader.py # Two-level retrieval quality assessment
│   │   ├── query_decomposer.py # Query decomposition + entity extraction
│   │   ├── answer_reflector.py # Answer quality self-reflection
│   │   ├── document_parser.py  # Factory: Docling/PyMuPDF/python-docx/python-pptx
│   │   ├── chunker.py          # FixedChunker, SemanticChunker, HierarchicalChunker
│   │   ├── quiz_generator.py   # LLM-based question generation
│   │   ├── transformations.py  # 8 transformation types (summary/keypoints/outline/flashcards/mindmap/qa/translate/explain)
│   │   ├── encryption.py       # Fernet credential encryption for API keys
│   │   ├── tts.py              # Edge TTS wrapper
│   │   ├── url_extractor.py    # Web content extraction
│   │   └── rate_limit.py       # slowapi rate limiting
│   ├── services/               # Business orchestration layer
│   │   ├── __init__.py
│   │   ├── auth_service.py     # register, login, refresh_token
│   │   ├── document_service.py # upload_document, delete_document, list_documents
│   │   ├── chat_service.py     # ask_question, stream_answer, get_history
│   │   ├── quiz_service.py     # generate_quiz, submit_quiz, get_wrong_questions
│   │   ├── analysis_service.py # record_wrong, get_knowledge_gaps, get_progress
│   │   ├── config_service.py   # get_config, update_config
│   │   ├── note_service.py     # Note CRUD + tagging + semantic search
│   │   ├── course_service.py   # Course space management + document associations
│   │   ├── transform_service.py # Content transformations orchestration
│   │   ├── task_service.py     # Async task queue (create, get_status, list, cancel)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy async engine + all ORM models
│   │   ├── migrations.py       # Schema migration helpers (Alembic)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── auth.py             # Password hashing, JWT creation/validation, get_current_user
│   │   ├── file_handler.py     # File save/delete helpers
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── main.py                 # FastAPI app, middleware, router includes
│   ├── exceptions.py           # Custom exception classes
│   ├── exception_handlers.py   # FastAPI exception handlers
│   ├── tests/                  # Pytest suite
│   │   ├── conftest.py         # Shared fixtures
│   │   ├── test_api.py
│   │   ├── test_auth.py
│   │   ├── test_chunker.py
│   │   ├── test_document_parser.py
│   │   ├── test_exceptions.py
│   │   ├── test_file_handler.py
│   │   ├── test_quiz_generator.py
│   │   ├── test_quiz.py
│   │   ├── test_rag_engine.py
│   │   ├── test_rate_limit.py
│   │   ├── test_tasks.py
│   │   ├── test_tts.py
│   │   ├── test_vector_store.py
├── uploads/                    # User-uploaded files (gitignored)
├── vectorstore/                # FAISS index files (gitignored)
├── alembic/                    # Database migrations
│   ├── versions/
│   ├── env.py
├── .embedding_cache/           # Embedding model cache (gitignored)
├── .pytest_cache/              # Pytest cache (gitignored)
├── requirements.txt
├── run.py                      # Entry point: uvicorn app.main:app
├── pytest.ini
└── alembic.ini
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
Three implementations in `vector_store.py`:
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
| POST | `/api/documents` | Upload document (PDF/DOCX/PPTX) |
| POST | `/api/documents/from-url` | Import document from URL |
| GET | `/api/documents` | List user's documents |
| GET | `/api/documents/{id}` | Get document detail |
| DELETE | `/api/documents/{id}` | Delete document |
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
| POST | `/api/analysis/wrong` | Analyze wrong answers |
| GET | `/api/analysis/knowledge` | Get knowledge stats |
| GET | `/api/analysis/progress` | Get learning progress |
| GET | `/api/notes` | List notes (with filters) |
| POST | `/api/notes` | Create note |
| GET | `/api/notes/{id}` | Get note detail |
| PUT | `/api/notes/{id}` | Update note (including tags) |
| DELETE | `/api/notes/{id}` | Delete note |
| GET | `/api/notes/tags/all` | List all tags |
| DELETE | `/api/notes/tags/{tag_id}` | Delete a tag |
| POST | `/api/courses` | Create course space |
| GET | `/api/courses` | List course spaces |
| GET | `/api/courses/{id}` | Get course detail |
| PUT | `/api/courses/{id}` | Update course space |
| DELETE | `/api/courses/{id}` | Delete course space |
| POST | `/api/transform` | Transform content (8 types) |
| GET | `/api/transform/transformations` | List available transformation types |
| POST | `/api/tts/generate` | Synthesize speech from text |
| GET | `/api/tts/voices` | List available TTS voices |
| GET | `/api/tasks` | List user's tasks (filterable by status) |
| GET | `/api/tasks/{id}` | Get task status |
| DELETE | `/api/tasks/{id}` | Cancel task |
| GET | `/api/config/llm` | Get user's LLM config |
| POST | `/api/config/llm` | Update user's LLM config |
| PUT | `/api/config/llm` | Update user's LLM config |
| GET | `/api/config/llm/with-secret` | Get LLM config with decrypted API key (internal) |
| GET | `/` | App info |
| GET | `/health` | Health check |
