# Testing Guide

## Overview

Study Copilot uses:
- **Backend**: `pytest` + `pytest-asyncio` + `pytest-cov` for unit and integration tests
- **Frontend**: `vitest` (dual-project: SPA jsdom + bot engine node) for component, store, and pure-function tests

## Backend Tests

### Setup

```bash
cd backend
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests (coverage enforced at ≥65% via pyproject.toml addopts)
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_document_parser.py

# Run a specific test
pytest tests/test_document_parser.py::test_parse_pdf

# Run with HTML coverage report
pytest tests/ --cov-report=html
# → opens htmlcov/index.html
```

**Note**: Coverage failure threshold (currently 65%) is set in `pyproject.toml` under `[tool.pytest.ini_options]` as `--cov-fail-under=65`. All invocations inherit it; use `--no-cov` to skip the check.

### Test Files (39 files, 490 tests, 72.52% coverage)

| File | Tests |
|------|-------|
| `tests/test_analysis_service.py` | Wrong answer analysis, knowledge stats, progress |
| `tests/test_api.py` | Health check, root endpoint |
| `tests/test_auth.py` | Password hash, JWT encode/decode, expiration |
| `tests/test_auth_service.py` | Registration, login, token refresh service logic |
| `tests/test_chat_service.py` | RAG Q&A, chat sessions, history retrieval |
| `tests/test_chunker.py` | Fixed/Semantic/Hierarchical chunking strategies |
| `tests/test_config_service.py` | LLM config CRUD, temperature roundtrip |
| `tests/test_course_generator.py` | Local course outline & quiz generation |
| `tests/test_course_service.py` | Course space CRUD, document associations |
| `tests/test_dimension_and_transform_fixes.py` | Embedding dimensions and transformation fixes |
| `tests/test_document_bundle.py` | Multi-document packing, CJK budget, proportional allocation |
| `tests/test_document_parser.py` | PDF/DOCX/PPTX parsing, edge cases |
| `tests/test_document_service.py` | Document upload, delete, soft-delete, restore |
| `tests/test_error_visibility_fixes.py` | API error responses and exception formatting |
| `tests/test_exceptions.py` | Custom exception hierarchy and mapping |
| `tests/test_hybrid_retrieval_contract.py` | FAISS+BM25 RRF hybrid retrieval contract |
| `tests/test_list_pagination.py` | Paginated list endpoints and offset/limit validation |
| `tests/test_logging_config.py` | Structured JSON/text logging and trace context |
| `tests/test_metrics.py` | `/api/metrics` operational task counts snapshot |
| `tests/test_note_indexing.py` | Note-vector-store indexing and semantic search |
| `tests/test_openmaic_integration.py` | OpenMAIC bridge, classroom status, webhook, self-healing |
| `tests/test_persona_discussion.py` | Multi-persona discussion presets and sequential chain |
| `tests/test_profile.py` | User profile and password update endpoints |
| `tests/test_quiz.py` | Quiz generation and submission API endpoints |
| `tests/test_quiz_generator.py` | LLM quiz generation, parsing, formatting |
| `tests/test_quiz_task_e2e.py` | Quiz async task end-to-end processing |
| `tests/test_rag_engine.py` | Agentic RAG pipeline, routing, retrieval, reflection |
| `tests/test_rate_limit.py` | Sliding-window IP rate limiter |
| `tests/test_security_headers.py` | Security middleware headers and trace propagation |
| `tests/test_soft_delete.py` | Document/note soft-delete and restore isolation |
| `tests/test_task_persistence.py` | Async task persistence, recovery, and watchdog |
| `tests/test_task_service.py` | Task CRUD service, enqueue, and status reporting |
| `tests/test_tasks.py` | Task API endpoints and cancellation |
| `tests/test_trace_middleware.py` | Trace middleware (X-Trace-ID propagation) |
| `tests/test_transform_service.py` | 9 content transformation types orchestration |
| `tests/test_tts.py` | Edge TTS audio generation and voice listing |
| `tests/test_type_safety_regressions.py` | Type safety baseline and regression checks |
| `tests/test_url_extractor.py` | Web URL content fetching and Markdown extraction |
| `tests/test_vector_store.py` | FAISS/BM25/pgvector stores and Chinese tokenization |

