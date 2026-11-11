import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk
from app.services.text import ALLOWED_SUFFIXES, CATEGORIES, extract_document, split_pages


@dataclass
class IngestResult:
    action: str
    document: Document
    message: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_filename(name: str) -> str:
    cleaned = Path(name).name.replace("\x00", "").strip()
    return cleaned[:255] or "未命名"


def ingest_path(
    db: Session,
    source: Path,
    *,
    category: str,
    original_filename: str | None = None,
    content_type: str | None = None,
    created_by: uuid.UUID | None = None,
) -> IngestResult:
    if category not in CATEGORIES:
        raise ValueError("分类只能是 design、regulation 或 other")
    if not source.is_file():
        raise ValueError("找不到文件")
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("只接受 txt、md、pdf、docx")
    size = source.stat().st_size
    if size == 0:
        raise ValueError("文件是空的")
    if size > settings.max_upload_bytes:
        raise ValueError("文件超过 20MB")

    filename = safe_filename(original_filename or source.name)
    digest = file_sha256(source)
    existing = db.scalar(select(Document).where(Document.content_hash == digest))
    if existing is not None:
        return IngestResult("skipped", existing, "相同内容已经在库里")

    try:
        pages = extract_document(source)
        pieces = split_pages(pages, settings.chunk_size, settings.chunk_overlap)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"读取失败：{exc}") from exc

    document_id = uuid.uuid4()
    library = settings.library_path
    library.mkdir(parents=True, exist_ok=True)
    stored = library / f"{document_id}{suffix}"
    shutil.copy2(source, stored)

    title = Path(filename).stem.strip()[:255] or "未命名"
    document = Document(
        id=document_id,
        title=title,
        category=category,
        original_filename=filename,
        content_type=content_type,
        size_bytes=size,
        storage_key=stored.name,
        content_hash=digest,
        chunk_count=len(pieces),
        created_by=created_by,
        status="review" if pieces else "rejected",
        reject_reason=None if pieces else "没有读出文字，可能是扫描件或空文件",
    )
    db.add(document)
    if pieces:
        db.add_all(
            DocumentChunk(
                document_id=document_id,
                ordinal=piece.ordinal,
                content=piece.content,
                page_number=piece.page_number,
                char_count=len(piece.content),
            )
            for piece in pieces
        )
    db.commit()
    db.refresh(document)
    if pieces:
        return IngestResult("imported", document, f"拆成 {len(pieces)} 个片段")
    return IngestResult("rejected", document, document.reject_reason or "没有读出文字")


def iter_inbox(inbox: Path):
    if not inbox.is_dir():
        raise ValueError(f"收件目录不存在：{inbox}")
    for category in sorted(CATEGORIES):
        folder = inbox / category
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            yield category, path
