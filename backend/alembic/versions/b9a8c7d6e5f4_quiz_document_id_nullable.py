"""quiz_document_id_nullable

Revision ID: b9a8c7d6e5f4
Revises: c8e2c0c3c258
Create Date: 2026-09-05

Opens quizzes.document_id to NULL: AI classroom-imported quizzes
have no associated document. The NOT NULL constraint made
classroom_service.sync_quiz_results fail with IntegrityError on
PostgreSQL (SQLite test runs don't enforce FKs, masking the bug).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9a8c7d6e5f4"
down_revision: str | None = "c8e2c0c3c258"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "quizzes",
        "document_id",
        existing_type=None,
        nullable=True,
    )


def downgrade() -> None:
    # Back to NOT NULL: classroom quizzes without a document must be
    # removed first (or reassigned) before downgrading.
    op.alter_column(
        "quizzes",
        "document_id",
        existing_type=None,
        nullable=False,
    )
