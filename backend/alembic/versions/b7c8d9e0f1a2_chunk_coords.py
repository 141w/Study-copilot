"""chunk coords + source_content + context_header + is_parent

Revision ID: b7c8d9e0f1a2
Revises: d4e5f6a7b8c9
Create Date: 2026-09-25

SQLite/PG dual-dialect: plain types + server_default only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BOOLEAN 默认值需按方言书写：PG 用 false，SQLite 用 0
    false_default = sa.text("false") if op.get_bind().dialect.name == "postgresql" else sa.text("0")
    with op.batch_alter_table("document_chunks") as batch:
        batch.add_column(sa.Column("source_content", sa.Text(), nullable=True))
        batch.add_column(sa.Column("char_start", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("char_end", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("context_header", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "is_parent",
                sa.Boolean(),
                nullable=False,
                server_default=false_default,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("document_chunks") as batch:
        batch.drop_column("is_parent")
        batch.drop_column("context_header")
        batch.drop_column("char_end")
        batch.drop_column("char_start")
        batch.drop_column("source_content")
