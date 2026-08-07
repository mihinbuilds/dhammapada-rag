"""Regression tests for group_id canonicalization and the provenance audit.

The bug these exist to prevent: three modules independently decided what a
group_id looks like. stories.jsonl stored "13.2", the prompt rendered
something the model read as "g13.2", and audit() compared raw strings. Result
was a reported 100% citation-fabrication rate consisting entirely of false
positives, which then propagated into the model-size sweep.

test_prompt_renders_canonical_ids is the one that actually stops recurrence:
it asserts that whatever the prompt shows the model matches the format the
audit expects. Wire it to the real prompt renderer.

Round 4/5 amendment (Task K/L amendment): `Claim` is now a discriminated
union -- VerseClaim / CommentaryClaim / SynthesisClaim -- with group_id and
verse_number required (non-Optional) on the first two and absent entirely
from the third. Several tests below that used to construct a claim with a
missing or null citation to exercise MISSING_PROVENANCE / SYNTHESIS_WITH_
CITATION now instead assert that construction itself fails (pydantic
ValidationError) or silently drops the extra fields -- the point of the
amendment is that those failure states are unrepresentable, not merely
caught after the fact.

Run: pytest test_provenance.py -v
"""

from __future__ import annotations

import unicodedata

import pytest
from pydantic import ValidationError

from schemas import (
    GROUP_ID_RE,
    AlignmentClaim,
    AuditWarning,
    CommentaryClaim,
    LayeredAnswer,
    SynthesisClaim,
    VerseClaim,
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


def answer(*claims, source_disposition: dict | None = None) -> LayeredAnswer:
    # Round 8, Task Z: source_disposition is required on LayeredAnswer but
    # defaults to {} here -- audit() treats an empty dict as "this caller
    # didn't populate the field" and skips the MISSING_DISPOSITION/
    # UNKNOWN_DISPOSITION_GROUP/DISPOSITION_CONTRADICTS_CLAIMS checks
    # entirely (see schemas.py's audit() docstring), so every existing test
    # in this file -- none of which exercise source_disposition -- is
    # unaffected. Tests that DO exercise it pass source_disposition=...
    # explicitly.
    return LayeredAnswer(question="q", claims=list(claims), source_disposition=source_disposition or {})


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
        answer(VerseClaim(text="...", group_id="g13.2", verse_number=168)),
        BUNDLES,
    )
    assert codes(ws) == ["MALFORMED_GROUP_ID"]
    assert summarize(ws)["error"] == 0


def test_clean_citation_produces_nothing():
    ws = audit(
        answer(VerseClaim(text="...", group_id="13.2", verse_number=169)),
        BUNDLES,
    )
    assert ws == []


# --------------------------------------------------------------------------
# Real failures still caught
# --------------------------------------------------------------------------

def test_group_not_retrieved_is_an_error():
    ws = audit(
        answer(CommentaryClaim(text="...", group_id="8.13", verse_number=114)),
        BUNDLES,
        corpus_group_ids={"8.13", "13.2", "1.14", "10.5"},
    )
    assert "GROUP_NOT_RETRIEVED" in codes(ws)


def test_unknown_group_id_distinguished_from_not_retrieved():
    ws = audit(
        answer(VerseClaim(text="...", group_id="26.99", verse_number=168)),
        BUNDLES,
        corpus_group_ids={"13.2", "1.14", "10.5"},
    )
    assert "UNKNOWN_GROUP_ID" in codes(ws)


def test_stitched_provenance_still_caught_when_group_also_wrong():
    """The elif bug: previously this returned only the group warning."""
    ws = audit(
        answer(VerseClaim(text="...", group_id="g13.2", verse_number=287)),
        BUNDLES,
    )
    assert "MALFORMED_GROUP_ID" in codes(ws)
    assert "VERSE_GROUP_MISMATCH" in codes(ws)


def test_unresolvable_group_id_still_validates_verse_number():
    """Round 4/5 amendment: a citation with no group_id at all is no longer
    representable (group_id is required), so the old 'verse-only citation'
    scenario is now reached via an unparseable group_id instead -- both
    UNPARSEABLE_GROUP_ID and VERSE_NOT_RETRIEVED fire together, since the
    group_id half of the citation is independently broken too."""
    ws = audit(
        answer(VerseClaim(text="...", group_id="not-a-group-id", verse_number=999)),
        BUNDLES,
    )
    assert "UNPARSEABLE_GROUP_ID" in codes(ws)
    assert "VERSE_NOT_RETRIEVED" in codes(ws)


