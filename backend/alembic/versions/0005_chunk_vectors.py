"""chunk vectors

Revision ID: 0005_chunk_vectors
Revises: 0004_access_roles
Create Date: 2026-11-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005_chunk_vectors"
down_revision: Union[str, Sequence[str], None] = "0004_access_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE chunk_vectors (
            chunk_id uuid PRIMARY KEY REFERENCES document_chunks(id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            embedding vector(512) NOT NULL,
            status varchar(32) NOT NULL,
            effective_status varchar(32),
            access_roles varchar(32)[] NOT NULL DEFAULT '{}',
            CONSTRAINT ck_chunk_vectors_status CHECK (status = 'published'),
            CONSTRAINT ck_chunk_vectors_effective_status CHECK (
                effective_status IS NULL OR effective_status IN ('current', 'abolished', 'draft')
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_chunk_vectors_document_id ON chunk_vectors (document_id)")
    op.execute(
        "CREATE INDEX ix_chunk_vectors_embedding ON chunk_vectors USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunk_vectors")
    op.execute("DROP EXTENSION IF EXISTS vector")
