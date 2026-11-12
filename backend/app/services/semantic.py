"""按 docs/知识库文档解析与分段方案.md 切分，并留下页码、章节路径和出处。"""

import re
from dataclasses import dataclass, field

from app.services.text import SplitPage, TextChunk, TextPage

_HEADING_MARK = re.compile(r"^§([1-6])\s+(\S.*)$")
_HASH_HEADING = re.compile(r"^(#{1,6})\s+(\S.*)$")
_PAGE_MARK = re.compile(r"^(?:第\s*)?\d{1,4}\s*(?:[/／]\s*\d{1,4})?\s*页?$")
_CAPTION = re.compile(r"^(?:图|表|附图|附表|图示)\s*[0-9一二三四五六七八九十]*\s*[:：.、]?\s*\S")
_FOOTNOTE = re.compile(r"^(?:注\s*[0-9０-９]*\s*[:：]|脚注\s*[:：])")
_LIST_ITEM = re.compile(r"^(?:[-*•·]\s+\S|[（(]\d+[）)]\s*\S|\d+[）)]\s*\S|[①②③④⑤⑥⑦⑧⑨⑩]\s*\S)")
_LONG_ENUM = re.compile(r"^\d+[.、]\s+\S")
_FORMULA_CHAR = re.compile(r"[=∑∫√±×÷≤≥≠≈∈∞]")
_IMAGE = re.compile(r"^!\[([^\]]*)\]\([^)]+\)$")
_CONNECTIVE = ("但是", "然而", "不过", "否则", "除外", "除非", "除了", "因此", "所以", "以及", "并且", "此外", "另外", "反之")
_FORMULA_NOTE = ("其中", "式中", "上式", "变量")


@dataclass
class Block:
    kind: str
    text: str
    page_number: int | None
    level: int = 0
    language: str = ""
    start: int = 0
    end: int = 0
    page_end: int | None = None
    locator: dict | None = None


@dataclass
class _Unit:
    kind: str
    text: str
    page_number: int | None
    page_end: int | None
    spans: list[tuple[int, int]] = field(default_factory=list)
    level: int = 0
    sticky: bool = False
    locator: dict | None = None


def parse_page(text: str, page_number: int | None, repeated: set[str] | None = None) -> list[Block]:
    """把一页文字分成标题、段落、列表、表格、公式、脚注、图片说明和代码。"""
    from app.services.code_chunks import _segments
    from app.services.text import clean_text

    blocks: list[Block] = []
    for kind, mapped, language in _segments(clean_text(text)):
        if kind == "code":
            code = mapped.text.strip("\n")
            if code:
                blocks.append(Block("code", code, page_number, language=language))
            continue
        blocks.extend(_prose_blocks(mapped.text, page_number, repeated or set()))
    return [block for block in blocks if block.text.strip()]


def assign_spans(blocks: list[Block]) -> str:
    """页文本就是这些块按顺序拼起来，位置也按这个文本计算。"""
    parts: list[str] = []
    cursor = 0
    for index, block in enumerate(blocks):
        if index:
            parts.append("\n\n")
            cursor += 2
        block.start = cursor
        parts.append(block.text)
        cursor += len(block.text)
        block.end = cursor
        if block.page_end is None:
            block.page_end = block.page_number
    return "".join(parts)