def test_missing_provenance_is_unrepresentable():
    """Round 4/5 amendment (Task K/L amendment): group_id and verse_number
    are required, non-Optional fields on VerseClaim/CommentaryClaim, so a
    verse or commentary claim citing nothing can no longer be constructed at
    all. MISSING_PROVENANCE moves from an audit()-time warning caught after
    the fact to a pydantic ValidationError at construction time -- this is
    the whole point of the amendment, proven directly rather than inferred
    from a warning list."""
    with pytest.raises(ValidationError):
        CommentaryClaim(text="...")
    with pytest.raises(ValidationError):
        VerseClaim(text="...")
    with pytest.raises(ValidationError):
        CommentaryClaim(text="...", group_id="13.2")  # verse_number still missing
    with pytest.raises(ValidationError):
        VerseClaim(text="...", verse_number=168)  # group_id still missing


def test_unparseable_id_is_an_error_not_a_warning():
    ws = audit(
        answer(VerseClaim(text="...", group_id="13-2", verse_number=168)),
        BUNDLES,
    )
    assert "UNPARSEABLE_GROUP_ID" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_synthesis_claim_cannot_carry_citation_fields():
    """Round 4/5 amendment: SynthesisClaim has no group_id/verse_number
    fields at all -- pydantic's default 'extra=ignore' silently drops them
    if passed, so SYNTHESIS_WITH_CITATION is now unrepresentable by
    construction rather than merely unobserved (same treatment Task K gave
    its own now-unreachable citation-format codes)."""
    s = SynthesisClaim(text="...", group_id="13.2", verse_number=168)
    assert not hasattr(s, "group_id")
    assert not hasattr(s, "verse_number")
    ws = audit(answer(s), BUNDLES)
    assert codes(ws) == []


# --------------------------------------------------------------------------
# STOP GATE 3 fix: zero-commentary answers must be visible, not silent
# --------------------------------------------------------------------------

def bundle_with_commentary(group_id: str, verses: list[int], vatthu_words: int = 60) -> dict:
    b = bundle(group_id, verses)
    b["stories"][0]["vatthu"] = " ".join(["word"] * vatthu_words)
    return b


def test_no_commentary_engagement_flagged_when_commentary_available():
    """The reproduced STOP GATE 3 failure: retrieved commentary substantial,
    answer entirely verse-tagged. Must be visible in the warning stream, not
    silently schema-valid."""
    rich_bundles = [bundle_with_commentary("8.13", [114])]
    ws = audit(
        answer(VerseClaim(text="...", group_id="8.13", verse_number=114)),
        rich_bundles,
    )
    assert "NO_COMMENTARY_ENGAGEMENT" in codes(ws)
    assert summarize(ws)["warning"] >= 1


def test_no_commentary_engagement_not_flagged_when_present():
    rich_bundles = [bundle_with_commentary("8.13", [114])]
    ws = audit(
        answer(
            VerseClaim(text="verse claim", group_id="8.13", verse_number=114),
            CommentaryClaim(text="commentary claim", group_id="8.13", verse_number=114),
        ),
        rich_bundles,
    )
    assert "NO_COMMENTARY_ENGAGEMENT" not in codes(ws)


