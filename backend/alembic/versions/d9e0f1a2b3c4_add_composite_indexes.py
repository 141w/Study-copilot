"""add composite indexes for common filter+sort patterns

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-08-29

These indexes replace sequential scan + heap fetch with index-only scans
for the most common query patterns:
  WHERE user_id=X AND deleted_at IS NULL ORDER BY created_at DESC
  WHERE quiz_id=X ORDER BY submitted_at DESC
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str = "c7d8e9f0a1b2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_user_deleted_created",
        "documents",
        ["user_id", "deleted_at", "created_at"],
    )
    op.create_index(
        "ix_notes_user_deleted_updated",
        "notes",
        ["user_id", "deleted_at", "updated_at"],
    )
    op.create_index(
        "ix_chat_sessions_user_created",
        "chat_sessions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_quiz_results_quiz_submitted",
        "quiz_results",
        ["quiz_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_results_quiz_submitted", table_name="quiz_results")
    op.drop_index("ix_chat_sessions_user_created", table_name="chat_sessions")
    op.drop_index("ix_notes_user_deleted_updated", table_name="notes")
    op.drop_index("ix_documents_user_deleted_created", table_name="documents")
