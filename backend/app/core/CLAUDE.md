# Core Modules (`backend/app/core/`)

## Purpose

Core modules contain **pure business logic** with no HTTP or framework dependencies. They are independently testable and composable.

## Module Reference

| Module | Responsibility | Key Classes/Functions |
|--------|---------------|----------------------|
| `rag_engine.py` | Agentic RAG orchestrator | 5-step pipeline: route → retrieve → grade/correct → generate → reflect |
| `query_router.py` | Intent classification & rewrite | `analyze()` — intent classification + context rewrite |
| `adaptive_retriever.py` | Adaptive retrieval strategy selection | 4 strategies: direct, single-doc, multi-doc, exhaustive |
| `retrieval_grader.py` | Retrieval quality assessment | Two-level grading with corrective fallback |
| `query_decomposer.py` | Query decomposition | Entity extraction and sub-query decomposition |
| `answer_reflector.py` | Answer quality self-reflection | Hallucination and alignment check with refinement |
| `document_parser.py` | Document parsing factory | PDF (Docling/PyMuPDF), DOCX (python-docx), PPTX (python-pptx) |
| `chunker.py` | Text chunking strategies | `FixedChunker` (512 tokens), `SemanticChunker`, `HierarchicalChunker` |
| `document_bundle.py` | Multi-doc budget allocation | OpenMAIC proportional fair text budget algorithm |
| `course_generator.py` | Local course & quiz generator | Auto-generate course outline and quizzes from docs |
| `persona_discussion.py` | Multi-agent persona discussion | 4 standard presets (苏老师, 学霸, 求知同学, 归纳助手) + sequential chain |
| `quiz_generator.py` | LLM-based quiz creation | Generates MCQ/short-answer with difficulty and explanations |
| `transformations.py` | Content transformation engine | 9 transform types: summary, keypoints, outline, flashcards, mindmap, qa, translate_en, translate_zh, explain |
| `pgvector_store.py` | Production vector store | PostgreSQL + pgvector (IVFFlat/HNSW cosine similarity) |
| `vector_store.py` | Legacy vector store | FAISS + rank-bm25 + jieba + RRF fusion |
| `embedder.py` | Text embedding | `embed_texts()`, `embed_query()` — wraps local SBERT models (async + caching) |
| `llm.py` | LLM client wrapper | OpenAI SDK with retry/backoff, supports OpenRouter/OpenAI/Anthropic/Gemini |
| `encryption.py` | Fernet credential encryption | `encrypt_value()`, `decrypt_value()` — API key encryption at rest |
| `tts.py` | Edge TTS text-to-speech | `synthesize_speech()` — async audio generation via edge-tts |
| `url_extractor.py` | Web content extraction | `extract_from_url()` — fetches and parses web page content |
| `rate_limit.py` | Request rate limiting | 自研滑动窗口 `IPRateLimiter` |
| `logger.py` | Structured logging | JSON/text logging with trace-id ContextVar |
| `template_manager.py` | Prompt template manager | Jinja2 renderer for 30 templates across 7 directories |
| `task_worker.py` | Background task worker | Enqueue/dequeue/process tasks with watchdog and crash recovery |
| `exceptions.py` | Custom exception hierarchy | `AppError`, `DocumentNotFoundError`, `LLMError`, etc. |

## Design Principles

1. **No HTTP concerns** — Core modules never import FastAPI, Request, Response, etc.
2. **Async where I/O happens** — All LLM/embedding/DB calls are async
3. **Dependency injection** — Pass config and clients as parameters, not globals
4. **Testable in isolation** — Mock external services (LLM, FAISS) at the boundary

## RAG Pipeline Flow

```
User Question
    → Query Rewriting (llm.py)
    → Embedding (embedder.py)
    → pgvector Search (pgvector_store.py, production)
    → CrossEncoder Reranking (rag_engine.py)
    → Context Assembly
    → LLM Generation with Citations (llm.py)
    → Stream Response
```