def test_no_commentary_engagement_not_flagged_when_no_commentary_retrieved():
    """BUNDLES (module-level fixture) carries only a 4-word placeholder
    synopsis, under MIN_COMMENTARY_WORDS -- an all-verse answer against it is
    not a coverage failure, since there was nothing substantive to engage
    with. Regression guard: every other test in this file uses BUNDLES with
    all-verse answers and must keep passing unaffected by this check."""
    ws = audit(
        answer(VerseClaim(text="...", group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "NO_COMMENTARY_ENGAGEMENT" not in codes(ws)


# --------------------------------------------------------------------------
# Round 2, Task B: citation scaffolding leaking into claim text
# --------------------------------------------------------------------------

def test_claim_text_carries_no_citation_markers():
    for bad in ("group_id", "verse_number", "citation_fields"):
        assert bad not in VerseClaim(text="The verse states X",
                                      group_id="8.13", verse_number=114).text


def test_citation_in_text_is_flagged_as_error():
    """The actual observed failure: a commentary claim whose `text` begins
    with the prompt's own citation scaffolding. MISSING_PROVENANCE alone
    doesn't name that the text is copied scaffolding, not composed prose --
    CITATION_IN_TEXT does. (Round 4/5 amendment: the original reproduction
    also left group_id/verse_number null; that half is now unrepresentable,
    so a valid citation is supplied here -- CITATION_IN_TEXT is checked
    independently of whether the structured fields are also correct, per
    test_citation_in_text_flagged_even_when_fields_also_populated below.)"""
    ws = audit(
        answer(CommentaryClaim(
            text="group_id: 15.6; verse_number: 204 The story of the Gifts beyond Compare...",
            group_id="13.2", verse_number=168,
        )),
        BUNDLES,
    )
    assert "CITATION_IN_TEXT" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_citation_in_text_flagged_even_when_fields_also_populated():
    """A leaked marker makes a claim untraceable regardless of whether the
    structured fields happen to also be correct -- checked independently,
    not only as a fallback for when fields are null."""
    ws = audit(
        answer(CommentaryClaim(
            text="<<citation_fields group_id=13.2 verse_number=168>> Kisa Gotami sought mustard seeds.",
            group_id="13.2", verse_number=168,
        )),
        BUNDLES,
    )
    assert "CITATION_IN_TEXT" in codes(ws)


def test_clean_commentary_claim_not_flagged_for_citation_in_text():
    ws = audit(
        answer(CommentaryClaim(
            text="Kisa Gotami sought mustard seeds from a house that had never known death.",
            group_id="13.2", verse_number=168,
        )),
        BUNDLES,
    )
    assert "CITATION_IN_TEXT" not in codes(ws)


def test_prompt_never_renders_a_bare_labeled_citation_line_in_commentary_block():
    """Round 2 regression guard: the commentary block's citation must be a
    <<citation_fields ...>> marker, not a "group_id: X" / "cite this
    commentary as verse_number: Y" line a model could copy into prose."""
    from dhammapada_rag.generate.prompt import format_verse_group

    b = bundle_with_commentary("8.13", [114])
    rendered = format_verse_group(b)
    assert "<<citation_fields group_id=8.13 verse_number=114>>" in rendered
    assert "cite this commentary as verse_number:" not in rendered


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


# --------------------------------------------------------------------------
# Round 5, Task L: layer/field label leaked as a sentence-opening prefix
# --------------------------------------------------------------------------

@pytest.mark.parametrize("prefix", ["verse:", "commentary:", "synthesis:", "group_id:", "verse_number:"])
def test_label_in_text_flags_every_prefix(prefix):
    ws = audit(
        answer(CommentaryClaim(text=f"{prefix} some claim content that follows the label.",
                                group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "LABEL_IN_TEXT" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_label_in_text_is_case_insensitive_and_ignores_leading_whitespace():
    ws = audit(
        answer(CommentaryClaim(text="  Commentary: The story explains the occasion.",
                                group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "LABEL_IN_TEXT" in codes(ws)


def test_label_in_text_not_flagged_when_label_is_not_a_prefix():
    """The word appearing later in the sentence, or as part of another word,
    must not trip this -- only a claim that OPENS with its own label."""
    ws = audit(
        answer(CommentaryClaim(text="The commentary explains that the verse was spoken at Jetavana.",
                                group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "LABEL_IN_TEXT" not in codes(ws)


def test_label_in_text_and_citation_in_text_are_independent_checks():
    """A claim can trip one, the other, both, or neither -- they check
    different things (a leading label vs. scaffolding leaked anywhere)."""
    only_label = audit(
        answer(VerseClaim(text="verse: some content with no scaffolding markers at all.",
                           group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "LABEL_IN_TEXT" in codes(only_label)
    assert "CITATION_IN_TEXT" not in codes(only_label)

    only_citation = audit(
        answer(VerseClaim(text="Some content that mentions group_id: mid-sentence, not as an opener.",
                           group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "CITATION_IN_TEXT" in codes(only_citation)
    assert "LABEL_IN_TEXT" not in codes(only_citation)


# --------------------------------------------------------------------------
# Round 4, Task F: verse text relabelled as commentary
# --------------------------------------------------------------------------

def bundle_with_verse_text(group_id: str, verse: int, verse_text: str) -> dict:
    b = bundle(group_id, [verse])
    b["verses"][0]["pali_mahasangiti"] = verse_text
    return b


DHP_222_TEXT = (
    "When anger surges like a lurching chariot, keep it in check. That's "
    "what I call a charioteer; others just hold the reins."
)


def test_verbatim_verse_tagged_commentary_is_flagged():
    """The actual observed failure: Dhp 222's own words, tagged 'commentary'
    because the model needed to satisfy the COVERAGE instruction and had
    little else to draw on."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(CommentaryClaim(text=DHP_222_TEXT, group_id="5.4", verse_number=222)),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_same_sentence_tagged_verse_is_not_flagged():
    """The mirror case: the identical wording, correctly tagged 'verse',
    must not trip the commentary-only check."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(VerseClaim(text=DHP_222_TEXT, group_id="5.4", verse_number=222)),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" not in codes(ws)


def test_genuine_narrative_commentary_is_not_flagged():
    """A real commentary claim, wording nothing like the verse, must not be
    flagged just for being tagged 'commentary'."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(CommentaryClaim(
            text="A quarrelsome bhikkhu was rebuked by the Buddha at Jetavana for his temper.",
            group_id="5.4", verse_number=222,
        )),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" not in codes(ws)


def test_commentary_legitimately_quoting_the_verse_is_not_flagged():
    """Moderate overlap is expected and tolerated -- a nidana commonly opens
    by naming the verse it explains. Only a dominant overlap (> threshold)
    is evidence of mislabelling, not any shared wording at all."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(CommentaryClaim(
            text="The Buddha spoke the verse about anger and the chariot to a monk who lost his temper "
                 "during a dispute over robes at the monastery in Savatthi.",
            group_id="5.4", verse_number=222,
        )),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" not in codes(ws)


def test_short_claim_is_not_scored():
    """Below MIN_CONTENT_WORDS a claim is too short to measure reliably --
    must not be flagged just because its handful of words happen to appear
    in the verse."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(CommentaryClaim(text="Keep anger in check.", group_id="5.4", verse_number=222)),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" not in codes(ws)


def test_verse_text_as_commentary_claim_without_citation_is_unrepresentable():
    """Round 4, Task G found live a 'commentary' claim that was verbatim Dhp
    39's own words AND carried no group_id/verse_number at all -- both
    VERSE_TEXT_AS_COMMENTARY and MISSING_PROVENANCE had to fire, and neither
    could gate the other. Round 4/5 amendment: the missing-citation half of
    that scenario can no longer be constructed at all, proven directly."""
    with pytest.raises(ValidationError):
        CommentaryClaim(text=DHP_222_TEXT)


def test_verse_text_as_commentary_falls_back_to_union_when_verse_number_unresolvable():
    """A commentary claim citing a verse_number outside the retrieved set is
    still checkable against the union of retrieved verse text -- this is an
    independent content check from whatever the citation-validity tier
    (VERSE_GROUP_MISMATCH etc.) makes of the same claim."""
    b = bundle_with_verse_text("5.4", 222, DHP_222_TEXT)
    ws = audit(
        answer(CommentaryClaim(text=DHP_222_TEXT, group_id="5.4", verse_number=999)),
        [b],
    )
    assert "VERSE_TEXT_AS_COMMENTARY" in codes(ws)


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


# --------------------------------------------------------------------------
# Round 4, Task J: pali_support validated as a substring of the cited
# verse's own Pali (pali_mahasangiti), NFC-normalized on both sides
# --------------------------------------------------------------------------

PALI_222 = "Yo ve uppatitaṃ kodhaṃ rathaṃ bhantaṃva vāraye"


def test_pali_support_matching_substring_not_flagged():
    b = bundle_with_verse_text("5.4", 222, PALI_222)
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222,
                           pali_support="uppatitaṃ kodhaṃ")),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)


def test_pali_support_not_a_substring_is_flagged():
    b = bundle_with_verse_text("5.4", 222, PALI_222)
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222,
                           pali_support="completely fabricated pali text")),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_pali_support_from_a_different_verse_is_flagged():
    """A quote that is genuine Pali, but not from the *cited* verse, is a
    fabricated primary source for this claim just the same as an invented
    string -- checked against the cited verse_number's own text only."""
    b1 = bundle_with_verse_text("5.4", 222, PALI_222)
    b2 = bundle("1.1", [1])
    b2["verses"][0]["pali_mahasangiti"] = "Manopubbaṅgamā dhammā manoseṭṭhā manomayā"
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222,
                           pali_support="Manopubbaṅgamā dhammā")),
        [b1, b2],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" in codes(ws)


def test_pali_support_absent_is_not_flagged():
    """pali_support is optional on the field; absence alone is not a
    PALI_QUOTE_NOT_IN_SOURCE failure -- the prompt asks for it, but this
    check only fires on a quote that fails to resolve."""
    b = bundle_with_verse_text("5.4", 222, PALI_222)
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222)),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)


def test_pali_support_nfc_normalization():
    """Combining-character differences between how the model reproduces
    diacritics and how the corpus stores them must not register as a
    mismatch -- both sides are NFC-normalized before comparison."""
    decomposed_source = unicodedata.normalize("NFD", PALI_222)
    b = bundle_with_verse_text("5.4", 222, decomposed_source)
    composed_quote = unicodedata.normalize("NFC", "uppatitaṃ kodhaṃ")
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222,
                           pali_support=composed_quote)),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)


def test_pali_support_only_checked_when_bundles_given():
    ws = audit(
        answer(VerseClaim(text="Anger is checked like a chariot.", group_id="5.4", verse_number=222,
                           pali_support="anything")),
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)


# --------------------------------------------------------------------------
# Round 6, Task P: three-tier Pali matching (exact / edition variant /
# fabrication). Worked examples are the brief's own table: Dhp 221's
# "sabbam-atikkameyya" vs Mahasangiti's "sabbamatikkameyya" (one hyphen),
# Dhp 222's "tam-ahaṁ"/"bhantaṁ va" vs "Tamahaṁ"/"bhantaṁva" (space, hyphen,
# case), Dhp 223 exact. Task O's probe found the hyphenated forms reach the
# model's own prompt via the story's narrative Pali (Ānandajoti's edition),
# not just pali_mahasangiti -- so the widened candidate set below includes
# interlinear_pali and a story's pali_verse, not pali_mahasangiti alone.
# --------------------------------------------------------------------------

MAHASANGITI_221 = (
    "Kodhaṁ jahe vippajaheyya mānaṁ, Saṁyojanaṁ sabbamatikkameyya; "
    "Taṁ nāmarūpasmimasajjamānaṁ, Akiñcanaṁ nānupatanti dukkhā."
)
ANANDAJOTI_221 = (
    "Kodhaṁ jahe, vippajaheyya mānaṁ, saṁyojanaṁ sabbam-atikkameyya, "
    "taṁ nāmarūpasmiṁ asajjamānaṁ, akiñcanaṁ nānupatanti dukkhā."
)


def bundle_with_two_pali_editions(group_id: str, verse: int, mahasangiti: str, interlinear: str) -> dict:
    b = bundle(group_id, [verse])
    b["verses"][0]["pali_mahasangiti"] = mahasangiti
    b["verses"][0]["interlinear_pali"] = interlinear
    return b


def test_pali_quote_matching_only_a_different_edition_is_warning_not_error():
    """The Round 6 finding: a quote absent from pali_mahasangiti but present
    verbatim in interlinear_pali (a field genuinely in the model's own
    context, per Task O) is a citable, exact match against THAT field --
    not an error, and not even folded-orthography 'variant' once the
    candidate set is widened to the field the model actually copied from."""
    b = bundle_with_two_pali_editions("20.11", 221, MAHASANGITI_221, ANANDAJOTI_221)
    ws = audit(
        answer(VerseClaim(text="Overcome all fetters.", group_id="20.11", verse_number=221,
                           pali_support="sabbam-atikkameyya")),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)
    assert "PALI_QUOTE_ORTHOGRAPHIC_VARIANT" not in codes(ws)


def test_pali_quote_orthographic_variant_matches_no_field_verbatim_is_warning():
    """A quote that matches no available field byte-for-byte, but folds to
    match one once hyphenation/spacing/case/niggahita variants are
    normalized away, is edition variance -- warning, not error."""
    b = bundle_with_two_pali_editions("20.11", 221, MAHASANGITI_221, ANANDAJOTI_221)
    ws = audit(
        # Space instead of hyphen: not a literal substring of either field.
        answer(VerseClaim(text="Overcome all fetters.", group_id="20.11", verse_number=221,
                           pali_support="sabbam atikkameyya")),
        [b],
    )
    assert "PALI_QUOTE_ORTHOGRAPHIC_VARIANT" in codes(ws)
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)
    warning = next(w for w in ws if w.code == "PALI_QUOTE_ORTHOGRAPHIC_VARIANT")
    assert warning.severity == "warning"


def test_pali_quote_matching_neither_edition_nor_variant_is_error():
    b = bundle_with_two_pali_editions("20.11", 221, MAHASANGITI_221, ANANDAJOTI_221)
    ws = audit(
        answer(VerseClaim(text="Overcome all fetters.", group_id="20.11", verse_number=221,
                           pali_support="completely invented pali words")),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" in codes(ws)
    error = next(w for w in ws if w.code == "PALI_QUOTE_NOT_IN_SOURCE")
    assert error.severity == "error"


def test_pali_quote_checked_against_story_pali_verse_too():
    """The widened candidate set includes a retrieved story's own pali_verse
    field, not just the verse record's two Pali fields."""
    b = bundle("20.11", [287])
    b["verses"][0]["pali_mahasangiti"] = "unrelated mahasangiti text for 287"
    b["stories"][0]["pali_verse"] = "Taṁ puttapasusammattaṁ byāsattamanasaṁ naraṁ"
    ws = audit(
        answer(VerseClaim(text="Death takes the doting.", group_id="20.11", verse_number=287,
                           pali_support="byāsattamanasaṁ naraṁ")),
        [b],
    )
    assert "PALI_QUOTE_NOT_IN_SOURCE" not in codes(ws)
    assert "PALI_QUOTE_ORTHOGRAPHIC_VARIANT" not in codes(ws)


# --------------------------------------------------------------------------
# Round 6, Task Q: no control character survives build_messages(). Corpus
# checked clean of the observed `\x01` (see prompt.py's Task Q comment) --
# this guards the one seam that check can't cover: a future corpus edit or
# a control character arriving via the `question` argument itself.
# --------------------------------------------------------------------------

_CONTROL_CHARS = [chr(c) for c in list(range(0x00, 0x09)) + [0x0b, 0x0c] + list(range(0x0e, 0x20))]


def test_build_messages_strips_control_characters_from_question():
    from dhammapada_rag.generate.prompt import build_messages

    b = bundle("13.2", [168])
    poisoned_question = "why\x01 does anger\x1b arise?"
    messages = build_messages(poisoned_question, [b])
    for m in messages:
        for ch in _CONTROL_CHARS:
            assert ch not in m["content"], f"{ch!r} survived in {m['role']} message"


def test_build_messages_strips_control_characters_from_bundle_text():
    from dhammapada_rag.generate.prompt import build_messages

    b = bundle("13.2", [168])
    b["stories"][0]["vatthu"] = "Once\x01 upon a time\x07 there was suffering."
    messages = build_messages("what does the Dhammapada say?", [b])
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    for ch in _CONTROL_CHARS:
        assert ch not in user_content


def test_build_messages_preserves_ordinary_whitespace():
    """Tabs/newlines/carriage returns are legitimate prompt structure, not
    corruption -- the strip must not remove them."""
    from dhammapada_rag.generate.prompt import build_messages

    b = bundle("13.2", [168])
    messages = build_messages("a question", [b])
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "\n" in user_content


# --------------------------------------------------------------------------
# Round 7, Task T: AlignmentClaim -- a fourth layer for facts about the
# corpus's own editorial structure (which story explains which verse group),
# distinct from VerseClaim/CommentaryClaim/SynthesisClaim. Carries
# verse_numbers (plural, the group's FULL range) instead of a single
# verse_number.
# --------------------------------------------------------------------------

def two_verse_bundle(group_id: str, verses: list[int]) -> dict:
    """Same shape as bundle(), but with more than one verse per group, so
    verses_by_group[group_id] is a real multi-element set to check
    completeness against."""
    return bundle(group_id, verses)


def test_alignment_claim_requires_verse_numbers_plural():
    """group_id alone, or with an empty verse_numbers list, must not
    construct -- min_length=1 mirrors VerseClaim/CommentaryClaim's required
    (non-Optional) citation fields."""
    with pytest.raises(ValidationError):
        AlignmentClaim(text="...", group_id="1.3")
    with pytest.raises(ValidationError):
        AlignmentClaim(text="...", group_id="1.3", verse_numbers=[])


def test_alignment_claim_full_range_is_clean():
    b = two_verse_bundle("1.3", [3, 4])
    ws = audit(
        answer(AlignmentClaim(text="Story 1.3 explains Dhp 3 and 4 together.",
                               group_id="1.3", verse_numbers=[3, 4])),
        [b],
    )
    assert ws == []


def test_alignment_claim_partial_range_is_flagged():
    """The actual observed failure this layer exists to fix: 'story 1.3
    explains Dhp 4' loses the fact that it explains Dhp 3 AND 4 together."""
    b = two_verse_bundle("1.3", [3, 4])
    ws = audit(
        answer(AlignmentClaim(text="Story 1.3 explains Dhp 4.", group_id="1.3", verse_numbers=[4])),
        [b],
    )
    assert "ALIGNMENT_RANGE_INCOMPLETE" in codes(ws)
    assert summarize(ws)["warning"] >= 1
    assert summarize(ws)["error"] == 0


def test_alignment_claim_group_not_retrieved_is_still_an_error():
    """Citation-validity checks apply to AlignmentClaim same as VerseClaim/
    CommentaryClaim -- a real story not among the retrieved sources is an
    error, not merely a range-completeness warning."""
    ws = audit(
        answer(AlignmentClaim(text="Story 8.13 explains Dhp 114.", group_id="8.13", verse_numbers=[114])),
        BUNDLES,
        corpus_group_ids={"8.13", "13.2", "1.14", "10.5"},
    )
    assert "GROUP_NOT_RETRIEVED" in codes(ws)


def test_alignment_claim_malformed_group_id_normalizes():
    b = two_verse_bundle("1.3", [3, 4])
    ws = audit(
        answer(AlignmentClaim(text="Story 1.3 explains Dhp 3 and 4 together.",
                               group_id="g1.3", verse_numbers=[3, 4])),
        [b],
    )
    assert codes(ws) == ["MALFORMED_GROUP_ID"]


def test_alignment_claim_without_bundles_only_checks_format():
    """No bundles -> no completeness or validity check possible, same
    graceful-degradation contract as VerseClaim/CommentaryClaim."""
    ws = audit(answer(AlignmentClaim(text="...", group_id="1.3", verse_numbers=[4])))
    assert codes(ws) == []


def test_alignment_claim_cannot_carry_a_singular_verse_number():
    """The discriminator: an AlignmentClaim has no verse_number field at all
    (plural verse_numbers instead), same treatment as SynthesisClaim's
    missing group_id/verse_number."""
    a = AlignmentClaim(text="...", group_id="1.3", verse_numbers=[3, 4])
    assert not hasattr(a, "verse_number")


# --------------------------------------------------------------------------
# Round 7, Task W: DUPLICATE_CLAIM -- two claims sharing a layer and
# verse_number with near-identical text, e.g. the same verse quoted twice
# under different orthography (the observed pācenti/pājenti pair).
# --------------------------------------------------------------------------

def test_duplicate_verse_claims_are_flagged():
    ws = audit(
        answer(
            VerseClaim(text="Anger is checked like a chariot driven by a skilled charioteer",
                       group_id="13.2", verse_number=168),
            VerseClaim(text="Anger is checked like a chariot driven by a skillful charioteer",
                       group_id="13.2", verse_number=168),
        ),
        BUNDLES,
    )
    assert "DUPLICATE_CLAIM" in codes(ws)
    assert summarize(ws)["warning"] >= 1
    assert summarize(ws)["error"] == 0


def test_duplicate_claim_flags_the_later_claim():
    ws = audit(
        answer(
            VerseClaim(text="Anger is checked like a chariot driven by a skilled charioteer",
                       group_id="13.2", verse_number=168),
            VerseClaim(text="Anger is checked like a chariot driven by a skillful charioteer",
                       group_id="13.2", verse_number=168),
        ),
        BUNDLES,
    )
    dup = next(w for w in ws if w.code == "DUPLICATE_CLAIM")
    assert dup.claim_index == 1


def test_different_verse_number_not_flagged_as_duplicate():
    ws = audit(
        answer(
            VerseClaim(text="Anger is checked like a chariot driven by a skilled charioteer",
                       group_id="13.2", verse_number=168),
            VerseClaim(text="Anger is checked like a chariot driven by a skilled charioteer",
                       group_id="13.2", verse_number=169),
        ),
        BUNDLES,
    )
    assert "DUPLICATE_CLAIM" not in codes(ws)


def test_different_layer_same_verse_number_not_flagged_as_duplicate():
    ws = audit(
        answer(
            VerseClaim(text="Watchfulness is the path to the deathless, heedlessness the path to death",
                       group_id="13.2", verse_number=168),
            CommentaryClaim(text="Watchfulness is the path to the deathless, heedlessness the path to death",
                             group_id="13.2", verse_number=168),
        ),
        BUNDLES,
    )
    assert "DUPLICATE_CLAIM" not in codes(ws)


def test_dissimilar_claims_same_layer_and_verse_not_flagged():
    ws = audit(
        answer(
            VerseClaim(text="Watchfulness is the path to the deathless.", group_id="13.2", verse_number=168),
            VerseClaim(text="Heedlessness is the path to death.", group_id="13.2", verse_number=168),
        ),
        BUNDLES,
    )
    assert "DUPLICATE_CLAIM" not in codes(ws)


def test_duplicate_claim_not_auto_merged():
    """Both claims survive in the answer -- audit() only flags, per the
    brief's explicit 'do not auto-merge' instruction."""
    a = answer(
        VerseClaim(text="Anger is checked like a chariot driven by a skilled charioteer",
                   group_id="13.2", verse_number=168),
        VerseClaim(text="Anger is checked like a chariot driven by a skillful charioteer",
                   group_id="13.2", verse_number=168),
    )
    audit(a, BUNDLES)
    assert len(a.claims) == 2


# --------------------------------------------------------------------------
# Round 8, Task Z: source_disposition -- required field, checked for
# completeness, validity, and self-consistency against what the claims
# actually cite. BUNDLES covers group_ids 13.2, 1.14, 10.5.
# --------------------------------------------------------------------------

def test_source_disposition_is_a_required_field():
    with pytest.raises(ValidationError):
        LayeredAnswer(question="q", claims=[VerseClaim(text="...", group_id="13.2", verse_number=168)])


def test_empty_source_disposition_is_not_flagged():
    """The test-suite escape hatch: an empty dict means 'this caller didn't
    populate the field' and skips the three checks entirely, not 'every
    retrieved group is missing'. Every other test in this file relies on
    this via the answer() helper's default."""
    ws = audit(
        answer(VerseClaim(text="...", group_id="13.2", verse_number=168)),
        BUNDLES,
    )
    assert "MISSING_DISPOSITION" not in codes(ws)


def test_complete_matching_disposition_is_clean():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "used", "1.14": "not_relevant", "10.5": "not_relevant"},
        ),
        BUNDLES,
    )
    assert ws == []


def test_missing_disposition_for_a_retrieved_group_is_an_error():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "used", "1.14": "not_relevant"},  # 10.5 omitted
        ),
        BUNDLES,
    )
    assert "MISSING_DISPOSITION" in codes(ws)
    assert summarize(ws)["error"] >= 1


def test_unknown_disposition_group_is_a_warning():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={
                "13.2": "used", "1.14": "not_relevant", "10.5": "not_relevant",
                "26.1": "used",  # never retrieved
            },
        ),
        BUNDLES,
    )
    assert "UNKNOWN_DISPOSITION_GROUP" in codes(ws)
    warning = next(w for w in ws if w.code == "UNKNOWN_DISPOSITION_GROUP")
    assert warning.severity == "warning"


