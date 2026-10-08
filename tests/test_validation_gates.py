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
    required = ["aj_interlinear.jsonl", "aj_stories.jsonl"]
    if not all((norm_dir / name).exists() for name in required):
        pytest.skip("data/normalized/ Stage 2 outputs not present -- run the normalize_aj_*.py scripts first")


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
    for name in ("5_metrical_sanity", "7_title_body_coherence"):
        assert report["gates"][name]["passed"] is True


def test_gate_6_is_retired():
    """Round 13: gate 6 compared the SuttaCentral Pali with Ānandajoti's;
    the SuttaCentral edition is gone, so the gate no longer runs."""
    _skip_unless_normalized_present()
    vg = _gates_module()
    report = vg.run_gates(ROOT)
    assert "6_cross_source_agreement" not in report["gates"]
    assert "Gate 6 -- Cross-source agreement (retired)" in vg.render_markdown(report)


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
            "interlinear_pali": {"value": "x", "source": "some_other_edition"},
            "interlinear_english": {"value": "x", "source": "anandajoti_2017_interlinear"},
        },
    }]
    result = vg.gate_2_field_ownership(records)
    assert result["passed"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0]["field"] == "interlinear_pali"


def test_gate_2_field_ownership_rejects_a_field_not_in_the_table():
    """A removed field reappearing (e.g. a stale join reintroducing a
    SuttaCentral field) must fail, not pass silently."""
    vg = _gates_module()
    records = [{
        "verse": 1,
        "text": {
            "interlinear_pali": {"value": "x", "source": "anandajoti_2017_interlinear"},
            "interlinear_english": {"value": "x", "source": "anandajoti_2017_interlinear"},
            "removed_field": {"value": "x", "source": "suttacentral"},
        },
    }]
    result = vg.gate_2_field_ownership(records)
    assert result["passed"] is False
    assert result["violations"][0]["problem"] == "field not in the ownership table at all"


def test_gate_3_encoding_catches_a_control_character():
    vg = _gates_module()
    records = [{
        "verse": 1,
        "text": {
            "interlinear_pali": {"value": "clean text"},
            "interlinear_english": {"value": "has a \x01 control char"},
        },
    }]
    result = vg.gate_3_encoding(records)
    assert result["passed"] is False
    assert len(result["control_characters"]) == 1


def test_gate_3_encoding_allows_the_interlinears_own_typography():
    """Per docs/corpus_audit.md check 3: curly quotes and dashes are genuine
    source typography (marking reported speech, e.g. Dhp 17), and Ānandajoti
    marks metrically short e/o with a breve -- none of it is OCR residue."""
    vg = _gates_module()
    records = [{
        "verse": 17,
        "text": {
            "interlinear_pali": {"value": "“papam me katan”ti tasma—dukkham – kĕna? ŏ: (x)!"},
            "interlinear_english": {"value": "clean"},
        },
    }]
    result = vg.gate_3_encoding(records)
    assert result["passed"] is True


def test_gate_3_encoding_still_flags_a_digit_in_pali():
    vg = _gates_module()
    records = [{
        "verse": 1,
        "text": {
            "interlinear_pali": {"value": "manopubbaṅgamā dhammā 123"},
            "interlinear_english": {"value": "clean"},
        },
    }]
    result = vg.gate_3_encoding(records)
    assert result["passed"] is False
    assert result["pali_charset_violations"][0]["field"] == "interlinear_pali"


def test_gate_4_alignment_closure_uses_the_real_alignment_table():
    _skip_unless_normalized_present()
    vg = _gates_module()
    result = vg.gate_4_alignment_closure()
    assert result["passed"] is True
    assert result["n_verses_covered"] == 423
