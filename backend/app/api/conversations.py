import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_visible_conversation, require_writer
from app.database import get_db, utcnow
from app.models import Conversation, Message, User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
    TurnOut,
)

router = APIRouter()

PLACEHOLDER = "这条消息已保存。查文档还是出方案会在对话里判断；检索和方案生成接入后，再按这个判断作答。"


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    stmt = select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)
    if user.role == "user":
        stmt = stmt.where(Conversation.user_id == user.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
) -> Conversation:
    title = payload.title.strip() or "新对话"
    conversation = Conversation(user_id=user.id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
) -> None:
    conversation = get_visible_conversation(conversation_id, db, user)
    db.delete(conversation)
    db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Message]:
    get_visible_conversation(conversation_id, db, user)
    stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    return list(db.scalars(stmt).all())


@router.post("/{conversation_id}/messages", response_model=TurnOut, status_code=201)
def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
) -> TurnOut:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息不能为空")
    conversation = get_visible_conversation(conversation_id, db, user)
    now = utcnow()
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        citations=[],
        created_at=now,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=PLACEHOLDER,
        citations=[],
        created_at=now + timedelta(milliseconds=1),
    )
    conversation.updated_at = now
    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return TurnOut(user_message=user_message, assistant_message=assistant_message)
