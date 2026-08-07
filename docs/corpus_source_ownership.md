# Corpus source ownership (Stage 1)

Per `dhammapada_fixes/corpus_rebuild_design.md`'s Stage 1: "One table,
written before any code. Each row is a field; each field has one owner and
no fallback." This is that table. No ingest code was written or run to
produce it — where a claim below needed checking rather than assuming, it
was checked directly (cited per row) rather than carried over from the
design doc's draft uncritically.

Three sources here (`pali_mahasangiti`, `english_sujato`, the three
`interlinear_*` fields) are **already fetched, ingested, and licensed** in
this corpus — Phase 1 did this work; this table cites it rather than
re-deriving it. Two sources (`atthakatha_pali`, `atthakatha_english`) are
**proposed, not yet fetched** — Stage 1 declares ownership in advance of
ingest, per the design doc's own sequencing, so this table names them
without pretending they're already in the corpus. `english_muller` is
listed as optional per the design doc and not investigated further here;
it doesn't affect anything this project currently generates against.

## The table

| Field | Owning source | Format | Licence | Status |
|---|---|---|---|---|
| `pali_mahasangiti` | SuttaCentral `bilara-data`, `published` branch, Mahāsaṅgīti root text | JSON, segment-keyed | **CC0 1.0** (confirmed) | Already fetched: `sources/external/mahasangiti_pali/` |
| `english_sujato` | SuttaCentral `bilara-data`, same branch, Bhikkhu Sujato's translation | JSON, segment-keyed | **CC0 1.0** (confirmed) | Already fetched: `sources/external/sujato_en/` |
| `interlinear_pali` | Ānandajoti Bhikkhu, *Dhammapada* interlinear ed., 2nd ed., Nov 2017, ancient-buddhist-texts.net | HTML | **CC BY-SA 3.0 Unported**, attribution required (confirmed) | Already fetched: `sources/external/anandajoti_interlinear/` |
| `interlinear_english` | same as above | HTML | same as above | same as above |
| `interlinear_notes` | same as above | HTML | same as above | same as above |
| `english_muller` (optional) | Müller, *Sacred Books of the East* vol. X, 1881 | text | Public domain (not verified this round) | Not fetched. Optional per design doc; not pursued further here |
| `atthakatha_pali` | CST4 (Chaṭṭha Saṅgāyana Tipiṭaka 4.0) Dhammapada-aṭṭhakathā, tipitaka.org (Vipassana Research Institute) | HTML/text | **Unconfirmed -- checked directly, no license found** | Not fetched. See "CST4 licensing" below |
| `atthakatha_english` | E.W. Burlingame, *Buddhist Legends*, Harvard Oriental Series vols. 28-30, 1921 | text, archive.org | **Public domain** (`NOT_IN_COPYRIGHT`, confirmed for vol. 1) | Not fetched. See "Burlingame original" below |
| story titles, grouping (`title_en`, `title_pali`, `cst4_title`, `burlingame_title`, `dhp_verses`, `group_id`) | Ānandajoti Bhikkhu, *The Dhamma Verses Commentary*, August 2024 revision (`sources/Dhammapada-Attakatha.pdf`) | PDF | **CC BY-SA 3.0 Unported**, attribution required, high confidence by inference (see `docs/licensing.md`) | Already fetched and ingested |

## Checked directly for this table, not carried over from the design doc's draft

**CST4 licensing (`atthakatha_pali`).** The design doc's own table hedges
with "see VRI terms" rather than asserting a license -- checked directly
against `tipitaka.org`'s homepage and help page: no copyright, license, or
terms-of-use statement appears on either. The site states only "We
encourage the use of our digital library and resources for academic,
personal, and monastic research" and asks that users cite the site. That is
an invitation to use, not a license grant, and is not sufficient basis to
mark this row licensed. **If Stage 2 proceeds to actually fetch CST4 text,
contact `help@tipitaka.org` (the Vipassana Research Institute) for written
terms before ingesting** -- the same standard `docs/licensing.md` already
applied to the Ānandajoti PDF's revision layer (checked the publisher's own
stated policy rather than assuming), applied here to a source where that
check came back empty rather than confirmatory.

**Burlingame original (`atthakatha_english`).** Confirmed on archive.org:
volume 1 of *Buddhist Legends* (HOS 28, 1921) is present, full text
downloadable, rights status `NOT_IN_COPYRIGHT`, consistent with
`docs/licensing.md`'s existing basis for the 1921 work generally ("US
copyright on an unrenewed 1921 work has expired"). Volumes 2-3 (HOS 29-30)
were not individually re-checked; same author, same publication year, same
basis expected to hold, worth confirming at Stage 2 rather than assumed
here.

## Two consequences, stated per the design doc

**The PDF stops owning the Pali.** `sources/Dhammapada-Attakatha.pdf`
(Ānandajoti's 2024 revision) currently supplies `pali_verse`/
`english_verse` on stories that quote their own verse inline
(`narrative_pali`/`narrative_english` in the current, un-rebuilt schema) --
under this table, it owns titles and grouping only. Every verse-side field
comes from a machine-readable, per-verse-keyed source instead. This isn't
a hypothetical risk: Stage 0's audit (`docs/corpus_audit.md`, checks 4-5)
already found real vagga-boundary contamination in `pali_mahasangiti`
itself (a machine-readable source), and separately found substantial
genuine word-level variance between `pali_mahasangiti` and
`interlinear_pali` -- two sources this table already keeps distinct. A PDF
text-extraction pipeline, the least reliable input in this project, has
never been asked to be a third independent voice on the same verse text;
this table keeps it that way.

**Burlingame's original, independent of the 2024 revision.** Right now,
story numbering and grouping (`group_id`, `dhp_verses`) has exactly one
source: the 2024 PDF. A parsing error in `ingest/parse_stories.py` against
that one source is undetectable by cross-reference -- only by manual
inspection, which is exactly how Round 4/5's generation work resolved the
23.1 title/body question (checking the source PDF directly), and exactly
what Stage 0's `audit_corpus.py` check 1 flags as a class of thing worth
automating. Burlingame's 1921 original is confirmed accessible and public
domain (above). Stage 2, if it proceeds, does not need to fully ingest it
-- extracting only story boundaries and verse references from it is enough
to diff against the 2024 revision's grouping, per the design doc.

## What this table does not do

It does not fetch anything. `atthakatha_pali` and `atthakatha_english`
remain unfetched; this table only declares, in advance, which source will
own each field if Stage 2 proceeds -- so that stage doesn't repeat Phase
1's original mistake of letting whichever source arrives first quietly
supply a field nobody assigned it in writing.
