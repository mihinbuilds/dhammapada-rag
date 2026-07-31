"""Build the indexable chunk corpus: the "tightest possible unit" to match on,
per DhammapadaRAG.txt Phase 3 ("retrieve small, return whole").

Each chunk is a small, single-topic span tagged with enough metadata
(dhp_verses, group_id) to resolve back to its parent verse-group at assembly
time (index/assemble.py). A chunk is NOT the unit returned to the user -- only
the unit matched on.

==========================================================================
FIX 1 -- NARRATIVE WINDOWING. The previous revision emitted each story's
entire vatthu as ONE chunk. index/embed.py encodes at max_length=512, so
BGE-M3 truncated every narrative at ~512 tokens (~380 words). A vatthu runs
500-5000 words, so for longer stories most of the commentary was never
embedded and could not be retrieved by any query, at any k, under any fusion.
Narrative queries were matched against opening paragraphs only.

FIX 2 -- STORY METADATA WAS NEVER INDEXED. build_chunks() emitted only
synopsis / nidana / vatthu / desanavasane. It never emitted title_en,
title_pali, cst4_title, burlingame_title, compare, cast, or keywords -- all
of which exist in stories.jsonl and models.py's Story. Consequences:

  * A query naming a person ("Suddhodana", "Kisa Gotami") only matched if the
    name happened to appear in the synopsis or in the first ~380 embedded
    words of the narrative. Story titles, which name exactly those people,
    were invisible to retrieval.
  * The eight CST4 gold questions in data/eval/build_gold_set.py ask about
    edition title variants -- and cst4_title was not in the index at all, so
    those questions were unanswerable by construction. That is a large part
    of why cross_recension scored 0.54 against ~0.86 elsewhere. The number
    was measuring a missing chunk type, not a retrieval weakness.

Both fixes change the chunk count, so the index must be rebuilt end to end:
    python -m dhammapada_rag.index.chunks
    python -m dhammapada_rag.index.embed
and every retrieval/generation metric recomputed. Numbers from the
2,769-chunk index are not comparable to numbers from this one.

Chunk types:

  verse-level (verses.jsonl, all 423):
    verse_pali_ms         Mahasangiti Pali
    verse_en_sujato       Sujato's English
    verse_en_interlinear  Anandajoti 2017 interlinear English
    verse_notes           Interlinear scholarly notes, WINDOWED (philological
                           query type)
    verse_en_narrative    The verse as quoted in its own story (226/423)

  story-level (stories.jsonl, 305 stories):
    story_titles          NEW -- title_en / title_pali / cst4_title /
                           burlingame_title / compare, one chunk, so edition
                           title variants and named persons are retrievable
    story_cast            NEW -- dramatis personae, where present
    story_keywords        NEW -- keyword list, where present
    story_synopsis        One-paragraph synopsis
    story_nidana          Opening pericope (257/305)
    story_vatthu          Narrative body, WINDOWED (multiple chunks/story)
    story_desanavasane    Closing "fruits of the teaching"

A chunk is skipped if its source field is null/empty -- no placeholder chunks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Window sizing in whitespace-delimited words. embed.py caps at 512 tokens.
# 320 words was the original estimate (English ~1.3 tokens/word) but
# embed.py's tokenizer-based check_lengths() measured up to 2.13 tokens/word
# on real windowed vatthu text -- narrative prose here is dense with
# untransliterated Pali names and quoted verse fragments, which the plain
# word-count heuristic undercounts badly. 200 words keeps every observed
# chunk (200 * 2.13 = 426 tokens) comfortably under 512 even allowing for a
# worse pocket than any window sampled so far. Re-derive this by running
# embed.py's check against the actual tokenizer if chunks.py changes what
# text ends up in a window, rather than trusting the ratio estimate.
WINDOW_WORDS = 200
OVERLAP_WORDS = 40

# Pure Pali (verse_pali_ms) is a categorically different density than English
# narrative with embedded Pali names: measured 3.98 tokens/word on the one
# case that actually overflowed (verse 423, 195 words -> 776 tokens -- under
# the WINDOW_WORDS=200 threshold by word count, so never even split, and
# would still have overflowed at 200 words even if it had: 200*3.98=796).
# WINDOW_WORDS's ratio was measured on English-with-Pali-names narrative
# (~2.13 t/w); it does not transfer to all-Pali text. 100*3.98=398, safe
# under 512 with margin for a denser pocket than the one sample measured.
PALI_WINDOW_WORDS = 100
PALI_OVERLAP_WORDS = 20


def _chunk(
    chunk_id: str,
    chunk_type: str,
    text: str,
    *,
    dhp_verses: list[int],
    group_id: str | None,
    window_index: int = 0,
    n_windows: int = 1,
    prev_chunk_id: str | None = None,
    next_chunk_id: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "chunk_type": chunk_type,
        "text": text,
        "dhp_verses": dhp_verses,
        "group_id": group_id,
        "window_index": window_index,
        "n_windows": n_windows,
        "prev_chunk_id": prev_chunk_id,
        "next_chunk_id": next_chunk_id,
    }


def _split_windows(text: str, window: int = WINDOW_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Split on word boundaries into overlapping windows.

    Paragraph-aware splitting would be better, but vatthu text as parsed does
    not carry reliable paragraph markers; word windows are the honest fallback
    and the overlap covers boundary-straddling sentences.
    """
    words = text.split()
    if len(words) <= window:
        return [text]
    step = window - overlap
    if step <= 0:
        raise ValueError("overlap must be smaller than window")
    out = []
    for start in range(0, len(words), step):
        piece = words[start:start + window]
        if not piece:
            break
        out.append(" ".join(piece))
        if start + window >= len(words):
            break
    return out


