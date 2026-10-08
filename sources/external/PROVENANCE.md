# Provenance: sources/external/

Fetched 2026-07-30 to close three gaps flagged after the first Phase 1 pass
(see `docs/datasheet.md` "Known limitations" as it stood before this fetch,
and `docs/licensing.md`): incomplete Pali verse coverage, no pada-gloss
layer, and unconfirmed licensing on the narrative source's revision layer.

## Removed: two SuttaCentral sources (2026-10-08)

This directory used to hold two more sources fetched the same day from
SuttaCentral: a Pali root text and an English translation of all 423 verses.
SuttaCentral asked that their material not be used in any project that uses
AI, so both were deleted, and the code and derived files built from them went
with them. The ruling, the date and what was removed are recorded in
[`data/raw/PROVENANCE.md`](../../data/raw/PROVENANCE.md).

**Purged from history, 2026-10-08.** Both directories were also removed from
every past commit with `git filter-repo --invert-paths`, together with the
two normalized files built from them and the code that only read them
(`normalize_sc_pali.py`, `normalize_sc_sujato.py`, `_sc_segments.py`,
`tests/test_normalize.py`). The README screenshots that showed their text
were stripped by blob ID. Every commit hash in the repository changed as a
result. Files whose contents carried the text but which are still part of the
project, such as `verses.jsonl`, were not rewritten; `data/raw/PROVENANCE.md`
says which and why.

## anandajoti_interlinear/ -- phrase-level gloss layer, all 423 verses

- Source: `https://ancient-buddhist-texts.net/Texts-and-Translations/Dhammapada/`,
  26 per-vagga HTML pages (`01-Pairs.htm` ... `26-Brahmins.htm`).
- Work: *Dhammapada* interlinear Pali-English edition, Ānandajoti Bhikkhu,
  2nd edition, November 2017 -- a **different, earlier work by the same
  translator** than `sources/Dhammapada-Attakatha.pdf` (which is his 2024
  revision of Burlingame's commentary/story translation). Not the source
  PDF's own text.
- License: **Creative Commons Attribution-ShareAlike 4.0**
  (<https://creativecommons.org/licenses/by-sa/4.0/>), confirmed in writing by
  Ānandajoti Bhikkhu on 2026-09-25 and stated on
  `https://ancient-buddhist-texts.net/tt/Dhammapada/index.htm`; see
  [`sources/PERMISSION.md`](../PERMISSION.md). Attribution required:
  Ānandajoti Bhikkhu. At fetch time this file recorded version 3.0 Unported,
  from the site-wide notice at
  `https://ancient-buddhist-texts.net/Miscellaneous/Copyright-Notice.htm`. He
  has since moved to 4.0 ("previously 3.0").
- What it actually is: not a traditional pada-vibhaṅga (word-by-word
  commentarial gloss in the Abhidhamma-commentary sense). It's a line-by-line
  interlinear Pali/English rendering with inline scholarly notes on specific
  word choices, textual variants, and parallel readings. It is, however, the
  closest available public resource providing phrase-level glossing for
  every verse, which the narrative source has zero of. Documented as such,
  not overclaimed, in `docs/datasheet.md`.
- Parsed by `src/dhammapada_rag/ingest/parse_interlinear.py` into
  `data/processed/interlinear_gloss.jsonl` (423/423 verses; ~180 verses
  appear a second time elsewhere on their page as incidental cross-reference
  quotes when another verse's discussion cites them for comparison -- the
  parser keeps the first occurrence in document order, which is always the
  verse's own canonical position, and logs every such case to stdout).
