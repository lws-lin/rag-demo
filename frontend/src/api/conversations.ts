import type { ChatMessage, Conversation } from "@/types";
import { http } from "./http";

export async function listConversations() {
  const { data } = await http.get<Conversation[]>("/conversations");
  return data;
}

export async function createConversation(payload: { title: string }) {
  const { data } = await http.post<Conversation>("/conversations", payload);
  return data;
}

export async function deleteConversation(conversationId: string) {
  await http.delete(`/conversations/${conversationId}`);
}

export async function listMessages(conversationId: string) {
  const { data } = await http.get<ChatMessage[]>(`/conversations/${conversationId}/messages`);
  return data;
}

export async function sendMessage(
  conversationId: string,
  content: string,
  onDelta: (text: string) => void,
) {
  const token = localStorage.getItem("token");
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
  });
  if (response.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    if (window.location.pathname !== "/login") window.location.assign("/login");
    throw new Error("请先登录");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      detail = "";
    }
    throw new Error(detail || "消息发送失败");
  }
  if (!response.body) throw new Error("消息发送失败");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let turn: { user_message: ChatMessage; assistant_message: ChatMessage } | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((item) => item.startsWith("data:"));
      if (!line) continue;
      const event = JSON.parse(line.slice(5).trim()) as {
        type?: string;
        text?: string;
        detail?: string;
        user_message?: ChatMessage;
        assistant_message?: ChatMessage;
      };
      if (event.type === "delta" && event.text) onDelta(event.text);
      if (event.type === "error") throw new Error(event.detail || "消息发送失败");
      if (event.type === "done" && event.user_message && event.assistant_message) {
        turn = { user_message: event.user_message, assistant_message: event.assistant_message };
      }
    }
  }
  if (!turn) throw new Error("对话没有完成，消息没有保存");
  return turn;
}
