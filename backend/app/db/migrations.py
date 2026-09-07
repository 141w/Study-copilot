"""
Alembic migration utilities for running migrations programmatically.
"""

import asyncio
import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from alembic import command
from app.db.database import engine

logger = logging.getLogger(__name__)

# Path to the alembic.ini file (backend/alembic.ini)
# 修复（2026-08-19）：旧路径少了一级 parent，解析到 backend/app/alembic.ini（不存在），
# 导致 alembic Config 读不到 script_location，应用启动即崩
# 修复（2026-08-30）：Docker 部署时代码安装在 site-packages，同时支持多路径搜索
_CANDIDATES = [
    Path(__file__).parent.parent.parent / "alembic.ini",  # 源码树: /app/alembic.ini
    Path("/app/alembic.ini"),  # Docker 容器固定路径
    Path(__file__).parent.parent.parent.parent / "alembic.ini",  # site-packages 上级
]

for _candidate in _CANDIDATES:
    if _candidate.exists() and _candidate.is_file():
        ALEMBIC_CFG_PATH = _candidate
        break
else:
    # Fallback: use first candidate (best-effort)
    ALEMBIC_CFG_PATH = _CANDIDATES[0]


def get_alembic_config() -> Config:
    """Get Alembic configuration, overriding URL from app settings."""
    from app.config import settings

    cfg = Config(str(ALEMBIC_CFG_PATH))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


async def run_migrations() -> None:
    """
    Run all pending Alembic migrations.
    Designed to be called on application startup.
    """
    cfg = get_alembic_config()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations_sync, cfg)


def _run_migrations_sync(cfg: Config) -> None:
    try:
        logger.info("Running database migrations...")
        command.upgrade(cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def get_current_revision() -> str | None:
    """Get the current database revision. Returns None on fresh DB (no alembic_version table)."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            return row[0] if row else None
    except Exception:
        return None


async def get_pending_migrations() -> list[str]:
    """Get list of pending migration revisions."""
    cfg = get_alembic_config()
    script_dir = ScriptDirectory.from_config(cfg)
    current_rev = await get_current_revision()

    revisions = []
    for revision in script_dir.walk_revisions():
        if revision.revision == current_rev:
            break
        revisions.append(revision.revision)

    return revisions


async def stamp_head() -> None:
    """Stamp the database with the head revision without running migrations.
    Useful when tables already exist and you want to mark them as current.
    """
    cfg = get_alembic_config()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, command.stamp, cfg, "head")
    logger.info("Database stamped with head revision.")
