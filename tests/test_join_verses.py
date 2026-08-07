"""Tests for Stage 4's join_verses.py (dhammapada_fixes/corpus_rebuild_design.md).

Runs against the real data/normalized/ output from Stage 2, same pattern
as test_alignment_table.py -- skipped if that hasn't been built yet.

Run: pytest test_join_verses.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _skip_unless_normalized_present():
    norm_dir = ROOT / "data" / "normalized"
    required = ["sc_pali.jsonl", "sc_sujato.jsonl", "aj_interlinear.jsonl", "aj_stories.jsonl"]
    if not all((norm_dir / name).exists() for name in required):
        pytest.skip("data/normalized/ Stage 2 outputs not present -- run the normalize_*.py scripts first")


def _joined():
    _skip_unless_normalized_present()
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.ingest.join_verses import join
    return {r["verse"]: r for r in join()}


def test_join_covers_all_423_verses():
    records = _joined()
    assert set(records) == set(range(1, 424))


def test_every_text_field_carries_provenance():
    records = _joined()
    r = records[1]
    for field in ("pali_mahasangiti", "english_sujato", "interlinear_pali", "interlinear_english"):
        entry = r["text"][field]
        assert entry["value"]
        assert entry["source"]
        assert entry["source_ref"]
        assert entry["retrieved"]


def test_source_names_are_field_specific_not_generic():
    """The design doc's own motivating example: "which field claims to be
    Mahasangiti but has a source that isn't?" must be answerable -- each
    field's `source` names the actual owning source, not a shared label."""
    records = _joined()
    r = records[1]
    assert r["text"]["pali_mahasangiti"]["source"] == "suttacentral_mahasangiti"
    assert r["text"]["english_sujato"]["source"] == "suttacentral_sujato"
    assert r["text"]["interlinear_pali"]["source"] == "anandajoti_2017_interlinear"


def test_stage2_boundary_fixes_hold_through_the_join():
    """Dhp 51 and Dhp 327 (normalize_aj_interlinear.py's own-vagga fix) and
    Dhp 423/416 (the vagga-colophon fix) must not regress once joined --
    Stage 4 reads Stage 2's output, not the raw sources, so a regression
    here would mean the join broke something Stage 2 already fixed."""
    records = _joined()
    for verse in (51, 327):
        assert records[verse]["flags"] == [], f"Dhp {verse} should have no cross_source_mismatch flag"
    assert "vaggo" not in records[423]["text"]["pali_mahasangiti"]["value"].lower()
    assert "jotikattheravatthu" not in records[416]["text"]["pali_mahasangiti"]["value"].lower()


def test_story_group_ids_populated_for_every_verse():
    records = _joined()
    assert all(records[v]["story_group_ids"] for v in range(1, 424))


def test_flags_carry_a_code_and_a_detail():
    records = _joined()
    flagged = [r for r in records.values() if r["flags"]]
    assert flagged, "expected at least one cross_source_mismatch flag given known genuine edition variance"
    for r in flagged:
        for f in r["flags"]:
            assert f["code"]
            assert f["detail"]


def test_vagga_info_matches_canonical_source():
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.vaggas import vagga_for_verse

    records = _joined()
    for verse in (1, 114, 423):
        expected = vagga_for_verse(verse)
        assert records[verse]["vagga"]["number"] == expected.number
        assert records[verse]["vagga"]["pali"] == expected.name_pali
