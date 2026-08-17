# Core Modules (`backend/app/core/`)

## Purpose

Core modules contain **pure business logic** with no HTTP or framework dependencies. They are independently testable and composable.

## Module Reference

| Module | Responsibility | Key Classes/Functions |
|--------|---------------|----------------------|
| `rag_engine.py` | RAG pipeline orchestrator | Query rewriting → embedding → FAISS search → reranking → LLM generation |
| `vector_store.py` | FAISS vector index management | `add_documents()`, `search()`, `delete_by_file()` — per-user isolation |
| `embedder.py` | Text embedding via sentence-transformers | `embed_texts()`, `embed_query()` — wraps local SBERT models |
| `llm.py` | LLM client wrapper | OpenAI SDK with retry/backoff, supports OpenRouter/OpenAI/Anthropic/Gemini |
| `document_parser.py` | Document parsing factory | PDF (Docling/PyMuPDF), DOCX (python-docx), PPTX (python-pptx) |
| `chunker.py` | Text chunking strategies | `FixedChunker` (512 tokens), `SemanticChunker` (sentence-boundary) |
| `quiz_generator.py` | LLM-based quiz creation | Generates MCQ/short-answer from context with difficulty levels |
| `encryption.py` | Fernet credential encryption | `encrypt_value()`, `decrypt_value()` — API key encryption at rest |
| `tts.py` | Edge TTS text-to-speech | `synthesize_speech()` — async audio generation via edge-tts |
| `url_extractor.py` | Web content extraction | `extract_from_url()` — fetches and parses web page content |
| `transformations.py` | Content transformation engine | 8 transform types: summary, key_points, outline, flashcards, mindmap, qa, translate, explain |
| `config.py` | User LLM config CRUD | Per-user model/base_url/api_key preferences |
| `rate_limit.py` | Request rate limiting | slowapi integration |
| `exceptions.py` | Custom exception hierarchy | `AppError`, `DocumentNotFoundError`, `LLMError`, etc. |
| `pdf_parser.py` | PDF-specific parsing | PyMuPDF fallback for large PDFs (>30 pages) |

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
    → FAISS Search (vector_store.py)
    → CrossEncoder Reranking (rag_engine.py)
    → Context Assembly
    → LLM Generation with Citations (llm.py)
    → Stream Response
```
