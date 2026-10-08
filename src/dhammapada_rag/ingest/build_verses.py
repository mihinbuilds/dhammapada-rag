"""Build the canonical per-verse record for all 423 Dhammapada verses.

Reads Stage 2's normalized output (data/normalized/aj_interlinear.jsonl)
for the verse layer, and data/processed/stories.jsonl for the narrative
quotations and story references.

The narrative source (Dhammapada-Attakatha.pdf) only reprints the full Pali
verse text inline for ~74% of stories (companion verses in multi-verse
groups often get only a teaser quote), so the verse layer comes from a
separate, fully-covering edition by the same editor:

  - Pali and English: Ānandajoti Bhikkhu's 2017 interlinear edition
    (CC BY-SA 4.0, used by written permission -- sources/PERMISSION.md),
    all 423 verses, with its phrase-level gloss notes.

ROUND 13 (2026-10-08): until this round the verse layer also carried a
second Pali edition and a second English translation, both published by
SuttaCentral. SuttaCentral asked that their material not be used in any
project that uses AI, so both fields were removed and the interlinear
fields now carry the verse layer alone. See data/raw/PROVENANCE.md.

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
    if not (norm_dir / "aj_interlinear.jsonl").exists():
        raise FileNotFoundError(
            f"{norm_dir / 'aj_interlinear.jsonl'} not found -- build_verses.py reads Stage 2's "
            f"normalized output; run normalize_aj_interlinear.py first."
        )

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
    coverage = {"interlinear": 0, "narrative_quote": 0, "story_ref": 0}
    for verse in range(1, 424):
        vagga = vagga_for_verse(verse)
        nq = narrative_quote.get(verse)
        gloss = interlinear.get(verse)

        rec = {
            "verse": verse,
            "vagga_number": vagga.number,
            "vagga_name_pali": vagga.name_pali,
            "vagga_name_en": vagga.name_en,
            "interlinear_pali": gloss["pali"] if gloss else None,
            "interlinear_english": gloss["english"] if gloss else None,
            "interlinear_notes": gloss["notes"] if gloss else [],
            "narrative_pali": nq["pali"] if nq else None,
            "narrative_english": nq["english"] if nq else None,
            "narrative_source_group_id": nq["group_id"] if nq else None,
            "story_group_ids": story_group_ids[verse],
        }
        records.append(rec)

        coverage["interlinear"] += bool(rec["interlinear_pali"] and rec["interlinear_english"])
        coverage["narrative_quote"] += rec["narrative_pali"] is not None
        coverage["story_ref"] += len(rec["story_group_ids"]) > 0

    # Since Round 13 the interlinear fields are the only verse layer, so a
    # verse without one has no verse text at all. Fail rather than ship a null.
    gaps = [
        (r["verse"], field)
        for r in records
        for field in ("interlinear_pali", "interlinear_english")
        if not (r[field] or "").strip()
    ]
    if gaps:
        raise ValueError(f"verse layer incomplete -- (verse, missing field): {gaps}")

    report = {
        "total_verses": 423,
        "coverage": coverage,
        "coverage_rate": {k: round(v / 423, 4) for k, v in coverage.items()},
        "fully_complete_all_layers": sum(
            1
            for r in records
            if r["interlinear_pali"] and r["interlinear_english"] and r["story_group_ids"]
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
