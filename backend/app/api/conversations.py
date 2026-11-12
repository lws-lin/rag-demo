import json
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_visible_conversation, require_writer
from app.database import SessionLocal, get_db, utcnow
from app.models import Conversation, Message, User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from app.services.answer import intent_of, prepare_sources
from app.services.llm import (
    ChatModelError,
    chat_configured,
    clip_history,
    compress_passage,
    compress_turns,
    conversation_messages,
    is_long_text,
    split_recent,
    stream_chat,
)
from app.services.vectors import VectorWriteError, search_published

router = APIRouter()


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


@router.post("/{conversation_id}/messages")
def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
) -> StreamingResponse:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息不能为空")
    if not chat_configured():
        raise HTTPException(status_code=502, detail="还没有配置对话模型。请在 .env 填写 CHAT_BASE_URL、CHAT_API_KEY 和 CHAT_MODEL，消息没有保存")
    conversation = get_visible_conversation(conversation_id, db, user)
    mode = intent_of(content)
    citations: list[dict] = []
    evidence = ""
    if mode != "chat":
        try:
            hits = search_published(db, content, role=user.role)
        except VectorWriteError as exc:
            raise HTTPException(status_code=502, detail="检索失败，消息没有保存") from exc
        evidence, citations = prepare_sources(hits)
    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        ).all()
    )
    stored_mode = mode if mode in {"qa", "proposal"} else conversation.mode
    title = content[:24] if conversation.title == "新对话" else conversation.title
    conversation_id = conversation.id
    summary, prior, history_truncated = _prepare_history(db, conversation, history)
    messages = conversation_messages(
        mode,
        prior,
        content,
        evidence,
        summary=summary,
        history_truncated=history_truncated,
    )

    def generate():
        parts: list[str] = []
        try:
            for piece in stream_chat(messages):
                parts.append(piece)
                yield _event({"type": "delta", "text": piece})
        except ChatModelError as exc:
            yield _event({"type": "error", "detail": f"{exc}，消息没有保存"})
            return
        reply = "".join(parts).strip()
        if not reply:
            yield _event({"type": "error", "detail": "对话模型没有返回内容，消息没有保存"})
            return
        try:
            turn = _save_turn(conversation_id, content, reply, citations, stored_mode, title)
        except Exception:
            yield _event({"type": "error", "detail": "回答已生成，但保存失败"})
            return
        yield _event({"type": "done", **turn})

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _prepare_history(db: Session, conversation: Conversation, history: list[Message]) -> tuple[str, list[tuple[str, str]], bool]:
    """过长的单条消息和放不下的早期对话压成摘要。页面仍读取原来的消息正文。"""
    try:
        prompt = [(message.role, _text_for_model(message)) for message in history]
        older, recent = split_recent(prompt)
        summary = _fold_summary(conversation, history[: len(older)], older) if older else ""
        if db.dirty:
            db.commit()
        return summary, recent, False
    except ChatModelError:
        db.rollback()
        clipped, truncated = clip_history([(message.role, message.content) for message in history])
        return "", clipped, truncated


def _text_for_model(message: Message) -> str:
    text = message.content.strip()
    if not is_long_text(text):
        return text
    if message.context_brief and message.context_brief.strip():
        return message.context_brief.strip()
    brief = compress_passage(message.role, text)
    message.context_brief = brief
    return brief


def _fold_summary(
    conversation: Conversation,
    older_messages: list[Message],
    older_turns: list[tuple[str, str]],
) -> str:
    previous = (conversation.context_summary or "").strip()
    start = 0
    if conversation.summary_until is not None:
        found = False
        for index, message in enumerate(older_messages):
            if message.id == conversation.summary_until:
                start = index + 1
                found = True
                break
        if not found:
            previous = ""
            start = 0
    else:
        previous = ""
    pending = older_turns[start:]
    if not pending:
        return previous
    summary = previous
    batch: list[tuple[str, str]] = []
    size = 0
    for item in pending:
        if batch and size + len(item[1]) > 8000:
            summary = compress_turns(summary, batch)
            batch = []
            size = 0
        batch.append(item)
        size += len(item[1])
    if batch:
        summary = compress_turns(summary, batch)
    conversation.context_summary = summary
    conversation.summary_until = older_messages[-1].id
    return summary


def _event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _save_turn(conversation_id: uuid.UUID, content: str, reply: str, citations: list[dict], mode: str | None, title: str) -> dict:
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("会话不存在")
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
            content=reply,
            citations=citations,
            created_at=now + timedelta(milliseconds=1),
        )
        conversation.mode = mode
        conversation.title = title
        conversation.updated_at = now
        db.add_all([user_message, assistant_message])
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return {
            "user_message": MessageOut.model_validate(user_message).model_dump(mode="json"),
            "assistant_message": MessageOut.model_validate(assistant_message).model_dump(mode="json"),
        }
    finally:
        db.close()
