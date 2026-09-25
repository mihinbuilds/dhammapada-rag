import type { Disposition, Layer, Severity } from "@/lib/api";

/** Mirrors ui/app.py's LAYER_STYLE / LAYER_DESC / LAYER_ORDER so the two
 * surfaces agree on what each layer means and looks like. */
export const LAYER_ORDER: Layer[] = ["verse", "commentary", "alignment", "synthesis"];

/** Static, literal class strings (not template-built) so Tailwind's scanner
 * can see and keep every variant -- a computed `bg-${layer}-bg` string would
 * not be discoverable at build time. */
export const LAYER_META: Record<
  Layer,
  { label: string; desc: string; var: string; badge: string; dot: string; solid: string }
> = {
  verse: {
    label: "Verse",
    desc: "canonical Dhammapada text",
    var: "--verse",
    badge: "bg-verse-bg text-verse border border-verse/20",
    dot: "bg-verse",
    solid: "bg-verse text-white",
  },
  commentary: {
    label: "Commentary",
    desc: "Buddhaghosa's gloss & narrative",
    var: "--commentary",
    badge: "bg-commentary-bg text-commentary border border-commentary/20",
    dot: "bg-commentary",
    solid: "bg-commentary text-white",
  },
  alignment: {
    label: "Alignment",
    desc: "editorial structure of the corpus",
    var: "--alignment",
    badge: "bg-alignment-bg text-alignment border border-alignment/20",
    dot: "bg-alignment",
    solid: "bg-alignment text-white",
  },
  synthesis: {
    label: "Synthesis",
    desc: "inference across retrieved sources",
    var: "--synthesis",
    badge: "bg-synthesis-bg text-synthesis border border-synthesis/20",
    dot: "bg-synthesis",
    solid: "bg-synthesis text-white",
  },
};

export const SEVERITY_META: Record<
  Severity,
  { label: string; box: string; code: string }
> = {
  error: {
    label: "Citation cannot be trusted",
    box: "bg-error-bg text-error-text border-error/25",
    code: "text-error",
  },
  warning: {
    label: "Citation resolved, format deviated",
    box: "bg-warning-bg text-warning-text border-warning/25",
    code: "text-warning",
  },
  info: {
    label: "Advisory note",
    box: "bg-info-bg text-info-text border-info/25",
    code: "text-info",
  },
};

export const DISPOSITION_META: Record<Disposition, { label: string; chip: string }> = {
  used: { label: "used", chip: "bg-used-bg text-used border-used/25" },
  partially_relevant: { label: "partial", chip: "bg-partial-bg text-partial border-partial/25" },
  not_relevant: {
    label: "not relevant",
    chip: "bg-not-relevant-bg text-not-relevant border-not-relevant/25",
  },
};

export function verseLabel(numbers: number[] | undefined | null): string {
  return numbers && numbers.length ? numbers.join(", ") : "—";
}
