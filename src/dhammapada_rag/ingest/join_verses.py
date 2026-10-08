"""Stage 4 (dhammapada_fixes/corpus_rebuild_design.md): join, with
provenance on every field.

Reads only Stage 2's normalized outputs (data/normalized/
aj_interlinear.jsonl, aj_stories.jsonl) -- never
data/processed/ directly, so this join can't silently inherit a defect
Stage 2 already fixed (the vagga-colophon contamination, the mid-sequence
title leak, the two aj_interlinear citation-vs-canonical swaps) by reading
around it.

Writes data/normalized/verses_joined.json, one record per verse 1-423:

    {
      "verse": 114,
      "vagga": {"number": 8, "pali": "Sahassavagga", "en": "..."},
      "text": {
        "interlinear_pali":    {"value": ..., "source": ..., "source_ref": ..., "retrieved": ...},
        "interlinear_english": {...}
      },
      "story_group_ids": ["8.13"],
      "flags": []
    }

WHY THIS SHAPE, per the design doc: "the hyphenated-Pali problem is a
one-line query -- which field claims to be one edition but has a `source`
that isn't? -- instead of something you discover from a model's output six
weeks later." Every value here carries its own source + source_ref, not
just the record.

ROUND 13 (2026-10-08): the two SuttaCentral fields (Pali and English) are
gone -- removed at SuttaCentral's request; see data/raw/PROVENANCE.md. Ānandajoti's interlinear Pali and English now carry
the verse layer on their own.

WHAT'S DELIBERATELY NOT HERE: the PDF's own inline verse quotations
(`narrative_pali`/`narrative_english` in the current live
data/processed/verses.jsonl, sourced from a story's `pali_verse`/
`english_verse`). Per docs/corpus_source_ownership.md's Stage 1 table --
"the PDF stops owning the Pali" -- and per normalize_aj_stories.py's own
Stage 2 scope, which deliberately excludes those fields from
aj_stories.jsonl entirely. This join can only join what Stage 2 produced;
it was never going to have this field, and that's the point, not an
oversight to flag.

`flags` is empty on every record. It used to carry `cross_source_mismatch`
(SuttaCentral vs. Ānandajoti Pali, via audit_corpus.classify_pali_pair());
with one Pali edition left there is no second source to disagree with.
`metre_irregular` is explicitly Stage 5's job in the design doc, not built
here. `hand_corrected` has no source of truth yet -- nothing has been
hand-corrected in this track.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.vaggas import vagga_for_verse  # noqa: E402

# Per sources/external/PROVENANCE.md / data/raw/PROVENANCE.md: the
# fetch/extraction batch this date comes from. Not "today" -- the
# date the bytes actually entered this project, so this field means what
# the design doc's own example ("retrieved": "2026-07-15") implies.
_AJ_RETRIEVED = "2026-07-30"

_SOURCE_NAMES = {
    "interlinear_pali": "anandajoti_2017_interlinear",
    "interlinear_english": "anandajoti_2017_interlinear",
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def _field(value, source_key: str, source_ref, retrieved: str) -> dict:
    return {
        "value": value,
        "source": _SOURCE_NAMES[source_key],
        "source_ref": source_ref,
        "retrieved": retrieved,
    }


def join() -> list[dict]:
    root = Path(__file__).resolve().parents[3]
    norm_dir = root / "data" / "normalized"
    for name in ("aj_interlinear.jsonl", "aj_stories.jsonl"):
        if not (norm_dir / name).exists():
            raise FileNotFoundError(
                f"{norm_dir / name} not found -- Stage 4 joins Stage 2's normalized output; "
                f"run the two normalize_aj_*.py scripts first."
            )

    aj_interlinear = {r["verse"]: r for r in _load_jsonl(norm_dir / "aj_interlinear.jsonl")}
    aj_stories = _load_jsonl(norm_dir / "aj_stories.jsonl")

    story_group_ids: dict[int, list[str]] = {v: [] for v in range(1, 424)}
    for s in aj_stories:
        for v in s["verses"]:
            if 1 <= v <= 423:
                story_group_ids.setdefault(v, []).append(s["group_id"])

    records = []
    for verse in range(1, 424):
        vagga = vagga_for_verse(verse)
        il_row = aj_interlinear[verse]

        text = {
            "interlinear_pali": _field(il_row["pali"], "interlinear_pali", il_row["source_ref"], _AJ_RETRIEVED),
            "interlinear_english": _field(il_row["english"], "interlinear_english", il_row["source_ref"], _AJ_RETRIEVED),
        }

        records.append({
            "verse": verse,
            "vagga": {"number": vagga.number, "pali": vagga.name_pali, "en": vagga.name_en},
            "text": text,
            "story_group_ids": story_group_ids[verse],
            "flags": [],
        })

    return records


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "normalized" / "verses_joined.json"
    report_path = root / "data" / "normalized" / "verses_joined_report.json"

    records = join()

    n_flagged = sum(1 for r in records if r["flags"])
    report = {
        "n_verses": len(records),
        "n_with_story_group_ids": sum(1 for r in records if r["story_group_ids"]),
        "n_flagged": n_flagged,
        "flagged_rate": round(n_flagged / len(records), 4),
        "flag_counts": {},
        "built": date.today().isoformat(),
    }
    for r in records:
        for f in r["flags"]:
            report["flag_counts"][f["code"]] = report["flag_counts"].get(f["code"], 0) + 1

    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {out_path} ({len(records)} verses)")
    print(f"Wrote {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
