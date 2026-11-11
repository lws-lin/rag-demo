from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User


def seed_admin() -> None:
    if len(settings.admin_password) < 8:
        raise RuntimeError("ADMIN_PASSWORD 至少 8 位")
    db: Session = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.username == settings.admin_username))
        if existing is not None:
            return
        db.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                display_name="系统管理员",
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()
