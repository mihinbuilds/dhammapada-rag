"""Tests for Stage 5's validation_gates.py (dhammapada_fixes/corpus_rebuild_design.md).

Same pattern as test_join_verses.py / test_alignment_table.py: real-corpus
regression pins where they add signal, plus a couple of gates exercised
against synthetic records so a genuine violation is provably caught rather
than just "never seen to fire."

Run: pytest test_validation_gates.py -v
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


def _gates_module():
    sys.path.insert(0, str(ROOT / "src"))
    from dhammapada_rag.ingest import validation_gates
    return validation_gates


def test_all_hard_gates_pass_on_the_real_corpus():
    """Regression pin: as of this round, gates 1-4 all pass on the joined
    corpus. If this starts failing, it means the corpus or join_verses.py
    changed in a way Stage 5 is specifically designed to catch -- investigate
    before updating the pin."""
    _skip_unless_normalized_present()
    vg = _gates_module()
    report = vg.run_gates(ROOT)
    assert report["build_ok"] is True, report["hard_failures"]
    for name in ("1_structure", "2_field_ownership", "3_encoding", "4_alignment_closure"):
        assert report["gates"][name]["passed"] is True, name


def test_warn_gates_never_fail_the_build():
    """Gates 5-7 must always report passed=True regardless of what they
    find -- the design doc's own severity split ("warn and record"), not a
    build blocker."""
    _skip_unless_normalized_present()
    vg = _gates_module()
    report = vg.run_gates(ROOT)
    for name in ("5_metrical_sanity", "6_cross_source_agreement", "7_title_body_coherence"):
        assert report["gates"][name]["passed"] is True


def test_gate_6_matches_stage2s_measured_effect():
    """Regression pin against docs/corpus_normalization.md's own reported
    numbers (246 exact, 0 boundary artifact, 177 distinct, out of 423) --
    gate 6 recomputes the same classification Stage 2 already measured, so
    a mismatch would mean the two have drifted apart."""
    _skip_unless_normalized_present()
    vg = _gates_module()
    report = vg.run_gates(ROOT)
    g6 = report["gates"]["6_cross_source_agreement"]
    assert g6["n_exact"] == 246
    assert g6["n_boundary_artifact"] == 0
    assert g6["n_distinct"] == 177


def test_gate_1_structure_catches_a_vagga_mismatch():
    vg = _gates_module()
    records = [
        {"verse": v, "vagga": {"number": 1, "pali": "Yamakavagga", "en": "x"}}
        for v in range(1, 424)
    ]
    # Corrupt one record's recorded vagga so it disagrees with vaggas.py's
    # ground truth for verse 423 (the last verse, vagga 26).
    records[-1]["vagga"] = {"number": 1, "pali": "Yamakavagga", "en": "x"}
    result = vg.gate_1_structure(records)
    assert result["passed"] is False
    assert any(m["verse"] == 423 for m in result["vagga_mismatches"])


def test_gate_1_structure_catches_a_missing_verse():
    vg = _gates_module()
    records = [
        {"verse": v, "vagga": {"number": 1, "pali": "x", "en": "x"}}
        for v in range(1, 423)  # missing verse 423
    ]
    result = vg.gate_1_structure(records)
    assert result["passed"] is False
    assert result["missing_verses"] == [423]


def test_gate_2_field_ownership_catches_a_wrong_source():
    vg = _gates_module()
    records = [{
        "verse": 1,
        "text": {
            "pali_mahasangiti": {"value": "x", "source": "anandajoti_2017_interlinear"},
            "english_sujato": {"value": "x", "source": "suttacentral_sujato"},
            "interlinear_pali": {"value": "x", "source": "anandajoti_2017_interlinear"},
            "interlinear_english": {"value": "x", "source": "anandajoti_2017_interlinear"},
        },
    }]
    result = vg.gate_2_field_ownership(records)
    assert result["passed"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0]["field"] == "pali_mahasangiti"


def test_gate_3_encoding_catches_a_control_character():
    vg = _gates_module()
    records = [{
        "verse": 1,
        "text": {
            "pali_mahasangiti": {"value": "clean text"},
            "english_sujato": {"value": "has a \x01 control char"},
            "interlinear_pali": {"value": "clean text"},
            "interlinear_english": {"value": "clean text"},
        },
    }]
    result = vg.gate_3_encoding(records)
    assert result["passed"] is False
    assert len(result["control_characters"]) == 1


def test_gate_3_encoding_allows_curly_quotes_and_em_dash_in_pali():
    """Per docs/corpus_audit.md check 3: curly quotes and an em dash are
    genuine source typography in pali_mahasangiti (marking reported speech,
    e.g. Dhp 17), not OCR residue -- must not be flagged."""
    vg = _gates_module()
    records = [{
        "verse": 17,
        "text": {
            "pali_mahasangiti": {"value": "“papam me katan”ti tasma—dukkham"},
            "english_sujato": {"value": "clean"},
            "interlinear_pali": {"value": "clean"},
            "interlinear_english": {"value": "clean"},
        },
    }]
    result = vg.gate_3_encoding(records)
    assert result["passed"] is True


def test_gate_4_alignment_closure_uses_the_real_alignment_table():
    _skip_unless_normalized_present()
    vg = _gates_module()
    result = vg.gate_4_alignment_closure()
    assert result["passed"] is True
    assert result["n_verses_covered"] == 423