def pack_pages(pages: list[TextPage], size: int, overlap: int) -> list[SplitPage]:
    from dataclasses import replace

    from app.services.text import detect_language

    kept: list[TextPage] = []
    blocks: list[Block] = []
    for page in pages:
        page_blocks = list(page.blocks) if page.blocks else parse_page(page.text, page.page_number)
        text = page.text if page.blocks else assign_spans(page_blocks)
        if not text.strip():
            continue
        kept.append(replace(page, text=text, blocks=tuple(page_blocks), language=page.language or detect_language(text)))
        blocks.extend(page_blocks)
    chunks = [_annotate(chunk, kept) for chunk in link_sections(_pack(blocks, size, overlap))]
    grouped: dict[int | None, list[TextChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.page_number, []).append(chunk)
    return [
        SplitPage(
            page.page_number,
            page.text,
            grouped.get(page.page_number, []),
            blocks=page.blocks,
            extraction_method=page.extraction_method,
            language=page.language,
            ocr_confidence=page.ocr_confidence,
            regions=page.regions,
        )
        for page in kept
    ]


def _prose_blocks(text: str, page_number: int | None, repeated: set[str]) -> list[Block]:
    lines = text.split("\n")
    blocks: list[Block] = []
    paragraph: list[str] = []
    items: list[str] = []
    formula: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(Block("paragraph", _join_paragraph(paragraph), page_number))
            paragraph.clear()

    def flush_items() -> None:
        if items:
            blocks.append(Block("list", "\n".join(items), page_number))
            items.clear()

    def flush_formula() -> None:
        if formula:
            blocks.append(Block("formula", "\n".join(formula), page_number))
            formula.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_items()
        flush_formula()

    while index < len(lines):
        raw = lines[index].strip()
        marked = _HEADING_MARK.match(raw)
        if marked:
            flush_all()
            blocks.append(Block("heading", marked.group(2).strip(), page_number, level=int(marked.group(1))))
            index += 1
            continue
        if not raw or raw in repeated or _is_banner(raw):
            flush_all()
            index += 1
            continue
        if raw.startswith("※图"):
            flush_all()
            caption = raw.removeprefix("※图").strip()
            if caption and not _is_banner(caption):
                blocks.append(Block("caption", caption, page_number))
            index += 1
            continue
        if raw.startswith("※"):
            raw = raw.removeprefix("※").strip()
            flush_all()
            if raw and raw not in repeated and not _is_banner(raw):
                blocks.append(Block("footnote", raw, page_number))
            index += 1
            continue
        image = _IMAGE.match(raw)
        if image:
            flush_all()
            blocks.append(Block("caption", image.group(1).strip() or "图片", page_number))
            index += 1
            continue
        hashed = _HASH_HEADING.match(raw)
        if hashed and not _looks_like_sentence(hashed.group(2)):
            flush_all()
            blocks.append(Block("heading", hashed.group(2).strip(), page_number, level=len(hashed.group(1))))
            index += 1
            continue
        level = _heading_level(raw)
        if level:
            flush_all()
            blocks.append(Block("heading", raw, page_number, level=level))
            index += 1
            continue
        if index + 1 < len(lines) and "|" in raw and _is_separator(lines[index + 1].strip()):
            flush_all()
            pipes = raw.count("|")
            table = [raw, lines[index + 1].strip()]
            index += 2
            while index < len(lines):
                row = lines[index].strip()
                if row.count("|") != pipes or _is_separator(row) or not row:
                    break
                table.append(row)
                index += 1
            blocks.append(Block("table", "\n".join(table), page_number))
            continue
        if _FOOTNOTE.match(raw):
            flush_all()
            note = raw.removeprefix("※").strip()
            if note and not _is_banner(note):
                blocks.append(Block("footnote", note, page_number))
            index += 1
            continue
        if _CAPTION.match(raw) and "|" not in raw:
            flush_all()
            blocks.append(Block("caption", raw, page_number))
            index += 1
            continue
        if _is_formula(raw) or (formula and raw.startswith(_FORMULA_NOTE)):
            flush_paragraph()
            flush_items()
            formula.append(raw)
            index += 1
            continue
        if formula:
            flush_formula()
        if _is_list_item(raw):
            flush_paragraph()
            flush_formula()
            items.append(raw)
            index += 1
            continue
        if items:
            flush_items()
        paragraph.append(raw)
        index += 1
    flush_all()
    return blocks


def _is_banner(line: str) -> bool:
    if _PAGE_MARK.fullmatch(line) or re.fullmatch(r"[-–—•]\s*\d{1,4}", line):
        return True
    return len(line) <= 40 and any(word in line for word in ("盗版必究", "版权所有"))


def _looks_like_sentence(text: str) -> bool:
    return len(text) > 48 or text.endswith(("。", "！", "？", "；", "，", ",", ";", "：", ":"))


def _heading_level(line: str) -> int:
    text = line.strip()
    if not text or _looks_like_sentence(text):
        return 0
    if re.match(r"^第[0-9一二三四五六七八九十百千]+章", text):
        return 1
    if re.match(r"^第[0-9一二三四五六七八九十百千]+[篇部]", text):
        return 1
    if re.match(r"^第[0-9一二三四五六七八九十百千]+节", text):
        return 2
    dotted = re.match(r"^(\d+(?:\.\d+){1,4})(?:[.\s、]\s*\S|\s*$)", text)
    if dotted:
        return min(dotted.group(1).count(".") + 1, 6)
    if re.match(r"^\d+[.、]\s*\S", text):
        return 2
    if re.match(r"^[一二三四五六七八九十]+、\S", text):
        return 2
    if re.match(r"^（[一二三四五六七八九十]+）\S", text):
        return 3
    return 0


def _is_separator(line: str) -> bool:
    if "|" not in line or "-" not in line:
        return False
    return line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "") == ""


