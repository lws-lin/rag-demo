#!/bin/sh
set -eu

python - <<'PY'
import time

from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)
last_error: Exception | None = None
for _ in range(30):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        break
    except Exception as exc:
        last_error = exc
        time.sleep(1)
else:
    raise SystemExit(f"数据库未就绪: {last_error}")
PY

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
