"""add_context_window_to_llm_config

Revision ID: c1d2e3f4a5b6
Revises: e8f9a0b1c2d3
Create Date: 2026-09-06

Adds context_window column to user_llm_configs table, defaulting to 256k (262144).
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_llm_configs
        ADD COLUMN IF NOT EXISTS context_window INTEGER NOT NULL DEFAULT 262144
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_llm_configs
        DROP COLUMN IF EXISTS context_window
    """)
