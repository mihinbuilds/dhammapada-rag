# Verse↔story alignment table (Stage 3)

Per `dhammapada_fixes/corpus_rebuild_design.md`'s Stage 3: "Build the
alignment table as its own artifact... this is the project's most citable
contribution."

Built by `ingest/build_alignment_table.py` from Stage 2's
`data/normalized/aj_stories.jsonl`. Output: `data/normalized/
alignment_table.json` (305 rows, one per story), `.csv` (same rows,
flattened), `alignment_table_report.json` (closure/duplication summary).

## The honest limitation this round

The design doc's own example row cross-references three sources
(`anandajoti_2024`, `burlingame_1921`, `cst4`) and computes `agreement` as
`full`/`partial`/`disputed` from where they agree or diverge -- "a
disagreement is a finding, not a bug... the most interesting thing in the
file." That's the real point of this stage: catching the case where one
edition groups verses differently than another, which no other Dhammapada
tool surfaces.

This table has **one source**. Stage 1 flagged fetching Burlingame's
original specifically to be that independent check; asked directly after
Stage 2 whether to pursue it now, the answer was to hold off and move to
Stage 3 with what's already normalized. So every row's `agreement` reads
`"single_source"`, not `"full"` -- a source agreeing with itself is not
independent verification, and labeling it `full` would misrepresent
exactly the risk Stage 1 named: "a parsing error [in story numbering/
grouping] is undetectable" with only one source. This table doesn't close
that gap; it's shaped so that adding `burlingame_1921`/`cst4` later means
populating those keys and recomputing `agreement` per row, not
restructuring the file.

## What it confirms, on the one source available

- **Closure holds**: 423/423 verses covered by the 305 stories, no gaps.
- **One duplicate, already known and legitimate**: Dhp 416 is claimed by
  two stories (26.33, 26.34) -- documented since Round 4/5 of
  `docs/generation.md`, not a new finding, now pinned as a regression test
  (`tests/test_alignment_table.py`).

## Publishing

The design doc suggests Zenodo, DOI, CSV + JSON, citable independent of
the code. Not done here -- publishing anything externally is a separate,
explicit decision, and the single-source caveat above means this isn't
yet the complete artifact the design doc describes. The files are ready in
`data/normalized/` if and when that decision is made.
