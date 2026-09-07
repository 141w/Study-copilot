# Services Layer (`backend/app/services/`)

## Purpose

The services layer acts as the **bridge between API routes and core business logic**. Each service encapsulates orchestration logic for a specific domain, keeping route handlers thin and core modules focused on single responsibilities.

## Pattern

```
API Route (app/api/*.py)
    ↓ receives HTTP request, validates input via Pydantic
Service (app/services/*.py)
    ↓ orchestrates calls to core modules, manages transactions
Core (app/core/*.py)
    ↓ pure business logic, no HTTP/DB concerns
```

### Responsibilities
- **Orchestrate** multiple core modules for a single use case
- **Manage** database sessions and transactions (commit/rollback)
- **Transform** between API schemas (Pydantic) and database models (ORM)
- **Handle** cross-cutting concerns (logging, error mapping)

### What Services Should NOT Do
- Direct HTTP response construction (that's the API layer)
- Raw SQL or vector operations (that's core/db)
- File I/O (that's utils)

## Existing Services

| File | Domain | Key Functions |
|------|--------|---------------|
| `auth_service.py` | Authentication | register, login, refresh_token |
| `document_service.py` | Document upload/parse | upload_document, delete_document, list_documents |
| `chat_service.py` | RAG Q&A | ask_question, stream_answer, get_history |
| `quiz_service.py` | Quiz generation | generate_quiz, submit_quiz, get_wrong_questions |
| `analysis_service.py` | Learning analytics | analyze_wrong_questions, get_knowledge_stats, get_progress |
| `config_service.py` | LLM configuration | get_config, update_config |
| `note_service.py` | Notes management | create_note, update_note, delete_note, search_notes, add_tags |
| `course_service.py` | Course spaces | create_course, update_course, list_courses, get_course_detail |
| `transform_service.py` | Content transformation | transform_content, get_transform_types |
| `task_service.py` | Async task queue | create_task, get_task_status, list_tasks, cancel_task |
| `classroom_service.py` | AI classroom engine bridge | build_classroom_request, submit_classroom_generation, poll_generation_status, sync_completed_classroom_job, handle_webhook_callback, sync_quiz_results |

## Adding a New Service

1. Create `backend/app/services/<name>_service.py`
2. Define async functions that accept a SQLAlchemy `AsyncSession` and domain parameters
3. Import and use core modules for business logic
4. Register the service in `__init__.py` if needed
5. Call from the corresponding API route via dependency injection
