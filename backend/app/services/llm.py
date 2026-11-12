"""通过 OpenAI 兼容接口调用对话模型。"""

import json
import urllib.error
import urllib.request

from app.config import settings

_TIMEOUT = 90


class ChatModelError(Exception):
    pass


def chat_configured() -> bool:
    return bool(settings.chat_base_url.strip() and settings.chat_api_key.strip() and settings.chat_model.strip())


# 放得下时，历史原样带上。超出后保留最近约 1.2 万字，更早的内容压成摘要。
_HISTORY_BUDGET = 32000
_RECENT_BUDGET = 12000
_MESSAGE_CAP = 4000


def is_long_text(text: str) -> bool:
    return len(text.strip()) > _MESSAGE_CAP


def clip_history(history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], bool]:
    """从最近一条往回装入历史，直到字数预算用完。返回截取结果，以及是否丢掉了更早的消息。"""
    chosen: list[tuple[str, str]] = []
    used = 0
    stopped = False
    for role, text in reversed(history):
        piece = text.strip()
        if not piece:
            continue
        if len(piece) > _MESSAGE_CAP:
            piece = piece[:_MESSAGE_CAP] + "…"
        if chosen and used + len(piece) > _HISTORY_BUDGET:
            stopped = True
            break
        chosen.append((role, piece))
        used += len(piece)
    chosen.reverse()
    if stopped and chosen and chosen[0][0] == "assistant":
        chosen = chosen[1:]
    return chosen, stopped


def split_recent(history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """返回更早的对话和需要原样保留的最近对话。最近部分从用户的一句开始。"""
    if not history:
        return [], []
    total = sum(len(text) for _role, text in history)
    if total <= _HISTORY_BUDGET and all(len(text) <= _MESSAGE_CAP for _role, text in history):
        return [], list(history)
    chosen: list[tuple[str, str]] = []
    used = 0
    for item in reversed(history):
        _role, text = item
        if chosen and used + len(text) > _RECENT_BUDGET:
            break
        chosen.append(item)
        used += len(text)
    chosen.reverse()
    if chosen and chosen[0][0] == "assistant":
        chosen = chosen[1:]
    older_count = len(history) - len(chosen)
    return history[:older_count], chosen


def compress_passage(role: str, text: str) -> str:
    """把一条过长的消息压成摘要。原文仍留在数据库里。"""
    speaker = "用户" if role == "user" else "助手"
    messages = [
        {
            "role": "system",
            "content": "把下面这一条对话压成简短记录。保留人名、文档名、页码、数字、结论和未完成的问题。用中文，不要寒暄，控制在 400 字以内。",
        },
        {"role": "user", "content": f"{speaker}：{text.strip()}"},
    ]
    brief = complete_chat(messages)
    if not brief:
        raise ChatModelError("对话压缩没有返回内容")
    return brief


def compress_turns(previous: str, turns: list[tuple[str, str]]) -> str:
    """把已有摘要和新增的早期对话合并成一段新摘要。"""
    parts: list[str] = []
    if previous.strip():
        parts.append("已有摘要：\n" + previous.strip())
    lines = []
    for role, text in turns:
        speaker = "用户" if role == "user" else "助手"
        lines.append(f"{speaker}：{text.strip()}")
    parts.append("新增对话：\n" + "\n".join(lines))
    messages = [
        {
            "role": "system",
            "content": "把已有摘要和新增对话合并成一段新的摘要。保留文档名、页码、数字、结论、用户要求和尚未回答的问题。用中文，不要寒暄，控制在 800 字以内。",
        },
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    summary = complete_chat(messages)
    if not summary:
        raise ChatModelError("对话压缩没有返回内容")
    return summary


def conversation_messages(
    mode: str,
    history: list[tuple[str, str]],
    content: str,
    evidence: str,
    *,
    summary: str = "",
    history_truncated: bool = False,
) -> list[dict]:
    name = settings.chat_model.strip() or "未配置"
    system = (
        f"你是医疗机构知识库的对话助手，当前接入的模型是 {name}。"
        "用户问你是什么模型时，直接说这个名称。"
        "用中文回答，写成正常对话，不要把资料整段照抄。"
    )
    if summary.strip():
        system += "此前对话已压缩为下面的记录，回答时要承接这些内容：\n" + summary.strip()
    elif history_truncated:
        system += "更早的对话没有放进这次请求。没有看到的内容不要当成没有发生过。"
    if mode == "qa":
        system += "回答资料问题时只根据本次给出的已发布原文，原文没有的事实不要编。原文不够时说明资料里没有。提到依据时带上文档名和页码。"
    elif mode == "proposal":
        system += "用户在做出方案。现在不能生成 PPT 或图像，用文字说明。如果给出了原文，其中的事实以原文为准。"
    else:
        system += "这是日常对话，不要假装查过知识库。"
    messages: list[dict] = [{"role": "system", "content": system}]
    for role, text in history:
        messages.append({"role": role, "content": text})
    if mode == "chat":
        messages.append({"role": "user", "content": content})
        return messages
    source = evidence.strip() or "（没有检索到可用的已发布原文）"
    messages.append({"role": "user", "content": f"问题：{content}\n\n已发布原文：\n{source}"})
    return messages


def complete_chat(messages: list[dict]) -> str:
    if not chat_configured():
        raise ChatModelError("还没有配置对话模型。请在 .env 填写 CHAT_BASE_URL、CHAT_API_KEY 和 CHAT_MODEL")
    request = _request(messages, stream=False)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise ChatModelError(_http_error(exc)) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise ChatModelError("对话模型没有及时返回") from exc
    except json.JSONDecodeError as exc:
        raise ChatModelError("对话模型返回的内容无法解析") from exc
    choices = body.get("choices") if isinstance(body, dict) else None
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    if not isinstance(message, dict):
        return ""
    return str(message.get("content") or "").strip()


def stream_chat(messages: list[dict]):
    if not chat_configured():
        raise ChatModelError("还没有配置对话模型。请在 .env 填写 CHAT_BASE_URL、CHAT_API_KEY 和 CHAT_MODEL")
    request = _request(messages, stream=True)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            for line in response:
                text = _delta(line)
                if text:
                    yield text
    except urllib.error.HTTPError as exc:
        raise ChatModelError(_http_error(exc)) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise ChatModelError("对话模型没有及时返回") from exc


def _request(messages: list[dict], stream: bool) -> urllib.request.Request:
    url = settings.chat_base_url.strip().rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {
            "model": settings.chat_model.strip(),
            "messages": messages,
            "temperature": 0.3,
            "stream": stream,
        },
        ensure_ascii=False,
    ).encode()
    return urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.chat_api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _delta(raw: bytes) -> str:
    line = raw.decode().strip()
    if not line.startswith("data:"):
        return ""
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return ""
    try:
        body = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ChatModelError("对话模型返回的内容无法解析") from exc
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and error.get("message"):
        raise ChatModelError(f"对话模型调用失败：{str(error['message'])[:180]}")
    choices = body.get("choices") if isinstance(body, dict) else None
    if not choices or not isinstance(choices[0], dict):
        return ""
    delta = choices[0].get("delta") or {}
    if not isinstance(delta, dict):
        return ""
    return str(delta.get("content") or "")


def _http_error(exc: urllib.error.HTTPError) -> str:
    if exc.code in {401, 403}:
        return "对话模型的密钥无效"
    try:
        payload = json.loads(exc.read().decode())
    except Exception:
        payload = {}
    message = ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message") or "")
    if message:
        return f"对话模型调用失败：{message[:180]}"
    return "对话模型调用失败"
