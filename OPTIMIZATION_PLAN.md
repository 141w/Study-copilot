# Optimization Plan v3 — Code-Level Findings

> **Based on: source code reading (not documents).** Every item below is verified
> against actual `.py` / `.vue` / `.ts` / `.conf` files as of 2026-08-29.
>
> Three stale documents were archived to `archive_docs/`:
> - `OPTIMIZATION_PLAN_v2.md` — 6 of 8 optimization phases already done or stale
> - `findings.md` — 50KB historical journal, resolved items mixed with living ones
> - `remaining_issues.md` — 1 valid item remaining, 26 resolved items listed

---

## Quick Summary

| Priority | Verified Code Issues | Est. Effort |
|----------|---------------------|-------------|
| High | 6 database/IO/blocking problems | Small–Medium |
| Medium | 5 concurrency/caching/logging issues | Small–Medium |
| Low | 5 hardcoded values/import/conn pool | Small |

**Fast wins** (small effort, immediate impact): `document_parser` DOCX/PPTX thread offload; `vector_store` hybrid search + cross-doc retrieval parallelized; 4 composite DB indexes via Alembic migration; task_worker debug log cleanup; LLM retry jitter.

## Done (2026-08-29 + 2026-08-30)

| Item | Files Changed | Verification |
|------|--------------|-------------|
| L-1: LLM retry jitter | `llm.py` — added `import random`, jitter to `2**attempt + random.uniform(0,1)` | ruff ✅ |
| M-1: FAISS+BM25 parallel | `vector_store.py` — `asyncio.gather` for both searches | ruff ✅, 400 tests ✅ |
| M-2: Cross-doc retrieval parallel | `rag_engine.py` — `asyncio.gather` for store loading + searching | ruff ✅, 400 tests ✅ |
| M-4: Temperature ×10 convention | `config_service.py` — all ×10/÷10 removed; migration `e1f2a3b4c5d6` backfills | ruff ✅, 400 tests ✅ |
| M-5: Debug log + redundant imports | `task_worker.py` — removed 6 lines debug logging + 3 lines redundant imports | ruff ✅, 400 tests ✅ |
| H-2: DOCX/PPTX thread offload | `document_parser.py` — `_parse_sync` + `asyncio.to_thread` for both parsers | ruff ✅, 400 tests ✅ |
| H-3: Hardcoded credentials | `config.py` — `""` for `openai_api_key` + `database_url`; `main.py` startup validation | ruff ✅ |
| —: alembic.ini env ref | `alembic.ini` — `${DATABASE_URL}` instead of hardcoded URL | manual review ✅ |
| H-4: Composite DB indexes | `alembic/versions/d9e0f1a2b3c4_add_composite_indexes.py` — 4 indexes | syntax ✅ (migration pattern verified) |
| H-1: analysis_service 4 full-table scans | `analysis_service.py` — 2 SQL GROUP BY queries (wrong + totals) + 1 func COUNT/SUM for stats + 1 DATE GROUP BY for progress | ruff ✅, 420 tests ✅, +18 tests, coverage 18%→71% |
| M-3: Vector store cache unbounded | `rag_engine.py` — OrderedDict LRU (max=20) + `evict_vector_store` + `clear_vector_stores`; `document_service.py` — evict on soft-delete | ruff ✅, 420 tests ✅ |
| L-2: generate()/chat_stream() no retry | `llm.py` — generate: max_retries=2; chat_stream: max_retries=1 (creation only, mid-stream re-raises) | ruff ✅, 420 tests ✅ |
| L-3: DB pool default without tuning | `database.py` — 4 env vars with SQLAlchemy-default fallbacks (pool_size=5, max_overflow=10, timeout=30, recycle=3600) | ruff ✅, 420 tests ✅ |
| —: analysis_service tests | `tests/test_analysis_service.py` — 15 tests (7 wrong+4 stats+4 progress+3 API integration) | 400 tests ✅, coverage 70.7% |
| —: transform_service tests | `tests/test_transform_service.py` — 20 tests (transform/note/document paths) | 420 tests ✅, transform_service coverage 23%→92% |