def _is_list_item(line: str) -> bool:
    if _heading_level(line):
        return False
    if _LIST_ITEM.match(line):
        return True
    return bool(_LONG_ENUM.match(line))


def _is_formula(line: str) -> bool:
    if "|" in line or _heading_level(line):
        return False
    if line.startswith("$$") or line.endswith("$$"):
        return True
    symbols = len(_FORMULA_CHAR.findall(line))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", line))
    if "=" in line and symbols >= 1 and cjk <= 16:
        return True
    return symbols >= 2 and cjk <= symbols


def _join_paragraph(lines: list[str]) -> str:
    merged = lines[0]
    for line in lines[1:]:
        boundary = merged.endswith(("。", "！", "？", "；", "：", ":", ".", ";", "！")) or line.startswith(_CONNECTIVE + _FORMULA_NOTE)
        if boundary:
            merged += "\n" + line
            continue
        previous = merged.rsplit("\n", 1)[-1]
        if len(previous) >= 16 and re.search(r"[\u4e00-\u9fff]$", previous) and re.match(r"[\u4e00-\u9fff（(“\"]", line):
            merged += line
            continue
        merged += "\n" + line
    return merged


def _pack(blocks: list[Block], size: int, overlap: int) -> list[TextChunk]:
    units = _units(_coalesce(blocks), size)
    low, high = _overlap_bounds(size, overlap)
    path: list[str] = []
    buffer: list[_Unit] = []
    chunks: list[TextChunk] = []
    pending_heading: _Unit | None = None

    def emit(items: list[_Unit], heading_path: list[str] | None = None) -> None:
        if not items and not (heading_path or path):
            return
        chunks.append(_chunk(len(chunks), items, tuple(heading_path if heading_path is not None else path)))

    def close() -> None:
        if buffer:
            emit(list(buffer))
            buffer.clear()

    for unit in units:
        if unit.kind == "heading":
            close()
            if pending_heading is not None and unit.level <= pending_heading.level:
                emit([pending_heading], path[:-1])
            path = _push(path, unit.level, unit.text)
            pending_heading = unit
            continue
        pending_heading = None
        if unit.kind in {"table", "code", "formula", "footnote", "caption", "record"} and not unit.sticky:
            close()
            emit([unit])
            continue
        if buffer and _measure(path, [*buffer, unit]) > size and not (unit.sticky and _measure(path, [*buffer, unit]) <= int(size * 1.5)):
            tail = [] if unit.kind in {"table", "code", "formula", "record"} else _overlap_tail(buffer, low, high)
            close()
            buffer.extend(tail)
        buffer.append(unit)
        if unit.kind in {"table", "code", "formula", "footnote", "caption", "record"}:
            close()
    close()
    if pending_heading is not None:
        emit([pending_heading], path[:-1])
    return chunks