def _windowed_chunks(
    base_id: str,
    chunk_type: str,
    text: str,
    *,
    dhp_verses: list[int],
    group_id: str | None,
    window: int = WINDOW_WORDS,
    overlap: int = OVERLAP_WORDS,
) -> list[dict]:
    """One chunk per window, chained via prev/next ids.

    A single-window field keeps its original unsuffixed chunk_id so ids stay
    stable for short fields; only genuinely long text gains :w0, :w1.
    """
    windows = _split_windows(text, window=window, overlap=overlap)
    if len(windows) == 1:
        return [_chunk(base_id, chunk_type, windows[0], dhp_verses=dhp_verses, group_id=group_id)]

    ids = [f"{base_id}:w{i}" for i in range(len(windows))]
    return [
        _chunk(
            ids[i], chunk_type, w,
            dhp_verses=dhp_verses, group_id=group_id,
            window_index=i, n_windows=len(windows),
            prev_chunk_id=ids[i - 1] if i > 0 else None,
            next_chunk_id=ids[i + 1] if i < len(windows) - 1 else None,
        )
        for i, w in enumerate(windows)
    ]


def _title_text(s: dict) -> str:
    """One chunk carrying every title this story is known by.

    Kept as a single chunk rather than one per title so that a query naming
    the story matches the cluster of names together; splitting them would
    scatter near-duplicate short chunks through the ranking and crowd out
    substantive content at fixed k.
    """
    parts = [f"Story {s['group_id']}: {s['title_en']}"]
    for label, key in (
        ("Pali title", "title_pali"),
        ("CST4 (Burmese edition) title", "cst4_title"),
        ("Burlingame's title", "burlingame_title"),
        ("Compare", "compare"),
    ):
        if s.get(key):
            parts.append(f"{label}: {s[key]}")
    return ". ".join(parts)


