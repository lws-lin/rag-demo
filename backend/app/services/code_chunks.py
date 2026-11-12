import re

_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.S)
_STYLE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.I | re.S)
_NUMBER = re.compile(r"\d{1,3}")

_ALIASES = {
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "py": "python",
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "css": "css",
    "html": "html",
    "htm": "html",
}

_HARD = {
    "javascript": {
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "method_definition",
        "export_statement",
    },
    "typescript": {
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "method_definition",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    },
    "tsx": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "export_statement",
    },
    "python": {"function_definition", "class_definition", "decorated_definition"},
    "css": {"rule_set", "qualified_rule", "at_rule", "keyframes_statement"},
    "html": {"element", "script_element", "style_element"},
}

_BODY = {"class_body", "statement_block", "block", "declaration_list"}

_LANGUAGES = {
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "python": ("tree_sitter_python", "language"),
    "css": ("tree_sitter_css", "language"),
    "html": ("tree_sitter_html", "language"),
}

_PARSERS: dict = {}


def _parser(language: str):
    cached = _PARSERS.get(language)
    if cached is not None:
        return cached
    import importlib

    from tree_sitter import Language, Parser

    module_name, factory = _LANGUAGES[language]
    module = importlib.import_module(module_name)
    parser = Parser(Language(getattr(module, factory)()))
    _PARSERS[language] = parser
    return parser


def split_document(text: str, size: int, overlap: int, split_prose) -> tuple[str, list[tuple[str, list[tuple[int, int]]]]]:
    """代码按语法树切，表格和正文仍走原来的规则。返回清理后的页文本和片段位置。"""
    from app.services.text import clean_text, normalize_mapped

    cleaned = clean_text(text)
    pieces: list[tuple[str, list[tuple[int, int]]]] = []
    for kind, mapped, language in _segments(cleaned):
        if kind == "prose":
            normalized = normalize_mapped(mapped)
            if not normalized.text:
                continue
            for content, spans in split_prose(normalized.text, size, overlap):
                if content.strip():
                    pieces.append((content, normalized.locate_all(spans)))
            continue
        for content, spans in chunk_code(mapped.text, language, size):
            if content.strip():
                pieces.append((content, mapped.locate_all(spans)))
    return cleaned, pieces


