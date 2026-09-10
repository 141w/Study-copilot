"""add_long_term_memory

Revision ID: fa1b2c3d4e5f
Revises: e8f9a0b1c2d3
Create Date: 2026-09-08

Adds memory_items and memory_subjects tables for five-category long-term memory.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fa1b2c3d4e5f"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "memory_subjects",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("block_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("last_extracted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "memory_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("origin", sa.String(length=30), nullable=False, server_default="explicit"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_items_user_id", "memory_items", ["user_id"])
    op.create_index("ix_memory_items_kind", "memory_items", ["kind"])
    op.create_index("ix_memory_items_status", "memory_items", ["status"])
    op.create_index("ix_memory_items_key", "memory_items", ["key"])


def downgrade() -> None:
    op.drop_index("ix_memory_items_key", table_name="memory_items")
    op.drop_index("ix_memory_items_status", table_name="memory_items")
    op.drop_index("ix_memory_items_kind", table_name="memory_items")
    op.drop_index("ix_memory_items_user_id", table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_table("memory_subjects")