def test_not_relevant_group_cited_by_a_claim_is_flagged():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "not_relevant", "1.14": "not_relevant", "10.5": "not_relevant"},
        ),
        BUNDLES,
    )
    assert "DISPOSITION_CONTRADICTS_CLAIMS" in codes(ws)


def test_used_group_cited_by_nothing_is_flagged():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "used", "1.14": "used", "10.5": "not_relevant"},
        ),
        BUNDLES,
    )
    assert "DISPOSITION_CONTRADICTS_CLAIMS" in codes(ws)
    assert sum(1 for w in ws if w.code == "DISPOSITION_CONTRADICTS_CLAIMS") == 1  # only 1.14, not 10.5


def test_partially_relevant_uncited_is_not_flagged():
    """'partially_relevant' makes no claim about whether a group was cited
    -- only 'used' (asserts citation) and 'not_relevant' (asserts no
    citation) can contradict what the claims actually did."""
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "used", "1.14": "partially_relevant", "10.5": "not_relevant"},
        ),
        BUNDLES,
    )
    assert "DISPOSITION_CONTRADICTS_CLAIMS" not in codes(ws)


def test_disposition_checks_need_bundles():
    ws = audit(
        answer(
            VerseClaim(text="...", group_id="13.2", verse_number=168),
            source_disposition={"13.2": "not_relevant"},  # would contradict, if checked
        ),
    )
    assert codes(ws) == []


