"""F17: chat_sessions 增加 updated_at（最后活动）与 is_pinned（置顶）。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3a4b5c6d7e8"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # 存量行回填 updated_at = created_at
    op.execute("UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_column("chat_sessions", "is_pinned")
    op.drop_column("chat_sessions", "updated_at")
