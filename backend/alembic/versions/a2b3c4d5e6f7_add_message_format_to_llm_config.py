"""add message_format column to user_llm_configs table

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-31

Adds a message_format column to support multi-provider message formats
(openai, anthropic, gemini, ollama), allowing the frontend and backend
to normalize message structures per-provider before API calls.
"""

from alembic import op

# revision identifiers
revision: str = "a2b3c4d5e6f7"
down_revision: str = "f1a2b3c4d5e6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_llm_configs
        ADD COLUMN message_format VARCHAR(32) NOT NULL DEFAULT 'openai'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_llm_configs
        DROP COLUMN message_format
    """)
