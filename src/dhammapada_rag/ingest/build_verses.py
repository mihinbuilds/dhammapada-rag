"""Build the canonical per-verse record for all 423 Dhammapada verses.

This is what closes the gap flagged in the first Phase 1 pass: the narrative
source (Dhammapada-Attakatha.pdf) only reprints the full Pali verse text
inline for ~74% of stories (companion verses in multi-verse groups often get
only a teaser quote). Rather than accepting that as the ceiling on verse-layer
completeness, this script joins in two independently-sourced, fully-covering
CC0/CC-BY-SA layers (see sources/external/PROVENANCE.md):

  - Pali: Mahasangiti edition via SuttaCentral (CC0), all 423 verses.
  - English: Bhikkhu Sujato's translation via SuttaCentral (CC0), all 423
    verses -- also incidentally fulfilling DhammapadaRAG.txt's original
    "two English translations" ask.
  - Interlinear phrase-level gloss + notes: Anandajoti Bhikkhu's 2017
    interlinear edition (CC BY-SA 3.0), all 423 verses -- the closest
    available substitute for the pada-gloss layer the narrative source omits.

The narrative source's own Pali/English quotations (where present) are kept
too, tagged with which story they came from, since a verse's *narrative*
recitation context (see DhammapadaRAG.txt Phase 3's parent-assembly design)
is meaningfully different from a standalone critical-edition quotation of the
same verse, even when the words are nearly identical.

Output: data/processed/verses.jsonl, one record per verse 1-423.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.vaggas import vagga_for_verse  # noqa: E402

SEGMENT_RE = re.compile(r"^dhp(\d+):(.+)$")


def load_segmented_json_dir(dir_path: Path) -> dict[int, str]:
    """Join `dhp<verse>:<line>` segments (excluding `:0`/`:0.N` header segments)
    into one text string per verse, in ascending line order."""
    raw: dict[int, dict[str, str]] = {}
    for f in sorted(dir_path.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key, text in data.items():
            m = SEGMENT_RE.match(key)
            if not m:
                continue
            verse = int(m.group(1))
            line_key = m.group(2)
            if line_key == "0" or line_key.startswith("0."):
                continue  # nikaya/vagga/story-title header segment, not verse text
            raw.setdefault(verse, {})[line_key] = text

    def sort_key(line_key: str) -> tuple[int, ...]:
        return tuple(int(p) for p in line_key.split("."))

    out: dict[int, str] = {}
    for verse, lines in raw.items():
        ordered = [lines[k] for k in sorted(lines, key=sort_key)]
        out[verse] = " ".join(t.strip() for t in ordered)
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

    pali_ms = load_segmented_json_dir(root / "sources" / "external" / "mahasangiti_pali")
    english_sujato = load_segmented_json_dir(root / "sources" / "external" / "sujato_en")
    interlinear = load_interlinear(root / "data" / "processed" / "interlinear_gloss.jsonl")
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

    records, report = build()

    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {out_path} ({len(records)} verses)")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
