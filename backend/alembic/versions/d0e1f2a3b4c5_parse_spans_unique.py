"""F13: document_parse_spans (document_id, attempt, name) 唯一。

重解析递增 attempt 后，同一 attempt 内同名 stage 不得重复行。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_parse_spans_doc_attempt_name",
        "document_parse_spans",
        ["document_id", "attempt", "name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_parse_spans_doc_attempt_name", "document_parse_spans", type_="unique"
    )