### How Backend Tests Work

Tests use **SQLite in-memory** via `aiosqlite` — no PostgreSQL needed. The `conftest.py` creates tables at session start and wipes all tables between each test to prevent cross-test contamination.

```python
# conftest.py overview:
# - session-scoped async engine (SQLite aiosqlite)
# - autouse fixture: TRUNCATE all tables after every test
# - db_session fixture: per-test async SQLAlchemy session
# - client fixture: httpx AsyncClient with FastAPI dependency overrides
```

### Writing Backend Tests

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_chunker_basic():
    """Unit test — no client needed."""
    from app.core.chunker import FixedChunker
    chunker = FixedChunker(chunk_size=100, overlap=20)
    text = "This is a test. " * 20
    chunks = chunker.chunk(text)
    assert len(chunks) > 1

@pytest.mark.asyncio
async def test_document_upload(client):
    """Integration test — uses httpx client fixture."""
    response = await client.post("/api/documents/upload", ...)
    assert response.status_code == 201
```

> **Skip `@pytest.mark.asyncio`**: with `asyncio_mode = "auto"` in pyproject.toml, all async test functions are auto-marked.

### Test Fixtures

No fixture directory exists. Tests that need sample documents create them inline using `python-docx` / `PyMuPDF` generators. If you need to add binary fixture files, place them under:

```
backend/tests/fixtures/
```

---

## Frontend Tests

### Setup

```bash
cd frontend
npm install
```

### Running Tests

```bash
# Run all tests across both projects (spa + bot)
npx vitest run

# Watch mode (auto-reruns on file change)
npx vitest

# Run only the spa project
npx vitest run --project spa

# Run only the bot engine tests
npx vitest run --project bot

# Run a specific test file
npx vitest run tests/stores/chat.test.ts

# Run a specific bot engine test
npx vitest run --project bot src/bot/engine.test.ts
```

### Test Structure

`vitest.config.ts` defines **two projects**:

| Project | Environment | Scope |
|---------|-------------|-------|
| `spa` | jsdom + Vue | `tests/**/*.{test,spec}.{js,ts}` — components, stores, composables, services |
| `bot` | node | `src/bot/**/*.test.ts` — bot expression/shape/skin/gaze engine |

Both share `tests/setup.js`, which auto-detects `window` availability:
- **jsdom**: registers Element Plus (zh-CN), mocks `axios` and `localStorage`, resets Pinia per test
- **node**: skips DOM mocks, only mocks `axios`

### Test Files (24 files, 227 tests)

#### SPA tests (`tests/` — 17 files)

| File | Tests |
|------|-------|
| `components/ChatMessageItem.test.js` | Chat message item rendering & interactions |
| `components/ConfirmDialog.test.js` | ConfirmDialog component |
| `components/UploadView.test.js` | Upload component rendering |
| `composables/chatExport.test.js` | Chat markdown export |
| `composables/useFormat.test.js` | Text formatting utility |
| `services/api.test.js` | Axios interceptor retry logic |
| `stores/auth.test.js` | Auth store: login, logout, token |
| `stores/chat.test.js` | Chat store: messages, streaming |
| `stores/chat.title.test.js` | Chat session title updates |
| `stores/chat.sse-error.test.js` | Chat SSE error resilience & handling |
| `stores/config.test.js` | LLM config store |
| `stores/document.test.js` | Document store: CRUD, SWR cache |
| `stores/note.test.js` | Note store: filters, SWR cache |
| `stores/openmaic.test.ts` | OpenMAIC store: job polling, auto-invalidation |
| `stores/quiz.test.js` | Quiz store: generation, submission |
| `views/AnalysisView.test.js` | Learning analytics dashboard rendering |
| `views/ProfileView.test.js` | User profile and settings view rendering |

#### Bot engine tests (`src/bot/` — 7 files)

| File | Tests |
|------|-------|
| `expressions.test.ts` | Expression parsing and evaluation |
| `shape.test.ts` | Avatar shape rendering |
| `skins.test.ts` | Skin/appearance logic |
| `engine.test.ts` | Bot engine orchestration |
| `face.test.ts` | Face expression logic |
| `gaze.test.ts` | Gaze/tracking calculations |
| `cycles.test.ts` | Animation cycle timing |

### Writing Frontend Tests

```typescript
import { describe, it, expect, vi } from 'vitest'

