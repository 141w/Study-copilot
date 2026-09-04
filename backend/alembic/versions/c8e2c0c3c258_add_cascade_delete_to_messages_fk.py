"""add_cascade_delete_to_messages_fk

Revision ID: c8e2c0c3c258
Revises: dd66bcce6b38
Create Date: 2026-09-04 09:16:39.616909

Adds ON DELETE CASCADE to messages.session_id foreign key so that
deleting a chat session automatically removes its messages.
"""

from alembic import op

# revision identifiers
revision: str = "c8e2c0c3c258"
down_revision: str | None = "dd66bcce6b38"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint("messages_session_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key(
        "messages_session_id_fkey",
        "messages", "chat_sessions",
        ["session_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("messages_session_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key(
        "messages_session_id_fkey",
        "messages", "chat_sessions",
        ["session_id"], ["id"],
    )
