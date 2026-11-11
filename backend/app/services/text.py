from dataclasses import dataclass
from pathlib import Path

ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
CATEGORIES = {"design", "regulation", "other"}


@dataclass(frozen=True)
class TextPage:
    text: str
    page_number: int | None


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    content: str
    page_number: int | None


def normalize(text: str) -> str:
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    blank = False
    for raw in cleaned.split("\n"):
        line = raw.strip()
        if not line:
            if lines and not blank:
                lines.append("")
            blank = True
            continue
        blank = False
        lines.append(line)
    return "\n".join(lines).strip()


def _break_at(text: str, start: int, end: int) -> int:
    window = text[start:end]
    floor = int(len(window) * 0.6)
    for mark in ("\n\n", "\n", "。", "；", "！", "？", ".", ";"):
        index = window.rfind(mark)
        if index >= floor:
            return start + index + len(mark)
    return end


def windows(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    step_floor = max(size - overlap, 1)
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _break_at(text, start, end)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = start + step_floor
        start = next_start
    return pieces


def split_pages(pages: list[TextPage], size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        text = normalize(page.text)
        if not text:
            continue
        for piece in windows(text, size, overlap):
            chunks.append(TextChunk(ordinal=len(chunks), content=piece, page_number=page.page_number))
    return chunks


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文件编码无法识别，请改成 UTF-8 或 GB18030")


def extract_pdf(path: Path) -> list[TextPage]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF 已加密，读不出文字") from exc
    return [TextPage(page.extract_text() or "", index) for index, page in enumerate(reader.pages, start=1)]


def extract_docx(path: Path) -> list[TextPage]:
    from docx import Document

    document = Document(str(path))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return [TextPage("\n".join(parts), None)]


def extract_document(path: Path) -> list[TextPage]:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("只接受 txt、md、pdf、docx")
    if suffix in {".txt", ".md"}:
        return [TextPage(read_text_file(path), None)]
    if suffix == ".pdf":
        return extract_pdf(path)
    return extract_docx(path)