def _coalesce(blocks: list[Block]) -> list[Block]:
    merged: list[Block] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.kind == "caption" and index + 1 < len(blocks) and blocks[index + 1].kind == "table":
            table = blocks[index + 1]
            merged.append(
                Block(
                    "table",
                    f"{block.text}\n{table.text}",
                    table.page_number,
                    start=block.start,
                    end=table.end,
                    page_end=table.page_end or table.page_number,
                    locator=table.locator,
                )
            )
            index += 2
            continue
        if block.kind == "formula" or _is_formula(block.text):
            parts = [block.text]
            page_end = block.page_end or block.page_number
            end = block.end
            index += 1
            while index < len(blocks) and blocks[index].kind != "heading" and blocks[index].text.lstrip().startswith(_FORMULA_NOTE):
                parts.append(blocks[index].text)
                page_end = blocks[index].page_number or page_end
                end = blocks[index].end or end
                index += 1
            if merged and _introduces_formula(merged[-1].text) and merged[-1].kind in {"paragraph", "list"}:
                previous = merged.pop()
                parts.insert(0, previous.text)
            merged.append(Block("formula", "\n".join(parts), block.page_number, start=block.start, end=end, page_end=page_end, locator=block.locator))
            continue
        merged.append(block)
        index += 1
    return merged


def _introduces_formula(text: str) -> bool:
    tail = text.rstrip()
    return tail.endswith(("：", ":")) or "公式" in tail[-20:]


def _units(blocks: list[Block], size: int) -> list[_Unit]:
    units: list[_Unit] = []
    for block in blocks:
        pieces = _split_block(block, size)
        for text, spans in pieces:
            units.append(
                _Unit(
                    kind=block.kind,
                    text=text,
                    page_number=block.page_number,
                    page_end=block.page_end or block.page_number,
                    spans=spans,
                    level=block.level,
                    locator=_locate_rows(text, block.locator) if block.kind == "table" else block.locator,
                )
            )
    for index, unit in enumerate(units):
        if index == 0 or unit.kind == "heading":
            continue
        previous = units[index - 1]
        if previous.kind == "heading":
            continue
        lead = unit.text.lstrip()
        if lead.startswith(_CONNECTIVE + _FORMULA_NOTE):
            unit.sticky = True
        elif previous.text.rstrip().endswith(("：", ":")) and unit.kind in {"paragraph", "list", "formula", "caption"}:
            unit.sticky = True
        elif previous.kind == "caption" and unit.kind == "table":
            unit.sticky = True
    return units


