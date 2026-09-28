"""Phase-5.1 wiki pages (concept pages with [[slug]] links).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-28

SQLite/PG dual-dialect: plain types only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("page_type", sa.String(length=32), nullable=False, server_default=sa.text("'concept'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'published'")),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_wiki_pages_user_slug"),
    )
    op.create_index("ix_wiki_pages_user_id", "wiki_pages", ["user_id"])
    op.create_index("ix_wiki_pages_slug", "wiki_pages", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_wiki_pages_slug", table_name="wiki_pages")
    op.drop_index("ix_wiki_pages_user_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
