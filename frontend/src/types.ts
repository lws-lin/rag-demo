import type { DocumentStatus, ReviewDecision } from "@/statuses";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "user";
  created_at?: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  category: string;
  status: DocumentStatus;
  original_filename: string;
  chunk_count: number;
  doc_number: string | null;
  publisher: string | null;
  effective_date: string | null;
  effective_status: string | null;
  quality_score: number | null;
  reject_reason: string | null;
  access_roles: string[];
  created_at: string;
  updated_at: string;
}

export interface SourceSpan {
  start: number;
  end: number;
}

export interface ChunkRegion {
  text?: string;
  x0?: number;
  y0?: number;
  x1?: number;
  y1?: number;
  score?: number;
  sheet?: string;
  row_start?: number;
  row_end?: number;
  path?: string;
  slide?: number;
  kind?: string;
  type?: string;
}

export interface DocumentChunk {
  ordinal: number;
  content: string;
  page_number: number | null;
  page_end: number | null;
  heading_path: string[] | null;
  block_kind: string | null;
  quality_flags: string[] | null;
  char_count: number;
  source_spans: SourceSpan[] | null;
  extraction_method: string | null;
  language: string | null;
  ocr_confidence: number | null;
  regions: ChunkRegion[] | null;
  parent_id: string | null;
  previous_id: string | null;
  next_id: string | null;
}

export interface DocumentPage {
  page_number: number | null;
  content: string;
  extraction_method: string | null;
  language: string | null;
  ocr_confidence: number | null;
  regions: ChunkRegion[] | null;
}

export interface DocumentDetail extends DocumentItem {
  chunks: DocumentChunk[];
  pages: DocumentPage[];
}

export interface DocumentReviewPayload {
  doc_number: string;
  publisher: string;
  effective_date: string | null;
  effective_status: "current" | "abolished" | "draft" | null;
  decision: ReviewDecision;
  reject_reason: string;
  access_roles: string[];
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

export interface Citation {
  document_id: string;
  title: string;
  filename: string;
  page_number: number | null;
  page_end: number | null;
  heading_path: string[];
  ordinal: number;
  effective_status: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}
