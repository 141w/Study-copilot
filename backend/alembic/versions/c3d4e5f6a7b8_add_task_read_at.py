"""Add async_tasks.read_at for notification unread tracking.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("async_tasks", sa.Column("read_at", sa.DateTime(), nullable=True))
    op.create_index("ix_async_tasks_read_at", "async_tasks", ["read_at"])


def downgrade() -> None:
    op.drop_index("ix_async_tasks_read_at", table_name="async_tasks")
    op.drop_column("async_tasks", "read_at")