def build_chunks(verses: list[dict], stories: list[dict]) -> list[dict]:
    chunks: list[dict] = []

    for v in verses:
        n = v["verse"]
        if v.get("pali_mahasangiti"):
            # Windowed defensively, not because verse text is normally long
            # (it isn't -- this is a no-op single-chunk pass-through in every
            # normal case) but because verse 423's pali_mahasangiti was found
            # to carry the Mahasangiti source's trailing colophon (per-vagga
            # story/verse-count uddana, ~170 extra words) concatenated on by
            # Phase 1's build_verses.py segment-join. 776 tokens, well over
            # embed.py's 512 limit. Out of scope to fix at the corpus level
            # here (brief: "Do not regenerate data/processed/*.jsonl"), so
            # made safe at chunking time like the synopsis/desanavasane cases
            # above.
            chunks.extend(
                _windowed_chunks(
                    f"verse:{n}:pali_ms", "verse_pali_ms", v["pali_mahasangiti"], dhp_verses=[n], group_id=None,
                    window=PALI_WINDOW_WORDS, overlap=PALI_OVERLAP_WORDS,
                )
            )
        if v.get("english_sujato"):
            chunks.extend(
                _windowed_chunks(f"verse:{n}:en_sujato", "verse_en_sujato", v["english_sujato"], dhp_verses=[n], group_id=None)
            )
        if v.get("interlinear_english"):
            chunks.extend(
                _windowed_chunks(f"verse:{n}:en_interlinear", "verse_en_interlinear", v["interlinear_english"], dhp_verses=[n], group_id=None)
            )
        notes = v.get("interlinear_notes") or []
        if notes:
            chunks.extend(
                _windowed_chunks(f"verse:{n}:notes", "verse_notes", " ".join(notes), dhp_verses=[n], group_id=None)
            )
        if v.get("narrative_english"):
            chunks.extend(
                _windowed_chunks(
                    f"verse:{n}:en_narrative", "verse_en_narrative", v["narrative_english"],
                    dhp_verses=[n], group_id=v.get("narrative_source_group_id"),
                )
            )

    for s in stories:
        gid = s["group_id"]
        dv = s["dhp_verses"]

        # NEW: titles across editions. Without this, cst4_title was unindexed
        # and the CST4 gold questions could not be answered by retrieval.
        chunks.append(_chunk(f"story:{gid}:titles", "story_titles", _title_text(s), dhp_verses=dv, group_id=gid))

        if s.get("cast"):
            chunks.append(_chunk(f"story:{gid}:cast", "story_cast", f"Cast of story {gid}: {s['cast']}", dhp_verses=dv, group_id=gid))
        if s.get("keywords"):
            chunks.append(
                _chunk(f"story:{gid}:keywords", "story_keywords", ", ".join(s["keywords"]), dhp_verses=dv, group_id=gid)
            )
        if s.get("synopsis"):
            # Usually one paragraph, but Phase 1's regex-based extraction
            # (parse_stories.py) occasionally over-captures -- e.g. 26.40 is
            # 1107 words, not a synopsis. Corpus is out of scope to fix here
            # (brief: "Do not regenerate data/processed/*.jsonl"), so this
            # field is windowed defensively like vatthu, not left to overflow
            # embed.py's length check.
            chunks.extend(
                _windowed_chunks(f"story:{gid}:synopsis", "story_synopsis", s["synopsis"], dhp_verses=dv, group_id=gid)
            )
        if s.get("nidana"):
            chunks.append(_chunk(f"story:{gid}:nidana", "story_nidana", s["nidana"], dhp_verses=dv, group_id=gid))
        if s.get("vatthu"):
            chunks.extend(
                _windowed_chunks(f"story:{gid}:vatthu", "story_vatthu", s["vatthu"], dhp_verses=dv, group_id=gid)
            )
        if s.get("desanavasane"):
            # Same over-capture issue, worse: some desanavasane fields contain
            # a full embedded past-life narrative (e.g. 4.5 is 2181 words --
            # a "Story of the Past" that the Phase 1 extraction regex attached
            # to the closing pericope instead of the narrative body). Windowed
            # for the same reason as synopsis above.
            chunks.extend(
                _windowed_chunks(f"story:{gid}:desanavasane", "story_desanavasane", s["desanavasane"], dhp_verses=dv, group_id=gid)
            )

    return chunks


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    verses = [json.loads(l) for l in (root / "data" / "processed" / "verses.jsonl").read_text(encoding="utf-8").splitlines()]
    stories = [json.loads(l) for l in (root / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()]

    chunks = build_chunks(verses, stories)

    out_path = root / "data" / "index" / "chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c["chunk_type"]] = by_type.get(c["chunk_type"], 0) + 1

    # Coverage evidence for docs/indexing.md: how much text the old scheme lost.
    with_vatthu = [s for s in stories if s.get("vatthu")]
    over = [s for s in with_vatthu if len(s["vatthu"].split()) > WINDOW_WORDS]
    total_words = sum(len(s["vatthu"].split()) for s in with_vatthu)
    reachable_before = sum(min(len(s["vatthu"].split()), WINDOW_WORDS) for s in with_vatthu)
    n_cst4 = sum(1 for s in stories if s.get("cst4_title"))

    print(f"Wrote {out_path}: {len(chunks)} chunks")
    print(json.dumps(by_type, indent=2))
    print(
        f"\nNarrative coverage: {total_words} vatthu words across {len(with_vatthu)} stories.\n"
        f"  {len(over)}/{len(with_vatthu)} stories exceed one window.\n"
        f"  Previously embeddable: ~{reachable_before}/{total_words} words "
        f"({reachable_before / total_words:.0%}); now 100%.\n"
        f"Story metadata: {n_cst4} stories carry a cst4_title, previously unindexed."
    )


if __name__ == "__main__":
    main()
