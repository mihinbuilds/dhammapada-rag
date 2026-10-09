"""Parent-group assembly: "retrieve small, return whole" (docs/project_plan.md
Phase 3). A search/rerank hit is a small chunk (one verse's Pali, one story's
title line, one window of a narrative); this resolves it back to its full
verse-group -- the Dhp verse(s) a story explains, all sourced text for those
verses, and every story that explains them -- so the caller always sees all
layers regardless of which single chunk matched.

A "verse group" is defined by a *story's* dhp_verses (e.g. one story
explaining Dhp 3-4 together), not by mechanically bundling adjacent verses --
Dhp 1 and Dhp 2 are separate single-verse stories that happen to be adjacent,
not a group.

--------------------------------------------------------------------------
FIXES over the previous revision:
1. A verse with an empty story_group_ids raised a bare IndexError. It now
   raises with the verse number, so a corpus gap is diagnosable rather than
   presenting as a mystery crash mid-eval.
2. matched_chunk carries window_index / n_windows. Now that long narratives
   are windowed (index/chunks.py), knowing WHICH window matched is what lets
   a UI show the right passage instead of the story's opening paragraph.
3. Bundles carry `matched_chunk_ids` across dedup. When several chunks from
   the same story rank highly, only the best survives dedup; recording the
   rest preserves the evidence that a match was broad rather than incidental.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_verses_and_stories(root: Path) -> tuple[dict[int, dict], dict[str, dict]]:
    verses = [json.loads(l) for l in (root / "data" / "processed" / "verses.jsonl").read_text(encoding="utf-8").splitlines()]
    stories = [json.loads(l) for l in (root / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()]
    return {v["verse"]: v for v in verses}, {s["group_id"]: s for s in stories}


def resolve_story_ids(chunk: dict, verses_by_number: dict[int, dict]) -> list[str]:
    """Every story in the verse-group a chunk belongs to, matched story first.

    A verse-only chunk resolves to all stories explaining its verse. A
    story-linked chunk resolves to its own story AND any other story
    explaining the same verses. Round 17: that second half was missing -- a
    story chunk resolved to its own story only, and query() deduplicates on
    the verse tuple, so when two stories explain one verse (Dhp 416: 26.33
    and 26.34) whichever ranked first won and the other could never be
    returned. That broke this module's own promise ("every story that
    explains them") and made the second story unretrievable at any rank.

    The single implementation: eval/retrieval_eval.py imports it, so the
    eval scores exactly the unit the system returns.
    """
    if chunk.get("group_id"):
        story_ids = [chunk["group_id"]]
        for v in chunk["dhp_verses"]:
            for gid in verses_by_number[v]["story_group_ids"]:
                if gid not in story_ids:
                    story_ids.append(gid)
        return story_ids
    v = chunk["dhp_verses"][0]
    story_ids = list(verses_by_number[v]["story_group_ids"])
    if not story_ids:
        raise ValueError(
            f"Dhp {v} has no story_group_ids; chunk {chunk['chunk_id']!r} cannot be "
            f"resolved to a verse-group. Check data/processed/verses.jsonl coverage."
        )
    return story_ids


def assemble(chunk: dict, verses_by_number: dict[int, dict], stories_by_id: dict[str, dict]) -> dict:
    story_ids = resolve_story_ids(chunk, verses_by_number)
    stories = [stories_by_id[gid] for gid in story_ids]
    verse_numbers = sorted({n for s in stories for n in s["dhp_verses"]})
    verses = [verses_by_number[n] for n in verse_numbers]
    return {"verse_numbers": verse_numbers, "verses": verses, "stories": stories}


def query(
    text: str,
    index=None,
    reranker=None,
    top_k: int = 5,
    candidates: int = 30,
    root: Path | None = None,
    verses_by_number: dict[int, dict] | None = None,
    stories_by_id: dict[str, dict] | None = None,
) -> list[dict]:
    """End-to-end: hybrid RRF search -> cross-encoder rerank -> dedupe by
    resolved parent group -> parent-group assembly. Returns up to top_k
    distinct verse-groups, best-matching chunk first within each.

    Pass pre-loaded index/reranker/verses_by_number/stories_by_id (as the API
    service does, loading each once at startup) to avoid reloading models and
    re-parsing JSONL on every call; each is loaded lazily here only as a
    convenience for one-off CLI use.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
    from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

    root = root or Path(__file__).resolve().parents[3]
    index = index or ChunkIndex(root / "data" / "index")
    reranker = reranker or CrossEncoderReranker()
    if verses_by_number is None or stories_by_id is None:
        verses_by_number, stories_by_id = load_verses_and_stories(root)

    hits = index.search(text, top_k=candidates)
    reranked = reranker.rerank(text, hits)

    by_key: dict[tuple[int, ...], dict] = {}
    order: list[tuple[int, ...]] = []
    for hit in reranked:
        bundle = assemble(hit, verses_by_number, stories_by_id)
        key = tuple(bundle["verse_numbers"])

        if key in by_key:
            # Keep evidence that other chunks from this group also ranked well.
            by_key[key]["matched_chunk_ids"].append(hit["chunk_id"])
            continue

        bundle["matched_chunk"] = {
            "chunk_id": hit["chunk_id"],
            "chunk_type": hit["chunk_type"],
            "text": hit["text"],
            "rerank_score": hit["rerank_score"],
            # Which window of a long narrative matched -- a UI should show
            # this passage, not the story's opening paragraph.
            "window_index": hit.get("window_index", 0),
            "n_windows": hit.get("n_windows", 1),
            # Which story this match belongs to (None for a verse-layer
            # match). generate/prompt.py uses this, paired with
            # window_index, to truncate a long vatthu around the passage
            # retrieval actually matched instead of always from its start --
            # see that module's _budget_around().
            "group_id": hit.get("group_id"),
        }
        bundle["matched_chunk_ids"] = [hit["chunk_id"]]
        by_key[key] = bundle
        order.append(key)
        if len(order) >= top_k:
            break

    return [by_key[k] for k in order]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top_k", type=int, default=3)
    args = parser.parse_args()

    bundles = query(args.query, top_k=args.top_k)
    for i, b in enumerate(bundles, 1):
        mc = b["matched_chunk"]
        win = f" [window {mc['window_index'] + 1}/{mc['n_windows']}]" if mc["n_windows"] > 1 else ""
        print(f"\n=== Result {i}: Dhp {b['verse_numbers']} (matched on {mc['chunk_type']}{win}, score {mc['rerank_score']:.3f}) ===")
        print(f"Matched text: {mc['text'][:150]}")
        for v in b["verses"]:
            print(f"\n  Dhp {v['verse']} ({v['vagga_name_pali']})")
            print(f"    Pali:    {v['interlinear_pali']}")
            print(f"    English: {v['interlinear_english']}")
        for s in b["stories"]:
            print(f"\n  Story {s['group_id']}: {s['title_en']}")
            print(f"    Synopsis: {s['synopsis']}")


if __name__ == "__main__":
    main()
