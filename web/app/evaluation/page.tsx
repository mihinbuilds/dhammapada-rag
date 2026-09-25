"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EvalTable } from "@/components/eval-table";
import { AblationChart, RetrievalByTypeChart } from "@/components/evaluation/retrieval-charts";
import { axisTickStyle, chartTooltipStyle } from "@/components/evaluation/chart-shell";
import { ConfusionMatrix } from "@/components/evaluation/confusion-matrix";
import { SweepChart } from "@/components/evaluation/sweep-chart";
import { MetricTiles } from "@/components/metric-tiles";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { fmt, pct } from "@/lib/format";
import type { GenerationMetrics, RetrievalMetrics } from "@/lib/eval-types";

type EvalTimes = { retrieval?: string | null; generation?: string | null; index?: string | null };

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "unknown date";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** A results file written before the index was last built describes an index that is no
 *  longer the one being served. */
function predatesIndex(written: string | null | undefined, index: string | null | undefined): boolean {
  return !!written && !!index && new Date(written) < new Date(index);
}

/** Mean F1 over layers that have gold claims. A layer with support 0 still gets F1 = 0
 *  whenever the model predicts it once, which drags the plain macro average down without
 *  measuring anything about that layer. */
function supportedMacroF1(perClass: GenerationMetrics["per_class"]): { value: number; n: number } | null {
  if (!perClass) return null;
  const f1s = Object.values(perClass)
    .filter((d) => (d.support ?? 0) > 0 && typeof d.f1 === "number")
    .map((d) => d.f1 as number);
  if (f1s.length === 0) return null;
  return { value: f1s.reduce((a, b) => a + b, 0) / f1s.length, n: f1s.length };
}

const ABLATION_LABELS: Record<string, string> = {
  verse_only: "Verse-only chunks",
  dense_only: "Dense-only (no RRF)",
  no_rerank: "No cross-encoder",
  flat: "Flat chunking",
};

