"""chunk page range, heading path and quality flags

Revision ID: 0007_chunk_context
Revises: 0006_page_spans
Create Date: 2026-11-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_chunk_context"
down_revision: Union[str, Sequence[str], None] = "0006_page_spans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("heading_path", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("document_chunks", sa.Column("block_kind", sa.String(length=32), nullable=True))
    op.add_column("document_chunks", sa.Column("quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "quality_flags")
    op.drop_column("document_chunks", "block_kind")
    op.drop_column("document_chunks", "heading_path")
    op.drop_column("document_chunks", "page_end")
