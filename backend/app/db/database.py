"""SQLAlchemy 2.0 typed ORM models + async engine/session factory.

2026-08-27: 全部模型从旧式 ``Column`` 声明迁移到 ``Mapped[]/mapped_column``
类型化风格。纯类型层重构，DDL（列类型/可空性/索引/外键行为）逐字段保持不变；
静态检查从此能直接使用真实字段类型（此前 service/api 层大量
Column[str] vs str 误报由此根除）。

2026-08-29: 连接池参数环境变量化，默认值与 SQLAlchemy 内置默认一致（向后兼容）。
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "3600")),
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base (SQLAlchemy 2.0 风格，含类型注解映射)。"""


def _utcnow_naive() -> datetime:
    """统一的时间默认值：UTC 当前时刻（去 tzinfo，与既有 NOT NULL 列语义一致）。"""
    return datetime.now(UTC).replace(tzinfo=None)

class _Vector(TypeDecorator):
    """pgvector 兼容类型：PostgreSQL 渲染为 vector(N)，SQLite 回退为 JSON 存储。"""

    impl = String
    cache_ok = True

    def __init__(self, dimension: int = 768):
        super().__init__()
        self.dimension = dimension

    def get_col_spec(self, **kw: Any) -> str:
        if kw.get("dialect") and kw["dialect"].name == "postgresql":
            return f"vector({self.dimension})"
        return "TEXT"

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """Convert Python list to the DB representation."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            # asyncpg/pgvector expects a string like "[0.1,0.2,...]"
            if isinstance(value, list):
                return "[" + ",".join(str(v) for v in value) + "]"
            return value
        import json as _json
        return _json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Convert DB value back to Python list."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        import json as _json
        return _json.loads(value)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    course_space_id: Mapped[str | None] = mapped_column(
        ForeignKey("course_spaces.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    vectorstore_path: Mapped[str | None] = mapped_column(String)
    # 软删除标记：NULL=正常；非空=回收站（文件与索引保留，可恢复）
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[str | None] = mapped_column(Text)
    # 语义搜索索引：用户消息写入时计算 embedding，支持历史对话向量检索
    embedding: Mapped[list[float] | None] = mapped_column(_Vector(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 批次9修复：课堂来源测验（OpenMAIC 导入）无关联文档，原 NOT NULL 会让
    # sync_quiz_results 的 INSERT 直接 IntegrityError（测试 SQLite 不强制
    # FK 掩盖了该缺陷，生产 PostgreSQL 必炸）。analysis_service 已按
    # `r.document_id or ""` 防御空值，放开可空不影响既有查询
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    question_type: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    user_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)


class UserLLMConfig(Base):
    __tablename__ = "user_llm_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String, default="openrouter")
    api_key: Mapped[str | None] = mapped_column(String)
    base_url: Mapped[str | None] = mapped_column(String)
    model_name: Mapped[str] = mapped_column(String, default="gpt-4o-mini")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    context_window: Mapped[int] = mapped_column(Integer, default=262144)
    embedding_model: Mapped[str] = mapped_column(
        String, default="shibing624/text2vec-base-chinese"
    )
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=768)
    message_format: Mapped[str] = mapped_column(
        String, default="openai"
    )  # openai | anthropic | gemini | ollama
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        onupdate=_utcnow_naive,
    )


# ── Note system & Course Space models ───────────────────────────────────

note_tags = Table(
    "note_tags",
    Base.metadata,
    # 关联表为非映射对象，沿用传统 Column 声明
    Column("note_id", String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class CourseSpace(Base):
    """A course space groups notes, documents, and chat sessions for a specific course."""

    __tablename__ = "course_spaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String, default="#6366f1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        onupdate=_utcnow_naive,
    )

    # relationships
    notes: Mapped[list["Note"]] = relationship(
        back_populates="course_space", cascade="all, delete-orphan"
    )


class Tag(Base):
    """Reusable tag for categorizing notes."""

    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)

    # relationships
    notes: Mapped[list["Note"]] = relationship(
        secondary=note_tags, back_populates="tags"
    )


class Note(Base):
    """A note belonging to a user, optionally linked to a course space and tagged."""

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    course_space_id: Mapped[str | None] = mapped_column(
        ForeignKey("course_spaces.id"), index=True
    )
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text, default="")
    note_type: Mapped[str] = mapped_column(String, default="markdown")  # markdown / plain
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        onupdate=_utcnow_naive,
    )
    # 软删除标记：NULL=正常；非空=回收站（可恢复）
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    # relationships
    course_space: Mapped["CourseSpace | None"] = relationship(back_populates="notes")
    tags: Mapped[list["Tag"]] = relationship(secondary=note_tags, back_populates="notes")


class AsyncTask(Base):
    """Tracks long-running background tasks (document processing, quiz generation, etc.)."""

    __tablename__ = "async_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String)  # e.g., "document_process", "quiz_generate"
    status: Mapped[str] = mapped_column(String, default="pending")  # pending / running / completed / failed / cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 ~ 1.0
    result: Mapped[str | None] = mapped_column(Text)  # JSON-encoded result data
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DocumentChunk(Base):
    """Text chunk with embedding for pgvector-based RAG retrieval.

    Replaces file-based FAISS + BM25 indices.  Each row stores one chunk's
    text, its dense embedding in the ``embedding`` vector column, and a JSON
    ``metadata`` bag for auxiliary info (source, page, chunking_method, etc.).
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(_Vector(), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)


class CustomPersona(Base):
    """User-defined custom discussion persona, persisted in DB and scoped per user."""

    __tablename__ = "custom_personas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(50), index=True)
    avatar: Mapped[str] = mapped_column(String(50), default="User")
    color: Mapped[str | None] = mapped_column(String(20), default="#6366f1")
    system_message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        onupdate=_utcnow_naive,
    )



async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_current_schema() -> None:
    """Create any missing tables from ORM models (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
