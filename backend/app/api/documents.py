import math
import mimetypes
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, like_pattern, require_writer
from app.config import settings
from app.database import get_db
from app.models import Document, User
from app.schemas.document import DocumentList, DocumentOut
from app.services.ingest import ingest_path, safe_filename
from app.services.text import ALLOWED_SUFFIXES, CATEGORIES

router = APIRouter()
STATUSES = {"pending", "parsing", "review", "published", "rejected", "offline"}


@router.get("", response_model=DocumentList)
def list_documents(
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DocumentList:
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="分类只能是 design、regulation 或 other")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail="状态不在允许范围内")
    filters = []
    if category:
        filters.append(Document.category == category)
    if status:
        filters.append(Document.status == status)
    keyword = (q or "").strip()
    if keyword:
        filters.append(Document.title.ilike(like_pattern(keyword), escape="\\"))
    total = db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    page_count = max(1, math.ceil(total / page_size)) if total else 1
    current = min(page, page_count)
    stmt = select(Document).where(*filters).order_by(Document.updated_at.desc())
    stmt = stmt.offset((current - 1) * page_size).limit(page_size)
    return DocumentList(
        items=list(db.scalars(stmt).all()),
        total=total,
        page=current,
        page_size=page_size,
    )


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_writer),
) -> Document:
    filename = safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail="只接受 txt、md、pdf、docx")
    if category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="分类只能是 design、regulation 或 other")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            temp_path = Path(handle.name)
            total = 0
            while True:
                block = await file.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="文件超过 20MB")
                handle.write(block)
        if total == 0:
            raise HTTPException(status_code=422, detail="文件是空的")
        try:
            result = ingest_path(
                db,
                temp_path,
                category=category,
                original_filename=filename,
                content_type=file.content_type or mimetypes.guess_type(filename)[0],
                created_by=user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if result.action == "skipped":
        raise HTTPException(status_code=409, detail="相同内容已经在库里")
    return result.document
