import math
import mimetypes
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, like_pattern, require_admin, require_writer
from app.config import settings
from app.database import get_db
from app.models import Document, DocumentChunk, DocumentPage, User
from app.schemas.document import ChunkOut, DocumentDetail, DocumentList, DocumentOut, DocumentReview
from app.services.ingest import ingest_path, safe_filename
from app.services.text import ALLOWED_SUFFIXES, CATEGORIES, FORMAT_MESSAGE
from app.services.vectors import VectorWriteError, sync_document_vectors
from app.statuses import REVIEW_DECISIONS, DocumentStatus

router = APIRouter()
ASSIGNABLE_ROLES = {"user"}


def visible_documents(user: User):
    if user.role == "admin":
        return None
    return or_(
        and_(Document.status == DocumentStatus.published.value, Document.access_roles.contains([user.role])),
        Document.created_by == user.id,
    )


def can_read_document(document: Document, user: User) -> bool:
    if user.role == "admin" or document.created_by == user.id:
        return True
    return document.status == DocumentStatus.published.value and user.role in (document.access_roles or [])


@router.get("", response_model=DocumentList)
def list_documents(
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentList:
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="分类只能是 design、regulation 或 other")
    if status is not None and status not in DocumentStatus:
        raise HTTPException(status_code=422, detail="状态不在允许范围内")
    filters = []
    if category:
        filters.append(Document.category == category)
    if status:
        filters.append(Document.status == status)
    keyword = (q or "").strip()
    if keyword:
        filters.append(Document.title.ilike(like_pattern(keyword), escape="\\"))
    visible = visible_documents(user)
    if visible is not None:
        filters.append(visible)
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


def document_detail(document: Document, db: Session) -> DocumentDetail:
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal)
        ).all()
    )
    pages = list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.ordinal)
        ).all()
    )
    body = DocumentOut.model_validate(document).model_dump()
    body["chunks"] = chunks
    body["pages"] = pages
    return DocumentDetail.model_validate(body)


@router.get("/{document_id}/file")
def read_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None or not can_read_document(document, user) or not document.storage_key:
        raise HTTPException(status_code=404, detail="找不到原文")
    library = settings.library_path.resolve()
    path = (library / document.storage_key).resolve()
    if path.parent != library or not path.is_file():
        raise HTTPException(status_code=404, detail="找不到原文")
    media = document.content_type or mimetypes.guess_type(document.original_filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, filename=document.original_filename, content_disposition_type="inline")


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentDetail:
    document = db.get(Document, document_id)
    if document is None or not can_read_document(document, user):
        raise HTTPException(status_code=404, detail="文档不存在")
    return document_detail(document, db)


@router.post("/{document_id}/review", response_model=DocumentDetail)
def review_document(
    document_id: uuid.UUID,
    payload: DocumentReview,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DocumentDetail:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if payload.decision not in REVIEW_DECISIONS:
        raise HTTPException(status_code=422, detail="复核只能是发布、拒绝或下线")
    if document.status == DocumentStatus.published.value and payload.decision != DocumentStatus.offline:
        raise HTTPException(status_code=422, detail="已发布的文档只能下线")
    if payload.decision == DocumentStatus.offline and document.status != DocumentStatus.published.value:
        raise HTTPException(status_code=422, detail="只有已发布的文档可以下线")
    reason = payload.reject_reason.strip()
    if payload.decision == DocumentStatus.rejected and not reason:
        raise HTTPException(status_code=422, detail="拒绝时要填写原因")
    roles: list[str] = []
    for role in payload.access_roles:
        if role not in ASSIGNABLE_ROLES:
            raise HTTPException(status_code=422, detail="可见角色只能是普通员工")
        if role not in roles:
            roles.append(role)
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal)
        ).all()
    )
    if payload.decision == DocumentStatus.published and not chunks:
        raise HTTPException(status_code=422, detail="没有片段，不能发布")
    try:
        sync_document_vectors(
            db,
            document,
            chunks,
            decision=payload.decision,
            roles=roles,
            effective_status=payload.effective_status,
        )
    except VectorWriteError:
        db.rollback()
        raise HTTPException(status_code=502, detail="向量写入失败，文档状态没有改变")
    document.access_roles = roles
    document.doc_number = payload.doc_number.strip() or None
    document.publisher = payload.publisher.strip() or None
    document.effective_date = payload.effective_date
    document.effective_status = payload.effective_status
    document.status = payload.decision.value
    document.reject_reason = reason if payload.decision == DocumentStatus.rejected else None
    db.commit()
    db.refresh(document)
    return document_detail(document, db)


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
        raise HTTPException(status_code=422, detail=FORMAT_MESSAGE)
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
