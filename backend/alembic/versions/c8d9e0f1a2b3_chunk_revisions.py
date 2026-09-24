"""chunk online edit: content_revision / index_status / last_editor_id + chunk_revisions

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-26

SQLite/PG dual-dialect: plain types + dialect-aware BOOLEAN server_default
(PG must use sa.text('false'/'true'), never 0/1).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    # PG BOOLEAN 默认值必须是 sa.text('false'/'true')，不能写 0/1
    false_default = sa.text("false") if is_pg else sa.text("0")
    true_default = sa.text("true") if is_pg else sa.text("1")

    with op.batch_alter_table("document_chunks") as batch:
        batch.add_column(
            sa.Column("content_revision", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch.add_column(
            sa.Column(
                "index_status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'ready'"),
            )
        )
        batch.add_column(sa.Column("last_editor_id", sa.String(), nullable=True))

    op.create_table(
        "chunk_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("chunk_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("editor_id", sa.String(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=true_default),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "revision", name="uq_chunk_revisions_chunk_revision"),
    )
    op.create_index("ix_chunk_revisions_chunk_id", "chunk_revisions", ["chunk_id"])
    # silence unused warning for false_default when no false-boolean col is added here
    _ = false_default


def downgrade() -> None:
    op.drop_index("ix_chunk_revisions_chunk_id", table_name="chunk_revisions")
    op.drop_table("chunk_revisions")
    with op.batch_alter_table("document_chunks") as batch:
        batch.drop_column("last_editor_id")
        batch.drop_column("index_status")
        batch.drop_column("content_revision")
