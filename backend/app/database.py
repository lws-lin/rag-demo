from datetime import datetime, timezone

from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _register_pgvector(dbapi_connection, _connection_record) -> None:
    register_vector(dbapi_connection)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
