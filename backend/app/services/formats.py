"""幻灯片、表格、网页、JSON 和票据。切分规则见 docs/知识库文档解析与分段方案.md。"""

import csv
import json
import re
from datetime import date, datetime
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
SPREADSHEET_SUFFIXES = {".xlsx", ".xls", ".csv", ".tsv"}

_RECEIPT_FIELDS = (
    ("发票号码", re.compile(r"发票号码[:：\s]*([0-9A-Za-z]{6,30})")),
    ("开票日期", re.compile(r"(?:开票日期|日期)[:：\s]*([0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日|[0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}日?)")),
    ("购买方", re.compile(r"购买方(?:名称)?[:：\s]*([^\n]{2,40})")),
    ("销售方", re.compile(r"销售方(?:名称)?[:：\s]*([^\n]{2,40})")),
    ("金额", re.compile(r"(?:价税合计|合计金额|金额|合计)[^\d\n]{0,12}([0-9]+(?:\.[0-9]{1,2})?)")),
    ("税额", re.compile(r"税额[^\d\n]{0,8}([0-9]+(?:\.[0-9]{1,2})?)")),
)


def extract_extra(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return _pptx(path)
    if suffix in SPREADSHEET_SUFFIXES:
        return _spreadsheet(path)
    if suffix in {".html", ".htm"}:
        return _html(path)
    if suffix == ".json":
        return _json(path)
    if suffix in IMAGE_SUFFIXES:
        return _receipt(path)
    return None


def _page(text: str, blocks, method: str, page_number: int | None = None, confidence=None, regions=()):
    from app.services.semantic import assign_spans
    from app.services.text import TextPage, detect_language

    if not blocks:
        blocks = []
    content = assign_spans(blocks) if blocks else text
    return TextPage(
        content,
        page_number,
        tuple(blocks),
        extraction_method=method,
        language=detect_language(content),
        ocr_confidence=confidence,
        regions=tuple(regions),
    )


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M").removesuffix(" 00:00")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\n", " ").strip()


def _sheet_blocks(name: str, rows: list[list[str]], page_number: int, hidden: bool = False):
    from app.services.semantic import Block
    from app.services.text import format_table

    title = f"{name}（隐藏）" if hidden else name
    indexed = [(index, row) for index, row in enumerate(rows, start=1) if any(cell.strip() for cell in row)]
    blocks = [Block("heading", title, page_number, level=1, locator={"sheet": name})]
    if len(indexed) < 2:
        if indexed:
            index, row = indexed[0]
            blocks.append(Block("paragraph", " | ".join(cell for cell in row if cell), page_number, locator={"sheet": name, "row_start": index, "row_end": index}))
        return blocks
    header_index, header_row = indexed[0]
    header = ["行", *header_row]
    body = []
    for index, row in indexed[1:]:
        width = len(header_row)
        padded = row[:width] + [""] * max(width - len(row), 0)
        body.append([str(index), *padded])
    table = format_table([header, *body])
    if table:
        start = indexed[1][0]
        end = indexed[-1][0]
        blocks.append(Block("table", table, page_number, locator={"sheet": name, "row_start": start, "row_end": end, "header_row": header_index}))
    return blocks


