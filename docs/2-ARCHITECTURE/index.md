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
│  ├─────────┤ ├─────────┤ ├─────────┴─────────┴─────────┘   │
│  │ Metrics │ │Classroom│ │                                         │
│  │  API    │ │  API    │ │                                         │
│  └────┬────┘ └────┬────┘ └─────────────────────────────────────────┘
│       └───────────┴─────────────────────────────────────────────────┐
│                            │                                        │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                      Core Engine                            │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │ Document   │ │  Vector    │ │    LLM     │              │    │
│  │  │ Parser     │ │  Store     │ │  Caller    │              │    │
│  │  │ (Docling)  │ │ (pgvector) │ │(OpenRouter)│              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │  Chunker   │ │   Quiz     │ │  Embedder  │              │    │
│  │  │            │ │ Generator  │ │  (SBERT)   │              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │ Query      │ │  Answer    │ │  Async     │              │    │
│  │  │  Router    │ │ Reflector  │ │  Worker    │              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │ Adaptive   │ │Corrective  │ │ Reranker   │              │    │
│  │  │ Retriever  │ │ Retriever  │ │(CrossEnc)  │              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │  URL       │ │ Transform  │ │ Encryption │              │    │
│  │  │ Extractor  │ │ (9 types)  │ │  (Fernet)  │              │    │
│  │  │(trafilatura)│            │ │            │              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │
│  │  │ Document   │ │ Persona    │ │ Course     │              │    │
│  │  │ Bundle     │ │ Discussion │ │ Generator  │              │    │
│  │  │ (Budget)   │ │ (Multi-Ag) │ │ (Outlines) │              │    │
│  │  └────────────┘ └────────────┘ └────────────┘              │    │
│  │  ┌──────────────────────────────────────────┐               │    │
│  │  │  Legacy VectorStore (FAISS + BM25 + RRF) │               │    │
│  │  └──────────────────────────────────────────┘               │    │
│  └────────────────────────────────────────────────────────────┘    │
│                            │                                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  PostgreSQL  │ │ File Storage │ │ AsyncTasks   │               │
│  │  + pgvector  │ │ (uploads/)   │ │ (Queue)      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
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
    → DocumentChunk via pgvector (production)
    → Legacy: BM25VectorStore for backward compat
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
        → pgvector Search (IVFFlat / HNSW cosine similarity)
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
    → pgvector search on document_chunks table
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

### Multi-Persona Discussion Flow

```
User selects topic, personas & context mode (ChatView)
    → POST /api/chat/discuss
    → If context_mode == "full_docs":
        → DocumentBundle packs multi-doc context using proportional fair budget (1500 base + dynamic share)
      Else:
        → RAGEngine retrieves relevant snippets
    → PersonaDiscussion runs sequential persona turn chain:
        → Persona 1 (e.g. 苏老师 / Teacher) introduces and scaffolds
        → Persona 2 (e.g. 学霸 / Thinker) critiques and deepens
        → Persona 3 (e.g. 求知同学 / Curious) asks clarifying questions
        → Persona 4 (e.g. 归纳助手 / Notetaker) summarizes key takeaways
    → SSE streams `persona_speak` events with token output to frontend
    → Summary synthesized and appended to conversation history
```

### AI Classroom Integration & Self-Healing Flow

```
User triggers classroom generation (DocumentView / CourseDetailView)
    → GenerateClassroomDialog (select requirement, TTS, Web search, AI Image Generation)
    → POST /api/classroom/generate
    → AI Classroom engine queues generation job (job_id returned)
    → Study Copilot creates placeholder CourseSpace
    → Dual-Channel Synchronization:
        Channel 1 (Active Polling): Frontend polls GET /api/classroom/{job_id}/status
            → If completed: backend automatically pulls classroom assets and syncs course & quizzes
        Channel 2 (Webhook): Classroom engine pushes completion webhook to POST /api/classroom/webhook
            → HMAC signature verified, course & quizzes synced
    → Quizzes integrated into Study Copilot error book and learning analytics
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
- **pgvector** — Production vector search (IVFFlat / HNSW via embeddings table)
- **PostgreSQL FTS** — Full-text keyword search (GIN tsvector index)
- **FAISS + BM25** — Legacy fallback (file-based, backward compat)
- **sentence-transformers** — Text embedding
- **Docling** — AI document parsing (IBM)
- **PyMuPDF** — PDF text extraction
- **python-docx / python-pptx** — DOCX/PPTX parsing
- **trafilatura** — Web URL content extraction
- **CrossEncoder** — Retrieval reranking
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
- **Element Plus** — UI Component library
- **TailwindCSS** — Utility-first CSS
- **Axios** — HTTP client with interceptors
- **markdown-it** — Markdown rendering
- **highlight.js** — Syntax highlighting
- **GSAP** — Animations
- **Vitest** — Unit testing

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | PostgreSQL+pgvector (production); FAISS+BM25+RRF (legacy) | pgvector: SQL-native, no extra service; legacy kept for migration path |
| Lexical Search | PostgreSQL FTS + optional BM25 | Chinese-aware via FTS/GIN; hybrid fusion available |
| Hybrid Retrieval | pgvector IVFFlat (production); RRF (legacy) | Production: SQL-native cosine sim; legacy: FAISS+BM25 RRF |
| Database | PostgreSQL | Robust, async support via asyncpg |
| Embedding | Local models (SBERT) | Privacy, no API cost for embedding |
| LLM | OpenAI-compatible API | Multi-provider flexibility |
| Streaming | SSE (Server-Sent Events) | Simple, works over HTTP, no WebSocket complexity |
| Auth | JWT tokens | Stateless, standard |
| Async Tasks | In-process asyncio queue | Simple deployment, no Redis dependency |
| Templates | Jinja2 | 30 prompt files across 7 subdirectories (rag/quiz/reflector/retriever/router/decomposer/transformations) |
| Document Budgets | Proportional fair budget allocation | 1500 char base + proportional surplus distribution |
| AI Classroom Integration | REST Engine + Webhook + Status Polling | Dual-channel self-healing; local course outline fallback |

## Project Structure

```
study-copilot/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (13 routers)
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
