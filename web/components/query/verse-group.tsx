"use client";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { DISPOSITION_META, verseLabel } from "@/lib/layers";
import type { Disposition, StoryOut, VerseOut } from "@/lib/api";

/** A resolved parent group: the shape both a search-result bundle
 * (VerseGroupResult, with a matched_chunk) and a direct corpus lookup
 * (lib/assemble.ts, no matched_chunk) share. */
export interface VerseGroupLike {
  verse_numbers: number[];
  verses: VerseOut[];
  stories: StoryOut[];
  matched_chunk?: {
    chunk_type: string;
    rerank_score: number;
    window_index?: number;
    n_windows?: number;
  };
}

function VersePair({
  pali,
  paliCaption,
  english,
  englishCaption,
}: {
  pali: string;
  paliCaption: string;
  english: string;
  englishCaption: string;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 items-stretch">
      <div className="flex flex-col">
        <p className="font-serif italic text-[0.92rem] leading-relaxed text-ink-soft">{pali}</p>
        <p className="mt-auto pt-1.5 font-sans text-[0.7rem] text-ink-faint">{paliCaption}</p>
      </div>
      <div className="flex flex-col">
        <p className="font-serif text-[0.92rem] leading-relaxed text-ink">{english}</p>
        <p className="mt-auto pt-1.5 font-sans text-[0.7rem] text-ink-faint">{englishCaption}</p>
      </div>
    </div>
  );
}

export function VerseGroup({
  bundle,
  disposition,
  defaultOpen = false,
}: {
  bundle: VerseGroupLike;
  disposition?: Record<string, Disposition> | null;
  defaultOpen?: boolean;
}) {
  const gids = bundle.stories.map((s) => s.group_id).join(", ") || "—";
  const title = bundle.stories.map((s) => s.title_en).join(" / ") || "(no story)";
  const chips = disposition
    ? Array.from(
        new Set(
          bundle.stories
            .map((s) => disposition[s.group_id])
            .filter((d): d is Disposition => Boolean(d)),
        ),
      )
    : [];
  const mc = bundle.matched_chunk;
  const windowNote =
    mc && mc.n_windows && mc.n_windows > 1
      ? ` · window ${(mc.window_index ?? 0) + 1}/${mc.n_windows}`
      : "";

  return (
    <div className="rounded-xl border border-line bg-surface overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1.5 px-4 pt-3.5 pb-2">
        <div className="font-serif text-[0.95rem] text-ink leading-snug">
          Dhp {verseLabel(bundle.verse_numbers)} — {title}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[0.68rem] text-ink-faint">
          {chips.map((d) => (
            <span
              key={d}
              className={`rounded-[3px] px-1.5 py-0.5 font-sans text-[0.58rem] font-bold uppercase tracking-wide ${DISPOSITION_META[d].chip}`}
            >
              {DISPOSITION_META[d].label}
            </span>
          ))}
          <span>DhpA {gids}</span>
        </div>
      </div>
      {mc && (
        <div className="px-4 pb-2 font-mono text-[0.66rem] text-ink-faint">
          matched on {mc.chunk_type.replace(/_/g, " ")}
          {windowNote} · score {mc.rerank_score.toFixed(3)}
        </div>
      )}

      <Accordion type="single" collapsible defaultValue={defaultOpen ? "content" : undefined}>
        <AccordionItem value="content" className="border-0 border-t border-line rounded-none">
          <AccordionTrigger className="px-4 text-[0.78rem] text-ink-soft normal-case font-medium">
            Verse text, translations and commentary
          </AccordionTrigger>
          <AccordionContent className="px-4 space-y-5">
            {bundle.verses.map((v) => (
              <div key={v.verse}>
                <div className="flex items-baseline gap-2 mb-1.5">
                  <span className="font-sans text-[0.8rem] font-bold text-ink">Dhp {v.verse}</span>
                  <span className="font-mono text-[0.68rem] text-ink-faint">
                    {v.vagga_name_pali}
                  </span>
                </div>
                <VersePair
                  pali={v.pali_mahasangiti ?? "(not available)"}
                  paliCaption="Pali · Mahāsaṅgīti (CC0)"
                  english={v.english_sujato ?? "(not available)"}
                  englishCaption="English · Sujato (CC0)"
                />
                {v.interlinear_english && (
                  <div className="mt-3">
                    <p className="font-serif text-[0.92rem] leading-relaxed text-ink">
                      {v.interlinear_english}
                    </p>
                    <p className="pt-1.5 font-sans text-[0.7rem] text-ink-faint">
                      English · Ānandajoti interlinear (CC BY-SA 4.0)
                    </p>
                  </div>
                )}
                <div className="mt-4 border-t border-line-soft" />
              </div>
            ))}

            {bundle.stories.map((s) => (
              <div key={s.group_id}>
                <div className="flex items-baseline gap-2 mb-1.5">
                  <span className="font-sans text-[0.8rem] font-bold text-ink">
                    Story {s.group_id}
                  </span>
                  <span className="font-mono text-[0.68rem] text-ink-faint">{s.title_en}</span>
                </div>
                {s.nidana && (
                  <p className="font-sans text-[0.7rem] text-ink-faint mb-1.5">
                    Nidāna: {s.nidana}
                  </p>
                )}
                {s.synopsis && (
                  <p className="font-serif text-[0.92rem] leading-relaxed text-ink mb-2">
                    {s.synopsis}
                  </p>
                )}
                {s.vatthu && (
                  <Accordion type="single" collapsible>
                    <AccordionItem value="vatthu">
                      <AccordionTrigger className="text-[0.78rem] text-ink-soft normal-case font-medium">
                        Full narrative (vatthu)
                      </AccordionTrigger>
                      <AccordionContent>
                        <p className="font-serif text-[0.9rem] leading-relaxed text-ink whitespace-pre-line">
                          {s.vatthu}
                        </p>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                )}
              </div>
            ))}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
