import type { DocumentDetail, DocumentItem, DocumentList, DocumentReviewPayload } from "@/types";
import { http } from "./http";

export async function listDocuments(params: { category?: string; status?: string; q?: string; page?: number; page_size?: number }) {
  const { data } = await http.get<DocumentList>("/documents", { params });
  return data;
}

export async function getDocument(id: string) {
  const { data } = await http.get<DocumentDetail>(`/documents/${id}`);
  return data;
}

export async function fetchDocumentFile(id: string) {
  const { data } = await http.get<Blob>(`/documents/${id}/file`, { responseType: "blob", timeout: 120000 });
  return data;
}

export async function reviewDocument(id: string, payload: DocumentReviewPayload) {
  const { data } = await http.post<DocumentDetail>(`/documents/${id}/review`, payload, { timeout: 120000 });
  return data;
}

export async function uploadDocument(file: File, category: string) {
  const body = new FormData();
  body.append("file", file);
  body.append("category", category);
  const { data } = await http.post<DocumentItem>("/documents", body, { timeout: 120000 });
  return data;
}
