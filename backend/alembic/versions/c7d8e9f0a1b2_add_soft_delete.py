"""add soft delete (deleted_at) to documents and notes

Revision ID: c7d8e9f0a1b2
Revises: b3c4d5e6f7a8
Create Date: 2026-08-24
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])
    op.add_column(
        "notes",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notes_deleted_at", "notes", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_notes_deleted_at", table_name="notes")
    op.drop_column("notes", "deleted_at")
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
