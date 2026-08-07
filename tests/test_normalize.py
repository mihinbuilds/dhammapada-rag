"""Tests for Stage 2's normalizers (dhammapada_fixes/corpus_rebuild_design.md)
and the shared _sc_segments loader they depend on.

Run: pytest test_normalize.py -v
"""

from __future__ import annotations

from dhammapada_rag.ingest._sc_segments import load_sc_segments


def _write_sc_json(tmp_path, filename, data):
    import json
    (tmp_path / filename).write_text(json.dumps(data), encoding="utf-8")


def test_sc_segments_joins_ordinary_verse_lines(tmp_path):
    _write_sc_json(tmp_path, "dhp1-2.json", {
        "dhp1:0": "header, excluded",
        "dhp1:1": "Line one,",
        "dhp1:2": "line two.",
    })
    out = load_sc_segments(tmp_path)
    assert out[1]["text"] == "Line one, line two."
    assert out[1]["source_ref"] == ["dhp1:1", "dhp1:2"]


def test_sc_segments_strips_vagga_colophon_tail(tmp_path):
    """The Round 6/Stage 0 finding: a vagga-final verse's segment range
    carries the closing colophon appended with no distinct marker -- only a
    segment whose ENTIRE text is "<word>vaggo <ordinal>." identifies where
    the real verse ends."""
    _write_sc_json(tmp_path, "dhp1-2.json", {
        "dhp1:1": "Manopubbaṅgamā dhammā,",
        "dhp1:2": "manoseṭṭhā manomayā.",
        "dhp1:3": "Yamakavaggo paṭhamo.",
        "dhp1:4": "Ettāvatā some colophon enumeration text.",
    })
    out = load_sc_segments(tmp_path)
    assert out[1]["text"] == "Manopubbaṅgamā dhammā, manoseṭṭhā manomayā."
    assert out[1]["source_ref"] == ["dhp1:1", "dhp1:2"]


def test_sc_segments_excludes_mid_sequence_title_header(tmp_path):
    """A second story's title header (segment key "N.0" for N > 0, e.g.
    "5.0") is not verse text -- distinct from the "0"/"0.N" header exclusion,
    which only covers the verse's OWN leading header."""
    _write_sc_json(tmp_path, "dhp1-2.json", {
        "dhp2:1": "First line,",
        "dhp2:2": "second line;",
        "dhp2:3.0": "Someotherstoryvatthu",
        "dhp2:3": "third line,",
        "dhp2:4": "fourth line.",
    })
    out = load_sc_segments(tmp_path)
    assert "Someotherstoryvatthu" not in out[2]["text"]
    assert out[2]["text"] == "First line, second line; third line, fourth line."


def test_sc_segments_excludes_leading_zero_header(tmp_path):
    _write_sc_json(tmp_path, "dhp1-2.json", {
        "dhp1:0": "Storytitlevatthu",
        "dhp1:0.1": "Also excluded",
        "dhp1:1": "Real verse line.",
    })
    out = load_sc_segments(tmp_path)
    assert out[1]["text"] == "Real verse line."


def test_sc_segments_reads_across_multiple_files(tmp_path):
    _write_sc_json(tmp_path, "dhp1-1.json", {"dhp1:1": "Verse one."})
    _write_sc_json(tmp_path, "dhp2-2.json", {"dhp2:1": "Verse two."})
    out = load_sc_segments(tmp_path)
    assert out[1]["text"] == "Verse one."
    assert out[2]["text"] == "Verse two."


def test_sc_segments_source_ref_lists_exact_segments_used():
    """The design doc's own stated purpose for source_ref: locate a value
    in the original in ten seconds. A colophon segment excluded from `text`
    must also be excluded from source_ref -- otherwise the pointer lies
    about what contributed to the value."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        _write_sc_json(Path(d), "dhp1-1.json", {
            "dhp1:1": "Kept line.",
            "dhp1:2": "Vaggo paṭhamo.",
            "dhp1:3": "Excluded colophon line.",
        })
        out = load_sc_segments(Path(d))
    assert out[1]["source_ref"] == ["dhp1:1"]
