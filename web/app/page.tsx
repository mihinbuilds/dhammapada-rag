"use client";

import { motion } from "framer-motion";
import { Copy } from "lucide-react";
import { useState } from "react";

import { AnswerSummary } from "@/components/query/answer-summary";
import { ClaimCard } from "@/components/query/claim-card";
import { LayerLegend } from "@/components/query/layer-legend";
import { AskParams, SearchBox } from "@/components/query/search-box";
import { VerseGroup } from "@/components/query/verse-group";
import { WarningList } from "@/components/query/warning-list";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, type AnswerResponse, type VerseGroupResult } from "@/lib/api";

interface RunState {
  question: string;
  loading: boolean;
  fatalError: string | null;
  generationError: string | null;
  generation: AnswerResponse | null;
  sources: VerseGroupResult[];
}

const STAGES = [
  { n: "1", label: "Hybrid retrieval", detail: "BGE-M3 · RRF" },
  { n: "2", label: "Rerank", detail: "cross-encoder" },
  { n: "3", label: "Constrained generation", detail: "Qwen2.5 · schema-decoded" },
  { n: "4", label: "Provenance audit", detail: "severity-tagged" },
];

export default function AskPage() {
  const [run, setRun] = useState<RunState | null>(null);

  async function handleSubmit(params: AskParams) {
    setRun({
      question: params.question,
      loading: true,
      fatalError: null,
      generationError: null,
      generation: null,
      sources: [],
    });

    if (params.generate) {
      try {
        const answer = await api.answer(params.question, params.topK, params.candidates, params.model);
        setRun({
          question: params.question,
          loading: false,
          fatalError: null,
          generationError: null,
          generation: answer,
          sources: answer.sources,
        });
        return;
      } catch (e) {
        const genMsg = e instanceof ApiError ? e.detail : "Generator could not be loaded or executed.";
        try {
          const fallback = await api.query(params.question, params.topK, params.candidates);
          setRun({
            question: params.question,
            loading: false,
            fatalError: null,
            generationError: `Generation failed: ${genMsg}`,
            generation: null,
            sources: fallback.results,
          });
        } catch (e2) {
          const msg = e2 instanceof ApiError ? e2.detail : "Retrieval pipeline failed.";
          setRun({
            question: params.question,
            loading: false,
            fatalError: msg,
            generationError: null,
            generation: null,
            sources: [],
          });
        }
        return;
      }
    }

    try {
      const result = await api.query(params.question, params.topK, params.candidates);
      setRun({
        question: params.question,
        loading: false,
        fatalError: null,
        generationError: null,
        generation: null,
        sources: result.results,
      });
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Retrieval pipeline failed.";
      setRun({
        question: params.question,
        loading: false,
        fatalError: msg,
        generationError: null,
        generation: null,
        sources: [],
      });
    }
  }

  function copyAnswer() {
    if (!run?.generation) return;
    const text = run.generation.claims
      .map((c) => `[${c.layer.toUpperCase()}] ${c.text}`)
      .join("\n\n");
    navigator.clipboard.writeText(text);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 sm:py-14">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="border-b-2 border-ink pb-6 mb-8"
      >
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-ink-faint mb-2">
          Dhammapada · Retrieval-Augmented Generation
        </p>
        <h1 className="font-serif-display text-[1.9rem] sm:text-[2.3rem] font-bold leading-[1.12] text-ink max-w-3xl">
          Layer-attributed answering over the Dhammapada and its commentary
        </h1>
        <p className="mt-3 max-w-2xl font-serif text-[0.98rem] leading-relaxed text-ink-soft">
          Every generated claim is tagged <strong>verse / commentary / alignment / synthesis</strong>{" "}
          and cited back to its source; the audit layer flags any citation that cannot be trusted.
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-5">
          {STAGES.map((s, i) => (
            <div key={s.n} className="flex items-center gap-2">
              <span className="rounded-full border border-line bg-surface px-3 py-1 font-sans text-[0.72rem] font-semibold text-ink-soft">
                {s.n} · {s.label}
                <em className="not-italic ml-1.5 font-mono text-[0.66rem] text-ink-faint">
                  {s.detail}
                </em>
              </span>
              {i < STAGES.length - 1 && <span className="text-ink-faint text-sm">→</span>}
            </div>
          ))}
        </div>
      </motion.header>

      <SearchBox loading={Boolean(run?.loading)} onSubmit={handleSubmit} />

      {!run && (
        <div className="mt-10 rounded-xl border border-dashed border-line p-6">
          <p className="font-sans text-[0.7rem] font-semibold uppercase tracking-wide text-ink-faint mb-3">
            Layers
          </p>
          <LayerLegend />
        </div>
      )}

      {run && (
        <div className="mt-10 space-y-8">
          <div className="rounded-xl border border-line bg-surface px-4 py-3 grid grid-cols-[auto_1fr] gap-3 items-baseline">
            <span className="font-mono text-[0.63rem] font-semibold uppercase tracking-wide text-ink-faint">
              Question
            </span>
            <span className="font-serif text-[1rem] text-ink">{run.question}</span>
          </div>

          {run.loading && (
            <div className="space-y-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}

          {!run.loading && run.fatalError && (
            <div className="rounded-lg border border-error/25 bg-error-bg px-4 py-3 font-sans text-sm text-error-text">
              {run.fatalError}
              <p className="mt-1 text-xs opacity-80">
                Check that the API is running (`uvicorn dhammapada_rag.api.main:app`) and reachable
                at the configured NEXT_PUBLIC_API_BASE_URL.
              </p>
            </div>
          )}

          {!run.loading && !run.fatalError && run.sources.length === 0 && (
            <div className="rounded-lg border border-warning/25 bg-warning-bg px-4 py-3 font-sans text-sm text-warning-text">
              No retrieval results for this question.
            </div>
          )}

          {!run.loading && run.generationError && (
            <div className="rounded-lg border border-warning/25 bg-warning-bg px-4 py-3 font-sans text-sm text-warning-text">
              {run.generationError}
            </div>
          )}

          {!run.loading && run.generation && (
            <section className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
                  1 · Answer
                </p>
                <Button variant="ghost" size="sm" onClick={copyAnswer}>
                  <Copy className="h-3.5 w-3.5" /> Copy
                </Button>
              </div>
              <AnswerSummary result={run.generation} />
              <div className="space-y-2.5">
                {run.generation.claims.map((c, i) => (
                  <ClaimCard key={i} claim={c} index={i} />
                ))}
              </div>
              <WarningList warnings={run.generation.warnings} />
            </section>
          )}

          {!run.loading && run.sources.length > 0 && (
            <section className="space-y-3">
              <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
                {run.generation ? "2 · " : ""}Sources ({run.sources.length} verse-group
                {run.sources.length === 1 ? "" : "s"})
              </p>
              {run.generation?.source_disposition && (
                <p className="font-sans text-[0.78rem] text-ink-faint -mt-1">
                  Each group is labelled with how the answer treated it — the model must account for
                  every group it was shown, not silently ignore one.
                </p>
              )}
              <div className="space-y-3">
                {run.sources.map((b, i) => (
                  <VerseGroup
                    key={b.verse_numbers.join("-")}
                    bundle={b}
                    disposition={run.generation?.source_disposition}
                    defaultOpen={i === 0}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
