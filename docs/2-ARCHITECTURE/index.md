# Architecture Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Frontend (Vue3 + Vite)                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Auth    │ │Document │ │  Chat   │ │  Quiz   │ │Analysis │   │
│  │ Views   │ │ Views   │ │  View   │ │  View   │ │  View   │   │
│  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤   │
│  │ Notes   │ │ Courses │ │ Tasks   │ │Transform│ │   TTS   │   │
│  │  View   │ │  View   │ │  View   │ │ Dialog  │ │ Player  │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                            │                                      │
│                    Pinia State Management                         │
│                    Vue Router + Axios                             │
│                    TypeScript + vue-tsc                           │
└────────────────────────────┼─────────────────────────────────────┘
                             │ HTTP + SSE (Server-Sent Events)
┌────────────────────────────┼─────────────────────────────────────┐
│                       Backend (FastAPI)                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  Auth   │ │Document │ │  Chat   │ │  Quiz   │ │Analysis │   │
│  │  API    │ │  API    │ │  API    │ │  API    │ │  API    │   │
│  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤   │
│  │ Notes   │ │ Courses │ │Transform│ │  TTS    │ │ Tasks   │   │
│  │  API    │ │  API    │ │  API    │ │  API    │ │  API    │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                            │                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                      Core Engine                            │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │ Document   │ │  Vector    │ │    LLM     │              │  │
│  │  │ Parser     │ │  Store     │ │  Caller    │              │  │
│  │  │ (Docling)  │ │  (FAISS)   │ │(OpenRouter)│              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │  Chunker   │ │   Quiz     │ │  Embedder  │              │  │
│  │  │            │ │ Generator  │ │  (SBERT)   │              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │ Query     │ │  Answer    │ │  Async     │              │  │
│  │  │  Router   │ │ Reflector  │ │  Worker    │              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │ Adaptive  │ │Corrective  │ │ Reranker   │              │  │
│  │  │ Retriever │ │ Retriever  │ │(CrossEnc)  │              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │  URL       │ │ Transform  │ │ Encryption │              │  │
│  │  │ Extractor  │ │ (8 types)  │ │  (Fernet)  │              │  │
│  │  │(trafilatura)│            │ │            │              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐                              │  │
│  │  │ Notes      │ │  Course    │                              │  │
│  │  │ Vector     │ │  Service   │                              │  │
│  │  │ Index      │ │            │                              │  │
│  │  └────────────┘ └────────────┘                              │  │
│  │  ┌──────────────────────────────────────────┐               │  │
│  │  │  BM25VectorStore (jieba + RRF fusion)   │               │  │
│  │  └──────────────────────────────────────────┘               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  PostgreSQL  │ │ File Storage │ │ Vector Index │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Document Upload & Processing

```
User uploads PDF/DOCX/PPTX
    → Document Parser (Docling/PyMuPDF/python-docx/python-pptx)
    → Text extracted as Markdown
    → URL Import (trafilatura) for web content
    → Chunker (Fixed 512-token or Semantic chunks)
    → Embedder (sentence-transformers → vector)
    → FAISS Vector Store (per-user index)
    → BM25VectorStore (jieba tokenizer, per-user index)
    → Hybrid Fusion (RRF) when querying
    → PostgreSQL metadata saved
    → Async Task Queue (background processing, status tracking)
```

### RAG Question Answering (Agentic)

```
User asks question
    → Query Router (classify: RAG / Web / Direct)
    → If RAG:
        → Query Rewriter (resolves pronouns/context from chat history)
        → Embedder (query → vector)
        → Hybrid Search: FAISS + BM25 + RRF fusion
        → Adaptive Retriever (iterative refinement)
        → Retrieval Grader (quality check)
        → If not quality:
            → Corrective Retriever (query rewrite + retry)
        → CrossEncoder Reranker (re-rank by relevance)
        → LLM (context + question → answer with citations)
        → Answer Reflector (self-check + regenerate if needed)
        → SSE stream to frontend
        → Citation cards linked to source text
```

### Quiz Generation