---

## High Priority — Blocking / Memory / Correctness

### H-1: `analysis_service.py` — 4 full-table scans per request

**Source lines:** 22–56 (analyze_wrong_questions), 82–93 (get_knowledge_stats), 101–124 (get_progress)

**What the code does:**
```python
# Line 22-24: Query 1 — loads every wrong quiz result into Python memory
result = await db.execute(
    select(QuizResult).where(QuizResult.user_id == user.id,
                             QuizResult.is_correct == False))
wrong_results = list(result.scalars().all())

# Line 30-32: Query 2 — loads every matching Quiz
q_result = await db.execute(select(Quiz).where(Quiz.id.in_(quiz_ids)))
quizzes = {q.id: q for q in q_result.scalars().all()}

# Line 35-39: Query 3 — loads matching Documents for filenames
d_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))

# Line 50-51: Query 4 — loads EVERY quiz result again (not just wrong)
all_r = await db.execute(select(QuizResult).where(QuizResult.user_id == user.id))
all_results = all_r.scalars().all()
```

**get_knowledge_stats (82-93):**
```python
result = await db.execute(select(QuizResult).where(QuizResult.user_id == user.id))
all_results = list(result.scalars().all())
total = len(all_results)                          # Python-side COUNT
correct = sum(1 for r in all_results if r.is_correct)  # Python-side SUM
```

**get_progress (101-124):** Same pattern, plus Python `defaultdict` date grouping.

**Impact:** For a user with 1,000 quiz results: each call fetches 1,000+ rows across 4 queries (1-4 round trips), ~100ms each on PostgreSQL. With SQL aggregation: single round trip + sub-millisecond compute.

**Suggested fix (SQL):**
```sql
-- analyze_wrong_questions as single query with CTEs:
WITH wrong AS (
    SELECT qr.quiz_id, q.document_id
    FROM quiz_results qr
    JOIN quizzes q ON qr.quiz_id = q.id
    WHERE qr.user_id = :uid AND NOT qr.is_correct
),
totals AS (
    SELECT q.document_id,
           COUNT(*) FILTER (WHERE qr.is_correct) AS correct,
           COUNT(*) AS total
    FROM quiz_results qr
    JOIN quizzes q ON qr.quiz_id = q.id
    WHERE qr.user_id = :uid
    GROUP BY q.document_id
)
SELECT ...  -- LEFT JOIN wrong + totals by document_id
```

```python
# get_knowledge_stats as single func.count query:
from sqlalchemy import func
stmt = (
    select(
        func.count(QuizResult.id).label("total"),
        func.sum(func.cast(QuizResult.is_correct, Integer)).label("correct"),
    )
    .where(QuizResult.user_id == user.id)
)
result = await db.execute(stmt)
row = result.one()
```

**Effort:** Medium.

---

### H-2: `document_parser.py` — DOCX/PPTX block event loop

**Source lines:** 418–471 (DOCXParser.parse), 491–532 (PPTXParser.parse)

**What the code does:**
```python
# Line 418: Declared async, but entirely synchronous inside
async def parse(self, file_path: str) -> dict[str, Any]:
    from docx import Document
    doc = Document(file_path)           # ← BLOCKS event loop for 50-200ms
    # ... all iteration, table parsing synchronous

# Line 491: Same issue
async def parse(self, file_path: str) -> dict[str, Any]:
    from pptx import Presentation
    prs = Presentation(file_path)        # ← BLOCKS event loop for 100-500ms
    # ... all slide iteration synchronous
```

**Contrast with PDFParser (277–370):** Already uses correct pattern:
```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(
    _executor, self._convert_with_docling, file_path, enable_ocr
)
```

**Impact:** A DOCX parse takes 50-200ms blocking the event loop. A PPTX takes 100-500ms. During peak upload, these serialize: upload 1 → blocks all → upload 2 → blocks all.

**Suggested fix:** Extract `_parse_sync(self, file_path)` method with the current body, then:
```python
async def parse(self, file_path: str) -> dict[str, Any]:
    return await asyncio.to_thread(self._parse_sync, file_path)
```

