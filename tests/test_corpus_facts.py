"""Round 17: structural facts about the edition, stated as text, so a
question about them has something to retrieve and something to answer from.

Run: pytest tests/test_corpus_facts.py -v
"""

from __future__ import annotations

from dhammapada_rag.generate.prompt import format_verse_group
from dhammapada_rag.index.chunks import build_chunks
from dhammapada_rag.index.corpus_facts import build_facts, facts_for


def story(gid: str, verses: list[int], title: str = "A Story") -> dict:
    return {"group_id": gid, "dhp_verses": verses, "title_en": title}


def test_a_shared_verse_is_stated_for_both_stories():
    facts = build_facts([story("9.1", [100], "First"), story("9.2", [100], "Second"), story("9.3", [101])])
    assert facts["9.1"] == facts["9.2"]
    assert "Dhp 100 is explained by 2 separate commentarial stories" in facts["9.1"][0]
    assert "story 9.2, Second" in facts["9.1"][0]
    assert "9.3" not in facts


def test_only_is_claimed_only_when_there_is_exactly_one_shared_verse():
    one = build_facts([story("9.1", [100]), story("9.2", [100])])
    two = build_facts([story("9.1", [100]), story("9.2", [100]), story("9.3", [101]), story("9.4", [101])])
    assert "only verse" in one["9.1"][0]
    assert "only verse" not in two["9.1"][0]


def test_a_corrected_header_is_stated_from_the_corrections_log():
    facts = build_facts([story("26.17", [400])])
    assert facts["26.17"] == [
        "Story 26.17's header line in the source, as extracted, reads Dhp 40, but the verses quoted "
        "in the story's own body are Dhp 400; this corpus records story 26.17 as explaining Dhp 400."
    ]


def test_the_real_corpus_states_dhp_416_and_the_26_17_header():
    assert any("Dhp 416 is explained by 2" in f for f in facts_for("26.34"))
    assert any("reads Dhp 40," in f for f in facts_for("26.17"))
    assert facts_for("1.1") == []


def test_facts_become_story_corpus_fact_chunks():
    chunks = build_chunks([], [story("9.1", [100]), story("9.2", [100])])
    facts = [c for c in chunks if c["chunk_type"] == "story_corpus_fact"]
    assert [c["chunk_id"] for c in facts] == ["story:9.1:corpus_fact0", "story:9.2:corpus_fact0"]
    assert all(c["group_id"] in ("9.1", "9.2") and c["dhp_verses"] == [100] for c in facts)


def test_facts_render_in_the_alignment_block():
    bundle = {
        "verse_numbers": [400],
        "verses": [{"verse": 400, "interlinear_pali": "<pali>", "interlinear_english": "<english>"}],
        "stories": [{"group_id": "26.17", "dhp_verses": [400], "title_en": "A Story", "synopsis": "S."}],
    }
    text = format_verse_group(bundle, narrative_budget_chars=100)
    alignment = text[text.index("[ALIGNMENT"):text.index("[COMMENTARY")]
    assert "Corpus note: Story 26.17's header line in the source, as extracted, reads Dhp 40" in alignment


# --------------------------------------------- assembly of a shared verse

def test_a_story_chunk_brings_every_story_explaining_its_verses():
    """Dhp 416 has two stories. A chunk from either must yield a bundle with
    both, matched story first -- otherwise query()'s dedup on the verse tuple
    drops whichever ranks second, and that story can never be returned."""
    from dhammapada_rag.index.assemble import resolve_story_ids

    verses = {416: {"story_group_ids": ["26.33", "26.34"]}, 1: {"story_group_ids": ["1.1"]}}
    assert resolve_story_ids({"group_id": "26.34", "dhp_verses": [416]}, verses) == ["26.34", "26.33"]
    assert resolve_story_ids({"group_id": "26.33", "dhp_verses": [416]}, verses) == ["26.33", "26.34"]
    assert resolve_story_ids({"group_id": None, "dhp_verses": [416], "chunk_id": "v"}, verses) == ["26.33", "26.34"]
    assert resolve_story_ids({"group_id": "1.1", "dhp_verses": [1]}, verses) == ["1.1"]
