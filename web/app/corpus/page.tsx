"use client";

import { useEffect, useState } from "react";

import { VaggaNav } from "@/components/corpus/vagga-nav";
import { MetricTiles } from "@/components/metric-tiles";
import { VerseGroup, type VerseGroupLike } from "@/components/query/verse-group";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type HealthResponse, type VaggaOut } from "@/lib/api";
import { assembleByStory, assembleByVerse } from "@/lib/assemble";
import { cn } from "@/lib/utils";

type Mode = "verse" | "story";

export default function CorpusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [vaggas, setVaggas] = useState<VaggaOut[]>([]);
  const [mode, setMode] = useState<Mode>("verse");
  const [verseInput, setVerseInput] = useState("114");
  const [storyInput, setStoryInput] = useState("8.13");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [group, setGroup] = useState<VerseGroupLike | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    api.vaggas().then(setVaggas).catch(() => {});
  }, []);

  async function lookupVerse(n: number) {
    setLoading(true);
    setError(null);
    setGroup(null);
    try {
      setGroup(await assembleByVerse(n));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.status === 404
            ? `Verse ${n} is not in the indexed corpus.`
            : e.detail
          : e instanceof Error
            ? e.message
            : "Lookup failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function lookupStory(gid: string) {
    setLoading(true);
    setError(null);
    setGroup(null);
    try {
      setGroup(await assembleByStory(gid));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.status === 404
            ? `No story '${gid}'. Expected format '<vagga>.<story>', e.g. '8.13'.`
            : e.detail
          : "Lookup failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Initial lookup so the panel isn't empty on first load; intentionally
    // runs once, not on every verseInput keystroke.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    lookupVerse(Number(verseInput));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeVaggaNumber =
    group && group.verses.length ? group.verses[0].vagga_number : null;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 sm:py-14">
      <header className="border-b-2 border-ink pb-6 mb-8">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-ink-faint mb-2">
          Corpus browser
        </p>
        <h1 className="font-serif-display text-[1.9rem] sm:text-[2.3rem] font-bold leading-[1.12] text-ink max-w-3xl">
          Verses, translations & commentary
        </h1>
        <p className="mt-3 max-w-2xl font-serif text-[0.98rem] leading-relaxed text-ink-soft">
          Look up a verse by number or a commentary story by its group id, and see every text
          layer assembled together.
        </p>
      </header>

      <MetricTiles
        items={[
          { label: "Verses indexed", value: health ? health.n_verses : "…", sub: "of 423 canonical" },
          { label: "Story groups", value: health ? health.n_stories : "…", sub: "Dhammapada-aṭṭhakathā" },
          { label: "Text layers", value: 3, sub: "Pali · Sujato · interlinear" },
        ]}
      />

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        <div className="space-y-4">
          <div className="flex rounded-lg border border-line bg-surface p-1">
            {(["verse", "story"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "flex-1 rounded-md py-1.5 font-sans text-[0.78rem] font-semibold transition-colors",
                  mode === m ? "bg-ink text-paper" : "text-ink-faint hover:text-ink",
                )}
              >
                {m === "verse" ? "Verse number" : "Story group_id"}
              </button>
            ))}
          </div>

          {mode === "verse" ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                lookupVerse(Number(verseInput));
              }}
              className="flex gap-2"
            >
              <input
                type="number"
                min={1}
                max={423}
                value={verseInput}
                onChange={(e) => setVerseInput(e.target.value)}
                className="w-full h-10 rounded-lg border border-line bg-surface px-3 font-mono text-sm text-ink outline-none focus:border-ink-faint"
              />
              <Button type="submit" size="md">
                Go
              </Button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                lookupStory(storyInput.trim());
              }}
              className="flex gap-2"
            >
              <input
                value={storyInput}
                onChange={(e) => setStoryInput(e.target.value)}
                placeholder="e.g. 8.13"
                className="w-full h-10 rounded-lg border border-line bg-surface px-3 font-mono text-sm text-ink outline-none focus:border-ink-faint"
              />
              <Button type="submit" size="md">
                Go
              </Button>
            </form>
          )}

          {mode === "verse" && (
            <VaggaNav
              vaggas={vaggas}
              activeNumber={activeVaggaNumber}
              onSelect={(v) => {
                setVerseInput(String(v.first_verse));
                lookupVerse(v.first_verse);
              }}
            />
          )}
        </div>

        <div>
          {loading && (
            <div className="space-y-3">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          )}
          {!loading && error && (
            <div className="rounded-lg border border-warning/25 bg-warning-bg px-4 py-3 font-sans text-sm text-warning-text">
              {error}
            </div>
          )}
          {!loading && !error && group && <VerseGroup bundle={group} defaultOpen />}
        </div>
      </div>
    </div>
  );
}
