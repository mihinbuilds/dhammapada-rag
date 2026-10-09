"""Round 14: the fifth layer, `note` -- Ānandajoti Bhikkhu's interlinear
notes on a verse, attributed to neither the verse nor the commentary.

Covers the four places the layer has to hold: the claim schema, the
decoder's constrained schema, the provenance audit, and the prompt/render
pair that keep the notes' authorship visible.

Run: pytest tests/test_note_layer.py -v
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from dhammapada_rag.generate.generate import _constrained_schema
from dhammapada_rag.generate.prompt import format_verse_group
from dhammapada_rag.generate.render import render_plain
from dhammapada_rag.generate.schemas import (
    CommentaryClaim,
    LayeredAnswer,
    NoteClaim,
    SynthesisClaim,
    VerseClaim,
    audit,
)

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
    verse_block = text[text.index("[VERSE]"):text.index("[NOTES")]
    assert KNOTS not in verse_block
    assert f"Dhp 90 -- note: {KNOTS}" in text[text.index("[NOTES"):]


def test_no_notes_block_when_no_verse_has_notes():
    assert "[NOTES" not in format_verse_group(bundle("1.1", [1]), narrative_budget_chars=100)


def test_note_claims_render_with_their_author_and_no_commentary_citation():
    out = render_plain(answer(
        VerseClaim(text="The verse speaks of abandoning all knots.", group_id="7.1", verse_number=90),
        NoteClaim(text="The four knots are avarice, ill-will, and two kinds of grasping.", verse_number=90),
    ))
    assert "The editor's note explains: The four knots" in out
    assert "[Dhp 90, note]" in out
    assert "DhpA" not in out.split("The editor's note explains")[1]


# ---------------------------------------------------------- Round 16 additions

def test_notes_block_carries_a_citation_marker_per_verse():
    text = format_verse_group(bundle("7.1", [90], {90: [KNOTS]}), narrative_budget_chars=100)
    notes_block = text[text.index("[NOTES"):]
    assert "neither verse nor commentary" in notes_block.splitlines()[0]
    assert "<<citation_fields layer=note verse_number=90>>" in notes_block


@pytest.mark.parametrize("claim", [
    CommentaryClaim(text="The commentary explains the four knots of avarice, ill-will, grasping at virtue "
                         "and practices, and insisting this is the truth.", group_id="7.1", verse_number=90),
    SynthesisClaim(text="The four knots are avarice, ill-will, grasping at virtue and practices, and "
                        "insisting this is the truth."),
])
def test_note_text_under_another_layer_is_flagged(claim):
    ws = audit(answer(claim), [bundle("7.1", [90], {90: [KNOTS]})])
    assert "NOTE_TEXT_AS_OTHER_LAYER" in codes(ws)


def test_the_same_text_tagged_note_is_not_flagged():
    claim = NoteClaim(text="The four knots are avarice, ill-will, grasping at virtue and practices, and "
                           "insisting this is the truth.", verse_number=90)
    ws = audit(answer(claim), [bundle("7.1", [90], {90: [KNOTS]})])
    assert "NOTE_TEXT_AS_OTHER_LAYER" not in codes(ws)


def test_a_verse_claim_closer_to_the_verse_than_the_note_is_not_flagged():
    b = bundle("7.1", [90], {90: ["The knots are abandoned by the one who has reached his goal."]})
    b["verses"][0]["interlinear_english"] = ("For the one who has reached his goal, who grieves not, "
                                             "who has abandoned all the knots, no fever is found.")
    claim = VerseClaim(text="For the one who has reached his goal and abandoned all the knots, no fever is found.",
                       group_id="7.1", verse_number=90)
    ws = audit(answer(claim), [b])
    assert "NOTE_TEXT_AS_OTHER_LAYER" not in codes(ws)


# ------------------------------------------------- Round 18: note retry

class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": json.dumps(self._payload)}, "eval_count": 1, "eval_duration": 1}


def _knot_answer(layer: str) -> dict:
    claim = {"text": "The four knots are avarice, ill-will, grasping at virtue and practices, and "
                     "insisting this is the truth.", "layer": layer, "verse_number": 90}
    if layer == "commentary":
        claim["group_id"] = "7.1"
    return {"question": "q", "claims": [claim], "source_disposition": {"7.1": "used"}}


def _run_generator(monkeypatch, responses: list[dict]):
    from dhammapada_rag.generate import generate as gen_module

    sent: list[list[dict]] = []

    def fake_post(url, json=None, timeout=None):  # noqa: A002 -- mirrors requests.post
        sent.append(json["messages"])
        return _FakeResponse(responses[len(sent) - 1])

    monkeypatch.setattr(gen_module.requests, "post", fake_post)
    result = gen_module.Generator().generate("What are the four knots?", [bundle("7.1", [90], {90: [KNOTS]})])
    return result, sent


def test_note_text_under_another_tag_triggers_one_corrective_retry(monkeypatch):
    result, sent = _run_generator(monkeypatch, [_knot_answer("commentary"), _knot_answer("note")])
    assert result["retry_reasons"] == ["note_misattribution"]
    assert result["answer"].claims[0].layer == "note"
    assert "NOTE_TEXT_AS_OTHER_LAYER" not in codes(result["warnings"])
    assert 'tag each of these claims "note"' in sent[1][-1]["content"]


def test_the_note_retry_happens_at_most_once(monkeypatch):
    result, sent = _run_generator(monkeypatch, [_knot_answer("commentary")] * 3)
    assert result["retry_reasons"] == ["note_misattribution"]
    assert len(sent) == 2
    assert "NOTE_TEXT_AS_OTHER_LAYER" in codes(result["warnings"])