export default function EvaluationPage() {
  const [retrieval, setRetrieval] = useState<RetrievalMetrics | null>(null);
  const [generation, setGeneration] = useState<GenerationMetrics | null>(null);
  const [sweep, setSweep] = useState<
    { model: string; max_retries: number; n: number; clean_rate: number; avg_latency_s: number | null }[]
  >([]);
  const [times, setTimes] = useState<EvalTimes>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .evalSummary()
      .then((d) => {
        setRetrieval((d.retrieval as RetrievalMetrics) ?? null);
        setGeneration((d.generation as GenerationMetrics) ?? null);
        setTimes({ retrieval: d.retrieval_written_at, generation: d.generation_written_at, index: d.index_built_at });
        setSweep(
          d.sweep as {
            model: string;
            max_retries: number;
            n: number;
            clean_rate: number;
            avg_latency_s: number | null;
          }[],
        );
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load evaluation data."))
      .finally(() => setLoading(false));
  }, []);

  const byTypeRows = retrieval?.by_type
    ? Object.entries(retrieval.by_type)
        .filter(([, d]) => "baseline" in d)
        .map(([type, d]) => {
          const base = (d as unknown as { n: number; baseline: Record<string, number> }).baseline;
          const n = (d as unknown as { n: number }).n;
          return {
            type,
            n,
            "recall@1": base["recall@1"] ?? 0,
            "recall@10": base["recall@10"] ?? 0,
            "ndcg@10": base["ndcg@10"] ?? 0,
            mrr: base["mrr"] ?? 0,
          };
        })
    : [];
  const substantial = byTypeRows.filter((r) => r.n >= 5);
  const worst =
    substantial.length > 0
      ? [...substantial].sort((a, b) => a["ndcg@10"] - b["ndcg@10"])[0].type
      : null;

  const ablationRows = retrieval?.ablation_deltas_ndcg10
    ? Object.entries(retrieval.ablation_deltas_ndcg10)
        .filter(([k]) => k in ABLATION_LABELS)
        .map(([key, v]) => ({
          key,
          label: ABLATION_LABELS[key],
          delta: v.delta,
          errPlus: v.ci[1] - v.delta,
          errMinus: v.delta - v.ci[0],
        }))
    : [];

  const layerDist = generation?.layer_count_distribution
    ? Object.entries(generation.layer_count_distribution)
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([k, n]) => ({ k, n }))
    : [];

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 sm:py-14">
      <header className="border-b-2 border-ink pb-6 mb-8">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-ink-faint mb-2">
          Results
        </p>
        <h1 className="font-serif-display text-[1.9rem] sm:text-[2.3rem] font-bold leading-[1.12] text-ink max-w-3xl">
          Evaluation dashboard
        </h1>
        <p className="mt-3 max-w-2xl font-serif text-[0.98rem] leading-relaxed text-ink-soft">
          Single-annotator evaluation pass — no inter-annotator agreement is computed or claimed.
          See docs/eval_rubric.md for methodology and this caveat&apos;s justification.
        </p>
        {(times.retrieval || times.generation) && (
          <p className="mt-2 max-w-2xl font-sans text-[0.8rem] text-ink-faint">
            Retrieval measured {fmtDate(times.retrieval)}, generation {fmtDate(times.generation)}, on the
            index built {fmtDate(times.index)}.
          </p>
        )}
        {(predatesIndex(times.retrieval, times.index) || predatesIndex(times.generation, times.index)) && (
          <div className="mt-3 max-w-2xl rounded-lg border border-warning/25 bg-warning-bg px-4 py-3 font-sans text-sm text-warning-text">
            {predatesIndex(times.retrieval, times.index) && predatesIndex(times.generation, times.index)
              ? "These results"
              : predatesIndex(times.retrieval, times.index)
                ? "The retrieval results"
                : "The generation results"}{" "}
            predate the index currently served, so they describe an earlier build. Re-run the evaluation
            (see README) before relying on them.
          </div>
        )}
      </header>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-error/25 bg-error-bg px-4 py-3 font-sans text-sm text-error-text">
          {error}
        </div>
      )}

      {!loading && !error && !retrieval && !generation && (
        <div className="rounded-lg border border-warning/25 bg-warning-bg px-4 py-3 font-sans text-sm text-warning-text">
          Evaluation results not found. Run src/dhammapada_rag/eval/*.py first (see README).
        </div>
      )}

      {!loading && !error && (retrieval || generation) && (
        <div className="space-y-14">
          {retrieval && (
            <section className="space-y-5">
              <div>
                <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint mb-1">
                  1 · Retrieval
                </p>
                <p className="font-sans text-[0.8rem] text-ink-faint">
                  {retrieval.n_questions ?? "?"} gold questions, single relevant verse-group each
                  (construction-from-known-answer — see rubric).
                </p>
              </div>

              <MetricTiles
                items={[
                  { label: "Recall@1", value: fmt(retrieval.overall?.baseline?.["recall@1"]) },
                  { label: "Recall@10", value: fmt(retrieval.overall?.baseline?.["recall@10"]) },
                  { label: "nDCG@10", value: fmt(retrieval.overall?.baseline?.["ndcg@10"]) },
                  { label: "MRR", value: fmt(retrieval.overall?.baseline?.mrr) },
                ]}
              />

              {byTypeRows.length > 0 && (
                <>
                  <EvalTable
                    columns={[
                      { header: "Query type" },
                      { header: "n", align: "right" },
                      { header: "Recall@1", align: "right" },
                      { header: "Recall@10", align: "right" },
                      { header: "nDCG@10", align: "right" },
                      { header: "MRR", align: "right" },
                    ]}
                    rows={[...byTypeRows]
                      .sort((a, b) => b["ndcg@10"] - a["ndcg@10"])
                      .map((r) => [
                        r.type,
                        r.n,
                        fmt(r["recall@1"]),
                        fmt(r["recall@10"]),
                        fmt(r["ndcg@10"]),
                        fmt(r.mrr),
                      ])}
                  />
                  {worst && (
                    <p className="font-sans text-[0.78rem] text-ink-faint">
                      &lsquo;{worst}&rsquo; scores worst among types with a meaningful sample size —
                      an aggregate-hides-the-result finding (docs/evaluation.md). Types with n&lt;5
                      are too small to conclude from.
                    </p>
                  )}
                  <RetrievalByTypeChart rows={byTypeRows} worst={worst} />
                </>
              )}

              {ablationRows.length > 0 && (
                <div className="space-y-2">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">
                    Ablations — delta from baseline, bootstrap 95% CI
                  </p>
                  <AblationChart rows={ablationRows} />
                  <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
                    Verse-only chunking causes by far the largest drop — the strongest evidence for
                    the core architectural claim. Flat-vs-assembled shows ~no difference (a genuine
                    null result, not oversold). <strong>Read with care</strong>: this overall number
                    is pulled down by alignment questions that verse-only retrieval structurally
                    cannot answer; the doctrinal row alone does <em>not</em> show the same drop — see
                    docs/evaluation.md.
                  </p>
                </div>
              )}

              {retrieval.by_subtype && (
                <div className="space-y-2">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">By subtype</p>
                  <EvalTable
                    columns={[
                      { header: "Subtype" },
                      { header: "Recall@1", align: "right" },
                      { header: "Recall@10", align: "right" },
                      { header: "nDCG@10", align: "right" },
                      { header: "MRR", align: "right" },
                    ]}
                    rows={Object.entries(retrieval.by_subtype)
                      .filter(([, d]) => d.baseline)
                      .map(([s, d]) => [
                        s,
                        fmt(d.baseline?.["recall@1"]),
                        fmt(d.baseline?.["recall@10"]),
                        fmt(d.baseline?.["ndcg@10"]),
                        fmt(d.baseline?.mrr),
                      ])}
                  />
                </div>
              )}
            </section>
          )}

          {generation && (
            <section className="space-y-5">
              <div>
                <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint mb-1">
                  2 · Generation
                </p>
                <p className="font-sans text-[0.8rem] text-ink-faint">
                  {generation.n_questions ?? "?"}-question stratified sample, {generation.n_claims ?? "?"}{" "}
                  claims, judged against a gold layer tag per claim.
                </p>
              </div>

              <MetricTiles
                items={[
                  { label: "Accuracy", value: fmt(generation.accuracy) },
                  (() => {
                    const m = supportedMacroF1(generation.per_class);
                    return m
                      ? { label: "Macro-F1", value: fmt(m.value), sub: `over ${m.n} layers with gold claims` }
                      : { label: "Macro-F1", value: fmt(generation.macro_f1) };
                  })(),
                  {
                    label: "Conflation rate",
                    value: fmt(generation.conflation_rate),
                    sub: "commentary as verse",
                  },
                  {
                    label: "Provenance errors",
                    value: `${generation.provenance_errors ?? "?"}/${generation.n_claims ?? "?"}`,
                    sub: "structural validity",
                  },
                ]}
              />

              {generation.confusion_matrix && (
                <div className="space-y-2">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">
                    Confusion matrix — rows gold, columns predicted
                  </p>
                  <ConfusionMatrix matrix={generation.confusion_matrix} />
                  <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
                    Conflation (commentary content tagged &lsquo;verse&rsquo;, the failure this
                    system exists to catch): {generation.commentary_tagged_verse ?? "?"}. Reverse
                    direction (verse tagged &lsquo;commentary&rsquo;):{" "}
                    {generation.verse_tagged_commentary ?? "?"}.
                  </p>
                </div>
              )}

              {generation.per_class && (
                <div className="space-y-2">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">
                    Per-class precision / recall / F1
                  </p>
                  <EvalTable
                    columns={[
                      { header: "Layer" },
                      { header: "Precision", align: "right" },
                      { header: "Recall", align: "right" },
                      { header: "F1", align: "right" },
                      { header: "Support", align: "right" },
                    ]}
                    rows={Object.entries(generation.per_class).map(([l, d]) => [
                      l,
                      fmt(d.precision),
                      fmt(d.recall),
                      fmt(d.f1),
                      d.support ?? "—",
                    ])}
                  />
                </div>
              )}

              {generation.context_utilization ? (
                <div className="space-y-3">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">Context utilization</p>
                  <MetricTiles
                    items={[
                      {
                        label: "Mean utilization",
                        value: fmt(generation.context_utilization.mean),
                        sub: "cited or dismissed",
                      },
                      {
                        label: "Fully accounted",
                        value: `${generation.context_utilization.n_fully_accounted ?? "?"}/${
                          generation.context_utilization.n_questions ?? "?"
                        }`,
                        sub: "answers using every group",
                      },
                      {
                        label: "Claims / answer",
                        value: fmt(generation.claims_per_answer?.mean, 2),
                        sub: "mean",
                      },
                    ]}
                  />
                  <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
                    Utilization = (groups cited + groups explicitly dismissed) / groups retrieved,
                    per question. A group neither cited nor dismissed was silently ignored —
                    retrieved but never accounted for.
                  </p>
                  {layerDist.length > 0 && (
                    <ResponsiveContainer width="100%" height={260} minWidth={320}>
                      <BarChart data={layerDist} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
                        <XAxis
                          dataKey="k"
                          tick={axisTickStyle}
                          axisLine={{ stroke: "var(--line)" }}
                          tickLine={false}
                          label={{ value: "layers", position: "insideBottom", offset: -4, style: axisTickStyle }}
                        />
                        <YAxis tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
                        <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: "var(--surface-2)" }} />
                        <Bar dataKey="n" fill="var(--ink-soft)" radius={[4, 4, 0, 0]} maxBarSize={48} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              ) : (
                <p className="font-sans text-[0.78rem] text-ink-faint">
                  Context-utilization metrics not present in this results file (added in Round 7/8).
                </p>
              )}

              {generation.pali_fidelity && (
                <div className="space-y-2">
                  <p className="font-serif text-[0.9rem] font-semibold text-ink">Pali quote fidelity</p>
                  <MetricTiles
                    items={[
                      { label: "Exact copy", value: pct(generation.pali_fidelity.exact_copy_rate) },
                      { label: "Variant", value: pct(generation.pali_fidelity.variant_rate) },
                      { label: "Fabrication", value: pct(generation.pali_fidelity.fabrication_rate) },
                      {
                        label: "Quote coverage",
                        value: pct(generation.pali_fidelity.quote_coverage_rate),
                        sub: `of cited verse quoted, n=${generation.pali_fidelity.n_pali_claims ?? "?"}`,
                      },
                    ]}
                  />
                  {generation.source_fidelity_rate != null && (
                    <p className="font-sans text-[0.78rem] text-ink-faint">
                      Source fidelity rate (does the claim say what the source says):{" "}
                      {pct(generation.source_fidelity_rate)}.
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          {sweep.length > 0 && (
            <section className="space-y-3">
              <div>
                <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint mb-1">
                  3 · Model-size sweep
                </p>
                <p className="font-sans text-[0.8rem] text-ink-faint">
                  Same retrieved context across all sizes and both retry settings — differences are
                  attributable to the generator, not retrieval variance. Clean rate is computed over
                  ALL attempts including failures.
                </p>
              </div>
              <EvalTable
                columns={[
                  { header: "Model" },
                  { header: "Retries", align: "right" },
                  { header: "n", align: "right" },
                  { header: "Clean rate", align: "right" },
                  { header: "Latency (s)", align: "right" },
                ]}
                rows={sweep.map((r) => [
                  r.model,
                  r.max_retries,
                  r.n,
                  fmt(r.clean_rate),
                  fmt(r.avg_latency_s, 1),
                ])}
              />
              <SweepChart rows={sweep} />
              <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
                Structural citation validity improves sharply with model size. Retrying does{" "}
                <strong>not</strong> reliably help — the 1.5B model&apos;s clean rate gets slightly{" "}
                <em>worse</em> with a retry enabled, so retries are not a substitute for capacity.
              </p>
            </section>
          )}

          <div className="rounded-lg border border-info/25 bg-info-bg px-4 py-3 font-sans text-[0.82rem] leading-relaxed text-info-text">
            Full discussion and every number&apos;s provenance, including the pre-fix numbers this
            pass superseded: docs/evaluation.md (baseline archived at docs/evaluation_pre_fix.md).
            Methodology and annotator-status caveats: docs/eval_rubric.md.
          </div>
        </div>
      )}
    </div>
  );
}
