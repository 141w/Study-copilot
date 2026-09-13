"""add token_usages

Revision ID: c3d4e5f6a7b8
Revises: c3d4e5f6a7b8
Create Date: 2026-09-13 14:21:36.605469

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="chat"),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="llm"),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="openai"),
        sa.Column("model_name", sa.String(length=100), nullable=False, server_default="unknown"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="token"),
        sa.Column("extra_meta", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_usages_user_id"), "token_usages", ["user_id"], unique=False)
    op.create_index(op.f("ix_token_usages_created_at"), "token_usages", ["created_at"], unique=False)
    op.create_index(op.f("ix_token_usages_source"), "token_usages", ["source"], unique=False)
    op.create_index(op.f("ix_token_usages_kind"), "token_usages", ["kind"], unique=False)
    op.create_index(op.f("ix_token_usages_model_name"), "token_usages", ["model_name"], unique=False)
    op.create_index(
        "ix_token_usages_user_created", "token_usages", ["user_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_token_usages_user_source", "token_usages", ["user_id", "source"], unique=False
    )


def downgrade() -> None:
    op.drop_table("token_usages")
