"""Regression tests for group_id canonicalization and the provenance audit.

The bug these exist to prevent: three modules independently decided what a
group_id looks like. stories.jsonl stored "13.2", the prompt rendered
something the model read as "g13.2", and audit() compared raw strings. Result
was a reported 100% citation-fabrication rate consisting entirely of false
positives, which then propagated into the model-size sweep.

test_prompt_renders_canonical_ids is the one that actually stops recurrence:
it asserts that whatever the prompt shows the model matches the format the
audit expects. Wire it to the real prompt renderer.

Run: pytest test_provenance.py -v
"""

from __future__ import annotations

import pytest

from schemas import (
    GROUP_ID_RE,
    AuditWarning,
    Claim,
    LayeredAnswer,
    audit,
    normalize_group_id,
    summarize,
)


def bundle(group_id: str, verses: list[int]) -> dict:
    """Minimal but build_context()-complete bundle: enough fields for
    audit()'s tests (group_id, dhp_verses) and for the prompt-renderer
    contract test below (verse_numbers, verses[].pali_mahasangiti,
    stories[].title_en are all accessed unconditionally by
    format_verse_group)."""
    return {
        "verse_numbers": verses,
        "verses": [{"verse": v, "pali_mahasangiti": f"<pali text for {v}>"} for v in verses],
        "stories": [
            {
                "group_id": group_id,
                "dhp_verses": verses,
                "title_en": f"Story about {group_id}",
                "synopsis": "A brief synopsis.",
            }
        ],
    }


BUNDLES = [bundle("13.2", [168, 169]), bundle("1.14", [19, 20]), bundle("10.5", [135])]


def answer(*claims: Claim) -> LayeredAnswer:
    return LayeredAnswer(question="q", claims=list(claims))


def codes(ws: list[AuditWarning]) -> list[str]:
    return [w.code for w in ws]


# --------------------------------------------------------------------------
# Canonicalization
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("13.2", "13.2"),
    ("g13.2", "13.2"),
    ("G13.2", "13.2"),
    ("story g13.2", "13.2"),
    ("story 13.2", "13.2"),
    ("[13.2]", "13.2"),
    ("  13.2  ", "13.2"),
    ("group 1.14", "1.14"),
    ("Dhp 20.11", "20.11"),
    ("26.1", "26.1"),
])
def test_normalizes_known_drift(raw, expected):
    assert normalize_group_id(raw) == expected


@pytest.mark.parametrize("raw", [
    "13-2",      # wrong separator: genuine malformation, do not coerce
    "13.02",     # zero-padded: not the stored form
    "27.1",      # vagga out of range (only 26 vaggas)
    "0.5",       # vagga 0 does not exist
    "13",        # no story component
    "abc",
    "",
    None,
])
def test_rejects_genuine_malformations(raw):
    assert normalize_group_id(raw) is None


def test_canonical_ids_match_the_regex():
    for gid in ("1.1", "9.12", "26.999"):
        assert GROUP_ID_RE.match(gid)


# --------------------------------------------------------------------------
# The false-positive regression
# --------------------------------------------------------------------------

def test_prefixed_id_is_not_a_hallucination():
    """The exact failure from the screenshots: 'g13.2' vs stored '13.2'."""
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id="g13.2", verse_number=168)),
        BUNDLES,
    )
    assert codes(ws) == ["MALFORMED_GROUP_ID"]
    assert summarize(ws)["error"] == 0


def test_clean_citation_produces_nothing():
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id="13.2", verse_number=169)),
        BUNDLES,
    )
    assert ws == []


# --------------------------------------------------------------------------
# Real failures still caught
# --------------------------------------------------------------------------

def test_group_not_retrieved_is_an_error():
    ws = audit(
        answer(Claim(text="...", layer="commentary", group_id="8.13", verse_number=114)),
        BUNDLES,
        corpus_group_ids={"8.13", "13.2", "1.14", "10.5"},
    )
    assert "GROUP_NOT_RETRIEVED" in codes(ws)


def test_unknown_group_id_distinguished_from_not_retrieved():
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id="26.99", verse_number=168)),
        BUNDLES,
        corpus_group_ids={"13.2", "1.14", "10.5"},
    )
    assert "UNKNOWN_GROUP_ID" in codes(ws)


def test_stitched_provenance_still_caught_when_group_also_wrong():
    """The elif bug: previously this returned only the group warning."""
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id="g13.2", verse_number=287)),
        BUNDLES,
    )
    assert "MALFORMED_GROUP_ID" in codes(ws)
    assert "VERSE_GROUP_MISMATCH" in codes(ws)


def test_verse_only_citation_is_validated():
    """Previously unreachable: every validity branch required group_id."""
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id=None, verse_number=999)),
        BUNDLES,
    )
    assert codes(ws) == ["VERSE_NOT_RETRIEVED"]


def test_missing_provenance():
    ws = audit(answer(Claim(text="...", layer="commentary")), BUNDLES)
    assert codes(ws) == ["MISSING_PROVENANCE"]


def test_unparseable_id_is_an_error_not_a_warning():
    ws = audit(
        answer(Claim(text="...", layer="verse", group_id="13-2", verse_number=168)),
        BUNDLES,
    )
    assert "UNPARSEABLE_GROUP_ID" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_synthesis_with_citation_is_info_only():
    ws = audit(
        answer(Claim(text="...", layer="synthesis", group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert codes(ws) == ["SYNTHESIS_WITH_CITATION"]
    assert summarize(ws)["error"] == 0


# --------------------------------------------------------------------------
# The contract test -- wire this to the real prompt renderer
# --------------------------------------------------------------------------

def test_prompt_renders_canonical_ids():
    """Every group_id the prompt shows the model must be canonical.

    This is the test that prevents the original bug class from recurring: it
    fails if the prompt ever decorates an ID that the audit expects bare.
    """
    from dhammapada_rag.generate.prompt import build_context

    rendered = build_context(BUNDLES)
    for b in BUNDLES:
        for s in b["stories"]:
            gid = s["group_id"]
            assert f"group_id: {gid}" in rendered, f"prompt never renders bare {gid!r} via the 'group_id:' token"
            for bad in (f"g{gid}", f"[{gid}]", f"story g{gid}", f"story {gid}", f"group {gid}"):
                assert bad not in rendered, f"prompt renders decorated id {bad!r}"


def test_corpus_ids_are_all_canonical():
    """Guard the other end: stories.jsonl itself must hold canonical IDs.

    Point this at data/processed/stories.jsonl in your repo.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "processed" / "stories.jsonl"
    if not path.exists():
        pytest.skip("stories.jsonl not present next to this test")

    for line in path.read_text(encoding="utf-8").splitlines():
        gid = json.loads(line)["group_id"]
        assert normalize_group_id(gid) == gid, f"non-canonical group_id in corpus: {gid!r}"
