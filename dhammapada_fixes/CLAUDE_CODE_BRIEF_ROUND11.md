# Task brief — round 11: licence permission received

Ānandajoti Bhikkhu replied on 2026-09-25 granting permission to use his texts.
This resolves the "licence by inference" item that has been open since the
September self-audit, but it also **corrects a version we had wrong** and
introduces a reproducibility requirement we had not accounted for.

His reply, verbatim:

> Dear Venerable,
>
> Good to hear from you. And yes, you may use the texts. I only make this
> proviso, that I do in fact regularly update files if any mistake is made. So
> presumably your copy may become out of date at some point.
>
> \>\> Whether I may release the derived data under an open licence
>
> The license is on https://ancient-buddhist-texts.net/tt/Dhammapada/index.htm
> is https://creativecommons.org/licenses/by-sa/4.0/deed.en (previously 3.0).
> You should not change that. Apart from that everything should be OK.
>
> Wish you all the very best for your project and if it goes online, please do
> let me know where.
>
> Metta, Anandajoti

Three things follow. Do them in order — Task B depends on knowing which
version Task A records.

---

## Task A — Preserve the permission as a citable artifact

A permission that exists only in an inbox is not evidence. A Zenodo depositor
or a journal will ask to see it.

Create `sources/PERMISSION.md` containing:

- Date received, sender name and address, and the subject line of the enquiry
- The reply verbatim, in a blockquote, unedited
- The licence URL he cited, and the page it is stated on
- A one-line statement of what it covers: use of the texts, and release of
  derived data under CC BY-SA 4.0
- A note that he asked to be informed of the project's public URL — an
  outstanding courtesy, not a condition

Link it from `README.md`, `DATA_LICENSE.md` and `data/raw/PROVENANCE.md`.
Commit it on its own so the commit message records when permission was
obtained.

---

## Task B — Correct the licence version throughout

**He states CC BY-SA 4.0, previously 3.0.** Our files say 3.0, taken from the
2017 interlinear edition's own page before the site was updated. Every
statement of the version is now wrong.

```
grep -rn "BY-SA 3.0\|by-sa/3.0\|CC-BY-SA-3" --include="*.md" --include="*.cff" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.html" .
```

Update each to CC BY-SA 4.0, including the licence URL where one appears.
Check at minimum: `DATA_LICENSE.md`, `README.md`, `CITATION.cff`,
`docs/licensing.md`, the web footer, and any `PROVENANCE.md`.

While you are in `DATA_LICENSE.md`, verify the share-alike propagation is
stated correctly and per file, not as a blanket claim:

| File | Derived from | Licence |
|---|---|---|
| `data/processed/stories.jsonl` | Ānandajoti 2024 aṭṭhakathā | CC BY-SA 4.0 |
| `data/processed/interlinear_gloss.jsonl` | Ānandajoti 2017 interlinear | CC BY-SA 4.0 |
| `data/processed/alignment_table.json` | Ānandajoti 2024 (story numbering) | CC BY-SA 4.0 |
| `data/processed/verses.jsonl` | mixed — see note | CC BY-SA 4.0 |
| `src/`, `tests/`, `web/` | this project | MIT |

`verses.jsonl` is the one to check carefully: Mahāsaṅgīti and Sujato are CC0,
but if the record also embeds `interlinear_pali` / `interlinear_english` /
`interlinear_notes`, the combined file is share-alike. Read the file and state
which case it is rather than assuming.

---

## Task C — Pin the source snapshot

This is the substantive consequence of his proviso, and it is a
reproducibility problem we do not currently address: **he updates the files
when he finds mistakes.** Our alignment table, story numbering, titles and
narrative text all derive from one download whose date is not recorded. A
reader comparing our alignment table against a newer PDF has no way to know
whether a discrepancy is our parsing error or his correction.

Do:

1. Compute and record a SHA-256 of `sources/Dhammapada-Attakatha.pdf` and of
   the fetched interlinear HTML, in `data/raw/PROVENANCE.md` alongside the
   source URL and the download date (use the file's mtime if the date was not
   logged, and say that is what it is).
2. Add a `source_version` block to `docs/datasheet.md`: which edition, which
   snapshot, what checksum, and the explicit statement that upstream may have
   changed since.
3. Add one line to `README.md`'s corpus section: the corpus reflects
   Ānandajoti's editions as of that date, and upstream corrections after it
   are not incorporated.

Optionally — and this is now the cleaner option rather than a workaround —
write `sources/fetch.sh` that downloads both sources and verifies the
checksums. With permission granted, shipping the PDF is allowed but no longer
necessary, and a fetch script makes version drift visible instead of silent.
Do not remove the PDF from the repo in this round; just add the script and
note the choice.

---

## Verify

```
grep -rn "BY-SA 3.0" .          # expect: no hits outside PERMISSION.md's quote
ls sources/PERMISSION.md
grep -n "sha256\|SHA-256" data/raw/PROVENANCE.md
python -m pytest -q
```

Then commit as one change per task, so the permission commit is findable on
its own.

---

## Do not

- Do not change the licence on the derived data to anything other than
  CC BY-SA 4.0. He wrote "You should not change that" — MIT or CC0 on
  `stories.jsonl` or `alignment_table.json` would be a licence violation, not
  a preference.
- Do not re-download the sources to "get the latest." That would silently
  change the corpus underneath an evaluation that has just been re-run, and
  the whole point of Task C is to pin what we actually have.
- Do not treat this as closing the provenance question entirely. Story
  grouping still has a single witness; permission to use the edition is not
  verification that the edition's numbering is internally consistent.

---

## Still open after this round

For the next status check, these remain:

1. **Second annotator.** Infrastructure is complete (blind sheet, 30-question
   sample, κ tooling, annotator brief). The blocker is a person, not code.
2. **`docs/evaluation.md` pre-cleaning numbers.** Round 10 added a new
   section; confirm the older sections are either updated or explicitly marked
   as superseded, and that nothing in the README quotes a superseded figure.
3. **Story 23.1's nidāna.** The stored location has been queried repeatedly and
   never reported either way. Print the field and say what it contains.
4. **Cross-edition variance classification.** The 42% Pali divergence is still
   one undifferentiated number rather than split into single-token variants,
   word substitutions and structural differences.

Do not start these in this round.
