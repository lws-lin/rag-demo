"""chunk and page provenance

Revision ID: 0008_chunk_provenance
Revises: 0007_chunk_context
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_chunk_provenance"
down_revision: Union[str, Sequence[str], None] = "0007_chunk_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_pages", sa.Column("extraction_method", sa.String(length=32), nullable=True))
    op.add_column("document_pages", sa.Column("language", sa.String(length=16), nullable=True))
    op.add_column("document_pages", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("document_pages", sa.Column("blocks", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("document_pages", sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("document_chunks", sa.Column("extraction_method", sa.String(length=32), nullable=True))
    op.add_column("document_chunks", sa.Column("language", sa.String(length=16), nullable=True))
    op.add_column("document_chunks", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("document_chunks", sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("document_chunks", sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("document_chunks", sa.Column("previous_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("document_chunks", sa.Column("next_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_document_chunks_parent",
        "document_chunks",
        "document_chunks",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_document_chunks_previous",
        "document_chunks",
        "document_chunks",
        ["previous_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_document_chunks_next",
        "document_chunks",
        "document_chunks",
        ["next_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_document_chunks_next", "document_chunks", type_="foreignkey")
    op.drop_constraint("fk_document_chunks_previous", "document_chunks", type_="foreignkey")
    op.drop_constraint("fk_document_chunks_parent", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "next_id")
    op.drop_column("document_chunks", "previous_id")
    op.drop_column("document_chunks", "parent_id")
    op.drop_column("document_chunks", "regions")
    op.drop_column("document_chunks", "ocr_confidence")
    op.drop_column("document_chunks", "language")
    op.drop_column("document_chunks", "extraction_method")
    op.drop_column("document_pages", "regions")
    op.drop_column("document_pages", "blocks")
    op.drop_column("document_pages", "ocr_confidence")
    op.drop_column("document_pages", "language")
    op.drop_column("document_pages", "extraction_method")
