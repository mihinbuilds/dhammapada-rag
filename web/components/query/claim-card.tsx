"use client";

import { motion } from "framer-motion";

import { LAYER_META, verseLabel } from "@/lib/layers";
import type { ClaimOut } from "@/lib/api";

export function ClaimCard({ claim, index }: { claim: ClaimOut; index: number }) {
  const meta = LAYER_META[claim.layer];

  const parts: string[] = [];
  if (claim.verse_numbers && claim.verse_numbers.length) {
    parts.push(`Dhp ${verseLabel(claim.verse_numbers)}`);
  } else if (claim.verse_number) {
    parts.push(`Dhp ${claim.verse_number}`);
  }
  if (claim.group_id) parts.push(`DhpA ${claim.group_id}`);
  const citation = parts.length ? parts.join(" · ") : "no citation";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index * 0.06, 0.4), ease: [0.16, 1, 0.3, 1] }}
      className={`rounded-lg border p-4 ${meta.badge}`}
      style={{ borderLeftWidth: 3 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <span
          className={`inline-flex items-center rounded-[3px] px-1.5 py-0.5 text-[0.59rem] font-sans font-bold uppercase tracking-wide text-white ${meta.dot}`}
        >
          {meta.label}
        </span>
        <span className="font-mono text-[0.69rem] text-ink-soft">{citation}</span>
      </div>
      <p className="font-serif text-[0.94rem] leading-relaxed text-ink">{claim.text}</p>
      {claim.pali_support && (
        <p className="mt-2.5 border-t border-dashed border-line pt-2 font-serif italic text-[0.84rem] leading-relaxed text-ink-soft">
          {claim.pali_support}
        </p>
      )}
    </motion.div>
  );
}
