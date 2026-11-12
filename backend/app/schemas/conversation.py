import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="", max_length=200)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    mode: str | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class CitationOut(BaseModel):
    document_id: uuid.UUID
    title: str
    filename: str
    page_number: int | None = None
    page_end: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    ordinal: int
    effective_status: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationOut] | None
    created_at: datetime


class TurnOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
