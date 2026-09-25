"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GENERATOR_MODELS } from "@/lib/api";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "the woman whose child died",
  "what does the Dhammapada say about anger?",
  "which single story explains Dhp 320, 321, and 322 together?",
];

export interface AskParams {
  question: string;
  generate: boolean;
  topK: number;
  candidates: number;
  model: string;
}

export function SearchBox({
  loading,
  onSubmit,
}: {
  loading: boolean;
  onSubmit: (params: AskParams) => void;
}) {
  const [question, setQuestion] = useState("");
  const [generate, setGenerate] = useState(true);
  const [model, setModel] = useState(GENERATOR_MODELS[0]);
  const [topK, setTopK] = useState(3);
  const [candidates, setCandidates] = useState(30);
  const [optionsOpen, setOptionsOpen] = useState(false);

  function submit(q: string) {
    const clean = q.trim();
    if (!clean || loading) return;
    onSubmit({ question: clean, generate, topK, candidates, model });
  }

  return (
    <div className="space-y-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        className="flex flex-col sm:flex-row gap-2.5"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. why did the Buddha teach Kisa Gotami about mustard seeds?"
            className="w-full h-12 rounded-xl border border-line bg-surface pl-10 pr-4 font-serif text-[0.98rem] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-ink-faint"
          />
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="lg"
            className={cn(optionsOpen && "bg-surface-2")}
            onClick={() => setOptionsOpen((v) => !v)}
            aria-label="Query options"
          >
            <SlidersHorizontal className="h-4 w-4" />
          </Button>
          <Button type="submit" variant="primary" size="lg" disabled={loading} className="flex-1 sm:flex-none">
            {loading ? "Searching…" : "Search"}
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setQuestion(ex);
              submit(ex);
            }}
            className="rounded-full border border-line bg-surface px-3.5 py-1.5 font-sans text-[0.78rem] font-medium text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
          >
            {ex}
          </button>
        ))}
      </div>

      {optionsOpen && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 rounded-xl border border-line bg-surface-2 p-4 animate-fade-in">
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              Generator model
            </span>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={!generate}
              className="h-9 rounded-lg border border-line bg-surface px-2.5 font-sans text-sm text-ink disabled:opacity-50"
            >
              {GENERATOR_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              Verse-groups to return: {topK}
            </span>
            <input
              type="range"
              min={1}
              max={10}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="accent-ink"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              Rerank candidates: {candidates}
            </span>
            <input
              type="range"
              min={5}
              max={60}
              value={candidates}
              onChange={(e) => setCandidates(Number(e.target.value))}
              className="accent-ink"
            />
          </label>

          <label className="flex items-end gap-2 pb-1.5">
            <input
              type="checkbox"
              checked={generate}
              onChange={(e) => setGenerate(e.target.checked)}
              className="h-4 w-4 accent-ink"
            />
            <span className="font-sans text-[0.82rem] text-ink-soft">
              Generate layer-attributed answer
            </span>
          </label>
        </div>
      )}
    </div>
  );
}
