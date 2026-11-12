"""根据已发布原文组织回答。出方案只判断意图，不生成 PPT 或图像。"""

import re

from app.services.vectors import SearchHit

_PROPOSAL = re.compile(
    r"(出方案|做成方案|写一份方案|生成方案|做个方案|做一个方案|生成\s*PPT|做成\s*PPT|做一版\s*PPT|幻灯片|效果图)",
    re.I,
)
_GREETING = re.compile(r"^(?:你好|您好|嗨|hi|hello|在吗|在不在)[啊呀吗呢!！。~\s]*$", re.I)
_THANKS = re.compile(r"^(?:谢谢|多谢|感谢)(?:你|了)?[啊呀!！。~\s]*$", re.I)
_BYE = re.compile(r"^(?:再见|拜拜)[啊呀!！。~\s]*$", re.I)
_ABOUT_SELF = re.compile(r"你(?:是谁|叫什么|能做什么|会做什么|可以做什么|是做什么)|介绍一下你|自我介绍")
_ABOUT_MODEL = re.compile(r"你(?:是|用|背后|属于).{0,8}(?:什么|哪个|啥)|(?:什么|哪个)大模型")
_LIMIT = 4


def intent_of(text: str) -> str:
    if _PROPOSAL.search(text):
        return "proposal"
    if _is_chat(text):
        return "chat"
    return "qa"


def _is_chat(text: str) -> bool:
    raw = text.strip()
    if _GREETING.match(raw) or _THANKS.match(raw) or _BYE.match(raw):
        return True
    if _ABOUT_SELF.search(raw):
        return True
    if re.search(r"你", raw) and _ABOUT_MODEL.search(raw) and not re.search(r"文档|资料|原文|规定|制度|面试", raw):
        return True
    return False


def _score(hit: SearchHit) -> float:
    return hit.distance - (0.22 if hit.keyword else 0)


def select_hits(hits: list[SearchHit]) -> list[SearchHit]:
    ordered = sorted(hits, key=_score)
    if not ordered:
        return []
    best = _score(ordered[0])
    if best > 0.50:
        return []
    chosen: list[SearchHit] = []
    for hit in ordered:
        if chosen and _score(hit) > best + 0.10:
            break
        if hit.distance > 0.68:
            break
        chosen.append(hit)
        if len(chosen) >= _LIMIT:
            break
    return chosen


def _place(hit: SearchHit) -> str:
    chunk = hit.chunk
    if not chunk.page_number:
        return ""
    unit = "张" if hit.document.original_filename.lower().endswith(".pptx") else "页"
    if chunk.page_end and chunk.page_end != chunk.page_number:
        return f"第{chunk.page_number}–{chunk.page_end}{unit}"
    return f"第{chunk.page_number}{unit}"


def _status_note(status: str | None) -> str:
    if status == "abolished":
        return "已废止"
    if status == "draft":
        return "草案"
    return ""


def citation_of(hit: SearchHit) -> dict:
    return {
        "document_id": str(hit.document.id),
        "title": hit.document.title,
        "filename": hit.document.original_filename,
        "page_number": hit.chunk.page_number,
        "page_end": hit.chunk.page_end,
        "heading_path": list(hit.chunk.heading_path or []),
        "ordinal": hit.chunk.ordinal,
        "effective_status": hit.document.effective_status,
    }


def prepare_sources(hits: list[SearchHit]) -> tuple[str, list[dict]]:
    chosen = select_hits(hits)
    blocks = []
    citations = []
    for index, hit in enumerate(chosen, start=1):
        parts = [f"[{index}] {hit.document.title}"]
        place = _place(hit)
        if place:
            parts.append(place)
        path = " / ".join(hit.chunk.heading_path or [])
        if path:
            parts.append(path)
        note = _status_note(hit.document.effective_status)
        if note:
            parts.append(note)
        blocks.append(" · ".join(parts) + "\n" + hit.chunk.content.strip())
        citations.append(citation_of(hit))
    return "\n\n".join(blocks), citations
