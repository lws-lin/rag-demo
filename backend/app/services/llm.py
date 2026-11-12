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


def conversation_messages(mode: str, history: list[tuple[str, str]], content: str, evidence: str) -> list[dict]:
    name = settings.chat_model.strip() or "未配置"
    system = (
        f"你是医疗机构知识库的对话助手，当前接入的模型是 {name}。"
        "用户问你是什么模型时，直接说这个名称。"
        "用中文回答，写成正常对话，不要把资料整段照抄。"
    )
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
