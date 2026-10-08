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
    required = ["aj_interlinear.jsonl", "aj_stories.jsonl"]
    if not all((norm_dir / name).exists() for name in required):
        pytest.skip("data/normalized/ Stage 2 outputs not present -- run the normalize_aj_*.py scripts first")


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
    for field in ("interlinear_pali", "interlinear_english"):
        entry = r["text"][field]
        assert entry["value"]
        assert entry["source"]
        assert entry["source_ref"]
        assert entry["retrieved"]


def test_source_names_are_field_specific_not_generic():
    """The design doc's own motivating example: "which field claims to be
    one edition but has a source that isn't?" must be answerable -- each
    field's `source` names the actual owning source, not a shared label."""
    records = _joined()
    r = records[1]
    assert r["text"]["interlinear_pali"]["source"] == "anandajoti_2017_interlinear"
    assert r["text"]["interlinear_english"]["source"] == "anandajoti_2017_interlinear"


def test_no_suttacentral_fields_survive_the_join():
    """Round 13: SuttaCentral's Pali and English were removed at their
    request (data/raw/PROVENANCE.md). Only Ānandajoti's fields remain."""
    records = _joined()
    for r in records.values():
        assert set(r["text"]) == {"interlinear_pali", "interlinear_english"}
        assert not any(e["source"].startswith("suttacentral") for e in r["text"].values())


def test_stage2_boundary_fixes_hold_through_the_join():
    """Dhp 51 and Dhp 327 (normalize_aj_interlinear.py's own-vagga fix) and
    Dhp 423 (vagga-colophon contamination) must not regress once joined --
    Stage 4 reads Stage 2's output, not the raw sources, so a regression
    here would mean the join broke something Stage 2 already fixed."""
    records = _joined()
    assert "yamakavaggo" not in records[51]["text"]["interlinear_pali"]["value"].lower()
    assert "vaggo" not in records[423]["text"]["interlinear_pali"]["value"].lower()


def test_story_group_ids_populated_for_every_verse():
    records = _joined()
    assert all(records[v]["story_group_ids"] for v in range(1, 424))


def test_flags_are_empty_with_one_pali_edition():
    """cross_source_mismatch compared two Pali editions; with the
    SuttaCentral one removed (Round 13) there is nothing to compare."""
    records = _joined()
    assert all(r["flags"] == [] for r in records.values())


def test_vagga_info_matches_canonical_source():
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.vaggas import vagga_for_verse

    records = _joined()
    for verse in (1, 114, 423):
        expected = vagga_for_verse(verse)
        assert records[verse]["vagga"]["number"] == expected.number
        assert records[verse]["vagga"]["pali"] == expected.name_pali
