# Testing Guide

## Overview

Study Copilot uses:
- **Backend**: `pytest` for unit and integration tests
- **Frontend**: `vitest` for component and store tests

## Backend Tests

### Setup

```bash
cd backend
conda activate study-c
pip install pytest pytest-asyncio httpx
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_document_parser.py

# Run a specific test
pytest tests/test_document_parser.py::test_parse_pdf

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Test Files

| File | Tests |
|------|-------|
| `tests/test_document_parser.py` | PDF/DOCX/PPTX parsing, edge cases |
| `tests/test_quiz_generator.py` | Quiz generation, question formatting |
| `tests/test_rag_engine.py` | RAG pipeline, retrieval, reranking |

### Writing Backend Tests

```python
import pytest
from app.core.chunker import FixedChunker

def test_fixed_chunker_basic():
    """Test that FixedChunker splits text correctly."""
    chunker = FixedChunker(chunk_size=100, overlap=20)
    text = "This is a test. " * 20
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    assert all(len(c.text) <= 120 for c in chunks)

@pytest.mark.asyncio
async def test_document_upload(client, auth_headers):
    """Test document upload endpoint."""
    with open("tests/fixtures/sample.pdf", "rb") as f:
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", f, "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 201
```

### Test Fixtures

Place test data in `backend/tests/fixtures/`:
- `sample.pdf` — Small PDF for parsing tests
- `sample.docx` — DOCX test file
- `sample.pptx` — PPTX test file

---

## Frontend Tests

### Setup

```bash
cd frontend
npm install
```

### Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Run with coverage
npx vitest run --coverage

# Run specific test file
npx vitest run tests/stores/auth.test.js
```

### Test Files

| File | Tests |
|------|-------|
| `tests/components/UploadView.test.js` | Upload component rendering, file selection |
| `tests/components/ChatMessage.test.js` | Message display, citation rendering |
| `tests/stores/auth.test.js` | Auth store: login, logout, token refresh |
| `tests/stores/chat.test.js` | Chat store: messages, streaming |
| `tests/stores/quiz.test.js` | Quiz store: generation, submission |

### Writing Frontend Tests

```javascript
import { describe, it, expect, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/auth';

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('logs in user and stores token', async () => {
    const store = useAuthStore();
    vi.spyOn(store, 'login').mockResolvedValue({ token: 'abc' });
    
    await store.login({ username: 'test', password: 'pass' });
    
    expect(store.isAuthenticated).toBe(true);
  });

  it('clears state on logout', () => {
    const store = useAuthStore();
    store.logout();
    
    expect(store.isAuthenticated).toBe(false);
    expect(store.token).toBeNull();
  });
});
```

### Test Configuration

Frontend tests use `vitest.config.js`:

```javascript
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
});
```

---

## Integration Testing

For full-stack integration tests:

```bash
# Start test database
psql postgres -c "CREATE DATABASE study_copilot_test;"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE study_copilot_test TO study_user;"

# Set test environment
export DATABASE_URL=postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot_test

# Run backend tests against test DB
cd backend && pytest tests/ -v
```

---

## CI/CD

### GitHub Actions (Recommended)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: study_copilot_test
          POSTGRES_USER: study_user
          POSTGRES_PASSWORD: study123
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt pytest pytest-asyncio
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

---

## Test Coverage Goals

| Area | Target |
|------|--------|
| API endpoints | 80%+ |
| Core business logic | 90%+ |
| Frontend stores | 80%+ |
| Frontend components | 60%+ |

---

## Troubleshooting Tests

| Issue | Fix |
|-------|-----|
| `pytest` not found | Activate conda env or `pip install pytest` |
| Database connection errors | Ensure PostgreSQL is running and test DB exists |
| `vitest` command not found | `npm install` in frontend directory |
| Snapshot failures | `npx vitest run --update` to update snapshots |
| Async test hangs | Ensure `@pytest.mark.asyncio` decorator is present |
