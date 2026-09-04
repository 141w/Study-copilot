"""add_embedding_column_to_messages

Revision ID: dd66bcce6b38
Revises: a2b3c4d5e6f7
Create Date: 2026-09-03 21:44:02.936891

Adds an embedding column to messages for semantic search of chat history.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "dd66bcce6b38"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE messages
        ADD COLUMN embedding vector(768)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE messages
        DROP COLUMN embedding
    """)