**Effort:** Small (copy-paste refactor, same logic, just async wrapper).

---

### H-3: `config.py` — Hardcoded dummy API key and DB credentials

**Source lines:** 8, 26

```python
class Settings(BaseSettings):
    openai_api_key: str = "sk-dummy"        # Line 8
    database_url: str = "postgresql+asyncpg://study_user:study123@localhost:5432/study_copilot"  # Line 26
```

**Impact:** If `.env` is missing in production (deployment mistake), server silently starts with `"sk-dummy"`. All LLM calls return provider 401 — confusing "200 OK with empty answer" behavior. Same DB URL: deployment without `.env` connects to developer's localhost postgres.

**Note:** `jwt_secret_key: str = ""` (line 20) and `encryption_key: str = ""` (line 40) already correctly default to empty with fail-fast behavior (JWT auth raises without key). The two fields above should match.

**Suggested fix:**
```python
openai_api_key: str = ""    # Fail loud: raise at startup if empty after env load
# (Add validation in main.py lifespan or __init__)
```

**Effort:** Small.

---

### H-4: `database.py` — Missing composite indexes

**Source lines:** 52–68 (Document), 190–215 (Note), 71–77 (ChatSession), 91–112 (QuizResult)

**Current indexes (from source):**
| Table | Individual Indexes | Missing for Common Patterns |
|-------|-------------------|---------------------------|
| `documents` | `user_id` (FK only), `deleted_at` (index), `course_space_id` (index) | `(user_id, deleted_at, created_at DESC)` |
| `notes` | `user_id` (FK only) (idx 196), `course_space_id` (index) (idx 198), `deleted_at` (index) (idx 211) | `(user_id, deleted_at, updated_at DESC)` |
| `chat_sessions` | None | `(user_id, created_at DESC)` |
| `quiz_results` | None | `(quiz_id, submitted_at)` — used by quiz_service lookups |

**What queries hit these:**
```python
# course_service.py:128 (and equivalents throughout)
select(Document).where(
    Document.course_space_id == course_id,   # Filter 1
    Document.user_id == user.id,            # Filter 2
)
# Without composite index: index scan on course_space_id, then filter user_id → seq scan
```

```python
# chat_service, document_service, note_service (list endpoints)
select(Model).where(Model.user_id == user.id).order_by(Model.created_at.desc())
# Without composite (user_id, created_at DESC): sort in memory
```

**Impact:** PostgreSQL can use index-only scan with composite index, eliminating heap FETCH. With 5,000 notes: list queries drop from ~30ms (with heap) to ~3ms (index-only). With 100 notes: arguably equivalent, but no regression.

**Suggested fix (Alembic migration):**
```python
op.create_index('ix_documents_user_deleted_created',
    'documents', ['user_id', 'deleted_at', 'created_at'],
    postgresql_using='btree', unique=False)
op.create_index('ix_notes_user_deleted_updated',
    'notes', ['user_id', 'deleted_at', 'updated_at'],
    postgresql_using='btree', unique=False)
op.create_index('ix_chat_sessions_user_created',
    'chat_sessions', ['user_id', 'created_at'],
    postgresql_using='btree', unique=False)
```

**Effort:** Small (migration file + model annotation).

---

## Medium Priority — Concurrency / Caching / Correctness

### M-1: Hybrid search FAISS + BM25 sequential

**Source line:** vector_store.py:401–402
```python
async def search(self, query: str, top_k: int = 5) -> list[dict]:
    faiss_results = await self._faiss.search(query, top_k * 2)   # ← blocks here
    bm25_results = await self._bm25.search(query, top_k * 2)    # ← then here
    fused = self._rrr_fusion(faiss_results, bm25_results, top_k)
    return fused
```

**Impact:** FAISS + BM25 are independent CPU operations running on the same thread pool. Running them sequentially doubles search latency (~10ms on typical corpora → ~20ms).

**Suggested fix:**
```python
faiss_results, bm25_results = await asyncio.gather(
    self._faiss.search(query, top_k * 2),
    self._bm25.search(query, top_k * 2),
)
```

