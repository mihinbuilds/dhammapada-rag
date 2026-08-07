"""Stage 3 (dhammapada_fixes/corpus_rebuild_design.md): the verse<->story
alignment table as its own first-class artifact, not a byproduct of the
join. "This is the project's most citable contribution."

Writes data/normalized/alignment_table.json (one record per story) and
.csv (same rows, flattened for spreadsheet/Zenodo use).

HONEST LIMITATION, stated up front rather than glossed over: the design
doc's own example row cross-references three independent sources
(anandajoti_2024, burlingame_1921, cst4) and assigns `agreement`:
`full`/`partial`/`disputed` based on where they agree or diverge -- "a
disagreement is a finding, not a bug... the most interesting thing in the
file." Stage 1 (docs/corpus_source_ownership.md) proposed fetching
Burlingame's original specifically as that independent check; Stage 2
built normalizers for the four already-licensed sources and stopped short
of fetching Burlingame/CST4 pending a decision on new external fetches
(one of which, CST4, has no confirmed license). That decision came back:
hold off for now.

So this table has exactly ONE source (anandajoti_2024, from
normalize_aj_stories.py) until that changes. `agreement` is therefore
`"single_source"` for every row -- not `"full"`, which would misrepresent
one source agreeing with itself as independent verification. This is
precisely the risk Stage 1's own text named: "a parsing error [in story
numbering/grouping] is undetectable" with one source. This table doesn't
solve that; it's built so that adding burlingame_1921/cst4 later is a
matter of populating the `sources` dict's other keys and recomputing
`agreement` per row, not restructuring the file.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def build() -> tuple[list[dict], dict]:
    root = Path(__file__).resolve().parents[3]
    aj_path = root / "data" / "normalized" / "aj_stories.jsonl"
    if not aj_path.exists():
        raise FileNotFoundError(
            f"{aj_path} not found -- run `python -m dhammapada_rag.ingest.normalize_aj_stories` first "
            f"(Stage 3 builds on Stage 2's normalized output, not data/processed/ directly)."
        )
    aj_stories = [json.loads(l) for l in aj_path.read_text(encoding="utf-8").splitlines()]

    rows = []
    for s in aj_stories:
        rows.append({
            "group_id": s["group_id"],
            "dhp_verses": s["verses"],
            "sources": {
                "anandajoti_2024": {
                    "story_no": s["group_id"],
                    "verses": s["verses"],
                    "title_en": s["title"]["en"],
                },
                # Populated once (if) Stage 2's Burlingame/CST4 normalizers exist:
                "burlingame_1921": None,
                "cst4": None,
            },
            # See module docstring: honest single-source status, not "full" --
            # "full"/"partial"/"disputed" require at least two sources to compare.
            "agreement": "single_source",
            "notes": None,
        })

    # Closure + duplication, computed here rather than re-imported from
    # ingest/validate.py: that script checks data/processed/stories.jsonl
    # (the live pipeline's own copy) against vaggas.py; this checks THIS
    # table's own rows, so a divergence between the two would itself be a
    # signal something drifted between the live pipeline and Stage 2/3's
    # rebuild track -- worth being able to see, not worth hiding by sharing
    # one check between two things that should independently agree.
    verse_to_groups: dict[int, list[str]] = {v: [] for v in range(1, 424)}
    for r in rows:
        for v in r["dhp_verses"]:
            verse_to_groups.setdefault(v, []).append(r["group_id"])

    missing = sorted(v for v, groups in verse_to_groups.items() if not groups)
    duplicated = {v: groups for v, groups in verse_to_groups.items() if len(groups) > 1}

    report = {
        "n_stories": len(rows),
        "n_verses_covered": sum(1 for g in verse_to_groups.values() if g),
        "n_verses_expected": 423,
        "missing_verses": missing,
        "duplicated_verses": duplicated,
        "closure_ok": not missing,
        "n_sources": 1,
        "agreement_breakdown": {"single_source": len(rows), "full": 0, "partial": 0, "disputed": 0},
    }
    return rows, report


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "group_id", "dhp_verses", "agreement", "notes",
            "anandajoti_2024_story_no", "anandajoti_2024_verses", "anandajoti_2024_title_en",
            "burlingame_1921", "cst4",
        ])
        for r in rows:
            aj = r["sources"]["anandajoti_2024"]
            writer.writerow([
                r["group_id"],
                ";".join(str(v) for v in r["dhp_verses"]),
                r["agreement"],
                r["notes"] or "",
                aj["story_no"],
                ";".join(str(v) for v in aj["verses"]),
                aj["title_en"],
                "" if r["sources"]["burlingame_1921"] is None else json.dumps(r["sources"]["burlingame_1921"], ensure_ascii=False),
                "" if r["sources"]["cst4"] is None else json.dumps(r["sources"]["cst4"], ensure_ascii=False),
            ])


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_dir = root / "data" / "normalized"
    json_path = out_dir / "alignment_table.json"
    csv_path = out_dir / "alignment_table.csv"
    report_path = out_dir / "alignment_table_report.json"

    rows, report = build()

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(rows, csv_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {json_path} ({len(rows)} stories)")
    print(f"Wrote {csv_path}")
    print(f"Wrote {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
