import type { DocumentItem, DocumentList } from "@/types";
import { http } from "./http";

export async function listDocuments(params: { category?: string; status?: string; q?: string; page?: number; page_size?: number }) {
  const { data } = await http.get<DocumentList>("/documents", { params });
  return data;
}

export async function uploadDocument(file: File, category: string) {
  const body = new FormData();
  body.append("file", file);
  body.append("category", category);
  const { data } = await http.post<DocumentItem>("/documents", body, { timeout: 120000 });
  return data;
}