**Effort:** Small.

---

### M-2: Cross-document retrieval sequential

**Source line:** rag_engine.py:296–298
```python
async def retrieve(self, doc_ids, query, top_k=5):
    all_results = []
    for doc_id in doc_ids:                           # ← serial await loop
        store = await self._get_vector_store(doc_id)
        results = await store.search(query, fetch_k)
        all_results.extend(results)
```

**Impact:** N documents → N sequential latency. With 3 documents: ~30ms → ~10ms with parallel.

**Suggested fix:**
```python
stores = await asyncio.gather(*[
    self._get_vector_store(did) for did in doc_ids
])
results_per_doc = await asyncio.gather(*[
    s.search(query, fetch_k) for s in stores
])
all_results = [r for sub in results_per_doc for r in sub]
```

**Effort:** Small.

---

### M-3: `rag_engine.py` — Vector store cache unbounded

**Source line:** rag_engine.py:53
```python
def __init__(self):
    self._vector_store_cache = {}   # Never evicted; grows without bound
```

**Per entry:** FAISS index (0.5–5 MB) + BM25 index (~100 KB) + all chunks in Python lists (~500 KB–5 MB). 100 documents → 100–1000 MB consumed, never released.

**Impact:** Long-running server processing multi-course users accumulates RAM indefinitely. With 50 documents (2 courses × 25): ~50–500 MB. Shadow memory pressure degrades other caches (OS page cache for FAISS mmap).

**Suggested fix:**
```python
from collections import OrderedDict

class VectorStoreCache:
    def __init__(self, max_size: int = 20):
        self._cache: OrderedDict[str, DocumentVectorStore] = OrderedDict()

    def get(self, doc_id: str) -> DocumentVectorStore | None:
        if doc_id in self._cache:
            self._cache.move_to_end(doc_id)
            return self._cache[doc_id]
        return None

    def put(self, doc_id: str, store: DocumentVectorStore) -> None:
        if doc_id in self._cache:
            self._cache.move_to_end(doc_id)
        else:
            if len(self._cache) >= self._cache.max_size:
                self._cache.popitem(last=False)  # Evict LRU
            self._cache[doc_id] = store

    def evict(self, doc_id: str) -> None:
        self._cache.pop(doc_id, None)
```

**Additionally:** In `document_service.py`'s `delete_document`, call `rag_engine._vector_store_cache.evict(doc_id)` to free immediately on delete.

**Effort:** Small–Medium.

---

### M-4: `config_service.py` — Temperature ×10 implicit convention ✅ DONE

**Source lines:** 60, 134 (write) and 104, 185 (read/response)

**Fix (2026-08-30):**
- `alembic/versions/e1f2a3b4c5d6_normalize_temperature_column.py` — backfills `temperature / 10.0 WHERE temperature > 1`
- `config_service.py` — removed all ×10 on write and ÷10 on read; temperature stored/returned as-is
- `tests/test_config_service.py` — removed legacy compat test (tested dead behavior)

**Verification:** ruff ✅, 400 tests ✅

---

### M-5: `task_worker.py` — Debug logging + redundant imports

**Source lines:** 86–91, 95–97
```python
# Line 86-91: Debug logging that fires on EVERY task claim (WARNING level)
logging.getLogger(__name__).warning(
    "CLAIM local=%r bind=%r found=%s",
    AsyncSessionLocal, getattr(db, "bind", None), task is not None
)

# Line 95-97: Redundant imports INSIDE function body (after closing previous session)
from sqlalchemy import select
from app.db import AsyncTask
# These are already imported at line 11-12
```

**Impact:** Log spam obscures real issues. With default 1s polling: 1,440 WARNING logs/hour per worker for zero useful information. The redundant imports are dead code maintenance burden.

**Suggested fix:**
```python
# Lines 86-91: Delete entirely (or reduce to logger.debug if actively debugging)
# Lines 95-97: Delete (already imported above)
```

**Effort:** Small (2-line edit).

---

## Low Priority — Configuration / Hygiene

### L-1: `llm.py` — Retry without jitter

