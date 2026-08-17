from app.db.database import (
    AsyncSessionLocal,
    AsyncTask,
    Base,
    ChatSession,
    CourseSpace,
    Document,
    Message,
    Note,
    Quiz,
    QuizResult,
    Tag,
    User,
    UserLLMConfig,
    engine,
    get_db,
    init_db,
    note_tags,
)
from app.db.migrations import get_current_revision, run_migrations, stamp_head
from app.db.database import ensure_current_schema
