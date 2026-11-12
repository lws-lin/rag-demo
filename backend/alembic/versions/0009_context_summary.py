"""conversation context summary

Revision ID: 0009_context_summary
Revises: 0008_chunk_provenance
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_context_summary"
down_revision: Union[str, Sequence[str], None] = "0008_chunk_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("context_summary", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("summary_until", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("messages", sa.Column("context_brief", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "context_brief")
    op.drop_column("conversations", "summary_until")
    op.drop_column("conversations", "context_summary")
