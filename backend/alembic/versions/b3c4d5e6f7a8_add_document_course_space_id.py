"""add_document_course_space_id

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "documents",
        sa.Column("course_space_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_course_space_id",
        "documents",
        "course_spaces",
        ["course_space_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_documents_course_space_id"),
        "documents",
        ["course_space_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_documents_course_space_id"), table_name="documents")
    op.drop_constraint("fk_documents_course_space_id", "documents", type_="foreignkey")
    op.drop_column("documents", "course_space_id")
