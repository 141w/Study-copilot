"""Add notes.embedding for pgvector semantic search (replaces FAISS file index).

Revision ID: b2c3d4e5f6a7
Revises: fa1b2c3d4e5f
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "fa1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        dim = 768
        try:
            from app.config import settings

            dim = int(settings.embedding_dimension or 768)
        except Exception:
            pass
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'notes' AND column_name = 'embedding'
                ) THEN
                    ALTER TABLE notes ADD COLUMN embedding vector({dim});
                ELSE
                    ALTER TABLE notes ALTER COLUMN embedding TYPE vector({dim}) USING embedding::vector({dim});
                END IF;
            END $$;
        """)
    else:
        # SQLite / test dialects: store JSON-encoded list
        op.add_column("notes", sa.Column("embedding", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("notes", "embedding")
