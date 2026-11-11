export interface User {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "user" | "auditor";
}

export interface DocumentItem {
  id: string;
  title: string;
  category: string;
  status: string;
  original_filename: string;
  chunk_count: number;
  doc_number: string | null;
  publisher: string | null;
  effective_date: string | null;
  effective_status: string | null;
  quality_score: number | null;
  reject_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Conversation {
  id: string;
  title: string;
  mode: "qa" | "proposal" | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: unknown[] | null;
  created_at: string;
}
