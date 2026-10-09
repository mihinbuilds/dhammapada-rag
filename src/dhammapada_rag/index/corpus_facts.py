"""Round 17: facts about the edition's own structure, stated as text.

Two kinds of fact this corpus already knows but never says anywhere a
retriever or a model can read it:

  * a verse explained by more than one story (computed from the stories'
    dhp_verses -- the same duplication the alignment table reports; in this
    edition only Dhp 416, stories 26.33 and 26.34);
  * a story whose own header line in the source misstates its verse numbers,
    hand-corrected with recorded evidence in ingest/corrections.py (6
    stories, e.g. 26.17's header "Dhp 40" for Dhp 400).

The same gap as Round 2's story_alignment chunk: the data was there as
metadata, and a question about it had no text to match and no context line
to answer from. Both kinds are generated from those two sources, never
written by hand, so they cannot drift from what validation and the
corrections log actually record. They are alignment-layer facts: modern
editorial structure, stated by neither the verse nor the commentary.

Used by index/chunks.py (story_corpus_fact chunks) and generate/prompt.py
(the [ALIGNMENT] block).
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest.corrections import CORRECTIONS  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def _range(verses: list[int]) -> str:
    vs = sorted(verses)
    if len(vs) > 1 and vs == list(range(vs[0], vs[-1] + 1)):
        return f"Dhp {vs[0]}-{vs[-1]}"
    return "Dhp " + ", ".join(str(v) for v in vs)


def build_facts(stories: list[dict]) -> dict[str, list[str]]:
    """group_id -> sentences stating its structural facts. Pure: no I/O."""
    by_id = {s["group_id"]: s for s in stories}
    verse_to_groups: dict[int, list[str]] = {}
    for s in stories:
        for v in s["dhp_verses"]:
            verse_to_groups.setdefault(v, []).append(s["group_id"])
    shared = {v: gids for v, gids in verse_to_groups.items() if len(gids) > 1}

    facts: dict[str, list[str]] = {}
    for v, gids in sorted(shared.items()):
        named = " and ".join(f"story {g}, {by_id[g]['title_en']}" for g in gids)
        only = (" It is the only verse in this edition explained by more than one story."
                if len(shared) == 1 else "")
        sentence = f"Dhp {v} is explained by {len(gids)} separate commentarial stories: {named}.{only}"
        for g in gids:
            facts.setdefault(g, []).append(sentence)

    for gid, c in sorted(CORRECTIONS.items()):
        if gid not in by_id:
            continue
        # Worded to say only what is recorded: what the header reads as
        # extracted and what the body quotes. Five of the six are the
        # source's own header; for 26.34 ("Dhp 416408") corrections.py
        # cannot tell a source typo from an extraction glitch, so no
        # sentence here blames the source.
        facts.setdefault(gid, []).append(
            f"Story {gid}'s header line in the source, as extracted, reads {_range(c.parsed_dhp_verses)}, "
            f"but the verses quoted in the story's own body are {_range(c.corrected_dhp_verses)}; this "
            f"corpus records story {gid} as explaining {_range(c.corrected_dhp_verses)}."
        )
    return facts


@lru_cache(maxsize=1)
def _corpus_facts() -> dict[str, list[str]]:
    path = ROOT / "data" / "processed" / "stories.jsonl"
    stories = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    return build_facts(stories)


def facts_for(group_id: str) -> list[str]:
    """The structural facts for one story, from the processed corpus."""
    return _corpus_facts().get(group_id, [])
