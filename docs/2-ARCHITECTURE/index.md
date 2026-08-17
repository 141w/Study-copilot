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
│  │  ┌────────────┐ ┌────────────┐                              │  │
│  │  │ Query     │ │ Reranker   │                              │  │
│  │  │  Rewriter  │ │(CrossEnc)  │                              │  │
│  │  │  Encryption │ │  TTS      │ │ URL Extractor              │  │
│  │  │ (Fernet)   │ │ (Edge TTS)│ │ (trafilatura)              │  │
│  │  │ Transformations            │ │  Async Tasks              │  │
│  │  │ (8 types)                  │ │ (Background)              │  │
│  │  └────────────┘ └────────────┘                              │  │
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
    → Chunker (Fixed 512-token or Semantic chunks)
    → Embedder (sentence-transformers → vector)
    → FAISS Vector Store (per-user index)
    → PostgreSQL metadata saved
```

### RAG Question Answering
```
User asks question
    → Query Rewriter (resolves pronouns/context from chat history)
    → Embedder (query → vector)
    → FAISS similarity search (top-k chunks)
    → CrossEncoder Reranker (re-rank by relevance)
    → LLM (context + question → answer with citations)
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

## Tech Stack Summary

### Backend
- **FastAPI** — Async web framework
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL
- **FAISS** — Vector similarity search
- **sentence-transformers** — Text embedding
- **Docling** — AI document parsing (IBM)
- **PyMuPDF** — PDF text extraction
- **OpenAI SDK** — LLM provider abstraction
- **python-jose** — JWT authentication

### Frontend
- **Vue 3** — Reactive UI framework
- **Vite** — Fast build tool
- **Pinia** — State management
- **TailwindCSS** — Utility-first CSS
- **Axios** — HTTP client with interceptors
- **markdown-it** — Markdown rendering
- **GSAP** — Animations

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | FAISS (file-based) | Simple, no extra service dependency |
| Database | PostgreSQL | Robust, async support via asyncpg |
| Embedding | Local models (SBERT) | Privacy, no API cost for embedding |
| LLM | OpenAI-compatible API | Multi-provider flexibility |
| Streaming | SSE (Server-Sent Events) | Simple, works over HTTP, no WebSocket complexity |
| Auth | JWT tokens | Stateless, standard |

## Project Structure

```
study-copilot/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers
│   │   ├── core/         # Business logic
│   │   ├── db/           # Database models & config
│   │   ├── utils/        # Helpers (auth, file handling)
│   │   ├── config.py     # Pydantic Settings
│   │   └── main.py       # App entry point
│   ├── tests/            # Backend tests
│   ├── uploads/          # User files (gitignored)
│   ├── vectorstore/      # FAISS indices (gitignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/        # Page components
│   │   ├── components/   # Reusable components
│   │   ├── stores/       # Pinia stores
│   │   ├── services/     # API client
│   │   └── router/       # Route config
│   ├── tests/            # Frontend tests
│   └── package.json
└── docs/                 # This documentation
```
