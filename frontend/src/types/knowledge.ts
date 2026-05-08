export type DocumentStatus = "pending" | "indexing" | "indexed" | "failed";

export interface KnowledgeDocument {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  file_type: string;
  file_size: number | null;
  status: DocumentStatus;
  chunk_count: number;
  is_active: boolean;
  module: string | null;
  vendor: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeStats {
  total_documents: number;
  total_chunks: number;
  by_status: Record<string, number>;
}

export interface SearchResult {
  query: string;
  context: string;
  chunk_count: number;
}
