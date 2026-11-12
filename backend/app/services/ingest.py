import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk, DocumentPage
from app.services.text import ALLOWED_SUFFIXES, CATEGORIES, FORMAT_MESSAGE, extract_document, split_pages
from app.statuses import DocumentStatus


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


def json_safe(value):
    """PostgreSQL 的文本和 JSON 不接受 NUL。"""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


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
        raise ValueError(FORMAT_MESSAGE)
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
        split = split_pages(pages, settings.chunk_size, settings.chunk_overlap)
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
        chunk_count=sum(len(page.chunks) for page in split),
        created_by=created_by,
        status=DocumentStatus.review.value if split and any(page.chunks for page in split) else DocumentStatus.rejected.value,
        reject_reason=None if split and any(page.chunks for page in split) else "没有读出文字，可能是扫描件或空文件",
    )
    db.add(document)
    pieces = [chunk for page in split for chunk in page.chunks]
    if split:
        from app.services.semantic import dump_blocks

        db.add_all(
            DocumentPage(
                document_id=document_id,
                ordinal=index,
                page_number=page.page_number,
                content=json_safe(page.text),
                extraction_method=page.extraction_method or None,
                language=page.language or None,
                ocr_confidence=page.ocr_confidence,
                blocks=json_safe(dump_blocks(page.blocks)) or None,
                regions=json_safe(list(page.regions)) or None,
            )
            for index, page in enumerate(split)
        )
    rows = [
        DocumentChunk(
            document_id=document_id,
            ordinal=piece.ordinal,
            content=json_safe(piece.content),
            page_number=piece.page_number,
            page_end=piece.page_end,
            heading_path=list(piece.heading_path) or None,
            block_kind=piece.kind,
            quality_flags=list(piece.quality_flags) or None,
            char_count=len(piece.content),
            source_spans=[{"start": start, "end": end} for start, end in piece.spans] or None,
            extraction_method=piece.extraction_method or None,
            language=piece.language or None,
            ocr_confidence=piece.ocr_confidence,
            regions=json_safe(list(piece.regions)) or None,
        )
        for piece in pieces
    ]
    if rows:
        db.add_all(rows)
        db.flush()
        by_ordinal = {row.ordinal: row for row in rows}
        for piece, row in zip(pieces, rows, strict=True):
            parent = by_ordinal.get(piece.parent_ordinal) if piece.parent_ordinal is not None else None
            if parent is not None:
                row.parent_id = parent.id
            previous = by_ordinal.get(piece.ordinal - 1)
            following = by_ordinal.get(piece.ordinal + 1)
            if previous is not None:
                row.previous_id = previous.id
            if following is not None:
                row.next_id = following.id
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