// Store test (spa project — Pinia auto-reset by setup.js)
describe('Auth Store', () => {
  it('logs in user and stores token', async () => {
    const store = useAuthStore()
    vi.spyOn(store, 'login').mockResolvedValue({ token: 'abc' })
    await store.login({ username: 'test', password: 'pass' })
    expect(store.isAuthenticated).toBe(true)
  })

  it('clears state on logout', () => {
    const store = useAuthStore()
    store.logout()
    expect(store.isAuthenticated).toBe(false)
    expect(store.token).toBeNull()
  })
})

// Component test (spa project)
import { mount } from '@vue/test-utils'
import UploadView from '@/components/UploadView.vue'

it('renders upload button', () => {
  const wrapper = mount(UploadView)
  expect(wrapper.find('button').exists()).toBe(true)
})

// Bot engine test (bot project — pure functions, no DOM)
import { evaluateExpression } from './expressions'

describe('Expression Engine', () => {
  it('parses simple expressions', () => {
    expect(evaluateExpression('idle')).toMatchObject({ state: 'idle' })
  })
})
```

### Test Configuration

Frontend tests use `vitest.config.ts` (dual-project):

```typescript
// Two projects: spa (jsdom) and bot (node)
export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: {
    projects: [
      {
        name: 'spa',
        environment: 'jsdom',
        globals: true,
        include: ['tests/**/*.{test,spec}.{js,ts}'],
        setupFiles: ['./tests/setup.js'],
      },
      {
        name: 'bot',
        environment: 'node',
        globals: true,
        include: ['src/bot/**/*.test.ts'],
        setupFiles: ['./tests/setup.js'],
      },
    ],
  },
})
```

`tests/setup.js` auto-detects environment and conditionally registers Element Plus, mocks `localStorage`, and resets Pinia.

---

## Integration Testing

Backend tests already run as integration tests (FastAPI `httpx` client + SQLite in-memory DB via `conftest.py`). For manual full-stack testing against a real PostgreSQL:

```bash
# Start PostgreSQL locally, then:
export DATABASE_URL=postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot

# Start backend
cd backend && uvicorn app.main:app --reload

# Start frontend (separate terminal)
cd frontend && npm run dev
```

---

## CI/CD

### GitHub Actions

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: cd backend && pytest tests/ -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci && npx vitest run
```

No PostgreSQL service needed — both backend and frontend tests run against SQLite in-memory.

---

## Type Check

```bash
cd frontend
npx vue-tsc --noEmit
```

---

## Test Coverage Goals

| Area | Target |
|------|--------|
| Backend overall | ≥65% (enforced, `--cov-fail-under`) |
| Core business logic (RAG, quiz, transform) | 90%+ |
| Frontend stores | 80%+ |
| Frontend components | Minimal (Element Plus provides UI) |

---

## Troubleshooting Tests

| Issue | Fix |
|-------|-----|
| `pytest` not found | `pip install -e ".[dev]"` in `backend/` |
| `event loop is already running` / `RuntimeError: attached to a different loop` | Use session-scoped fixtures (already in `conftest.py`); run with `pytest` not individual files if shared state issues persist |
| Coverage below threshold | Add tests or temporarily pass `--no-cov` to skip the check |
| `vitest` command not found | `npm install` in `frontend/` |
| Bot test DOM errors | Bot project runs in `node` environment — no window; check `setup.js` guards |
| Async store test fails | Ensure `setActivePinia(createPinia())` called (auto-handled by `setup.js` for spa tests) |