# --------------------------------------------------------------------------
# Round 8, Task AA: the [ALIGNMENT] block -- verse-range/title/synopsis
# facts render there, before [COMMENTARY]; [COMMENTARY] carries only
# nidana/vatthu/desanavasane.
# --------------------------------------------------------------------------

def test_alignment_block_renders_before_commentary_block():
    from dhammapada_rag.generate.prompt import format_verse_group

    b = bundle_with_commentary("8.13", [114])
    rendered = format_verse_group(b)
    align_pos = rendered.index("[ALIGNMENT")
    commentary_pos = rendered.index("[COMMENTARY")
    assert align_pos < commentary_pos


def test_alignment_block_carries_verse_range_and_title():
    from dhammapada_rag.generate.prompt import format_verse_group

    b = bundle_with_commentary("8.13", [114])
    rendered = format_verse_group(b)
    align_block = rendered[rendered.index("[ALIGNMENT"):rendered.index("[COMMENTARY")]
    assert "group_id 8.13 covers Dhp 114 (1 verse)" in align_block
    assert "Story about 8.13" in align_block  # title_en, from the bundle() helper
    assert "<<citation_fields group_id=8.13 verse_numbers=[114]>>" in align_block


def test_commentary_block_no_longer_carries_title_or_synopsis():
    from dhammapada_rag.generate.prompt import format_verse_group

    b = bundle_with_commentary("8.13", [114])
    rendered = format_verse_group(b)
    commentary_block = rendered[rendered.index("[COMMENTARY"):]
    assert "Story title:" not in commentary_block
    assert "Synopsis:" not in commentary_block


def test_commentary_block_still_carries_narrative():
    from dhammapada_rag.generate.prompt import format_verse_group

    b = bundle_with_commentary("8.13", [114])
    rendered = format_verse_group(b)
    commentary_block = rendered[rendered.index("[COMMENTARY"):]
    assert "Narrative:" in commentary_block


def test_alignment_marker_leak_is_flagged_by_verse_numbers_variant():
    """The [ALIGNMENT] block's marker uses 'verse_numbers:' (plural), which
    is not a substring of 'verse_number:' (singular) -- needs its own
    _CITATION_LEAK_MARKERS entry, checked directly here."""
    ws = audit(
        answer(AlignmentClaim(
            text="group_id: 1.3 verse_numbers: [3, 4] Story 1.3 explains Dhp 3 and 4.",
            group_id="1.3", verse_numbers=[3, 4],
        )),
        [bundle("1.3", [3, 4])],
    )
    assert "CITATION_IN_TEXT" in codes(ws)