def _split_block(block: Block, size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    if block.kind == "heading":
        return [(block.text, _span(block, 0, len(block.text)))]
    if block.kind == "code":
        return _code_pieces(block, size)
    if block.kind == "table":
        return _table_pieces(block, size)
    if len(block.text) <= size:
        return [(block.text, _span(block, 0, len(block.text)))]
    if block.kind == "list" or (block.kind == "record" and len(block.text) > size):
        return [(piece, _span(block, block.text.find(piece), block.text.find(piece) + len(piece))) for piece in _split_lines(block.text, size)]
    return [(piece, _span(block, 0, len(block.text))) for piece in _split_sentences(block.text, size)]


def _span(block: Block, start: int, end: int) -> list[tuple[int, int]]:
    if end <= start or block.end <= block.start:
        return []
    return [(block.start + start, block.start + min(end, len(block.text)))]


def _code_pieces(block: Block, size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    from app.services.code_chunks import chunk_code

    pieces = chunk_code(block.text, block.language, size)
    if not pieces:
        return [(block.text, _span(block, 0, len(block.text)))]
    covered = _span(block, 0, len(block.text))
    return [(content, covered) for content, _spans in pieces]


def _table_pieces(block: Block, size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    from app.services.text import split_with_tables

    lines = block.text.split("\n")
    split_at = 0
    for index, line in enumerate(lines[:-1]):
        if "|" in line and _is_separator(lines[index + 1]):
            split_at = index
            break
    preface = "\n".join(lines[:split_at]).strip()
    table = "\n".join(lines[split_at:])
    offset = len(preface) + 1 if preface else 0
    pieces = split_with_tables(table, size, 0)
    if not pieces:
        return [(block.text, _span(block, 0, len(block.text)))]
    rendered: list[tuple[str, list[tuple[int, int]]]] = []
    for content, spans in pieces:
        body = f"{preface}\n{content}" if preface else content
        located = [(block.start + offset + start, block.start + offset + end) for start, end in spans]
        if preface:
            located = [(block.start, block.start + len(preface)), *located]
        rendered.append((body, located))
    return rendered


def _split_lines(text: str, size: int) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    length = 0
    for line in text.split("\n"):
        if not line:
            continue
        extra = len(line) + 1
        if current and length + extra > size:
            groups.append("\n".join(current))
            current = []
            length = 0
        if len(line) > size:
            if current:
                groups.append("\n".join(current))
                current = []
                length = 0
            groups.extend(_split_sentences(line, size, 0))
            continue
        current.append(line)
        length += extra
    if current:
        groups.append("\n".join(current))
    return groups or [text]


def _split_sentences(text: str, size: int) -> list[str]:
    flat = text.replace("\n", "")
    raw = re.findall(r".+?(?:[。！？；]|$)", flat) or [flat]
    sentences: list[str] = []
    for piece in raw:
        if sentences and (piece.lstrip().startswith(_CONNECTIVE + _FORMULA_NOTE) or sentences[-1].endswith(("：", ":"))):
            sentences[-1] += piece
        else:
            sentences.append(piece)
    groups: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > size:
            groups.append(current)
            current = ""
        if len(sentence) > size:
            if current:
                groups.append(current)
                current = ""
            groups.extend(_hard_cut(sentence, size))
            continue
        current += sentence
    if current:
        groups.append(current)
    return groups or [text]


def _hard_cut(text: str, size: int) -> list[str]:
    from app.services.text import windows_with_spans

    return [piece for piece, _start, _end in windows_with_spans(text, size, 0)]


def _push(path: list[str], level: int, title: str) -> list[str]:
    level = min(max(level, 1), 6)
    return [*path[: level - 1], title]


def _overlap_bounds(size: int, overlap: int) -> tuple[int, int]:
    ratio = overlap / size if size else 0.15
    high = int(size * min(max(ratio, 0.10), 0.20))
    low = int(size * 0.10)
    return low, max(high, low)


def _measure(path: list[str], units: list[_Unit]) -> int:
    parts = list(path)
    parts.extend(unit.text for unit in units)
    return len("\n\n".join(part for part in parts if part))


def _overlap_tail(units: list[_Unit], low: int, high: int) -> list[_Unit]:
    chosen: list[_Unit] = []
    total = 0
    for unit in reversed(units):
        if unit.kind in {"table", "code", "formula", "footnote", "caption", "record"}:
            break
        if total + len(unit.text) > high:
            break
        chosen.append(unit)
        total += len(unit.text)
        if total >= low:
            break
    if total >= low and len(chosen) < len(units):
        chosen.reverse()
        if not chosen[0].text.lstrip().startswith(_CONNECTIVE):
            return chosen
    last = units[-1]
    if last.kind not in {"paragraph", "list"}:
        return []
    sentences = re.findall(r".+?(?:[。！？；]|$)", last.text.replace("\n", ""))
    if len(sentences) < 2:
        return []
    tail = sentences[-1].strip()
    if not low <= len(tail) <= high or tail.startswith(_CONNECTIVE):
        return []
    return [_Unit(kind=last.kind, text=tail, page_number=last.page_number, page_end=last.page_end, spans=list(last.spans), locator=last.locator)]


def _chunk(ordinal: int, units: list[_Unit], path: tuple[str, ...]) -> TextChunk:
    body = [unit.text for unit in units]
    content = "\n\n".join([*path, *body]).strip()
    pages = [number for unit in units for number in (unit.page_number, unit.page_end) if number is not None]
    page_number = min(pages) if pages else None
    page_end = max(pages) if pages else None
    spans: list[tuple[int, int]] = []
    if page_number is not None and all(unit.page_number in {None, page_number} for unit in units):
        for unit in units:
            if unit.page_number == page_number:
                spans.extend(unit.spans)
    kind = _kind(units)
    flags = _flags(content, path, kind)
    regions = tuple(unit.locator for unit in units if unit.locator)
    return TextChunk(
        ordinal=ordinal,
        content=content,
        page_number=page_number,
        spans=_merge(spans),
        page_end=page_end,
        heading_path=path,
        kind=kind,
        quality_flags=flags,
        regions=regions,
    )


def _kind(units: list[_Unit]) -> str:
    kinds = {unit.kind for unit in units}
    if "table" in kinds:
        return "table"
    if kinds == {"code"}:
        return "code"
    if "formula" in kinds:
        return "formula"
    if kinds == {"list"}:
        return "list"
    if kinds == {"footnote"}:
        return "footnote"
    if kinds == {"caption"}:
        return "caption"
    if "record" in kinds:
        return "record"
    return "prose"


def _flags(content: str, path: tuple[str, ...], kind: str) -> tuple[str, ...]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    index = 0
    for title in path:
        if index < len(lines) and lines[index] == title:
            index += 1
    body = lines[index:]
    flags: list[str] = []
    if kind in {"prose", "list", "formula"} and body and body[0].startswith(_CONNECTIVE):
        flags.append("开头是转折或例外，条件和上一块分开了")
    if kind in {"prose", "list"} and content.rstrip().endswith(("，", "、", ",")):
        flags.append("结尾停在逗号，句子没有说完")
    if kind == "table" and "---" not in content:
        flags.append("表格缺少表头")
    return tuple(flags)


def link_sections(chunks: list[TextChunk]) -> list[TextChunk]:
    """按标题路径把块连成父子，并记下相邻块。"""
    from dataclasses import replace

    leads: dict[tuple[str, ...], int] = {}
    linked: list[TextChunk] = []
    for chunk in chunks:
        path = chunk.heading_path
        parent = None
        for length in range(len(path) - 1, -1, -1):
            if path[:length] in leads:
                parent = leads[path[:length]]
                break
        if path not in leads:
            leads[path] = chunk.ordinal
        linked.append(replace(chunk, parent_ordinal=parent))
    return linked


def _annotate(chunk: TextChunk, pages: list[TextPage]) -> TextChunk:
    from dataclasses import replace

    from app.services.text import detect_language

    page = next((item for item in pages if item.page_number == chunk.page_number), None)
    method = page.extraction_method if page else ""
    language = detect_language(chunk.content) or (page.language if page else "")
    confidence = page.ocr_confidence if page else None
    regions = chunk.regions or tuple(_match_regions(chunk, pages))
    if method == "json" and not regions and chunk.heading_path:
        regions = ({"path": chunk.heading_path[-1]},)
    flags = tuple(chunk.quality_flags)
    note = "识别置信度偏低，数字和名称需要复核"
    if confidence is not None and confidence < 0.75 and note not in flags:
        flags = flags + (note,)
    return replace(
        chunk,
        extraction_method=method,
        language=language,
        ocr_confidence=confidence,
        regions=regions,
        quality_flags=flags,
    )


def _match_regions(chunk: TextChunk, pages: list[TextPage]) -> list[dict]:
    end = chunk.page_end if chunk.page_end is not None else chunk.page_number
    found: list[dict] = []
    for page in pages:
        if page.page_number is None or chunk.page_number is None:
            continue
        if page.page_number < chunk.page_number or (end is not None and page.page_number > end):
            continue
        for region in page.regions:
            text = str(region.get("text") or "")
            if len(text) < 4 and not re.search(r"[\u4e00-\u9fff]", text):
                continue
            if text and text in chunk.content:
                found.append(region)
            if len(found) >= 40:
                return found
    return found


def _locate_rows(text: str, locator: dict | None) -> dict | None:
    if not locator or "sheet" not in locator:
        return locator
    numbers = []
    for line in text.splitlines():
        cell = line.split("|", 1)[0].strip()
        if cell.isdigit():
            numbers.append(int(cell))
    if not numbers:
        return locator
    return {**locator, "row_start": min(numbers), "row_end": max(numbers)}


def dump_blocks(blocks) -> list[dict]:
    dumped = []
    for block in blocks:
        dumped.append(
            {
                "kind": block.kind,
                "text": block.text,
                "level": block.level,
                "language": block.language,
                "start": block.start,
                "end": block.end,
                "page_number": block.page_number,
                "page_end": block.page_end,
                "locator": block.locator,
            }
        )
    return dumped


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    from app.services.text import merge_spans

    return merge_spans(spans)
