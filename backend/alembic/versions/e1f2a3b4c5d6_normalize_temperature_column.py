"""normalize temperature column from multiplied integer (7) to actual decimal (0.7)

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-08-30

The backend stored temperature * 10 in the DB (e.g. 0.7 → 7.0) with
×10 on write and /10 on read. This convention added cognitive load and
risked double-conversion in new code paths.

This migration backfills existing rows (divided by 10), after which the
code no longer multiplies or divides — the column stores actual values.
"""

from alembic import op

# revision identifiers
revision: str = "e1f2a3b4c5d6"
down_revision: str = "d9e0f1a2b3c4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Backfill: divide existing multiplied temperatures by 10."""
    # Only rows where temperature > 1 are the old multiplied form; actual decimals (< 1) are correct.
    op.execute(
        "UPDATE user_llm_configs SET temperature = temperature / 10.0 WHERE temperature > 1"
    )


def downgrade() -> None:
    """Restore multiplied form (only if rows were backfilled)."""
    op.execute(
        "UPDATE user_llm_configs SET temperature = temperature * 10 WHERE temperature < 1"
    )
