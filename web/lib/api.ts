/**
 * Typed client for the Dhammapada RAG FastAPI service
 * (src/dhammapada_rag/api/{main,schemas}.py). Interfaces below hand-mirror
 * the Pydantic response models field-for-field rather than generating a
 * client, since the service is small and stable enough that keeping the two
 * in sync by hand is cheaper than adding a codegen step.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Layer = "verse" | "commentary" | "alignment" | "note" | "synthesis";
export type Severity = "error" | "warning" | "info";
export type Disposition = "used" | "partially_relevant" | "not_relevant";

export interface VerseOut {
  verse: number;
  vagga_number: number;
  vagga_name_pali: string;
  vagga_name_en: string;
  interlinear_pali: string | null;
  interlinear_english: string | null;
  interlinear_notes: string[];
  narrative_pali: string | null;
  narrative_english: string | null;
  narrative_source_group_id: string | null;
  story_group_ids: string[];
}

export interface FootnoteOut {
  marker: string;
  source: string;
  text: string;
}

export interface StoryOut {
  group_id: string;
  vagga_number: number;
  story_number: number;
  dhp_verses: number[];
  title_en: string;
  title_pali: string | null;
  cst4_title: string | null;
  burlingame_title: string | null;
  compare: string | null;
  synopsis: string | null;
  cast: string | null;
  keywords: string[];
  rating: number | null;
  pali_verse: string | null;
  english_verse: string | null;
  pali_verse_number: number | null;
  nidana: string | null;
  vatthu: string;
  desanavasane: string | null;
  footnotes: FootnoteOut[];
}

export interface MatchedChunkOut {
  chunk_id: string;
  chunk_type: string;
  text: string;
  rerank_score: number;
  window_index?: number;
  n_windows?: number;
}

export interface VerseGroupResult {
  verse_numbers: number[];
  verses: VerseOut[];
  stories: StoryOut[];
  matched_chunk: MatchedChunkOut;
}

export interface QueryResponse {
  query: string;
  results: VerseGroupResult[];
}

export interface HealthResponse {
  status: string;
  n_chunks: number;
  n_verses: number;
  n_stories: number;
}

export interface ClaimOut {
  text: string;
  layer: Layer;
  group_id?: string | null;
  verse_number?: number | null;
  pali_support?: string | null;
  verse_numbers?: number[] | null;
}

export interface WarningOut {
  code: string;
  severity: Severity;
  claim_index: number;
  message: string;
}

export interface LayerCounts {
  verse: number;
  commentary: number;
  alignment: number;
  note: number;
  synthesis: number;
}

export interface AnswerResponse {
  question: string;
  claims: ClaimOut[];
  warnings: WarningOut[];
  layer_counts: LayerCounts;
  source_disposition: Record<string, Disposition>;
  model: string;
  latency_s: number;
  prompt_tokens: number;
  num_ctx: number;
  sources: VerseGroupResult[];
}

export interface VaggaOut {
  number: number;
  name_pali: string;
  name_en: string;
  first_verse: number;
  last_verse: number;
  verse_count: number;
}

export interface EvalSummaryOut {
  retrieval: Record<string, unknown> | null;
  retrieval_v2?: Record<string, unknown> | null;
  generation: Record<string, unknown> | null;
  sweep: Record<string, unknown>[];
  retrieval_written_at?: string | null;
  retrieval_v2_written_at?: string | null;
  generation_written_at?: string | null;
  index_built_at?: string | null;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(
      0,
      `Could not reach the API at ${API_BASE}. Is \`uvicorn dhammapada_rag.api.main:app\` running?`,
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  query: (query: string, top_k = 5, candidates = 30) =>
    request<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({ query, top_k, candidates }),
    }),

  answer: (question: string, top_k = 3, candidates = 30, model?: string) =>
    request<AnswerResponse>("/answer", {
      method: "POST",
      body: JSON.stringify({ question, top_k, candidates, model: model ?? null }),
    }),

  verse: (verseNumber: number) => request<VerseOut>(`/verses/${verseNumber}`),

  story: (groupId: string) => request<StoryOut>(`/stories/${encodeURIComponent(groupId)}`),

  vaggas: () => request<VaggaOut[]>("/vaggas"),

  evalSummary: () => request<EvalSummaryOut>("/eval/summary"),
};

export const GENERATOR_MODELS = [
  "qwen2.5:7b-instruct",
  "qwen2.5:1.5b-instruct",
  "qwen2.5:14b-instruct",
];