def _spreadsheet(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        sheets = _xlsx_sheets(path)
    elif suffix == ".xls":
        sheets = _xls_sheets(path)
    else:
        sheets = [_csv_sheet(path)]
    pages = []
    for index, (name, rows, hidden) in enumerate(sheets, start=1):
        blocks = _sheet_blocks(name, rows, index, hidden)
        pages.append(_page("", blocks, "spreadsheet", index))
    return [page for page in pages if page.text.strip()]


def _xlsx_sheets(path: Path):
    import openpyxl

    values = openpyxl.load_workbook(path, data_only=True)
    formulas = openpyxl.load_workbook(path, data_only=False)
    sheets = []
    for sheet, formula_sheet in zip(values.worksheets, formulas.worksheets):
        rows = []
        for row, formula_row in zip(sheet.iter_rows(), formula_sheet.iter_rows()):
            cells = []
            for cell, formula in zip(row, formula_row):
                text = _cell(cell.value)
                formula_text = formula.value if isinstance(formula.value, str) else ""
                if formula_text.startswith("=") and text and text != formula_text:
                    text = f"{text}（{formula_text}）"
                elif formula_text.startswith("=") and not text:
                    text = formula_text
                cells.append(text)
            rows.append(cells)
        sheets.append((sheet.title, rows, sheet.sheet_state != "visible"))
    values.close()
    formulas.close()
    return sheets


def _xls_sheets(path: Path):
    import xlrd

    book = xlrd.open_workbook(str(path))
    sheets = []
    for sheet in book.sheets():
        rows = []
        for row_index in range(sheet.nrows):
            cells = []
            for col_index in range(sheet.ncols):
                cell = sheet.cell(row_index, col_index)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        cells.append(_cell(xlrd.xldate_as_datetime(cell.value, book.datemode)))
                    except Exception:
                        cells.append(_cell(cell.value))
                else:
                    cells.append(_cell(cell.value))
            rows.append(cells)
        hidden = False
        visibility = getattr(sheet, "visibility", 0)
        if visibility not in (0,):
            hidden = True
        sheets.append((sheet.name, rows, hidden))
    return sheets


def _csv_sheet(path: Path):
    from app.services.text import read_text_file

    sample = read_text_file(path)
    delimiter = "\t" if path.suffix.lower() == ".tsv" else _sniff(sample)
    rows = []
    for row in csv.reader(sample.splitlines(), delimiter=delimiter):
        rows.append([_cell(cell) for cell in row])
    return (path.stem or "表格", rows, False)


def _sniff(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",\t;|")
    except csv.Error:
        return ","
    return dialect.delimiter or ","


def _pptx(path: Path):
    from pptx import Presentation
    from pptx.enum.shapes import PP_PLACEHOLDER

    from app.services.semantic import Block
    from app.services.text import format_table

    deck = Presentation(str(path))
    title = (deck.core_properties.title or "").strip() or path.stem or "幻灯片"
    pages = []
    for index, slide in enumerate(deck.slides, start=1):
        blocks = [Block("heading", title, index, level=1, locator={"slide": index})]
        shapes = sorted(_walk_shapes(slide.shapes), key=lambda shape: (int(shape.top or 0), int(shape.left or 0)))
        for shape in shapes:
            if getattr(shape, "has_table", False):
                rows = [[_cell(cell.text) for cell in row.cells] for row in shape.table.rows]
                rendered = format_table(rows)
                if rendered:
                    blocks.append(Block("table", rendered, index, locator={"slide": index}))
                continue
            if getattr(shape, "has_chart", False):
                chart_title = ""
                try:
                    if shape.chart.has_title:
                        chart_title = shape.chart.chart_title.text_frame.text.strip()
                except Exception:
                    chart_title = ""
                if chart_title:
                    blocks.append(Block("caption", chart_title, index, locator={"slide": index}))
                continue
            text = _shape_text(shape)
            if not text:
                alt = (getattr(shape, "alternative_text", None) or "").strip() if hasattr(shape, "alternative_text") else ""
                if alt:
                    blocks.append(Block("caption", alt, index, locator={"slide": index}))
                continue
            if _is_slide_title(shape, PP_PLACEHOLDER):
                blocks.append(Block("heading", text, index, level=2, locator={"slide": index}))
            else:
                blocks.append(Block("paragraph", text, index, locator={"slide": index}))
        note = _notes(slide)
        if note:
            blocks.append(Block("footnote", f"演讲者备注：{note}", index, locator={"slide": index, "notes": True}))
        pages.append(_page("", blocks, "pptx", index))
    return [page for page in pages if page.text.strip()]


def _walk_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk_shapes(shape.shapes)
        else:
            yield shape


def _shape_text(shape) -> str:
    if not getattr(shape, "has_text_frame", False):
        return ""
    lines = [paragraph.text.strip() for paragraph in shape.text_frame.paragraphs if paragraph.text.strip()]
    return "\n".join(lines)


def _is_slide_title(shape, placeholder) -> bool:
    try:
        if not shape.is_placeholder:
            return False
        return shape.placeholder_format.type in {placeholder.TITLE, placeholder.CENTER_TITLE}
    except Exception:
        return False


def _notes(slide) -> str:
    try:
        frame = slide.notes_slide.notes_text_frame
    except Exception:
        return ""
    if frame is None:
        return ""
    return "\n".join(paragraph.text.strip() for paragraph in frame.paragraphs if paragraph.text.strip())


def _html(path: Path):
    from bs4 import BeautifulSoup

    from app.services.semantic import Block
    from app.services.text import format_table, read_text_file

    soup = BeautifulSoup(read_text_file(path), "html.parser")
    for tag in soup.find_all(["script", "style", "noscript", "nav", "footer", "iframe"]):
        tag.decompose()
    root = soup.body or soup
    blocks = []
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        blocks.append(Block("heading", title, None, level=1))
    for tag in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table", "figcaption"]):
        if tag.name != "table" and tag.find_parent(["table", "pre"]):
            continue
        if tag.name == "li" and tag.find_parent("li"):
            continue
        if tag.name.startswith("h"):
            text = tag.get_text(" ", strip=True)
            if text:
                blocks.append(Block("heading", text, None, level=int(tag.name[1])))
            continue
        if tag.name == "table":
            rows = []
            for row in tag.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            rendered = format_table(rows)
            if rendered:
                blocks.append(Block("table", rendered, None))
            continue
        if tag.name == "pre":
            text = tag.get_text("\n", strip=True)
            if text:
                blocks.append(Block("code", text, None, language=""))
            continue
        if tag.name == "li":
            text = tag.get_text(" ", strip=True)
            if text:
                blocks.append(Block("list", text if text.startswith(("•", "-", "*")) else f"• {text}", None))
            continue
        if tag.name == "figcaption":
            text = tag.get_text(" ", strip=True)
            if text:
                blocks.append(Block("caption", text, None))
            continue
        text = tag.get_text(" ", strip=True)
        if text:
            blocks.append(Block("paragraph", text, None))
    if len(blocks) <= (1 if title else 0):
        plain = root.get_text("\n", strip=True)
        if plain:
            blocks.append(Block("paragraph", plain, None))
    return [_page("", _merge_list_blocks(blocks), "html")] if blocks else []


def _merge_list_blocks(blocks):
    merged = []
    items: list[str] = []

    def flush():
        if items:
            from app.services.semantic import Block

            merged.append(Block("list", "\n".join(items), None))
            items.clear()

    for block in blocks:
        if block.kind == "list":
            items.append(block.text)
            continue
        flush()
        merged.append(block)
    flush()
    return merged


def _json(path: Path):
    from app.services.semantic import Block
    from app.services.text import read_text_file

    try:
        payload = json.loads(read_text_file(path))
    except json.JSONDecodeError as exc:
        raise ValueError("不是合法的 JSON") from exc
    blocks: list[Block] = []
    _json_blocks(payload, "$", blocks, 1)
    return [_page("", blocks, "json")] if blocks else []


def _json_blocks(value, path: str, blocks, level: int):
    from app.services.semantic import Block

    level = min(max(level, 1), 6)
    if isinstance(value, dict):
        blocks.append(Block("heading", path, None, level=level, locator={"path": path}))
        scalars = []
        nested = []
        for key, item in value.items():
            child = f"{path}.{key}"
            if isinstance(item, (dict, list)):
                nested.append((child, item))
            else:
                scalars.append(f"{key}：{_json_scalar(item)}")
        if scalars:
            blocks.append(Block("record", "\n".join(scalars), None, locator={"path": path}))
        for child, item in nested:
            _json_blocks(item, child, blocks, level + 1)
        return
    if isinstance(value, list):
        blocks.append(Block("heading", path, None, level=level, locator={"path": path}))
        scalars = []
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            if isinstance(item, (dict, list)):
                if scalars:
                    blocks.append(Block("record", "\n".join(scalars), None, locator={"path": path}))
                    scalars = []
                _json_blocks(item, child, blocks, level + 1)
            else:
                scalars.append(f"[{index}]：{_json_scalar(item)}")
        if scalars:
            blocks.append(Block("record", "\n".join(scalars), None, locator={"path": path}))
        return
    blocks.append(Block("record", f"{path}：{_json_scalar(value)}", None, locator={"path": path}))


def _json_scalar(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _receipt(path: Path):
    from app.services.ocr import ocr_image_detail
    from app.services.semantic import Block, parse_page

    recognized = ocr_image_detail(path.read_bytes())
    if not recognized.text.strip():
        return []
    blocks = [Block("heading", "票据", 1, level=1)]
    fields = _receipt_fields(recognized.text)
    if fields:
        body = "\n".join(f"{label}：{value}" for label, value in fields)
        blocks.append(Block("record", body, 1, locator={"type": "receipt_fields"}))
    blocks.extend(block for block in parse_page(recognized.text, 1) if block.kind != "heading")
    return [_page("", blocks, "receipt", 1, recognized.confidence, recognized.regions)]


def _receipt_fields(text: str) -> list[tuple[str, str]]:
    found = []
    for label, pattern in _RECEIPT_FIELDS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip(" ：:，,。")
        if value and value not in {item[1] for item in found}:
            found.append((label, value))
    return found
