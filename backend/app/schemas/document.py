import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    category: str
    status: str
    original_filename: str
    chunk_count: int
    doc_number: str | None
    publisher: str | None
    effective_date: date | None
    effective_status: str | None
    quality_score: float | None
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int
