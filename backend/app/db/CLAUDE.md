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
| `User` | `users` | id, username, email, hashed_password, created_at |
| `Document` | `documents` | id, user_id (FK), filename, file_path, file_type, chunk_count, created_at |
| `ChatSession` | `chat_sessions` | id, user_id (FK), document_id (FK), title, created_at |
| `Message` | `messages` | id, session_id (FK), role, content, citations (JSON), created_at |
| `Quiz` | `quizzes` | id, user_id (FK), document_id (FK), questions (JSON), created_at |
| `QuizResult` | `quiz_results` | id, quiz_id (FK), user_id (FK), answers (JSON), score, created_at |
| `WrongQuestion` | `wrong_questions` | id, user_id (FK), question, correct_answer, user_answer, review_count, created_at |
| `UserLLMConfig` | `user_llm_configs` | id, user_id (FK), provider, model, base_url, api_key (encrypted), created_at |
| `CourseSpace` | `course_spaces` | id, user_id (FK), name, description, created_at |
| `Note` | `notes` | id, user_id (FK), course_id (FK nullable), title, content, note_type, embedding_id, created_at, updated_at |
| `Tag` | `tags` | id, name, user_id (FK) |
| `AsyncTask` | `async_tasks` | id, user_id (FK), task_type, status, result (JSON), error, created_at, completed_at |
| `note_tags` | `note_tags` | note_id (FK), tag_id (FK) — association table |

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
- **Soft deletes not implemented**: Hard deletes via cascade (documented tech debt)
