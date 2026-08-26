# Study Copilot — Optimization Plan v2

> Based on full project assessment on 2026-08-25.
> Most items from the original OPTIMIZATION_PLAN.md have been resolved
> (see remaining_issues.md for the fixed-item history).
> This plan focuses on the 2 remaining low-risk issues and next-gen infrastructure upgrades.

---

## Current State Summary

| Metric | Current | Assessment |
|--------|---------|------------|
| Backend Python files | 81 | Feature-complete |
| Backend test files | 19 | Core modules well covered |
| Frontend Vue files | 35 | 13 views + 21 components |
| Frontend test files | 5 | Significantly lacking |
| Coverage gate | 65% (pytest-cov) | CI integrated |
| Ruff linter | 25 auto-fixes + dead code removal | Closed loop |
| Task persistence | DB polling + watchdog timeout | Restart-safe |
| Corrective retrieval | Integrated into ask_stream | Deployed |
| Soft delete | documents + notes recoverable | Deployed |
| LLM bounded timeout | In-stream visible errors | Deployed |
| Remaining issues | 2 (both low-risk P3) | Acceptable |
| Frontend typecheck | vue-tsc installed | Script ready |
| Backend pyproject.toml | MISSING | Only requirements.txt |
| Package mgmt | pip + requirements.txt | uv available but unused |
| Frontend build | Vite 5 + manualChunks | Production-ready |

---

## Remaining Issues (2 items, both P3)

| # | Issue | Location | Recommendation |
|---|-------|----------|----------------|
| R-1 | analysis/wrong is POST without request body | backend/app/api/analysis.py | Change to GET or add body schema |
| R-2 | pytest-asyncio event_loop fixture deprecation risk | backend/tests/conftest.py | Mitigated; monitor version bumps |

---

## Optimization Directions

| Phase | Focus | Est. Hours | Priority |
|-------|-------|-----------|----------|
| O1 | Modern Python packaging (pyproject.toml + uv) | 2-3h | CRITICAL |
| O2 | Docker multi-stage build + security | 1-2h | CRITICAL |
| O3 | CI pipeline completion | 1h | HIGH |
| O4 | Frontend test expansion | 4-6h | HIGH |
| O5 | Backend test expansion | 3-4h | HIGH |
| O6 | Structured logging + tracing | 2-3h | MEDIUM |
| O7 | Health check enhancements | 1h | MEDIUM |
| O8 | Documentation sync | 1-2h | MEDIUM |

**Total: ~15-22 engineer-hours**

---

## Phase O1: Modern Python Packaging

**Goal**: Migrate from requirements.txt to pyproject.toml with uv.

### O1.1 Create backend/pyproject.toml

Create at backend/pyproject.toml with:
- [project] metadata, all deps from requirements.txt
- [project.optional-dependencies] dev = test deps
- [build-system] hatchling
- [tool.ruff] config (migrated from root)
- [tool.pytest.ini_options]
- [tool.mypy]

Then:
- Remove [tool.ruff] from root pyproject.toml
- Update backend/requirements.txt to shim: "-e ."
- Delete test-requirements.txt

### O1.2 Generate uv.lock + Update CI

- cd backend && uv lock
- Update .github/workflows/test.yml to use astral-sh/setup-uv

**Acceptance**: uv install + pytest + ruff all green in CI.

---

## Phase O2: Docker Multi-Stage Build

### O2.1 Rewrite backend/Dockerfile

Two stages: builder (compiles deps) + runtime (minimal).
Non-root user, healthcheck, smaller image.

### O2.2 Create .dockerignore

Exclude pycache, tests, uploads, vectorstore, frontend, node_modules,
.git, .github, open-notebook-main, backups, *.md.

**Acceptance**: Image 50% smaller, non-root, healthcheck passes.

---

## Phase O3: CI Pipeline Completion

- Add vue-tsc --noEmit to frontend-tests job
- Add npm run build to frontend-tests job
- Add ruff check to backend-tests job

**Acceptance**: Type errors + build failures block merge.

---

## Phase O4: Frontend Test Expansion

By priority:
- P1: ChatView, UploadView, auth store expansion
- P2: DocumentView, QuizView, note store, BaseDialog
- P3: BaseTable, config store, chat composable

Target: 15+ test files, core views 3+ scenarios each.

---

## Phase O5: Backend Test Expansion

Services layer tests:
- test_chat_service, test_document_service, test_config_service,
  test_note_service, test_course_service

API integration tests:
- Full chat flow (mock LLM), upload error branches,
  quiz generate+submit flow, 401/403 guards

Target: 25+ test files.

---

## Phase O6: Observability

- loguru for structured logging (JSON prod, colored dev)
- TraceIdMiddleware for request tracing
- Optional: prometheus-client /metrics

---

## Phase O7: Runtime Quality

- /health returns dependency checks (DB, FAISS, embedding)
- Lifespan startup checklist (DB, FAISS dir, encryption key, JWT key)
- TTS output to dedicated dir + periodic cleanup

---

## Phase O8: Documentation Sync

- AGENTS.md Current State: add recent features
- CLAUDE.md: update task persistence description
- README.md: feature status table all stable
- docs/3-API-REFERENCE: add new endpoints

---

## Execution Timeline

Week 1: O1 + O2
Week 2: O3 + O4 (start)
Week 3: O5 + O4 (continue)
Week 4: O6 + O7 + O8

Risk: run pytest + npm test after each phase.
Docker: verify in branch before merge.
Tests (O4/O5): progressive, no big-bang.
O6/O7/O8: do not block releases.
