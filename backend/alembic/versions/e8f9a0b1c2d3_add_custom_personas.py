"""add_custom_personas

Revision ID: e8f9a0b1c2d3
Revises: b9a8c7d6e5f4
Create Date: 2026-09-06

Adds custom_personas table for user-defined multi-agent discussion personas.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: str | None = "b9a8c7d6e5f4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "custom_personas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("avatar", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("system_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_custom_personas_user_id"),
        "custom_personas",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_personas_role"),
        "custom_personas",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_custom_personas_role"), table_name="custom_personas")
    op.drop_index(op.f("ix_custom_personas_user_id"), table_name="custom_personas")
    op.drop_table("custom_personas")
