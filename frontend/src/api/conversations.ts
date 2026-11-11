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

export async function sendMessage(conversationId: string, content: string) {
  const { data } = await http.post<{ user_message: ChatMessage; assistant_message: ChatMessage }>(
    `/conversations/${conversationId}/messages`,
    { content },
  );
  return data;
}