def chunk_code(code: str, language: str, size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    language = _language(language, code)
    lead = len(code) - len(code.lstrip("\n"))
    source = code.strip("\n")
    if not source:
        return []

    def shift(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(lead + start, lead + end) for start, end in spans]

    try:
        parser = _parser(language)
        data = source.encode()
        tree = parser.parse(data)
    except Exception:
        return [(content, shift(spans)) for content, spans in _plain(source, language, size)]
    if _error_ratio(tree.root_node) > 0.3:
        return [(content, shift(spans)) for content, spans in _plain(source, language, size)]
    units = _units(tree.root_node, data, language, size)
    if not units:
        return [(content, shift(spans)) for content, spans in _plain(source, language, size)]
    shifted = []
    for content, spans in _pack(units, size):
        if content.strip():
            shifted.append((_fence(language, content), shift(spans)))
    return shifted


def _segments(text: str):
    from app.services.text import SpanMap

    regions: list[tuple[int, int, int, str, str]] = []
    for match in _FENCE.finditer(text):
        regions.append((match.start(), match.end(), match.start(2), match.group(1).strip().lower(), match.group(2)))
    for match in _STYLE.finditer(text):
        regions.append((match.start(), match.end(), match.start(1), "css", match.group(1)))
    for match in _SCRIPT.finditer(text):
        regions.append((match.start(), match.end(), match.start(1), "javascript", match.group(1)))
    regions.sort(key=lambda item: item[0])
    cursor = 0
    for start, end, code_at, language, code in regions:
        if start < cursor:
            continue
        if start > cursor:
            yield from _heuristic(text[cursor:start], cursor)
        yield "code", SpanMap.identity(code, code_at), _language(language, code)
        cursor = end
    if cursor < len(text):
        yield from _heuristic(text[cursor:], cursor)


def _heuristic(text: str, base: int):
    entries = _line_entries(text, base)
    prose: list[tuple[str, int]] = []
    index = 0
    while index < len(entries):
        if not _is_code_line(entries[index][0]):
            prose.append(entries[index])
            index += 1
            continue
        start = index
        code_lines = 0
        while index < len(entries):
            if _is_code_line(entries[index][0]) or _indented_code(entries[index][0]):
                code_lines += 1
                index += 1
                continue
            if _is_noise(entries[index][0]) and _ahead_is_code([line for line, _ in entries], index):
                index += 1
                continue
            break
        source = _map_lines(entries[start:index], drop_numbers=True).strip()
        if code_lines >= 2 or ("{" in source.text and "}" in source.text):
            blob = _map_lines(prose, drop_numbers=True)
            prose = []
            if blob.text.strip():
                yield "prose", blob, ""
            yield "code", source, _guess_language(source.text)
        else:
            prose.extend(entries[start:index])
    blob = _map_lines(prose, drop_numbers=True)
    if blob.text.strip():
        yield "prose", blob, ""


def _line_entries(text: str, base: int) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    cursor = 0
    lines = text.split("\n")
    for index, line in enumerate(lines):
        entries.append((line, base + cursor))
        cursor += len(line)
        if index < len(lines) - 1:
            cursor += 1
    return entries


def _map_lines(lines: list[tuple[str, int]], drop_numbers: bool):
    from app.services.text import SpanMap

    kept = [(line, start) for line, start in lines if not (drop_numbers and _is_number(line))]
    chars: list[str] = []
    indexes: list[int] = []
    for index, (line, start) in enumerate(kept):
        if index:
            chars.append("\n")
            indexes.append(start - 1 if start > 0 else start)
        for offset, char in enumerate(line):
            chars.append(char)
            indexes.append(start + offset)
    return SpanMap("".join(chars), indexes).strip()


def _is_number(line: str) -> bool:
    return _NUMBER.fullmatch(line.strip()) is not None


def _is_noise(line: str) -> bool:
    return not line.strip() or _is_number(line)


def _ahead_is_code(lines: list[str], index: int) -> bool:
    cursor = index
    while cursor < len(lines) and _is_noise(lines[cursor]):
        cursor += 1
    return cursor < len(lines) and (_is_code_line(lines[cursor]) or _indented_code(lines[cursor]))


def _indented_code(line: str) -> bool:
    if not line.startswith((" ", "\t")) or not line.strip():
        return False
    stripped = line.strip()
    if stripped.startswith(("//", "/*", "*", "#")):
        return True
    if re.search(r"[\u4e00-\u9fff]", stripped) and not re.search(r"[{}();]|=>", stripped):
        return False
    return True


def _is_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _is_number(stripped) or " | " in stripped:
        return False
    if stripped.startswith(("//", "/*", "*/")):
        return True
    has_cjk = re.search(r"[\u4e00-\u9fff]", stripped) is not None
    if stripped.startswith("#") and not has_cjk:
        return True
    syntactic = bool(re.search(r"[{};]|=>", stripped) or re.search(r"</?[A-Za-z][^>]*>", stripped))
    if has_cjk and not syntactic:
        return False
    if re.search(r"\b(function|const|let|var|class|import|export|return|async|await|def)\b", stripped):
        return True
    if "=>" in stripped or stripped in {"{", "}"} or stripped.endswith(("{", "}")):
        return True
    if re.search(r"</?[A-Za-z][^>]*>", stripped):
        return True
    head = stripped.split("(", 1)[0]
    if re.match(r"[A-Za-z_$][\w$.]*\s*\(", stripped) and ("." in head or stripped.endswith(";")):
        return True
    if re.match(r"[.#]?[A-Za-z_-][\w-]*\s*:", stripped) and stripped.endswith(";"):
        return True
    return syntactic and not has_cjk


def _language(hint: str, code: str) -> str:
    hinted = _ALIASES.get(hint.lower(), hint.lower())
    if hinted in _HARD:
        return hinted
    return _guess_language(code)


def _guess_language(code: str) -> str:
    if re.search(r"\b(const|let|function|require|export)\b", code) or "=>" in code:
        return "javascript"
    if re.search(r"^\s*(def|class)\s+\w+", code, re.M) and "function" not in code:
        return "python"
    if re.search(r"</?[A-Za-z][^>]*>", code):
        return "html"
    return "css"


def _units(root, data: bytes, language: str, size: int) -> list[dict]:
    from app.services.text import merge_spans

    hard_types = _HARD.get(language, set())
    units: list[dict] = []
    pending: list[tuple[str, tuple[int, int]]] = []
    for child in root.children:
        start, end, text = _bounds(data, child)
        if not text.strip():
            continue
        if child.type == "comment":
            pending.append((text, (start, end)))
            continue
        spans = [(start, end)]
        if pending:
            text = "\n".join([item[0] for item in pending] + [text])
            spans = [(pending[0][1][0], end)]
            pending.clear()
        hard = child.type in hard_types or any(item.type in hard_types for item in child.children)
        parts = _split_large(child, data, language, "", [], size) if hard and len(text) > size else []
        units.append({"text": text, "hard": hard, "parts": parts, "spans": merge_spans(spans)})
    if pending:
        units.append(
            {
                "text": "\n".join(item[0] for item in pending),
                "hard": False,
                "parts": [],
                "spans": merge_spans([item[1] for item in pending]),
            }
        )
    return units


def _split_large(
    node,
    data: bytes,
    language: str,
    prefix: str,
    prefix_spans: list[tuple[int, int]],
    size: int,
) -> list[tuple[str, list[tuple[int, int]]]]:
    from app.services.text import merge_spans

    start, end, text = _bounds(data, node)
    if not text.strip():
        return []
    header = _header(text, language)
    context = f"{prefix}\n{header}".strip() if prefix else header
    header_end = start + len(header) if text.startswith(header) else end
    header_span = (start, header_end)
    own = [(start, end)]
    if len(text) <= size or _body(node) is None:
        wrapped = _wrap(prefix, text, language) if prefix and not text.startswith(prefix) else text
        return [(wrapped, merge_spans([*prefix_spans, *own]))]
    body = _body(node)
    children = [child for child in body.children if child.is_named and child.type not in _BODY and _bounds(data, child)[2].strip()]
    if not children:
        wrapped = _wrap(prefix, text, language) if prefix else text
        return [(wrapped, merge_spans([*prefix_spans, *own]))]
    hard_types = _HARD.get(language, set())
    context_spans = merge_spans([*prefix_spans, header_span])
    pieces: list[tuple[str, list[tuple[int, int]]]] = []
    current: list[tuple[str, tuple[int, int]]] = []
    current_len = len(context)

    def emit() -> None:
        nonlocal current_len
        if current:
            body_text = "\n".join(item[0] for item in current)
            spans = merge_spans([*context_spans, *(item[1] for item in current)])
            pieces.append((_wrap(context, body_text, language), spans))
            current.clear()
            current_len = len(context)

    for child in children:
        child_start, child_end, child_text = _bounds(data, child)
        if not child_text.strip():
            continue
        nested = child.type in hard_types and len(child_text) > size and _body(child) is not None
        if nested:
            emit()
            pieces.extend(_split_large(child, data, language, context, context_spans, size))
            continue
        if current and current_len + len(child_text) + 1 > size:
            emit()
        current.append((child_text, (child_start, child_end)))
        current_len += len(child_text) + 1
    emit()
    return pieces or [(text, merge_spans([*prefix_spans, *own]))]


def _pack(units: list[dict], size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    from app.services.text import merge_spans

    chunks: list[tuple[str, list[tuple[int, int]]]] = []
    buffer: list[dict] = []
    length = 0

    def flush() -> None:
        nonlocal length
        if buffer:
            chunks.append(("\n\n".join(item["text"] for item in buffer), merge_spans([span for item in buffer for span in item["spans"]])))
            buffer.clear()
            length = 0

    for unit in units:
        text = unit["text"]
        if unit["hard"] and len(text) > size:
            flush()
            chunks.extend(unit["parts"] or [(text, unit["spans"])])
            continue
        if length and length + len(text) + 2 > size:
            flush()
        buffer.append(unit)
        length += len(text) + 2
    flush()
    return chunks


def _wrap(header: str, body: str, language: str) -> str:
    if language == "python":
        return f"{header}\n{body}".rstrip()
    if header.rstrip().endswith("{"):
        return f"{header}\n{body}\n}}".rstrip()
    return f"{header}\n{body}".rstrip()


def _header(text: str, language: str) -> str:
    if language == "python":
        lines = []
        for line in text.splitlines():
            lines.append(line)
            if line.rstrip().endswith(":"):
                break
        return "\n".join(lines)
    brace = text.find("{")
    if 0 <= brace <= 180:
        return text[: brace + 1].rstrip()
    lines = text.splitlines()
    return lines[0] if lines else text


def _body(node):
    for child in node.children:
        if child.type in _BODY:
            return child
    return None


def _bounds(data: bytes, node) -> tuple[int, int, str]:
    start_byte = node.start_byte
    while start_byte > 0 and data[start_byte - 1 : start_byte] in {b" ", b"\t"}:
        start_byte -= 1
    raw = data[start_byte : node.end_byte].decode("utf-8", errors="replace")
    lead = len(raw) - len(raw.lstrip("\r\n"))
    trail = len(raw) - len(raw.rstrip("\r\n"))
    text = raw[lead : len(raw) - trail if trail else len(raw)]
    char_start = len(data[:start_byte].decode("utf-8", errors="replace")) + lead
    char_end = len(data[: node.end_byte].decode("utf-8", errors="replace")) - trail
    return char_start, char_end, text


def _error_ratio(node) -> float:
    nodes = 0
    errors = 0
    stack = [node]
    while stack:
        current = stack.pop()
        nodes += 1
        if current.type == "ERROR" or current.is_missing:
            errors += 1
        stack.extend(current.children)
    return 1 if nodes == 0 else errors / nodes


def _plain(source: str, language: str, size: int) -> list[tuple[str, list[tuple[int, int]]]]:
    from app.services.text import windows_with_spans

    return [(_fence(language, piece), [(start, end)]) for piece, start, end in windows_with_spans(source, size, 0)]


def _fence(language: str, code: str) -> str:
    return f"```{language}\n{code.strip()}\n```"
