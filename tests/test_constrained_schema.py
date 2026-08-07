"""Regression tests for Round 5, Task K: constraining group_id/verse_number
to enums built from the retrieved bundles, so a malformed, invented, or
not-retrieved citation becomes unrepresentable rather than merely detected
after the fact by generate/schemas.py's audit().

Round 4/5 amendment (Task K/L amendment): Claim became a discriminated union
(VerseClaim / CommentaryClaim / SynthesisClaim), so there is no single
"Claim" $def to patch -- _constrained_schema() now patches VerseClaim and
CommentaryClaim independently, and both fields are required (no "anyOf" with
null) since group_id/verse_number are non-Optional on those two claim types.
SynthesisClaim has neither field and is untouched.

Run: pytest tests/test_constrained_schema.py -v
"""

from __future__ import annotations

import pytest

from dhammapada_rag.generate.generate import _constrained_schema


def bundle(group_id: str, verses: list[int]) -> dict:
    return {"verse_numbers": verses, "stories": [{"group_id": group_id}]}


@pytest.mark.parametrize("claim_type", ["VerseClaim", "CommentaryClaim"])
def test_group_id_enum_contains_exactly_the_retrieved_group_ids(claim_type):
    schema = _constrained_schema([bundle("13.2", [168, 169]), bundle("1.14", [19, 20])])
    props = schema["$defs"][claim_type]["properties"]
    assert props["group_id"]["enum"] == ["1.14", "13.2"]


@pytest.mark.parametrize("claim_type", ["VerseClaim", "CommentaryClaim"])
def test_verse_number_enum_contains_exactly_the_retrieved_verses(claim_type):
    schema = _constrained_schema([bundle("13.2", [168, 169]), bundle("1.14", [19, 20])])
    props = schema["$defs"][claim_type]["properties"]
    assert props["verse_number"]["enum"] == [19, 20, 168, 169]


def test_fields_remain_required_not_nullable():
    """group_id/verse_number are non-Optional on VerseClaim/CommentaryClaim
    (Task K/L amendment), so the constrained schema must not reintroduce a
    null option -- that would make an uncited claim representable again."""
    schema = _constrained_schema([bundle("13.2", [168])])
    for claim_type in ("VerseClaim", "CommentaryClaim"):
        defn = schema["$defs"][claim_type]
        assert "group_id" in defn["required"]
        assert "verse_number" in defn["required"]
        assert defn["properties"]["group_id"]["type"] == "string"
        assert defn["properties"]["verse_number"]["type"] == "integer"


def test_synthesis_claim_untouched():
    schema = _constrained_schema([bundle("13.2", [168])])
    props = schema["$defs"]["SynthesisClaim"]["properties"]
    assert "group_id" not in props
    assert "verse_number" not in props


def test_fabricated_or_malformed_values_are_outside_the_enum():
    """Not a decoding test (that needs a live Ollama call) -- confirms the
    exact observed failures ("g17.8", "Dhp 114" in group_id, "inferred from
    Dhp 1 commentary") are not members of the constrained enum, which is
    what makes them unrepresentable once Ollama compiles this into a
    grammar."""
    schema = _constrained_schema([bundle("17.8", [221, 222, 223])])
    gid_enum = schema["$defs"]["VerseClaim"]["properties"]["group_id"]["enum"]
    vnum_enum = schema["$defs"]["VerseClaim"]["properties"]["verse_number"]["enum"]
    for bad_gid in ("g17.8", "Dhp 114", "inferred from Dhp 1 commentary", "story 17.8"):
        assert bad_gid not in gid_enum
    assert 114 not in vnum_enum  # not among this bundle's retrieved verses


def test_empty_bundles_raise_rather_than_produce_an_empty_enum():
    """An empty enum would make every verse/commentary claim impossible to
    satisfy, not just malformed ones -- fail loudly instead."""
    with pytest.raises(ValueError):
        _constrained_schema([])


def test_multiple_stories_in_one_bundle_all_contribute_to_the_enum():
    """Dhp 416 is the corpus's one verse with two explaining stories --
    format_verse_group() already lists both group_ids for that case; the
    constrained schema must allow either, not just the first."""
    multi = {"verse_numbers": [416], "stories": [{"group_id": "26.34"}, {"group_id": "26.35"}]}
    schema = _constrained_schema([multi])
    gid_enum = schema["$defs"]["VerseClaim"]["properties"]["group_id"]["enum"]
    assert gid_enum == ["26.34", "26.35"]