```
User requests quiz for document
    → Retrieve document text chunks
    → LLM generates questions (MCQ + short answer)
    → Questions stored in PostgreSQL
    → User answers → auto-grading
    → Wrong answers → error book
```

### Note Semantic Search

```
User searches notes
    → Embed query (SBERT)
    → FAISS search on notes_{user.id} vector store
    → Retrieve note_ids + scores
    → PostgreSQL query by note_ids
    → Return NoteBrief with relevance scores
```

### Course-Document Association

```
User adds document to course
    → POST /api/courses/{course_id}/documents
    → Update document.course_space_id
    → Frontend CourseDetailView shows associated documents
    → Notes can also be tagged with course_id
```

### Async Task Queue

```
User uploads document / generates quiz
    → Create Task record (pending)
    → Enqueue job to in-process asyncio queue
    → Return task_id immediately (non-blocking)
    → Worker consumes queue:
        → document_process: parse → chunk → embed → index
        → quiz_generate: LLM generation → save questions
    → Update Task status (pending → running → completed/failed)
    → Frontend polls GET /api/tasks/{task_id}
```

## Tech Stack Summary

### Backend
- **FastAPI** — Async web framework
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL
- **FAISS** — Vector similarity search
- **BM25** — Lexical search (rank_bm25 + jieba tokenizer)
- **sentence-transformers** — Text embedding
- **Docling** — AI document parsing (IBM)
- **PyMuPDF** — PDF text extraction
- **python-docx / python-pptx** — DOCX/PPTX parsing
- **trafilatura** — Web URL content extraction
- **jieba** — Chinese text segmentation for BM25
- **jinja2** — Template engine for prompts
- **Edge TTS** — Text-to-speech synthesis
- **OpenAI SDK** — LLM provider abstraction
- **python-jose** — JWT authentication
- **Alembic** — Database migrations

### Frontend
- **Vue 3** — Reactive UI framework
- **Vite** — Fast build tool
- **TypeScript** — Type safety
- **vue-tsc** — Vue type checking
- **Pinia** — State management
- **TailwindCSS** — Utility-first CSS
- **Axios** — HTTP client with interceptors
- **markdown-it** — Markdown rendering
- **highlight.js** — Syntax highlighting
- **GSAP** — Animations
- **Vitest** — Unit testing

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | FAISS (file-based) | Simple, no extra service dependency |
| Lexical Search | BM25 + jieba | Chinese-aware keyword search, hybrid fusion |
| Hybrid Retrieval | RRF (Reciprocal Rank Fusion) | Combine FAISS + BM25 results without score normalization |
| Database | PostgreSQL | Robust, async support via asyncpg |
| Embedding | Local models (SBERT) | Privacy, no API cost for embedding |
| LLM | OpenAI-compatible API | Multi-provider flexibility |
| Streaming | SSE (Server-Sent Events) | Simple, works over HTTP, no WebSocket complexity |
| Auth | JWT tokens | Stateless, standard |
| Async Tasks | In-process asyncio queue | Simple deployment, no Redis dependency |
| Templates | Jinja2 | Maintainable prompt management, 14 migrated modules |
| Frontend TS | TypeScript + vue-tsc | Type safety, better IDE support |

## Project Structure

```
study-copilot/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (11 routers)
│   │   ├── core/         # Business logic (RAG, chunker, embedder, worker)
│   │   ├── db/           # Database models & config
│   │   ├── services/     # Business services (notes, courses, tasks, quiz)
│   │   ├── utils/        # Helpers (auth, encryption, file handling)
│   │   ├── config.py     # Pydantic Settings
│   │   └── main.py       # App entry point with lifespan
│   ├── tests/            # Backend tests
│   ├── uploads/          # User files (gitignored)
│   ├── vectorstore/      # FAISS indices (gitignored)
│   ├── alembic/          # DB migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/        # Page components
│   │   ├── components/   # Reusable components
│   │   ├── stores/       # Pinia stores
│   │   ├── services/     # API client
│   │   ├── composables/  # Vue composables (useMarkdown)
│   │   ├── types/        # TypeScript types
│   │   └── router/       # Route config
│   ├── tests/            # Frontend tests
│   └── package.json
└── docs/                 # This documentation
```
