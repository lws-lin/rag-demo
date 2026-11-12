import re
from dataclasses import dataclass
from pathlib import Path

ALLOWED_SUFFIXES = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".csv",
    ".tsv",
    ".html",
    ".htm",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
}
FORMAT_MESSAGE = "只接受 txt、md、pdf、docx、pptx、xlsx、xls、csv、tsv、html、json、png、jpg、jpeg、webp、tif、tiff"
CATEGORIES = {"design", "regulation", "other"}


@dataclass(frozen=True)
class TextPage:
    text: str
    page_number: int | None
    blocks: tuple = ()
    extraction_method: str = ""
    language: str = ""
    ocr_confidence: float | None = None
    regions: tuple = ()


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    content: str
    page_number: int | None
    spans: list[tuple[int, int]]
    page_end: int | None = None
    heading_path: tuple[str, ...] = ()
    kind: str = "prose"
    quality_flags: tuple[str, ...] = ()
    parent_ordinal: int | None = None
    extraction_method: str = ""
    language: str = ""
    ocr_confidence: float | None = None
    regions: tuple = ()


@dataclass(frozen=True)
class SplitPage:
    page_number: int | None
    text: str
    chunks: list[TextChunk]
    blocks: tuple = ()
    extraction_method: str = ""
    language: str = ""
    ocr_confidence: float | None = None
    regions: tuple = ()


