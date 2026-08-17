# Architecture Implementation Plan

> Generated: 2026-08-14 after P0-P3 completion
> Based on comprehensive codebase audit of Study Copilot

## Five Remaining Architecture Features

| # | Feature | Status | Effort |
|---|---------|--------|--------|
| B | Hybrid Retrieval (FAISS+BM25+RRF) | Upload uses FAISS only | 1d |
| E | Corrective Retrieval Integration | Dead code in rag_engine | 4h |
| C | Note Semantic Search | Not implemented | 1d |
| D | Course-Document Association | FK exists, no API | 0.5d |
| A | Async Task Queue | Service exists, no producer | 2-3d |

## Implementation Order: B -> E -> C -> D -> A

Rationale:
- B: smallest change, immediate retrieval quality gain
- E: reuses existing grader, small integration diff
- C: depends on embedder (already ready) and FAISS (from B)
- D: straightforward CRUD, model FK already in place
- A: largest change, needs careful testing

---

## B. Hybrid Retrieval Enablement

### Steps
1. Add _tokenize() with jieba for Chinese in BM25VectorStore
2. Add jieba to requirements.txt
3. Switch upload to RETRIEVAL_TYPE_HYBRID
4. Verify existing FAISS-only indices auto-load (already handled)
5. Run backend tests

### Files to Change
- backend/app/core/vector_store.py (BM25VectorStore: add _tokenize)
- backend/app/services/document_service.py (upload: change retrieval type)
- backend/requirements.txt (add jieba)

---

## E. Corrective Retrieval Integration

### Steps
1. In ask() / ask_stream(): call retrieval_grader.grade() after adaptive_retrieve
2. If quality is bad, call _corrective_retrieve()
3. Emit thinking event for the retry
4. Use retry results if better, fallback if not
5. Remove _needs_rewrite() dead method
6. Run tests

### Files to Change
- backend/app/core/rag_engine.py (integrate corrective flow)
- backend/tests/test_rag_engine.py (update tests)

---

## C. Note Semantic Search

### Steps
1. Create per-user FAISSVectorStore for notes in note_service.py
2. Index notes on create/update
3. Add POST /api/notes/search endpoint with NoteSearchRequest
4. Return NoteBrief list with relevance score
5. Update README to mark /notes/search as implemented
6. Run tests

### Files to Change
- backend/app/services/note_service.py (add vector store, index, search)
- backend/app/api/notes.py (add search endpoint + schema)
- backend/app/services/transform_service.py (update if needed)
- docs/3-API-REFERENCE/index.md (update path)
- README.md (remove "not implemented" note)

---

## D. Course-Document Association

### Steps
1. Add api/course_document_service.py (or extend course_service.py)
2. Add GET/POST/DELETE /courses/{id}/documents endpoints
3. Verify alembic migration for course_space_id FK
4. Re-enable frontend documents tab in CourseDetailView
5. Uncomment course.js methods
6. Run tests

### Files to Change
- backend/app/services/course_service.py (add document CRUD)
- backend/app/api/courses.py (add document routes)
- frontend/src/stores/course.js (uncomment methods)
- frontend/src/views/CourseDetailView.vue (re-add documents tab)

---

## A. Async Task Queue

### Steps
1. Create backend/app/core/task_worker.py (in-process queue worker)
2. Wire into document_service.upload_document (create task, return immediately)
3. Wire into quiz_service.generate_quizzes (same pattern)
4. Add POST /api/tasks endpoint
5. Startup: mark orphaned "running" tasks as "failed"
6. Re-enable TaskPanel polling
7. Run tests

### Files to Change
- backend/app/core/task_worker.py (NEW)
- backend/app/services/document_service.py (enqueue instead of blocking)
- backend/app/services/quiz_service.py (enqueue instead of blocking)
- backend/app/api/tasks.py (add POST endpoint)
- backend/app/main.py (start worker on startup)

---

## Validation

After each feature:
1. pytest tests/ --tb=short (all passing)
2. npx vitest run (all passing)
3. Manual: curl endpoint, verify response
4. git add -A && git commit