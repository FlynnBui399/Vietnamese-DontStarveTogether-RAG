export type Confidence = "high" | "medium" | "low" | "none";

export type Citation = {
  id: string;
  chunk_id: string;
  page_title: string;
  section: string;
  url: string;
  revision_id: number;
  retrieved_at: string | null;
  corpus_version: string;
  content: string;
  source_kind: string;
  subjective: boolean;
};

export type ResolvedEntity = {
  entity_title: string;
  entity_slug: string;
  matched_alias: string;
  alias_type: string;
  match_type: string;
  verified: boolean;
  confidence: number;
};

export type SourceConflict = {
  page_title: string;
  field: string;
  values: string[];
  source_ids: string[];
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  resolved_entities: ResolvedEntity[];
  confidence: Confidence;
  abstained: boolean;
  abstention_reason: string | null;
  corpus_version: string | null;
  subjective_warning: boolean;
  conflicts: SourceConflict[];
  latency_ms: {
    supabase_retrieval: number;
    rerank_and_context: number;
    generation: number;
    total: number;
  };
};

export type CorpusStatus = {
  available: boolean;
  version: string | null;
  page_count: number;
  chunk_count: number;
  embedding_model: string | null;
  activated_at: string | null;
  last_sync_at: string | null;
};