@dataclass(frozen=True)
class SpanMap:
    """字符串里每个字符对应页文本中的位置。"""

    text: str
    index: list[int]

    @classmethod
    def identity(cls, text: str, base: int = 0) -> "SpanMap":
        return cls(text, [base + offset for offset in range(len(text))])

    def slice(self, start: int, end: int) -> "SpanMap":
        return SpanMap(self.text[start:end], self.index[start:end])

    def strip(self, chars: str | None = None) -> "SpanMap":
        text = self.text.strip() if chars is None else self.text.strip(chars)
        if not text:
            return SpanMap("", [])
        raw = self.text
        lead = len(raw) - len(raw.lstrip() if chars is None else raw.lstrip(chars))
        return self.slice(lead, lead + len(text))

    def locate(self, start: int, end: int) -> tuple[int, int] | None:
        if start < 0 or end > len(self.index) or start >= end:
            return None
        return (self.index[start], self.index[end - 1] + 1)

    def locate_all(self, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        located = [item for item in (self.locate(start, end) for start, end in spans) if item]
        return merge_spans(located)


def detect_language(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk == 0 and latin == 0:
        return ""
    if cjk > 20 and latin > 20 and min(cjk, latin) / max(cjk, latin) > 0.3:
        return "mixed"
    return "zh" if cjk >= latin else "en"


def clean_text(text: str) -> str:
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted((start, end) for start, end in spans if end > start)
    if not ordered:
        return []
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


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
    return [piece for piece, _, _ in windows_with_spans(text, size, overlap)]


def windows_with_spans(text: str, size: int, overlap: int) -> list[tuple[str, int, int]]:
    if not text:
        return []
    if len(text) <= size:
        return [(text, 0, len(text))]
    step_floor = max(size - overlap, 1)
    pieces: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _break_at(text, start, end)
        pieces.extend(_stripped_span(text[start:end], start))
        if end >= len(text):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = start + step_floor
        start = next_start
    return pieces


def _stripped_span(text: str, base: int) -> list[tuple[str, int, int]]:
    piece = text.strip()
    if not piece:
        return []
    lead = len(text) - len(text.lstrip())
    return [(piece, base + lead, base + lead + len(piece))]


def normalize_mapped(mapped: SpanMap) -> SpanMap:
    chars: list[str] = []
    indexes: list[int] = []
    blank = False
    for start, raw in _lines(mapped.text):
        stripped = raw.strip()
        if not stripped:
            if chars and not blank:
                blank = True
            continue
        lead = len(raw) - len(raw.lstrip())
        content_at = start + lead
        if chars:
            newline_at = start - 1 if start > 0 else content_at
            chars.append("\n")
            indexes.append(mapped.index[newline_at])
            if blank:
                chars.append("\n")
                indexes.append(mapped.index[newline_at])
        blank = False
        for offset, char in enumerate(stripped):
            chars.append(char)
            indexes.append(mapped.index[content_at + offset])
    return SpanMap("".join(chars), indexes)


def _lines(text: str) -> list[tuple[int, str]]:
    lines = text.split("\n")
    located: list[tuple[int, str]] = []
    cursor = 0
    for index, line in enumerate(lines):
        located.append((cursor, line))
        cursor += len(line)
        if index < len(lines) - 1:
            cursor += 1
    return located


def _is_table_separator(line: str) -> bool:
    if "|" not in line or "-" not in line:
        return False
    return line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "") == ""


def _split_table(
    header: tuple[str, tuple[int, int]],
    separator: tuple[str, tuple[int, int]],
    rows: list[tuple[str, tuple[int, int]]],
    size: int,
) -> list[tuple[str, list[tuple[int, int]]]]:
    """每个表格片段都带表头，列名不会只出现在第一段。"""
    header_text, header_span = header
    separator_text, separator_span = separator
    prefix = f"{header_text}\n{separator_text}"
    prefix_spans = [header_span, separator_span]
    if not rows:
        return [(prefix, merge_spans(prefix_spans))]
    pieces: list[tuple[str, list[tuple[int, int]]]] = []
    current: list[tuple[str, tuple[int, int]]] = []
    current_len = len(prefix)
    for row in rows:
        extra = len(row[0]) + 1
        if current and current_len + extra > size:
            body = "\n".join(item[0] for item in current)
            pieces.append((prefix + "\n" + body, merge_spans([*prefix_spans, *(item[1] for item in current)])))
            current = []
            current_len = len(prefix)
        current.append(row)
        current_len += extra
    if current:
        body = "\n".join(item[0] for item in current)
        pieces.append((prefix + "\n" + body, merge_spans([*prefix_spans, *(item[1] for item in current)])))
    return pieces


def split_with_tables(text: str, size: int, overlap: int) -> list[tuple[str, list[tuple[int, int]]]]:
    located = _lines(text)
    pieces: list[tuple[str, list[tuple[int, int]]]] = []
    prose: list[tuple[int, str]] = []
    index = 0

    def flush_prose() -> None:
        if not prose:
            return
        start = prose[0][0]
        end = prose[-1][0] + len(prose[-1][1])
        region = text[start:end]
        prose.clear()
        lead = len(region) - len(region.lstrip())
        for piece, piece_start, piece_end in windows_with_spans(region.strip(), size, overlap):
            pieces.append((piece, [(start + lead + piece_start, start + lead + piece_end)]))

    while index < len(located):
        line_start, header = located[index]
        if index + 1 < len(located) and "|" in header and _is_table_separator(located[index + 1][1]):
            flush_prose()
            separator_start, separator = located[index + 1]
            pipes = header.count("|")
            index += 2
            rows: list[tuple[str, tuple[int, int]]] = []
            while index < len(located) and located[index][1].count("|") == pipes and not _is_table_separator(located[index][1]):
                row_start, row = located[index]
                rows.append((row, (row_start, row_start + len(row))))
                index += 1
            pieces.extend(
                _split_table(
                    (header, (line_start, line_start + len(header))),
                    (separator, (separator_start, separator_start + len(separator))),
                    rows,
                    size,
                )
            )
            continue
        prose.append((line_start, header))
        index += 1
    flush_prose()
    return pieces


def split_pages(pages: list[TextPage], size: int, overlap: int) -> list[SplitPage]:
    from app.services.semantic import pack_pages

    return pack_pages(pages, size, overlap)


def format_table(rows: list[list[str]]) -> str:
    cleaned_rows = []
    for row in rows:
        cells = [(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cells):
            cleaned_rows.append(cells)
    kept = cleaned_rows
    if not kept:
        return ""
    width = max(len(row) for row in kept)

    def line(cells: list[str]) -> str:
        padded = cells + [""] * (width - len(cells))
        return " | ".join(padded)

    header = line(kept[0])
    separator = " | ".join("---" for _ in range(width))
    body = [line(row) for row in kept[1:]]
    return "\n".join([header, separator, *body])


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文件编码无法识别，请改成 UTF-8 或 GB18030")


_SCANNED_PAGE_CHARS = 20
_CID = re.compile(r"\(cid:\d+\)")


def _text_is_garbled(text: str) -> bool:
    """字体没有 Unicode 映射时，正文会变成 (cid:24) 这类占位，和页面上的字对不上。"""
    return len(_CID.findall(text)) >= 3


def _pdf_image_text(page) -> str:
    from app.services.ocr import ocr_image

    parts: list[str] = []
    for image in getattr(page, "images", []):
        try:
            data = image.data
        except Exception:
            continue
        parts.append(ocr_image(data))
    return "\n".join(part for part in parts if part.strip())


def _text_outside_tables(page, bboxes: list[tuple]) -> str:
    if not bboxes:
        return page.extract_text() or ""

    def keep(obj) -> bool:
        if obj.get("object_type") != "char":
            return True
        x = (obj["x0"] + obj["x1"]) / 2
        y = (obj["top"] + obj["bottom"]) / 2
        for x0, top, x1, bottom in bboxes:
            if x0 <= x <= x1 and top <= y <= bottom:
                return False
        return True

    return page.filter(keep).extract_text() or ""


def _repeated_lines(pages: list[str]) -> set[str]:
    from collections import Counter

    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in set(lines[:2] + lines[-2:]):
            if 0 < len(line) <= 40:
                counts[line] += 1
    threshold = max(3, int(len(pages) * 0.3))
    return {line for line, count in counts.items() if count >= threshold}


def _point_in_boxes(x: float, y: float, boxes: list[tuple]) -> bool:
    return any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in boxes)


def _font_heading_level(text: str, size: float, body: float, bold: bool) -> int:
    from app.services.semantic import _heading_level

    if _heading_level(text) or len(text) < 2 or len(text) > 40:
        return 0
    if text.endswith(("。", "！", "？", "；", "，", ",", "：", ":")):
        return 0
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return 0
    if size >= body * 1.25:
        return 1 if size >= body * 1.7 else 2
    if bold and size >= body * 1.05:
        return 2
    return 0


def _image_caption(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 2 or re.fullmatch(r"[\d\W_]+", line):
            continue
        if len(line) < 4 and not re.search(r"[\u4e00-\u9fff]", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _pdf_marked_text(page, raw_page, repeated: set[str], tables) -> tuple[str, list[dict]]:
    """按阅读顺序输出这一页，大字和加粗短行标成标题，底部小字标成脚注。"""
    import statistics

    boxes = [table.bbox for table in tables]
    events: list[tuple[float, str, dict]] = []
    measured: list[tuple[float, str, float, bool, float, float, float]] = []
    for line in page.extract_text_lines(return_chars=True) or []:
        text = str(line.get("text") or "").replace("\x00", "").strip()
        if not text or text in repeated:
            continue
        top = float(line.get("top") or 0)
        bottom = float(line.get("bottom") or top)
        x0 = float(line.get("x0") or 0)
        x1 = float(line.get("x1") or x0)
        if _point_in_boxes((x0 + x1) / 2, (top + bottom) / 2, boxes):
            continue
        chars = line.get("chars") or []
        sizes = [float(char.get("size") or 0) for char in chars if float(char.get("size") or 0) > 0]
        size = max(sizes) if sizes else 0
        bold = any("bold" in str(char.get("fontname") or "").lower() for char in chars)
        measured.append((top, text, size, bold, x0, x1, bottom))
    body_sizes = [size for _top, _text, size, _bold, _x0, _x1, _bottom in measured if size]
    body = statistics.median(body_sizes) if body_sizes else 12
    height = float(getattr(page, "height", 0) or 0)
    for top, text, size, bold, x0, x1, bottom in measured:
        region = {"text": text, "x0": x0, "y0": top, "x1": x1, "y1": bottom}
        if height and top > height * 0.9 and 0 < size < body * 0.92 and len(text) <= 80:
            events.append((top, f"※ {text}", region))
            continue
        level = _font_heading_level(text, size, body, bold)
        events.append((top, f"§{level} {text}" if level else text, region))
    for table in tables:
        rendered = format_table(table.extract() or [])
        if not rendered:
            continue
        x0, top, x1, bottom = (float(value) for value in table.bbox)
        label = next((line.strip() for line in rendered.splitlines() if line.strip()), "表格")
        events.append((top, rendered, {"text": label[:80], "x0": x0, "y0": top, "x1": x1, "y1": bottom, "kind": "table"}))
    events.sort(key=lambda item: item[0])
    parts = [text for _top, text, _region in events if text.strip()]
    regions = [region for _top, text, region in events if text.strip() and region.get("text")]
    body_text = "\n".join(parts)
    if len(normalize(body_text)) < 400:
        image_text = _image_caption(_pdf_image_text(raw_page))
        if image_text and image_text not in body_text:
            parts.append(f"※图 {image_text}")
    return "\n".join(parts), regions


def extract_pdf(path: Path) -> list[TextPage]:
    import pdfplumber
    from pypdf import PdfReader

    from app.services.ocr import ocr_pdf_page_detail
    from app.services.semantic import assign_spans, parse_page

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF 已加密，读不出文字") from exc
    pages: list[TextPage] = []
    with pdfplumber.open(path) as pdf:
        captured = []
        for index, (page, raw_page) in enumerate(zip(pdf.pages, reader.pages), start=1):
            captured.append((index, page, raw_page, page.extract_text() or ""))
        repeated = _repeated_lines([plain for _index, _page, _raw, plain in captured])
        for index, page, raw_page, plain in captured:
            tables = page.find_tables() or []
            rendered = [item for item in (format_table(table.extract() or []) for table in tables) if item]
            prose = _text_outside_tables(page, [table.bbox for table in tables])
            if _text_is_garbled(plain) or (len(normalize(prose)) < _SCANNED_PAGE_CHARS and not rendered):
                recognized = ocr_pdf_page_detail(path, index - 1)
                marked = recognized.text
                method = "ocr"
                confidence = recognized.confidence
                regions = list(recognized.regions)
            else:
                marked, regions = _pdf_marked_text(page, raw_page, repeated, tables)
                method = "pdf_layout"
                confidence = None
            blocks = parse_page(marked, index, repeated)
            pages.append(
                TextPage(
                    assign_spans(blocks),
                    index,
                    tuple(blocks),
                    extraction_method=method,
                    ocr_confidence=confidence,
                    regions=tuple(regions),
                )
            )
    return pages


def _docx_image_text(document) -> str:
    from app.services.ocr import ocr_image

    parts: list[str] = []
    seen: set[int] = set()
    for rel in document.part.rels.values():
        if "image" not in rel.reltype:
            continue
        try:
            blob = rel.target_part.blob
        except Exception:
            continue
        digest = hash(blob)
        if digest in seen:
            continue
        seen.add(digest)
        parts.append(ocr_image(blob))
    return "\n".join(part for part in parts if part.strip())


def _iter_docx_blocks(document):
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _docx_table(table) -> str:
    rows = []
    for row in table.rows:
        rows.append([cell.text.replace("\n", " ").strip() for cell in row.cells])
    return format_table(rows)


def _docx_heading_level(style: str) -> int:
    match = re.search(r"(?:Heading|标题)\s*(\d+)", style, re.I)
    if not match:
        return 0
    return min(max(int(match.group(1)), 1), 6)


def _docx_is_list(paragraph, style: str) -> bool:
    if "List" in style or "列表" in style:
        return True
    properties = paragraph._p.pPr
    return properties is not None and properties.numPr is not None


def _docx_footnotes(document) -> list[str]:
    from docx.oxml.ns import qn

    part = None
    for rel in document.part.rels.values():
        if str(rel.reltype).endswith("/footnotes"):
            part = rel.target_part
            break
    if part is None:
        return []
    notes: list[str] = []
    for footnote in part.element.findall(qn("w:footnote")):
        if footnote.get(qn("w:type")) in {"separator", "continuationSeparator"}:
            continue
        texts = [node.text for node in footnote.findall(".//" + qn("w:t")) if node.text]
        text = "".join(texts).strip()
        if text:
            notes.append(text)
    return notes


def extract_docx(path: Path) -> list[TextPage]:
    from docx import Document
    from docx.table import Table

    from app.services.semantic import assign_spans, parse_page

    document = Document(str(path))
    parts: list[str] = []
    list_lines: list[str] = []

    def flush_list() -> None:
        if list_lines:
            parts.append("\n".join(list_lines))
            list_lines.clear()

    for block in _iter_docx_blocks(document):
        if isinstance(block, Table):
            flush_list()
            rendered = _docx_table(block)
            if rendered:
                parts.append(rendered)
            continue
        text = block.text.strip()
        if not text:
            continue
        style = block.style.name if block.style is not None and block.style.name else ""
        level = _docx_heading_level(style)
        if level:
            flush_list()
            parts.append(f"§{level} {text}")
            continue
        if _docx_is_list(block, style):
            list_lines.append(text if text.startswith(("•", "-", "*")) else f"• {text}")
            continue
        flush_list()
        if "caption" in style.lower() or "题注" in style:
            parts.append(f"※图 {text}")
            continue
        parts.append(text)
    flush_list()
    for note in _docx_footnotes(document):
        parts.append(f"※ {note}")
    image_text = _docx_image_text(document)
    if image_text:
        parts.append(f"※图 {image_text}")
    blocks = parse_page("\n\n".join(parts), None)
    return [TextPage(assign_spans(blocks), None, tuple(blocks), extraction_method="docx")]


def _finish(pages: list[TextPage]) -> list[TextPage]:
    from dataclasses import replace

    finished = []
    for page in pages:
        finished.append(replace(page, language=page.language or detect_language(page.text)))
    return finished


def extract_document(path: Path) -> list[TextPage]:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(FORMAT_MESSAGE)
    from app.services.formats import extract_extra

    extra = extract_extra(path)
    if extra is not None:
        return _finish(extra)
    if suffix in {".txt", ".md"}:
        method = "markdown" if suffix == ".md" else "plain"
        return _finish([TextPage(read_text_file(path), None, extraction_method=method)])
    if suffix == ".pdf":
        return _finish(extract_pdf(path))
    return _finish(extract_docx(path))
