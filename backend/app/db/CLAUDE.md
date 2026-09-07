# Database Layer (`backend/app/db/`)

## Purpose

The database layer manages **PostgreSQL connections, ORM models, and migrations** using SQLAlchemy 2.0 in async mode.

## Module Reference

| File | Responsibility |
|------|---------------|
| `database.py` | Async engine, session factory, `Base` declarative class, all ORM models |
| `migrations.py` | Schema migration helpers (used by Alembic) |
| `__init__.py` | Re-exports for convenient imports |

## ORM Models (defined in `database.py`)

| Model | Table | Key Fields |
|-------|-------|------------|
| `User` | `users` | id, username, email, password_hash, is_active, created_at |
| `Document` | `documents` | id, user_id, course_space_id, filename, file_path, status, chunk_count, file_size, deleted_at (soft delete) |
| `ChatSession` | `chat_sessions` | id, user_id, title, created_at |
| `Message` | `messages` | id, session_id, role, content, sources, created_at |
| `Quiz` | `quizzes` | id, document_id (nullable, for course-wide quizzes), question_type, question, options, answer, explanation, created_at |
| `QuizResult` | `quiz_results` | id, quiz_id, user_id, user_answer, is_correct, submitted_at |
| `UserLLMConfig` | `user_llm_configs` | id, user_id, provider, api_key, base_url, model_name, temperature, max_tokens, embedding_model, embedding_dimension, created_at, updated_at |
| `CourseSpace` | `course_spaces` | id, user_id, name, description, color, created_at, updated_at |
| `Tag` | `tags` | id, user_id, name, created_at |
| `Note` | `notes` | id, user_id, course_space_id, title, content, note_type, is_pinned, deleted_at (soft delete), created_at, updated_at |
| `DocumentChunk` | `document_chunks` | id, document_id, content, **embedding (vector)**, chunk_metadata (JSON), chunk_index, created_at |
| `AsyncTask` | `async_tasks` | id, user_id, task_type, status, progress, result, error, created_at, completed_at |
| `note_tags` | `note_tags` | note_id, tag_id — association table |

## Session Management

```python
from app.db.database import get_db

# In API routes — use FastAPI dependency injection:
@router.get("/")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model))
    return result.scalars().all()
```

## Migrations (Alembic)

```bash
cd backend
alembic upgrade head          # Apply all pending migrations
alembic revision --autogenerate -m "description"  # Generate new migration
alembic downgrade -1          # Rollback one migration
```

Migration files live in `backend/alembic/versions/`.

## Design Decisions

- **Async everywhere**: Uses `asyncpg` driver with `create_async_engine()`
- **Single file for models**: All models in `database.py` for simplicity (could split later)
- **UUID primary keys**: All models use `uuid.uuid4` as default PK
- **Soft deletes (2026-08-24)**: documents.deleted_at / notes.deleted_at 标记回收站；DELETE 端点软删可恢复，物理清除走 purge_deleted_* 服务函数（运维脚本用）
- **Course-wide Quizzes (2026-09-05)**: `quizzes.document_id` nullable migration（`b9a8c7d6e5f4`），允许课程级大纲生成与 AI 互动课堂跨文档测验沉淀入库
