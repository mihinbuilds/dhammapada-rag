"""Build the indexable chunk corpus: the "tightest possible unit" to match on,
per docs/project_plan.md Phase 3 ("retrieve small, return whole").

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

ROUND 2, FIX 3 -- VERSE-NUMBER ALIGNMENT NEVER EXPRESSED AS TEXT. A question
phrased by verse number ("which single story explains Dhp 320, 321, and 322
together?") had nothing to match: no chunk's text contains the literal
string "320" anywhere in the corpus. Third instance of the same pattern as
FIX 1 and FIX 2 above -- the data was there (dhp_verses/group_id, on every
chunk, as metadata) and the index never exposed it as retrievable text. See
docs/evaluation.md's "three instances of one pattern" section.

FIX 4 -- COLOPHON/PAGE-BREAK LEAK (following Round 5 Task M's arm_diagnosis
finding). "What is the purpose of life?" and several other abstract-concept
probes all converged on story 26.40 (Dhp 423, the Brahmin Devahita story)
regardless of retrieval arm. Cause: 26.40 is the *last* story in the source
PDF, so parse_stories.py's regex-based field extraction swept the entire
closing colophon -- an enumeration of all 26 chapters' story counts plus a
Buddhaghosa authorship ascription, sharing no real content with Dhp 423 --
into its `synopsis` (1107 words) and `desanavasane` (671 words) fields,
windowed into 11 near-identical chunks that lexically/semantically resemble
almost any query about the text as a whole. `_truncate_at_page_break()`
drops everything from the source PDF's page-break character onward before
windowing -- a corpus-wide rule (form-feed never belongs in narrative prose),
not a 26.40 special case; it also cleans 21 other stories' minor
next-chapter-heading leaks (each is the last story of its own vagga) as a
side effect of the same one-line fix.

ROUND 13 (2026-10-08) -- VERSE LAYER NOW ĀNANDAJOTI ONLY. The two
SuttaCentral verse chunk types (Pali and English) are gone, removed at
SuttaCentral's request (data/raw/PROVENANCE.md). Ānandajoti's interlinear
Pali, previously unindexed, takes the Pali slot as verse_pali_interlinear;
his interlinear English already had its own chunk type.

Chunk types:

  verse-level (verses.jsonl, all 423):
    verse_pali_interlinear  Anandajoti 2017 interlinear Pali
    verse_en_interlinear  Anandajoti 2017 interlinear English
    verse_notes           Interlinear scholarly notes, WINDOWED (philological
                           query type)
    verse_en_narrative    The verse as quoted in its own story (226/423)

  story-level (stories.jsonl, 305 stories):
    story_titles          NEW -- title_en / title_pali / cst4_title /
                           burlingame_title / compare, one chunk, so edition
                           title variants and named persons are retrievable
    story_alignment       NEW (round 2) -- one templated sentence naming
                           every Dhp verse number the story explains, so
                           verse-grouping questions have literal text to
                           match against instead of only dhp_verses metadata
    story_corpus_fact     Round 17 -- a structural fact about the edition (a verse
                           with two stories; a header corrected against the
                           story's own body), from index/corpus_facts.py
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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.index.corpus_facts import build_facts  # noqa: E402

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

# Pure Pali (verse_pali_interlinear) is a categorically different density than English
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


_COLOPHON_MARKER = "Conclusion, Nigamanakath"


def _truncate_at_page_break(text: str) -> str:
    """Drop everything from the first PDF page-break (form-feed, U+000C), or
    the book's own closing colophon heading, whichever comes first.

    22 stories are the last story in their vagga, so the source PDF's next
    page -- the next chapter's own heading -- got glued onto the end of
    `desanavasane` (and, via `extract_nidana_desanavasane`'s chunk_end ==
    len(lines) for the very last story, `synopsis` too) by parse_stories.py's
    regex-based field extraction. For 21 of the 22 this is a harmless few-word
    leak ("2. The Chapter about Heedfulness, ...") and the form-feed catches
    it. For story 26.40 -- the last story in the whole book -- what follows
    is the source's entire closing colophon: an enumeration of all 26
    chapters' story counts plus a Buddhaghosa authorship ascription, 1107
    words in `synopsis` and 671 in `desanavasane`, none of it about Dhp 423
    or the Brahmin Devahita story this chunk is nominally for. Task M's
    arm_diagnosis.py found this single story's colophon chunks acting as a
    near-universal lexical/semantic attractor across dense, sparse, and
    ColBERT alike for abstract-concept queries ("purpose of life", "wisdom",
    "suffering", "mind", "meditation") -- generic eulogistic vocabulary plus
    every chapter name in the book resembles almost any query about the text
    as a whole.

    The form-feed alone is not enough here: it survives in `desanavasane`
    (which is sliced directly out of `body_raw`) but is stripped by
    `synopsis`'s line-by-line, blank-line-skipping paragraph collector in
    parse_stories.py before the colophon text ever reaches this function --
    confirmed empirically (`\\x0c` absent from `synopsis`, present in
    `desanavasane`/`body_raw`, for the same story). `_COLOPHON_MARKER` is the
    Pali heading of the colophon's own first subsection ("Conclusion,
    Nigamanakathā") and is confirmed unique across all 305 stories' five
    narrative fields -- it exists nowhere else in the corpus, so matching it
    literally cannot misfire on genuine narrative content.

    Neither marker is ever legitimate inside narrative prose, so truncating
    on either is safe corpus-wide, not a 26.40-specific patch -- it happens
    to fix one large leak and 21 small ones with the same rule.
    data/processed/stories.jsonl itself is left untouched (out of scope per
    the brief); this runs at chunk-build time only.

    Since the September 2026 text-cleaning pass, parse_stories.py cuts every
    story at the next vagga title page and at the colophon itself, so on the
    current corpus this is a no-op; kept as a guard for a regression there.
    """
    candidates = [i for i in (text.find("\x0c"), text.find(_COLOPHON_MARKER)) if i != -1]
    if not candidates:
        return text
    return text[: min(candidates)].rstrip()


_PRONOUNCED_VERSE = re.compile(r"pronounc\w*\s+the\s+following\s+(?:verse|stanza)s?\s*:?", re.I)
_VERSE_NUMBER_MARKER = re.compile(r"(?<![\d.])(\d{1,3})\.\s")


def _strip_closing_verse_quote(text: str, dhp_verses: list[int]) -> str:
    """Drop a story's own closing citation of the Dhp verse(s) it explains
    from vatthu/desanavasane text, before windowing.

    Burlingame's translation convention closes most stories with "...he
    pronounced the following verse: <number>. <Pali>. <English>" -- the
    narrative quotes, verbatim, the exact verse text that verse:<n>:pali_interlinear /
    en_interlinear already carry as separate chunks. For short
    single-verse stories this closing quote is most of the field, so the
    resulting story_vatthu/story_desanavasane chunk is barely distinguishable
    from a verse chunk -- and out-competes the true verse-layer chunks (and
    other stories' more diffuse commentary) on any query naming words from
    that verse, because it scores as *both* layers on a single dense passage.
    Found via a research-validation cross-layer failure (Q16/Q26,
    docs/dhammapada_research_validation_results.md): a "mustard seed" query
    matched two short single-verse stories (Dhp 401, 407) ahead of Kisā
    Gotamī's story (Dhp 114), even though 114's own commentary discusses
    mustard seed at length -- because 401/407's vatthu chunk *is* their own
    verse, quoted whole, while 114's vatthu is long, windowed, and never puts
    the "mustard seed" narrative and its closing verse-quote in the same
    chunk. Same failure family as `_truncate_at_page_break` above (verse-
    layer content leaking into a nominally commentary-only chunk_type), just
    triggered by narrative convention instead of PDF pagination.

    Same phrase also introduces verses recited *by characters* mid-narrative
    (e.g. a "Story of the Past" flashback, or a secondary Udāna verse) that
    are not the story's own dhp_verses and are genuine narrative content --
    stripping those would be a content loss, not a fix. So this only strips
    the LAST occurrence of the trigger phrase, and only when what follows it
    is verse-shaped and accounted for:
      1. it names at least one number from this story's own dhp_verses;
      2. every own-verse number found is a contiguous suffix of dhp_verses
         sorted ascending (Dhp 294 alone when dhp_verses is [294, 295] means
         295's quote is missing or something else is going on -- leave it);
      3. the remaining text is short relative to how many verses it quotes
         (<=110 words/verse -- a stanza's Pali + numbering + two English
         renderings runs 25-60 words; a "Story of the Past" continuing for
         several more paragraphs after a single quoted verse does not).
    Verified against the corpus: 291/297 candidates satisfy all three and
    inspection of the other 6 (rejected on check 2 or 3) confirms real
    narrative -- not a quote -- follows in each. Corpus-wide rule, not a
    per-story patch, for the same reason as `_truncate_at_page_break`.
    """
    matches = list(_PRONOUNCED_VERSE.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    segment = text[last.end():]
    numbers = [int(n) for n in _VERSE_NUMBER_MARKER.findall(segment)]
    own_numbers = sorted(set(n for n in numbers if n in dhp_verses))
    if not own_numbers:
        return text
    dv_sorted = sorted(dhp_verses)
    is_suffix = dv_sorted[-len(own_numbers):] == own_numbers
    ratio = len(segment.split()) / len(own_numbers)
    if not (is_suffix and ratio <= 110):
        return text
    return text[: last.start()].rstrip()


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
    corpus_facts = build_facts(stories)

    for v in verses:
        n = v["verse"]
        if v.get("interlinear_pali"):
            # Windowed defensively, not because verse text is normally long
            # (it isn't -- a single-chunk pass-through in every normal case)
            # but because pure Pali runs ~4 tokens/word (see
            # PALI_WINDOW_WORDS) and one bad extraction once pushed a verse
            # well past embed.py's 512-token limit.
            chunks.extend(
                _windowed_chunks(
                    f"verse:{n}:pali_interlinear", "verse_pali_interlinear", v["interlinear_pali"],
                    dhp_verses=[n], group_id=None,
                    window=PALI_WINDOW_WORDS, overlap=PALI_OVERLAP_WORDS,
                )
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

        # ROUND 2, FIX 3 -- VERSE-NUMBER ALIGNMENT WAS NEVER EXPRESSED AS
        # TEXT. Every other chunk holds Pali, English translation, or
        # narrative prose; none of them contain the literal string "320".
        # A query phrased by verse number ("which single story explains Dhp
        # 320, 321, and 322 together?") had nothing to match against -- not
        # a retrieval weakness, a representational gap, the same pattern as
        # story_titles above (round 1) and narrative windowing before that
        # (round 1, fix 1): the corpus had the answer, the index just never
        # said it in words. This one small templated chunk per story is
        # sufficient because it's the *only* thing that needs to name the
        # verse numbers -- the story's own content chunks still carry the
        # substance.
        if dv:
            verses_str = ", ".join(f"Dhp {n}" for n in dv)
            alignment_text = (
                f"{verses_str} {'are' if len(dv) > 1 else 'is'} explained by a single "
                f"commentarial story: story {gid}, {s['title_en']}. "
                f"This story covers {len(dv)} verse(s): {verses_str}."
            )
            chunks.append(_chunk(f"story:{gid}:alignment", "story_alignment",
                                 alignment_text, dhp_verses=dv, group_id=gid))

        # Round 17: structural facts about this story, as text -- the same
        # gap story_alignment closed in Round 2 (see index/corpus_facts.py).
        for k, fact in enumerate(corpus_facts.get(gid, [])):
            chunks.append(_chunk(f"story:{gid}:corpus_fact{k}", "story_corpus_fact", fact,
                                 dhp_verses=dv, group_id=gid))

        if s.get("cast"):
            chunks.append(_chunk(f"story:{gid}:cast", "story_cast", f"Cast of story {gid}: {s['cast']}", dhp_verses=dv, group_id=gid))
        if s.get("keywords"):
            chunks.append(
                _chunk(f"story:{gid}:keywords", "story_keywords", ", ".join(s["keywords"]), dhp_verses=dv, group_id=gid)
            )
        if s.get("synopsis"):
            # Usually one paragraph, but Phase 1's regex-based extraction
            # (parse_stories.py) occasionally over-captures -- e.g. 26.40 was
            # 1107 words, not a synopsis, until _truncate_at_page_break below
            # cut it back to the genuine one-liner. Corpus is out of scope to
            # fix here (brief: "Do not regenerate data/processed/*.jsonl"),
            # so this field is windowed defensively like vatthu, not left to
            # overflow embed.py's length check, on top of the page-break trim.
            synopsis = _truncate_at_page_break(s["synopsis"])
            chunks.extend(
                _windowed_chunks(f"story:{gid}:synopsis", "story_synopsis", synopsis, dhp_verses=dv, group_id=gid)
            )
        if s.get("nidana"):
            chunks.append(_chunk(f"story:{gid}:nidana", "story_nidana", s["nidana"], dhp_verses=dv, group_id=gid))
        if s.get("vatthu"):
            # _strip_closing_verse_quote: drop the narrative's own closing
            # citation of dhp_verses (Burlingame's "...pronounced the
            # following verse: <Pali>. <English>" convention) so this
            # commentary chunk doesn't also double as a verbatim verse-layer
            # chunk -- see that function's docstring for the cross-layer
            # retrieval failure this was found to cause.
            vatthu = _strip_closing_verse_quote(s["vatthu"], dv)
            chunks.extend(
                _windowed_chunks(f"story:{gid}:vatthu", "story_vatthu", vatthu, dhp_verses=dv, group_id=gid)
            )
        if s.get("desanavasane"):
            # Same over-capture issue, worse: some desanavasane fields contain
            # a full embedded past-life narrative (e.g. 4.5 is 2181 words --
            # a "Story of the Past" that the Phase 1 extraction regex attached
            # to the closing pericope instead of the narrative body -- a
            # genuine content over-capture, NOT a page-break leak, so
            # _truncate_at_page_break does not and should not touch it).
            # Windowed for the same reason as synopsis above, after the
            # page-break trim strips 26.40's colophon (and 21 other stories'
            # next-chapter-heading crumbs) specifically, and the same closing-
            # verse-quote strip applied to vatthu above.
            desanavasane = _strip_closing_verse_quote(_truncate_at_page_break(s["desanavasane"]), dv)
            chunks.extend(
                _windowed_chunks(f"story:{gid}:desanavasane", "story_desanavasane", desanavasane, dhp_verses=dv, group_id=gid)
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