**Source line:** llm.py:84
```python
await asyncio.sleep(2**attempt)  # Pure exponential backoff, no jitter
```

**Impact:** Under concurrent request failures (e.g., rate limit from upstream), all N requests retry simultaneously after the same delay → thundering herd.

**Suggested fix:**
```python
import random
await asyncio.sleep(2**attempt + random.uniform(0, 1))
```

**Effort:** Small.

---

### L-2: `llm.py` — `generate()` and `chat_stream()` lack retry

**Source lines:** 40–60 (generate), 88–107 (chat_stream)

```python
# generate (40-60): Had NO retry loop. Any transient 502 = hard failure.
# FIXED: Added max_retries=2 with exponential backoff + jitter (lines 65-76).

# chat_stream (88-107): Had NO retry. Stream dead = user sees error.
# FIXED: Added max_retries=1. Stream creation stage retries; mid-stream failures
#         re-raise since partial tokens cannot be replayed (lines 98-108).
```

**Contrast with `chat()` (62-86) which has `max_retries=3`.**

**Impact fixed:** `generate()` now retries 2 times on transient failures. `chat_stream()` retries once during stream creation. Mid-stream failures still surface to user (correct: SSE cannot be rewound).

**Done:** 2026-08-29 — ruff ✅, 383 tests ✅.

---

### L-3: `database.py` — Default pool size without tuning

**Source line:** database.py:28
```python
engine = create_async_engine(settings.database_url, echo=settings.debug)
# No pool_size, max_overflow, pool_timeout, pool_recycle
```

**SQLAlchemy defaults:** pool_size=5, max_overflow=10.

**Impact:** With 5 concurrent embedding requests (each opens a session + transaction), pgBouncer isn't used. Database handles at most 5 active connections. Under load: `PoolExhausted` + 30s pool_timeout → request hangs then 500.

**Suggested fix (env-configurable):**
```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "20")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "3600")),
)
```

**Effort:** Small.

---

## Infrastructure — Docker 镜像合并

### INFRA-1: 合并 frontend + backend 为单个 Docker 镜像

**动机：** 当前部署需要 2 个应用镜像（`study-copilot-backend: 2.31GB` + `study-copilot-frontend: 93.8MB`），管理维护 2 套镜像标签/构建流程。且多阶段构建后代码安装在 site-packages 而非 `/app/app/`，导致路径相关的隐性问题（如 `alembic.ini` 解析）。

**目标：** 1 个应用镜像 + 1 个数据库镜像 = 2 容器，`docker compose up` 一键启动。

**方案：**
- 构建阶段：分别构建前端静态文件（Vite build）和安装 Python 依赖，两个输出合并进最终镜像
- 运行阶段：
  - nginx 作为唯一对外入口（端口 80）
  - nginx serve 前端静态文件（`/usr/share/nginx/html/`）
  - nginx 反向代理 `/api/*` → `http://127.0.0.1:8000/`（本地 uvicorn）
  - supervisord 或 entrypoint script 管理 nginx + uvicorn 双进程
- 删除独立的 `frontend/Dockerfile`
- docker-compose.yml 从 3 服务（db/backend/frontend）简化为 2 服务（db/app）

**影响文件：**
- `backend/Dockerfile` — 合并构建逻辑，新增 nginx 配置层
- `docker-compose.yml` — 移除 frontend 服务，合并为 app 服务
- `frontend/nginx.conf` — 合并后仍被使用，确认反向代理配置正确
- `Makefile` — 更新 build/up 目标

**预期收益：**
- 镜像数量从 2 → 1（依赖的 base image 仍为 4 个）
- 部署管理简化，`docker compose up -d` 后只需访问一个端口
- 移除 site-packages 路径问题（代码直接 COPY 到 `/app/`，不再经过 pip install）

**Effort:** Medium（Dockerfile 重构 + 验证）。

---

## Verified Correct (no action needed)

