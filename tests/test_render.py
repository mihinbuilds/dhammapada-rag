"""Regression tests for Round 3's presentation-layer fixes in
dhammapada_rag.generate.render.

Task A: a citation renders the normalized group_id, never the model's raw
(possibly malformed) string, and drops entirely if it doesn't resolve.
Task B: a layer lead-in ("The verse states...") marks the *transition*
between layers, not every claim -- consecutive same-layer claims share one
paragraph and one lead-in.

Round 4/5 amendment (Task K/L amendment): `Claim` is now a discriminated
union (VerseClaim / CommentaryClaim / SynthesisClaim), so these tests
construct the concrete subtype directly instead of a flat `Claim(layer=...)`.
Round 4, Task J: VerseClaim.pali_support renders as an indented line beneath
the verse claim.

Run: pytest tests/test_render.py -v
"""

from __future__ import annotations

from dhammapada_rag.generate.render import render_markdown, render_plain
from dhammapada_rag.generate.schemas import CommentaryClaim, LayeredAnswer, SynthesisClaim, VerseClaim


def answer(*claims) -> LayeredAnswer:
    # Round 8, Task Z: source_disposition is now required on LayeredAnswer;
    # empty is fine here since these tests exercise rendering, not audit()'s
    # disposition checks (which treat an empty dict as "not populated").
    return LayeredAnswer(question="q", claims=list(claims), source_disposition={})


# --------------------------------------------------------------------------
# Task A: citation normalization / dropping
# --------------------------------------------------------------------------

def test_malformed_group_id_renders_normalized_not_raw():
    """The exact observed bug: group_id='Dhp 20.11' rendered as the literal
    'DhpA Dhp 20.11' instead of the resolved 'DhpA 20.11'."""
    out = render_plain(answer(
        CommentaryClaim(text="Kisa Gotami sought a mustard seed.",
                         group_id="Dhp 20.11", verse_number=287)
    ))
    assert "DhpA 20.11" in out
    assert "DhpA Dhp" not in out


def test_unresolvable_group_id_is_dropped_not_shown_broken():
    """A group_id the audit could not resolve at all must not be printed --
    showing a citation known to be broken is worse than showing none."""
    out = render_plain(answer(
        CommentaryClaim(text="Some claim text here.",
                         group_id="not-a-group-id", verse_number=1)
    ))
    assert "not-a-group-id" not in out
    assert "DhpA" not in out


def test_verse_number_alone_still_renders():
    out = render_plain(answer(
        VerseClaim(text="Some claim text here.", group_id="not-a-group-id", verse_number=222)
    ))
    assert out.strip().endswith("[Dhp 222]")


# --------------------------------------------------------------------------
# Task B: lead-in only on layer transition, paragraph per run
# --------------------------------------------------------------------------

def test_no_repeated_lead_in_within_a_same_layer_run():
    out = render_markdown(answer(
        CommentaryClaim(text="First commentary claim.", group_id="1.11", verse_number=1),
        CommentaryClaim(text="Second commentary claim.", group_id="1.11", verse_number=1),
    ))
    assert out.count("The commentary relates") == 1


def test_lead_in_reappears_on_layer_change():
    out = render_markdown(answer(
        VerseClaim(text="A verse claim.", group_id="1.11", verse_number=1),
        CommentaryClaim(text="A commentary claim.", group_id="1.11", verse_number=1),
    ))
    assert out.count("The verse states") == 1
    assert out.count("The commentary relates") == 1


def test_layer_change_starts_a_new_paragraph():
    out = render_markdown(answer(
        VerseClaim(text="A verse claim.", group_id="1.11", verse_number=1),
        CommentaryClaim(text="A commentary claim.", group_id="1.11", verse_number=1),
    ))
    assert "\n\n" in out


def test_same_layer_run_stays_one_paragraph():
    out = render_markdown(answer(
        CommentaryClaim(text="First commentary claim.", group_id="1.11", verse_number=1),
        CommentaryClaim(text="Second commentary claim.", group_id="1.11", verse_number=1),
    ))
    assert len(out.split("\n\n")) == 1


def test_returning_to_a_layer_gets_its_own_new_lead_in():
    """verse -> commentary -> verse: the second verse run is a new
    transition and must re-announce itself, not be silently merged with the
    first verse paragraph."""
    out = render_markdown(answer(
        VerseClaim(text="First verse claim.", group_id="1.11", verse_number=1),
        CommentaryClaim(text="A commentary claim.", group_id="1.11", verse_number=1),
        VerseClaim(text="Second verse claim.", group_id="1.11", verse_number=2),
    ))
    assert out.count("The verse states") == 2
    assert len(out.split("\n\n")) == 3


# --------------------------------------------------------------------------
# Round 4, Task J: pali_support rendered beneath the verse claim
# --------------------------------------------------------------------------

def test_pali_support_renders_beneath_verse_claim():
    out = render_plain(answer(
        VerseClaim(text="Anger is checked like a lurching chariot.",
                   group_id="5.4", verse_number=222,
                   pali_support="Yo ve uppatitaṃ kodhaṃ"),
    ))
    assert "Yo ve uppatitaṃ kodhaṃ" in out


def test_no_pali_support_line_when_field_absent():
    out = render_plain(answer(
        VerseClaim(text="Anger is checked like a lurching chariot.",
                   group_id="5.4", verse_number=222),
    ))
    assert "Pali:" not in out


def test_pali_support_never_rendered_for_commentary_or_synthesis():
    """pali_support only exists on VerseClaim -- render.py must not attempt
    to read it off the other two claim types."""
    out = render_plain(answer(
        CommentaryClaim(text="A story was told at Jetavana.", group_id="5.4", verse_number=222),
        SynthesisClaim(text="This connects to patience more broadly."),
    ))
    assert "Pali:" not in out


# --------------------------------------------------------------------------
# Round 7: same-layer run join must not glue a Pali quote to the next claim
# --------------------------------------------------------------------------

def test_multiple_verse_claims_with_pali_do_not_interleave():
    """Observed bug: a 3-verse-claim run (Dhp 221/222/223, each with its own
    pali_support) joined with a plain space put claim N's "Pali: ..." line
    directly in front of claim N+1's English text on the *same* line, and
    claim N+1's own Pali line in front of claim N+2's text -- every quote
    visually glued to the wrong claim. Each claim's own text and its own
    Pali quote must always share a line together, never with a neighbor's."""
    out = render_markdown(answer(
        VerseClaim(text="First verse claim.", group_id="17.1", verse_number=221,
                   pali_support="Kodham jahe vippajaheyya."),
        VerseClaim(text="Second verse claim.", group_id="17.2", verse_number=222,
                   pali_support="Yo ve uppatitam kodham."),
        VerseClaim(text="Third verse claim.", group_id="17.3", verse_number=223,
                   pali_support="Akkodhena jine kodham."),
    ))
    lines = out.splitlines()
    pali_lines = [ln for ln in lines if "Pali:" in ln]
    assert len(pali_lines) == 3
    for pali_line in pali_lines:
        assert "verse claim." not in pali_line
