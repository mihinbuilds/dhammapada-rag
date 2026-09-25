# Corpus rebuild: design notes

The current corpus was built by letting one source (Ānandajoti's revision of
Burlingame, a PDF) supply the commentary, the story numbering, the verse
grouping, **and** — where present — the Pali and English verse text, with other
sources added afterward to fill gaps. That is the defect. When one source can
silently supply another's field, you cannot tell from the record which edition
you are reading, and the errors that follow (a title paired with the wrong
narrative, Ānandajoti's hyphenation appearing in a field labelled Mahāsaṅgīti)
are invisible until something downstream trips over them.

The rebuild principle is one sentence: **every field has exactly one owning
source, declared in advance, and a field is empty rather than filled from
elsewhere.**

---

## Stage 0 — Diagnose before rebuilding

Do not rebuild until you know the scale. Write `ingest/audit_corpus.py` that
reports, without changing anything:

1. **Title/body coherence.** For each story, extract proper nouns from
   `title_en` (capitalised tokens, minus stopwords like "The", "Story",
   "About") and check whether each appears in `vatthu` or `synopsis`. Report
   every story where none does. This is the check that catches 23.1.
2. **Control characters.** Any codepoint below U+0020 except `\n` and `\t`, in
   any field, in `stories.jsonl` and `verses.jsonl`.
3. **Pali character set.** Any character in `pali_mahasangiti` outside
   `[a-zāīūṁṃṅñṭḍṇḷ\s.,;'-]` (case-insensitive). Latin punctuation, digits, or
   stray Greek/Cyrillic are OCR residue.
4. **Cross-source verse agreement.** Normalize `pali_mahasangiti` and
   `interlinear_pali` (fold hyphens, spacing, case, ṃ/ṁ) and compare. Report
   the disagreement rate and the 20 worst offenders. A high rate means one
   field is contaminated by the other.
5. **Inline-vs-canonical.** For stories carrying `pali_verse`, compare against
   the canonical Pali for `pali_verse_number`. Same normalization.
6. **Alignment closure.** Union of all `dhp_verses` across stories must equal
   1..423 exactly. Report gaps and verses claimed by more than one story
   (some are legitimate — Dhp 416 has two stories — so list rather than fail).
7. **Length outliers.** Stories whose `vatthu` is under 200 characters, or
   whose `nidana` is longer than its `vatthu`. Both indicate a parse that
   split in the wrong place.

Write the output to `docs/corpus_audit.md`. **That document is a deliverable
regardless of what you do next** — a candid corpus audit is exactly the kind of
artifact a digital-humanities reviewer looks for, and most projects don't have
one.

---

## Stage 1 — Declare source ownership

One table, written before any code. Each row is a field; each field has one
owner and no fallback.

| Field | Owning source | Format | Licence |
|---|---|---|---|
| `pali_mahasangiti` | SuttaCentral bilara-data (Mahāsaṅgīti) | JSON, segment-keyed | CC0 |
| `english_sujato` | SuttaCentral bilara-data (Sujato) | JSON, segment-keyed | CC0 |
| `interlinear_pali` | Ānandajoti 2017 interlinear | HTML | CC BY-SA 4.0 |
| `interlinear_english` | Ānandajoti 2017 interlinear | HTML | CC BY-SA 4.0 |
| `interlinear_notes` | Ānandajoti 2017 interlinear | HTML | CC BY-SA 4.0 |
| `english_muller` (optional) | Müller 1881, SBE X | text | public domain |
| `atthakatha_pali` | CST4 Dhammapada-aṭṭhakathā, tipitaka.org | HTML/text | see VRI terms |
| `atthakatha_english` | Burlingame, *Buddhist Legends* HOS 28–30 | text (archive.org) | public domain |
| story titles, grouping | Ānandajoti 2024 revision | PDF | verify |

Two consequences worth stating explicitly.

**The PDF stops owning the Pali.** It supplies commentary and grouping only.
Everything verse-side comes from machine-readable, per-verse-keyed sources. PDF
text extraction is the least reliable input you have and it should not be
touching your canonical text.

**Add Burlingame's original as an independent check on the 2024 revision.** You
currently have one source for story numbering and grouping, which means a
parsing error there is undetectable. Burlingame is public domain and on
archive.org. You don't need to ingest it fully — extracting just the story
boundaries and verse references is enough to diff against.

---

## Stage 2 — Three independent normalizers, no joining yet

Separate script per source, each writing its own file. None of them reads
another's output.

```
data/normalized/
  sc_pali.jsonl          {verse, pali, source_ref}          423 rows
  sc_sujato.jsonl        {verse, english, source_ref}       423 rows
  aj_interlinear.jsonl   {verse, pali, english, notes}      423 rows
  cst_atthakatha.jsonl   {cst_ref, pali_text}               ~300 rows
  bl_legends.jsonl       {bl_ref, title, english_text}      ~300 rows
  aj_stories.jsonl       {group_id, title, sections, verses} ~305 rows
```

Each row carries a `source_ref` locating it in the original — a SuttaCentral
segment id, an HTML anchor, a PDF page number. When something looks wrong three
months from now, that field is how you check it in ten seconds instead of an
afternoon.

Each normalizer validates only its own output: row count, no control
characters, character set, no empty required fields. A normalizer that can't
meet its own contract fails loudly rather than emitting partial rows.

---

## Stage 3 — Build the alignment table as its own artifact

This is the project's most citable contribution and it deserves to be a
first-class file rather than a byproduct.

```json
{
  "group_id": "8.13",
  "dhp_verses": [114],
  "sources": {
    "anandajoti_2024": {"story_no": "8.13", "verses": [114]},
    "burlingame_1921":  {"book_story": "VIII.13", "verses": [114]},
    "cst4":             {"ref": "...", "verses": [114]}
  },
  "agreement": "full",
  "notes": null
}
```

`agreement` takes `full`, `partial`, or `disputed`. **A disagreement is a
finding, not a bug.** If Ānandajoti groups Dhp 21–23 under one story and
another edition splits them, record both and mark it `disputed`. Those rows are
the most interesting thing in the file, and a system that can answer "editions
differ on how these verses are grouped" is doing something no other Dhammapada
tool does.

Publish this separately on Zenodo with a DOI, as CSV plus JSON. It's citable on
its own even if nobody ever runs your code.

---

## Stage 4 — Join, with provenance on every field

```json
{
  "verse": 114,
  "vagga": {"number": 8, "pali": "Sahassavagga"},
  "text": {
    "pali_mahasangiti": {
      "value": "Yo ca vassasataṁ jīve...",
      "source": "suttacentral_mahasangiti",
      "source_ref": "dhp114:1.1",
      "retrieved": "2026-07-15"
    },
    "english_sujato": {"value": "...", "source": "suttacentral_sujato", "...": "..."},
    "interlinear_pali": {"value": "...", "source": "anandajoti_2017", "...": "..."}
  },
  "story_group_ids": ["8.13"],
  "flags": []
}
```

Verbose, and worth it. With this shape the hyphenated-Pali problem is a
one-line query — *which field claims to be Mahāsaṅgīti but has a `source` that
isn't?* — instead of something you discover from a model's output six weeks
later.

`flags` carries per-record validation results (`metre_irregular`,
`cross_source_mismatch`, `hand_corrected`) so anomalies travel with the data
rather than living in a separate report that drifts out of sync.

---

## Stage 5 — Validation gates

Fail the build on 1–4. Warn and record on 5–7.

1. **Structure.** 423 verses, 26 vaggas, boundaries matching `vaggas.py`, no
   gaps, no duplicates. You have this already.
2. **Field ownership.** Every populated field's `source` matches the ownership
   table. No exceptions, no fallbacks.
3. **Encoding.** NFC everywhere; no control characters; Pali fields contain
   only IAST characters and permitted punctuation.
4. **Alignment closure.** Union of `dhp_verses` equals 1..423.
5. **Metrical sanity.** Count syllables per pāda (Pali vowels `a ā i ī u ū e o`,
   with `e`/`o` single) and flag verses matching no known pattern — siloka is
   8 per pāda, tuṭṭhubha 11. The Dhammapada has genuine metrical variety, so
   this is a heuristic flag, not a gate. But a pāda coming in at 3 or 19
   syllables is almost always truncation or OCR damage, and this catches it
   without a human reading 423 verses.
6. **Cross-source agreement.** Normalized `pali_mahasangiti` vs
   `interlinear_pali`. Expect high agreement; investigate every outlier.
   Record the rate — it's a corpus-quality number worth publishing.
7. **Title/body coherence.** The Stage 0 check, run permanently as a gate.

---

## What this buys you

- **The Pali audit becomes meaningful.** Right now `PALI_QUOTE_NOT_IN_SOURCE`
  compares against one field while several editions' text may be in play. With
  declared ownership you know exactly which edition the model was shown, so a
  variant is unambiguously the model's doing.
- **Edition variance becomes answerable.** "Do editions disagree about this
  verse's grouping?" is a query, not a research project.
- **The audit document is itself a contribution.** Corpus construction is the
  part of digital-humanities work that gets skipped and then quietly determines
  everything downstream. Writing yours up honestly — including what the first
  attempt got wrong — is more valuable than a clean pipeline with no history.

---

## Sequence

1. Stage 0 audit. **Report before touching anything.** The result decides patch
   vs rebuild.
2. If rebuilding: Stages 1–2 first, keeping the old corpus intact alongside.
3. Stage 3 alignment table, diffed across sources, hand-verified on
   disagreements.
4. Stage 4 join, Stage 5 gates.
5. Rebuild the index and re-run everything. Any metric from the old corpus is
   not comparable.
6. Diff old against new and write up what changed. That diff is evidence, and
   throwing it away wastes the most interesting part.

Budget real time for Stage 3. It's the part that can't be automated and the
part that's worth the most.
