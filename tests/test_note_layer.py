"""Round 14: the fifth layer, `note` -- Ānandajoti Bhikkhu's interlinear
notes on a verse, attributed to neither the verse nor the commentary.

Covers the four places the layer has to hold: the claim schema, the
decoder's constrained schema, the provenance audit, and the prompt/render
pair that keep the notes' authorship visible.

Run: pytest tests/test_note_layer.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dhammapada_rag.generate.generate import _constrained_schema
from dhammapada_rag.generate.prompt import format_verse_group
from dhammapada_rag.generate.render import render_plain
from dhammapada_rag.generate.schemas import LayeredAnswer, NoteClaim, VerseClaim, audit

KNOTS = "Usually enumerated as four: the knots of avarice, ill-will, grasping at virtue and practices, and insisting 'this is the truth'."


def bundle(group_id: str, verses: list[int], notes: dict[int, list[str]] | None = None) -> dict:
    notes = notes or {}
    return {
        "verse_numbers": verses,
        "verses": [
            {"verse": v, "interlinear_pali": f"<pali {v}>", "interlinear_english": f"<english {v}>",
             "interlinear_notes": notes.get(v, [])}
            for v in verses
        ],
        "stories": [{"group_id": group_id, "dhp_verses": verses, "title_en": f"Story {group_id}",
                     "synopsis": "A synopsis."}],
    }


def answer(*claims, disposition=None) -> LayeredAnswer:
    return LayeredAnswer(question="q", claims=list(claims), source_disposition=disposition or {})


def codes(ws) -> list[str]:
    return [w.code for w in ws]


# -------------------------------------------------------------- claim schema

def test_note_claim_requires_a_verse_number():
    with pytest.raises(ValidationError):
        NoteClaim(text="The note lists four knots.")


def test_note_claim_has_no_group_id_field():
    """A note belongs to a verse, not to a commentarial story."""
    assert "group_id" not in NoteClaim.model_fields


def test_note_claim_round_trips_through_the_union():
    a = LayeredAnswer.model_validate({
        "question": "q", "source_disposition": {},
        "claims": [{"layer": "note", "text": "Four knots.", "verse_number": 90}],
    })
    assert isinstance(a.claims[0], NoteClaim)


# ---------------------------------------------------------- decoder schema

def test_constrained_schema_limits_note_verses_to_those_with_notes():
    schema = _constrained_schema([bundle("7.1", [90], {90: [KNOTS]}), bundle("1.1", [1])])
    assert schema["$defs"]["NoteClaim"]["properties"]["verse_number"]["enum"] == [90]


def test_constrained_schema_drops_note_claims_when_no_note_was_retrieved():
    """An empty enum is not a valid schema, and a note claim with nothing to
    cite should be unrepresentable rather than flagged after the fact."""
    schema = _constrained_schema([bundle("1.1", [1])])
    items = schema["properties"]["claims"]["items"]
    assert {"$ref": "#/$defs/NoteClaim"} not in items["oneOf"]
    assert "note" not in items["discriminator"]["mapping"]
    assert "NoteClaim" not in schema["$defs"]


# ------------------------------------------------------------------- audit

def test_note_claim_on_a_retrieved_noted_verse_is_clean():
    b = bundle("7.1", [90], {90: [KNOTS]})
    ws = audit(answer(NoteClaim(text="The four knots are avarice, ill-will, ...", verse_number=90)), [b])
    assert "NOTE_NOT_IN_CONTEXT" not in codes(ws)


def test_note_claim_on_a_verse_without_a_note_is_an_error():
    b = bundle("1.1", [1])
    ws = audit(answer(NoteClaim(text="The note says something.", verse_number=1)), [b])
    assert "NOTE_NOT_IN_CONTEXT" in codes(ws)
    assert next(w for w in ws if w.code == "NOTE_NOT_IN_CONTEXT").severity == "error"


def test_note_claim_on_an_unretrieved_verse_is_an_error():
    b = bundle("7.1", [90], {90: [KNOTS]})
    ws = audit(answer(NoteClaim(text="The note says something.", verse_number=383)), [b])
    assert "NOTE_NOT_IN_CONTEXT" in codes(ws)


def test_note_claim_counts_its_group_as_used():
    """A group whose only cited content is a note was still used -- the
    disposition cross-check must not call 'used' a contradiction."""
    b = bundle("7.1", [90], {90: [KNOTS]})
    ws = audit(answer(NoteClaim(text="Four knots.", verse_number=90), disposition={"7.1": "used"}), [b])
    assert "DISPOSITION_CONTRADICTS_CLAIMS" not in codes(ws)


def test_note_label_in_text_is_flagged():
    b = bundle("7.1", [90], {90: [KNOTS]})
    ws = audit(answer(NoteClaim(text="note: four knots.", verse_number=90)), [b])
    assert "LABEL_IN_TEXT" in codes(ws)


# --------------------------------------------------------- prompt / render

def test_notes_render_in_their_own_block_not_inside_verse():
    text = format_verse_group(bundle("7.1", [90], {90: [KNOTS]}), narrative_budget_chars=100)
    verse_block = text[text.index("[VERSE]"):text.index("[NOTES]")]
    assert KNOTS not in verse_block
    assert f"Dhp 90 -- note: {KNOTS}" in text[text.index("[NOTES]"):]


def test_no_notes_block_when_no_verse_has_notes():
    assert "[NOTES]" not in format_verse_group(bundle("1.1", [1]), narrative_budget_chars=100)


def test_note_claims_render_with_their_author_and_no_commentary_citation():
    out = render_plain(answer(
        VerseClaim(text="The verse speaks of abandoning all knots.", group_id="7.1", verse_number=90),
        NoteClaim(text="The four knots are avarice, ill-will, and two kinds of grasping.", verse_number=90),
    ))
    assert "The editor's note explains: The four knots" in out
    assert "[Dhp 90, note]" in out
    assert "DhpA" not in out.split("The editor's note explains")[1]
