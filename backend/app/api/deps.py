import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import Conversation, User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    subject = payload.get("sub")
    try:
        user_id = uuid.UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


def require_writer(user: User = Depends(get_current_user)) -> User:
    if user.role == "auditor":
        raise HTTPException(status_code=403, detail="当前角色只能查看")
    return user


def get_visible_conversation(
    conversation_id: uuid.UUID,
    db: Session,
    user: User,
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user.role == "user" and conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
