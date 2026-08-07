"""Tests for Stage 3's build_alignment_table.py
(dhammapada_fixes/corpus_rebuild_design.md).

Exercises the closure/duplication computation directly against synthetic
rows, rather than the real 305-story data/normalized/aj_stories.jsonl, so
these stay fast and independent of corpus content.

Run: pytest test_alignment_table.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _skip_unless_normalized_present():
    if not (ROOT / "data" / "normalized" / "aj_stories.jsonl").exists():
        pytest.skip("data/normalized/aj_stories.jsonl not present -- run normalize_aj_stories.py first")


def _closure_and_duplicates(rows: list[dict]) -> tuple[list[int], dict[int, list[str]]]:
    """Mirrors build()'s closure logic in build_alignment_table.py --
    duplicated here rather than imported, since build() reads from disk
    and this test wants to exercise just the pure computation."""
    verse_to_groups: dict[int, list[str]] = {v: [] for v in range(1, 424)}
    for r in rows:
        for v in r["dhp_verses"]:
            verse_to_groups.setdefault(v, []).append(r["group_id"])
    missing = sorted(v for v, groups in verse_to_groups.items() if not groups)
    duplicated = {v: groups for v, groups in verse_to_groups.items() if len(groups) > 1}
    return missing, duplicated


def test_full_coverage_no_gaps():
    rows = [{"group_id": f"1.{i}", "dhp_verses": [v]} for i, v in enumerate(range(1, 424), start=1)]
    missing, duplicated = _closure_and_duplicates(rows)
    assert missing == []
    assert duplicated == {}


def test_missing_verse_detected():
    rows = [{"group_id": f"1.{i}", "dhp_verses": [v]} for i, v in enumerate(range(2, 424), start=1)]
    missing, _ = _closure_and_duplicates(rows)
    assert missing == [1]


def test_duplicated_verse_listed_not_failed():
    """The design doc's own instruction: a verse claimed by two stories is
    listed, not treated as a hard failure -- some are legitimate (Dhp 416)."""
    rows = [{"group_id": f"1.{i}", "dhp_verses": [v]} for i, v in enumerate(range(1, 424), start=1)]
    rows.append({"group_id": "1.999", "dhp_verses": [1]})  # second story also claims Dhp 1
    missing, duplicated = _closure_and_duplicates(rows)
    assert missing == []
    assert duplicated == {1: ["1.1", "1.999"]}


def test_single_source_agreement_status():
    """agreement must read 'single_source', not 'full' -- one source
    agreeing with itself is not independent verification, and calling it
    'full' would misrepresent that (see build_alignment_table.py's
    module docstring)."""
    _skip_unless_normalized_present()
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.ingest.build_alignment_table import build

    rows, report = build()
    assert all(r["agreement"] == "single_source" for r in rows)
    assert report["agreement_breakdown"]["full"] == 0
    assert report["agreement_breakdown"]["single_source"] == len(rows)


def test_alignment_table_closure_matches_known_corpus_state():
    """Regression pin against the real corpus: 423/423 covered, exactly one
    known legitimate duplicate (Dhp 416, stories 26.33/26.34 -- documented
    since Round 4/5 of docs/generation.md). If this ever changes, it means
    the corpus or normalize_aj_stories.py changed, not that this test is
    wrong -- update the pin deliberately, don't just silence the assert."""
    _skip_unless_normalized_present()
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.ingest.build_alignment_table import build

    _, report = build()
    assert report["closure_ok"] is True
    assert report["n_verses_covered"] == 423
    assert report["duplicated_verses"] == {416: ["26.33", "26.34"]}
