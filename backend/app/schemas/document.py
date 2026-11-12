import uuid
from datetime import date, datetime
from typing import Literal

from app.statuses import DocumentStatus

from pydantic import BaseModel, ConfigDict, Field


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
    access_roles: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class SourceSpan(BaseModel):
    start: int
    end: int


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ordinal: int
    content: str
    page_number: int | None
    page_end: int | None = None
    heading_path: list[str] | None = None
    block_kind: str | None = None
    quality_flags: list[str] | None = None
    char_count: int
    source_spans: list[SourceSpan] | None = None
    extraction_method: str | None = None
    language: str | None = None
    ocr_confidence: float | None = None
    regions: list[dict] | None = None
    parent_id: uuid.UUID | None = None
    previous_id: uuid.UUID | None = None
    next_id: uuid.UUID | None = None


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int | None
    content: str
    extraction_method: str | None = None
    language: str | None = None
    ocr_confidence: float | None = None
    regions: list[dict] | None = None


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut]
    pages: list[PageOut]


class DocumentReview(BaseModel):
    doc_number: str = Field(default="", max_length=128)
    publisher: str = Field(default="", max_length=128)
    effective_date: date | None = None
    effective_status: Literal["current", "abolished", "draft"] | None = None
    decision: DocumentStatus
    reject_reason: str = Field(default="", max_length=2000)
    access_roles: list[str] = Field(default_factory=list)
