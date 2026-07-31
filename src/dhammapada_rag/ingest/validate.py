"""Build the verse<->story alignment table and validate corpus completeness.

DhammapadaRAG.txt Phase 1 items 1 and 3:
  - "Validate hard: 423 verses, 26 vaggas, no gaps."
  - "Build the verse<->story alignment table by hand and have it checked...
     Record edition-numbering variants explicitly."

The alignment here isn't hand-built from scratch: this source's own story
headers already state which Dhp verse number(s) each story explains (the
"Dhp N" / "Dhp N-M" line), so the table is *derived* from that and then
checked against the canonical 26-vagga/423-verse structure in vaggas.py --
independent ground truth, not just an internal-consistency check. Any verse
whose header-stated vagga doesn't match the canonical vagga for that verse
number is flagged as an edition-numbering variant for hand review, not
silently resolved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.vaggas import VAGGAS, vagga_for_verse  # noqa: E402


def build_and_validate(stories: list[dict]) -> tuple[dict, dict]:
    verse_to_groups: dict[int, list[str]] = {v: [] for v in range(1, 424)}
    vagga_mismatches: list[dict] = []
    out_of_range: list[dict] = []

    for s in stories:
        for verse in s["dhp_verses"]:
            if not (1 <= verse <= 423):
                out_of_range.append({"group_id": s["group_id"], "verse": verse})
                continue
            verse_to_groups[verse].append(s["group_id"])
            canonical = vagga_for_verse(verse)
            if canonical.number != s["vagga_number"]:
                vagga_mismatches.append(
                    {
                        "group_id": s["group_id"],
                        "verse": verse,
                        "story_states_vagga": s["vagga_number"],
                        "canonical_vagga_for_verse": canonical.number,
                        "canonical_vagga_name": canonical.name_pali,
                    }
                )

    missing = [v for v, groups in verse_to_groups.items() if not groups]
    duplicated = {v: groups for v, groups in verse_to_groups.items() if len(groups) > 1}

    vaggas_seen = sorted({s["vagga_number"] for s in stories})
    expected_vaggas = [v.number for v in VAGGAS]
    missing_vaggas = sorted(set(expected_vaggas) - set(vaggas_seen))
    unexpected_vaggas = sorted(set(vaggas_seen) - set(expected_vaggas))

    alignment_table = {
        str(v): {
            "vagga": vagga_for_verse(v).number,
            "vagga_name_pali": vagga_for_verse(v).name_pali,
            "group_ids": groups,
        }
        for v, groups in verse_to_groups.items()
    }

    validation_report = {
        "total_verses_expected": 423,
        "total_verses_covered": sum(1 for g in verse_to_groups.values() if g),
        "missing_verses": missing,
        "n_missing_verses": len(missing),
        "duplicated_verses": duplicated,
        "n_duplicated_verses": len(duplicated),
        "n_vaggas_expected": 26,
        "vaggas_seen": vaggas_seen,
        "missing_vaggas": missing_vaggas,
        "unexpected_vaggas": unexpected_vaggas,
        "vagga_mismatches": vagga_mismatches,
        "n_vagga_mismatches": len(vagga_mismatches),
        "out_of_range_verse_refs": out_of_range,
        "passes_hard_validation": (
            len(missing) == 0
            and len(missing_vaggas) == 0
            and len(unexpected_vaggas) == 0
            and len(out_of_range) == 0
        ),
    }

    return alignment_table, validation_report


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    stories_path = root / "data" / "processed" / "stories.jsonl"
    alignment_path = root / "data" / "processed" / "alignment_table.json"
    report_path = root / "data" / "processed" / "validation_report.json"

    with stories_path.open(encoding="utf-8") as f:
        stories = [json.loads(line) for line in f]

    alignment_table, report = build_and_validate(stories)

    alignment_path.write_text(json.dumps(alignment_table, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {alignment_path}")
    print(f"Wrote {report_path}")
    print(json.dumps({k: v for k, v in report.items() if k not in ("duplicated_verses", "vagga_mismatches")}, indent=2))
    if report["n_duplicated_verses"]:
        print(f"\nDuplicated verses ({report['n_duplicated_verses']}):")
        for v, groups in list(report["duplicated_verses"].items())[:20]:
            print(f"  Dhp {v}: {groups}")
    if report["n_vagga_mismatches"]:
        print(f"\nVagga mismatches ({report['n_vagga_mismatches']}):")
        for m in report["vagga_mismatches"][:20]:
            print(f"  {m}")


if __name__ == "__main__":
    main()