| Item | Source Verification |
|------|-------------------|
| FAISS hybrid search normalization | `vector_store.py:435-448` — batch-relative normalization with comment documenting the bug fix (2026-08-27) |
| RRF fusion weights | `vector_store.py:383-384` — explicit `faiss_weight`/`bm25_weight` params, currently 0.5/0.5 |
| PDF parser uses thread pool | `document_parser.py:314-316` — correct `run_in_executor` pattern |
| Text parser uses thread pool | `document_parser.py:577` — correct `asyncio.to_thread` |
| JWT/ENCRYPTION empty default + fail-fast | `config.py:20,40` + `main.py:30-45` — empty defaults, startup validation raises in production |
| DB init uses `create_all` on startup | `database.py:242-250` — correct `ensure_current_schema()` |
| LLM `chat()` retries | `llm.py:69-85` — `max_retries=3` with `2**attempt` exponential backoff |
| `openai_api_key` + `database_url` defaults | `config.py:8,26` — both now empty strings; `main.py:37-48` validates in prod |
| `alembic.ini` url | `alembic.ini:93` — `${DATABASE_URL}` env var ref; `env.py` overrides from app settings |
| `_rewrite_query` in corrective path only | `rag_engine.py:164` — not called on every QA, only in `_corrective_retrieve` |
| Adaptive retriever strategy one-time | `rag_engine.py:509` — `select_strategy` once per question |
| Corrective retrieval in ask path | `rag_engine.py:517-527` — only when retrieval quality is poor |
| CamelCase SQLAlchemy migration | `database.py:1-7` — full `Mapped[]/mapped_column` type-safe style, 2026-08-27 |
| Encrypted credential storage | `database.py:123` + `config_service.py:29-30,66-70` — Fernet encrypt/decrypt |
| Masked API key return | `config_service.py:35` — `api_key_masked`, never plaintext |
| `/health` endpoint | `main.py:128-148` — liveness + DB ping |

### Frontend — Done (2026-08-29)

| Item | Files Changed | Verification |
|------|--------------|-------------|
| F-H2: Double filter() in ChatView | `ChatView.vue` — use `documentStore.readyDocuments`; `stores/document.ts` — added `readyDocuments`, `hasDocuments`, SWR cache (30s) | vue-tsc ✅, 59 tests ✅ |
| F-M1: Duplicate streamingContent/streamingSources | `stores/chat.ts` — removed 2 redundant refs; SSE handler now only writes to temp message item | vue-tsc ✅, 59 tests ✅ |
| F-M4: Hardcoded gray colors (ChatView + AnalysisView) | `ChatView.vue` — 6 `gray-*` → CSS vars; `AnalysisView.vue` — 3 `gray-*` → CSS vars | vue-tsc ✅ |

---

## Frontend — Verified Findings (2026-08-29 source review)

> Files read: ChatView.vue, stores/chat.ts, stores/document.ts, stores/course.ts,
> stores/quiz.ts, services/api.ts, composables/useMarkdown.ts, AppSidebar.vue,
> App.vue, CourseCard.vue, QuizView.vue, NotesView.vue, NoteEditor.vue

### F-H1: SSE stream re-renders entire message list per token

**Source:** `stores/chat.ts:271-280` (BEFORE fix), `ChatView.vue:132`
```typescript
// BEFORE:每条 token 触发 messages 数组局部 patch，Vue 重新 diff 所有消息模板
// 对 v-html="renderMarkdown(msg.content)" 造成全量 markdown 重解析
```

**Impact:** 100-token response × N messages = N×100 markdown parses. ~1s wasted CPU during streaming.

**Fix status: ✅ DONE (2026-08-29).** Added markdown render cache (`_mdCache` Map) + streaming bypass:
- Completed messages (`!isStreaming`): rendered once, cached by content string
- Streaming messages (`isStreaming`): rendered as plain text with `<br>` line breaks — no markdown parsing overhead during token streaming
- Cache is unbounded but entries are proportional to message count (not token count), so memory impact is minimal

**Effort when tackled:** Medium (debounce markdown render + memoize per-message).

---

### F-H2: Double `filter()` in ChatView template

