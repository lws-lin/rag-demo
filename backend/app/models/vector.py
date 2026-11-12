import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base
from app.statuses import DocumentStatus


class ChunkVector(Base):
    """一个片段一条向量。只保留已发布文档，元数据用于之后按权限过滤。"""

    __tablename__ = "chunk_vectors"
    __table_args__ = (
        CheckConstraint(f"status = '{DocumentStatus.published.value}'", name="ck_chunk_vectors_status"),
        CheckConstraint(
            "effective_status is null or effective_status in ('current', 'abolished', 'draft')",
            name="ck_chunk_vectors_effective_status",
        ),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    status: Mapped[str] = mapped_column(String(32))
    effective_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    access_roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list, server_default="{}")
