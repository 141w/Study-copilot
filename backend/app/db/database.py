from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    is_active = Column(Boolean, default=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    course_space_id = Column(
        String, ForeignKey("course_spaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="pending")
    chunk_count = Column(Integer, default=0)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    vectorstore_path = Column(String, nullable=True)
    # 软删除标记：NULL=正常；非空=回收站（文件与索引保留，可恢复）
    deleted_at = Column(DateTime, nullable=True, index=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    question_type = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    options = Column(Text, nullable=True)
    answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(String, primary_key=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    submitted_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))


class UserLLMConfig(Base):
    __tablename__ = "user_llm_configs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    provider = Column(String, default="openrouter")
    api_key = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    model_name = Column(String, default="gpt-4o-mini")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    embedding_model = Column(String, default="shibing624/text2vec-base-chinese")
    embedding_dimension = Column(Integer, default=768)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


# ── Note system & Course Space models ───────────────────────────────────

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class CourseSpace(Base):
    """A course space groups notes, documents, and chat sessions for a specific course."""

    __tablename__ = "course_spaces"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True, default="#6366f1")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    # relationships
    notes = relationship("Note", back_populates="course_space", cascade="all, delete-orphan")


class Tag(Base):
    """Reusable tag for categorizing notes."""

    __tablename__ = "tags"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    # relationships
    notes = relationship("Note", secondary=note_tags, back_populates="tags")


class Note(Base):
    """A note belonging to a user, optionally linked to a course space and tagged."""

    __tablename__ = "notes"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_space_id = Column(String, ForeignKey("course_spaces.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False, default="")
    note_type = Column(String, default="markdown")  # markdown / plain
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    # 软删除标记：NULL=正常；非空=回收站（可恢复）
    deleted_at = Column(DateTime, nullable=True, index=True)

    # relationships
    course_space = relationship("CourseSpace", back_populates="notes")
    tags = relationship("Tag", secondary=note_tags, back_populates="notes")


class AsyncTask(Base):
    """Tracks long-running background tasks (document processing, quiz generation, etc.)."""

    __tablename__ = "async_tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    task_type = Column(String, nullable=False)  # e.g., "document_process", "quiz_generate"
    status = Column(String, default="pending")  # pending / running / completed / failed / cancelled
    progress = Column(Float, default=0.0)  # 0.0 ~ 1.0
    result = Column(Text, nullable=True)  # JSON-encoded result data
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    completed_at = Column(DateTime, nullable=True)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_current_schema() -> None:
    """Create any missing tables from ORM models (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
