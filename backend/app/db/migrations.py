"""
Alembic migration utilities for running migrations programmatically.
"""

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.database import engine

logger = logging.getLogger(__name__)

# Path to the alembic.ini file (relative to backend directory)
ALEMBIC_CFG_PATH = Path(__file__).parent.parent.parent / "alembic.ini"


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    alembic_cfg = Config(str(ALEMBIC_CFG_PATH))
    return alembic_cfg


async def run_migrations() -> None:
    """
    Run all pending Alembic migrations.
    This is designed to be called on application startup.
    """
    alembic_cfg = get_alembic_config()

    # Run migrations in a thread pool since alembic commands are synchronous
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations_sync, alembic_cfg)


def _run_migrations_sync(alembic_cfg: Config) -> None:
    """Synchronous migration runner (executed in thread pool)."""
    try:
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def get_current_revision() -> str | None:
    """Get the current database revision."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None


async def get_pending_migrations() -> list[str]:
    """Get list of pending migration revisions."""
    alembic_cfg = get_alembic_config()
    script_dir = ScriptDirectory.from_config(alembic_cfg)

    current_rev = await get_current_revision()

    # Get all revisions after current
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
    alembic_cfg = get_alembic_config()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, command.stamp, alembic_cfg, "head")
    logger.info("Database stamped with head revision.")
