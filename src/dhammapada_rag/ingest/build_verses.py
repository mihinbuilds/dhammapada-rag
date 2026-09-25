"""Build the canonical per-verse record for all 423 Dhammapada verses.

CUTOVER (dhammapada_fixes/corpus_rebuild_design.md, Sequence step 5): this
now reads Stage 2's normalized outputs (data/normalized/sc_pali.jsonl,
sc_sujato.jsonl, aj_interlinear.jsonl) instead of re-deriving pali_mahasangiti
/ english_sujato / interlinear_* from sources/external/ and
data/processed/interlinear_gloss.jsonl directly. This is not a schema
change -- verses.jsonl's fields are unchanged, and api/schemas.py's VerseOut
still mirrors it exactly -- it's a provenance change: the three real bugs
docs/corpus_normalization.md's normalizers found and fixed (the vagga-final
colophon folded into pali_mahasangiti/english_sujato's own SuttaCentral
segmentation, Dhp 416's second-story title leaking into a shared verse's
segments, and Dhp 51/327's citation-vs-canonical swap in interlinear_pali/
english) now flow into the live corpus instead of staying quarantined in the
rebuild track. See that doc's "Measured effect" table for what changed
(boundary-artifact cross-source disagreements: 19 -> 0).

Originally (first Phase 1 pass) this closed the gap where the narrative
source (Dhammapada-Attakatha.pdf) only reprints the full Pali verse text
inline for ~74% of stories (companion verses in multi-verse groups often get
only a teaser quote), by joining in two independently-sourced, fully-covering
CC0/CC-BY-SA layers (see sources/external/PROVENANCE.md):

  - Pali: Mahasangiti edition via SuttaCentral (CC0), all 423 verses.
  - English: Bhikkhu Sujato's translation via SuttaCentral (CC0), all 423
    verses -- also incidentally fulfilling docs/project_plan.md's original
    "two English translations" ask.
  - Interlinear phrase-level gloss + notes: Anandajoti Bhikkhu's 2017
    interlinear edition (CC BY-SA 4.0), all 423 verses -- the closest
    available substitute for the pada-gloss layer the narrative source omits.

The narrative source's own Pali/English quotations (where present) are kept
too, tagged with which story they came from, since a verse's *narrative*
recitation context (see docs/project_plan.md Phase 3's parent-assembly design)
is meaningfully different from a standalone critical-edition quotation of the
same verse, even when the words are nearly identical. Per
docs/corpus_source_ownership.md's Stage 1 table ("the PDF stops owning the
Pali"), these narrative_* fields stay sourced from stories.jsonl unchanged --
they are a distinct, separately-tagged field, not a fallback for the
canonical verse-level fields above.

Output: data/processed/verses.jsonl, one record per verse 1-423.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.vaggas import vagga_for_verse  # noqa: E402


def load_normalized_jsonl(path: Path, value_field: str) -> dict[int, str]:
    """Stage 2's normalized files are already one clean row per verse
    (`{"verse": int, <value_field>: str, "source_ref": ...}`) -- no
    segment-joining or page-selection logic needed here, since normalize_
    sc_pali.py / normalize_sc_sujato.py already did it, with the boundary
    fixes documented in docs/corpus_normalization.md."""
    out: dict[int, str] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            out[rec["verse"]] = rec[value_field]
    return out


def load_interlinear(path: Path) -> dict[int, dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            out[rec["verse"]] = rec
    return out


def load_stories(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build() -> tuple[list[dict], dict]:
    root = Path(__file__).resolve().parents[3]
    norm_dir = root / "data" / "normalized"
    for name in ("sc_pali.jsonl", "sc_sujato.jsonl", "aj_interlinear.jsonl"):
        if not (norm_dir / name).exists():
            raise FileNotFoundError(
                f"{norm_dir / name} not found -- build_verses.py now reads Stage 2's "
                f"normalized output; run normalize_sc_pali.py, normalize_sc_sujato.py, "
                f"and normalize_aj_interlinear.py first."
            )

    pali_ms = load_normalized_jsonl(norm_dir / "sc_pali.jsonl", "pali")
    english_sujato = load_normalized_jsonl(norm_dir / "sc_sujato.jsonl", "english")
    interlinear = load_interlinear(norm_dir / "aj_interlinear.jsonl")
    stories = load_stories(root / "data" / "processed" / "stories.jsonl")

    story_group_ids: dict[int, list[str]] = {v: [] for v in range(1, 424)}
    narrative_quote: dict[int, dict] = {}
    for s in stories:
        for verse in s["dhp_verses"]:
            if 1 <= verse <= 423:
                story_group_ids[verse].append(s["group_id"])
        if s.get("pali_verse_number") in range(1, 424):
            narrative_quote[s["pali_verse_number"]] = {
                "pali": s["pali_verse"],
                "english": s["english_verse"],
                "group_id": s["group_id"],
            }

    records = []
    coverage = {"pali_ms": 0, "english_sujato": 0, "interlinear": 0, "narrative_quote": 0, "story_ref": 0}
    for verse in range(1, 424):
        vagga = vagga_for_verse(verse)
        nq = narrative_quote.get(verse)
        gloss = interlinear.get(verse)

        rec = {
            "verse": verse,
            "vagga_number": vagga.number,
            "vagga_name_pali": vagga.name_pali,
            "vagga_name_en": vagga.name_en,
            "pali_mahasangiti": pali_ms.get(verse),
            "english_sujato": english_sujato.get(verse),
            "interlinear_pali": gloss["pali"] if gloss else None,
            "interlinear_english": gloss["english"] if gloss else None,
            "interlinear_notes": gloss["notes"] if gloss else [],
            "narrative_pali": nq["pali"] if nq else None,
            "narrative_english": nq["english"] if nq else None,
            "narrative_source_group_id": nq["group_id"] if nq else None,
            "story_group_ids": story_group_ids[verse],
        }
        records.append(rec)

        coverage["pali_ms"] += rec["pali_mahasangiti"] is not None
        coverage["english_sujato"] += rec["english_sujato"] is not None
        coverage["interlinear"] += rec["interlinear_pali"] is not None
        coverage["narrative_quote"] += rec["narrative_pali"] is not None
        coverage["story_ref"] += len(rec["story_group_ids"]) > 0

    report = {
        "total_verses": 423,
        "coverage": coverage,
        "coverage_rate": {k: round(v / 423, 4) for k, v in coverage.items()},
        "fully_complete_all_layers": sum(
            1
            for r in records
            if r["pali_mahasangiti"] and r["english_sujato"] and r["interlinear_pali"] and r["story_group_ids"]
        ),
    }
    return records, report


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "processed" / "verses.jsonl"
    report_path = root / "data" / "processed" / "verses_report.json"

    # Stage 5 gates (dhammapada_fixes/corpus_rebuild_design.md): "Fail the
    # build on 1-4." Runs against the same Stage 2 normalized files this
    # build() call is about to read, so a hard-gate failure here means the
    # cutover would write a corpus Stage 5 itself would reject -- catch it
    # before it reaches data/processed/, not after.
    from dhammapada_rag.ingest.validation_gates import run_gates  # noqa: E402 (local import: avoid a hard
    gates_report = run_gates(root)                                # dependency on Stage 3/4 unless this runs)
    if not gates_report["build_ok"]:
        raise RuntimeError(
            f"Stage 5 validation gates failed: {gates_report['hard_failures']}. "
            f"Not writing {out_path}. See data/normalized/validation_gates_report.json."
        )

    records, report = build()

    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {out_path} ({len(records)} verses)")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
