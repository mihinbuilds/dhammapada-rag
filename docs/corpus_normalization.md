# Corpus normalization (Stage 2)

Per `dhammapada_fixes/corpus_rebuild_design.md`'s Stage 2: "Three
independent normalizers, no joining yet... Each normalizer validates only
its own output... A normalizer that can't meet its own contract fails
loudly rather than emitting partial rows."

Four of the design doc's six normalizers are implemented (the four sources
already fetched and licensed per `docs/corpus_source_ownership.md`'s Stage
1 table). The other two -- `cst_atthakatha.jsonl`, `bl_legends.jsonl` --
require fetching new external content and are **not started**; see
"What's not done" below.

## What was built

| Script | Reads | Writes | Rows |
|---|---|---|---|
| `ingest/normalize_sc_pali.py` | `sources/external/mahasangiti_pali/` | `data/normalized/sc_pali.jsonl` | 423 |
| `ingest/normalize_sc_sujato.py` | `sources/external/sujato_en/` | `data/normalized/sc_sujato.jsonl` | 423 |
| `ingest/normalize_aj_interlinear.py` | `sources/external/anandajoti_interlinear/*.htm` | `data/normalized/aj_interlinear.jsonl` | 423 |
| `ingest/normalize_aj_stories.py` | `data/processed/stories.jsonl` (itself already PDF-only) | `data/normalized/aj_stories.jsonl` | 305 |

Each script reads only its own source (or, for `aj_stories`, the existing
PDF-only extraction) and validates only its own output before writing --
none reads another normalizer's `data/normalized/*.jsonl`. `sc_pali` and
`sc_sujato` share `ingest/_sc_segments.py`, a parsing-logic module (not a
data dependency between the two) for the segmentation both sources use.
Every `source_ref` is either a list of the exact SuttaCentral segment keys
that contributed to a value, or the specific HTML page / PDF-story
identifier -- checkable in the ten seconds the design doc asks for.

## Three real bugs found and fixed, none of them hypothetical

Stage 2's own validation step (`validate()` in each script, failing loudly
on a broken contract) found all three by refusing to write a row that
didn't meet it -- not by separately going looking for problems.

**1. The vagga-final colophon is folded into SuttaCentral's own
segmentation**, not introduced anywhere in this project's pipeline.
`dhp423:1`-`dhp423:6` is the actual last verse of the Dhammapada;
`dhp423:7`-`dhp423:57` is the entire 26-vagga closing colophon (chapter
names, story counts, verse counts, the closing line "Dhammapadapāḷi
samattā" -- "The Dhammapada text is finished"), keyed under the same verse
number with no distinct marker. Every vagga-final verse (26 of them)
carries its own vagga-name colophon the same way, at smaller scale. This is
exactly what Stage 0's audit (`docs/corpus_audit.md`, checks 4-5) found
from the *symptom* side (a "boundary artifact" tier in the cross-source
comparison) without yet knowing the cause; Stage 2 traced it to the raw
JSON directly. `_sc_segments.py`'s `_VAGGA_COLOPHON_RE` detects a segment
whose entire text is `<word>vaggo <ordinal>.` and excludes it and
everything after it, for that verse.

**2. A second story's title header leaks into a shared verse's segments.**
Dhp 416 has two stories (26.33, 26.34 -- an already-known, legitimate
duplicate). SuttaCentral's Pali file inserts the second story's title
(`dhp416:5.0`, "Jotikattheravatthu") mid-sequence, between the verse's own
lines 4 and 6. `build_verses.py`'s existing `load_segmented_json_dir()`
only excludes segments equal to `"0"` or starting with `"0."` -- it missed
this "N.0" form entirely, so this title header was silently concatenated
into the verse text on the pipeline currently in production. Fixed in
`_sc_segments.py`'s `_MID_SEQUENCE_TITLE_RE`.

**3. `parse_interlinear.py`'s own documented invariant is false for two
verses.** Its docstring states "the parser keeps the first occurrence in
document order, which is always the verse's own canonical position." For
Dhp 51 and Dhp 327, it isn't: each has a clean, canonical occurrence in its
own vagga's page, but an *earlier-processed* vagga's page cites it first,
as a "Related Verse from the Dhammapada" comparison -- prefixed with that
earlier page's own closing colophon, in **both** Pali and English, since
neither heading paragraph closes with the `[N]` marker `parse_page()` uses
to end a verse. `normalize_aj_interlinear.py` fixes the actual mechanism
(prefer the occurrence whose page matches the verse's own canonical vagga,
via `dhammapada_rag.vaggas.vagga_for_verse()`, over mere document order) --
not a string-matched patch, since the leaked English text is a different
chapter name each time and can't be regex-matched generically the way the
fixed Pali-side "Related Verse(s) from the Dhammapada" template text could
be. This makes `parse_interlinear.py`'s own stated invariant actually hold,
rather than holding by accident of processing order.

None of these three fixes touch the live pipeline (`build_verses.py`,
`parse_interlinear.py`, `data/processed/*.jsonl`) -- they're applied only
in the new Stage 2 normalizer scripts and land only in `data/normalized/`.
Porting them into the currently-shipped scripts is a legitimate follow-up,
not done as a side effect of this stage.

A fourth, already-known issue (Stage 0, check 2) recurred here in
`aj_stories`: the `\x0c` PDF page-break form feed in `desanavasane`/
`body_raw` on the same 22 vagga-final stories. Stripped in
`normalize_aj_stories.py`'s own transform, same reasoning.

## Measured effect

Re-running Stage 0's cross-source classifier
(`audit_corpus.classify_pali_pair()`) against the new, fixed
`sc_pali.jsonl` vs. `aj_interlinear.jsonl` (423 verses each):

| Tier | Stage 0 (pre-fix) | Stage 2 (post-fix) |
|---|---|---|
| exact | 227 | **246** |
| boundary artifact | 19 | **0** |
| distinct (genuine cross-edition variance) | 177 | 177 (unchanged) |

Boundary artifacts -- the actual bug -- are fully eliminated. The distinct
tier is unchanged, as expected: that count was already identified in Stage
0 as mostly genuine word-level variance between two real editions, not
something a boundary-contamination fix should touch.

## What's not done

`cst_atthakatha.jsonl` (CST4 Dhammapada-aṭṭhakathā, tipitaka.org) and
`bl_legends.jsonl` (Burlingame's 1921 original, archive.org) are not
implemented. Both require fetching new content from external sources, not
just reshaping what this project already has on disk:

- **CST4's license is unconfirmed** -- `docs/corpus_source_ownership.md`'s
  Stage 1 table already checked `tipitaka.org` directly and found no
  formal terms, only an "encouragement" to use the site for research. That
  table's own conclusion was to contact `help@tipitaka.org` before
  ingesting. Nothing has changed since Stage 1 that would license this.
- **Burlingame's original is confirmed public domain and accessible**
  (archive.org, `NOT_IN_COPYRIGHT`), but has not actually been downloaded,
  and normalizing it means writing a new parser for a ~450-page OCR'd
  1921 text with no existing extraction logic to reuse -- a materially
  different scope of work than the four normalizers above, which all
  reused correct, already-tested parsing logic and only needed reshaping
  plus targeted bug fixes.

Both are new external fetches this stage stopped short of making without
checking in first.
