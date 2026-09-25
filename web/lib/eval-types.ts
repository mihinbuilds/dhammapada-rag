/** Loose shapes for data/eval/*.json, matching what
 * eval/aggregate_retrieval.py and aggregate_generation.py actually write.
 * Kept separate from lib/api.ts's EvalSummaryOut (which deliberately types
 * these as Record<string, unknown> -- see that file's docstring) since the
 * page needs concrete field access; every read still goes through
 * lib/format.ts's fmt()/pct() so a missing field renders "n/a" rather than
 * throwing, matching ui/app.py's defensive .get() reads. */

export interface MetricSet {
  "recall@1"?: number;
  "recall@3"?: number;
  "recall@5"?: number;
  "recall@10"?: number;
  "ndcg@10"?: number;
  mrr?: number;
}

export interface RetrievalMetrics {
  n_questions?: number;
  overall?: { baseline?: MetricSet } & Record<string, MetricSet | undefined>;
  by_type?: Record<string, { n: number } & Record<string, MetricSet | number>>;
  by_subtype?: Record<string, { n?: number; baseline?: MetricSet }>;
  ablation_deltas_ndcg10?: Record<string, { delta: number; ci: [number, number] }>;
}

export interface GenerationMetrics {
  n_questions?: number;
  n_claims?: number;
  provenance_errors?: number;
  accuracy?: number;
  macro_f1?: number;
  conflation_rate?: number;
  commentary_tagged_verse?: number;
  verse_tagged_commentary?: number;
  confusion_matrix?: Record<string, Record<string, number>>;
  per_class?: Record<string, { precision?: number; recall?: number; f1?: number; support?: number }>;
  context_utilization?: {
    mean?: number;
    n_fully_accounted?: number;
    n_questions?: number;
  } | null;
  layer_count_distribution?: Record<string, number>;
  claims_per_answer?: { mean?: number };
  source_fidelity_rate?: number;
  pali_fidelity?: {
    n_pali_claims?: number;
    exact_copy_rate?: number;
    variant_rate?: number;
    fabrication_rate?: number;
    quote_coverage_rate?: number;
  } | null;
}