**Source:** `ChatView.vue:63` and `ChatView.vue:76` (BEFORE fix)
```html
<!-- Line 63: computed per render pass -->
<label v-for="doc in documentStore.documents.filter(d => d.status === 'ready')">
<!-- Line 76: same filter again, separate array creation -->
<span v-if="documentStore.documents.filter(d => d.status === 'ready').length === 0">
```

**Status: ✅ DONE (2026-08-29).** Added `readyDocuments`, `hasDocuments` computed getters to `stores/document.ts` + SWR cache (30s TTL). ChatView now uses `readyDocs`.

**Effort:** Small.

---

### F-M1: `streamingContent` / `streamingSources` duplicate state

**Source:** `stores/chat.ts:56-58` (BEFORE)
```typescript
const streamingContent = ref('')   // ← duplicates messages[messages.length-1].content
const streamingSources = ref<Source[]>([]) // ← duplicates messages[messages.length-1].sources
```

**Status: ✅ DONE (2026-08-29).** Removed both refs. SSE handler now only writes to temp message item. No synchronization hazard.

**Effort when done:** Small (~10 refs).

---

### F-M2: `api.ts` — No 429/503 retry handling

**Status: ✅ DONE (2026-08-29).** Added 429/503 retry with backoff in response interceptor:
- 429: respects `retry-after` header, defaults to 3s
- 503: retries after 2s
- Shares `_retry` flag with 401 retry (max one retry per request regardless of error type)

**Remaining (not done):** request dedup, GET abort cleanup, stale-while-revalidate (useDocumentStore SWR partially covers this).

**Effort when done:** Small for 429/503, Medium for dedup + abort cleanup.

---

### F-M3: `document.ts` — No getters, no caching

**Source:** `stores/document.ts:7-9`

```typescript
const documents = ref<Document[]>([] )
// No getters. Every consumer does inline O(N) filter/find.
```

**Impact:** ChatView, QuizView, AppSidebar each independently call `fetchDocuments()`. 5 components × 1 API call on mount = 5 requests for same data.

**Fix:** Add `readyDocuments`, `hasDocuments` computed getters. Add `lastFetched` timestamp + SWR logic (return cached if < 30s old).

**Effort:** Small–Medium.

---

### F-M4: Hardcoded gray colors bypass design tokens (dark mode breakage)

**Status: ✅ DONE (2026-08-29).** All 205 instances across 11 files replaced:
`text-gray-*` → `text-[var(--text-primary|secondary|muted)]`, `bg-gray-*` → `bg-[var(--bg-secondary|tertiary|active)]`, `border-gray-*` → `border-[var(--border-default)]`, `placeholder-gray-*` → `placeholder-[var(--text-muted)]`.

Files: ChatView, AnalysisView, DocumentView, UploadView, ModelConfigView, NoteEditor, CourseCard, NoteCard, TransformDialog, TTSPlayer, TaskPanel, BaseButton, BaseDialog, UrlImportDialog, CourseDetailView, global.css.

---

### F-M5: Inline SVG icons duplicated across views

**Source verified:**
- `AppSidebar.vue:75-140` — 6 icon render functions (home, upload, chat, quiz, analysis, model, document, course, notes)
- `ChatView.vue:19-21, 32, 42-44, 112-116` — user, AI, new-chat, export, history icons inline
- `CourseCard.vue`, `DocumentView.vue` — additional inline SVGs

**Fix:** Extract to `src/components/common/Icon*.vue` or use SVGO-optimized sprite.

**Effort:** Medium.

---

### Frontend Summary

| Priority | Items | Effort | Impact |
|----------|-------|--------|--------|
| ✅ Done | F-H1 SSE markdown cache, F-H2 double filter, F-M1 duplicate state, F-M4 all 205 gray instances | Small–Medium | Streaming perf, correctness, dark mode |
| ✅ Partial | F-M2 429/503 retry (done), dedup + abort cleanup (remaining) | Small + Medium | Resilience |
| 🟡 Partial | F-M3 document.ts SWR (done), other stores (remaining) | Small | Perf |
| Optional | F-M5 icon dedup | Medium | Bundle size |

**All High-priority frontend items resolved.** Remaining items are low-impact improvements.
