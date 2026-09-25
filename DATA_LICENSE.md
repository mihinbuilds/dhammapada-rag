# Data licence

The code in this repository (`src/`, `tests/`, `web/`, and the build and
evaluation scripts) is under the MIT licence in [`LICENSE`](LICENSE). The
text data is not: it is derived from third-party sources, and those sources'
licences decide what it can be released under. Per-source evidence is in
[`docs/licensing.md`](docs/licensing.md), `data/raw/PROVENANCE.md` and
`sources/external/PROVENANCE.md`.

## Upstream sources, redistributed unmodified

| Path | Source | Licence |
|---|---|---|
| `sources/external/mahasangiti_pali/` | Mahāsaṅgīti Pāli (Dhamma Society, 2005) via SuttaCentral `bilara-data` | CC0 1.0 |
| `sources/external/sujato_en/` | Bhikkhu Sujato's English translation via SuttaCentral `bilara-data` | CC0 1.0 |
| `sources/external/anandajoti_interlinear/` | Ānandajoti Bhikkhu, *Dhammapada* interlinear edition, 2nd ed., 2017 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `sources/Dhammapada-Attakatha.pdf` | Ānandajoti Bhikkhu's 2024 revision of E.W. Burlingame's *Buddhist Legends* (1921, public domain) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), confirmed in writing ([`sources/PERMISSION.md`](sources/PERMISSION.md)) |

## Derived data

The whole `data/` tree is released under
**[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**. For
files built from an Ānandajoti source, that is a requirement: share-alike
carries through to adaptations, and he asked that the licence not be
changed. For the few files built only from CC0 sources, it is this project's
choice, and the CC0 text inside them stays free to reuse on its own.

| File | Derived from | Licence |
|---|---|---|
| `data/processed/stories.jsonl` | Ānandajoti 2024 aṭṭhakathā | CC BY-SA 4.0 (required) |
| `data/processed/interlinear_gloss.jsonl` | Ānandajoti 2017 interlinear | CC BY-SA 4.0 (required) |
| `data/processed/alignment_table.json` | Ānandajoti 2024 (story numbering and grouping) | CC BY-SA 4.0 (required) |
| `data/processed/verses.jsonl` | Mixed, see note | CC BY-SA 4.0 (required) |
| `data/normalized/aj_stories.jsonl`, `alignment_table.json`, `alignment_table.csv` | Ānandajoti 2024 aṭṭhakathā | CC BY-SA 4.0 (required) |
| `data/normalized/aj_interlinear.jsonl` | Ānandajoti 2017 interlinear | CC BY-SA 4.0 (required) |
| `data/normalized/verses_joined.json` | Mixed: CC0 verse text plus Ānandajoti 2017 and 2024 fields | CC BY-SA 4.0 (required) |
| `data/normalized/sc_pali.jsonl`, `sc_sujato.jsonl` | Mahāsaṅgīti and Sujato only | CC BY-SA 4.0 (project's choice; the text is CC0) |
| `data/raw/dhammapada-attakatha.txt`, `dhammapada-attakatha-cleaned.txt` | Text extraction of the Ānandajoti 2024 PDF | CC BY-SA 4.0 (required) |
| `data/index/chunks.jsonl` | Story and verse text from the files above | CC BY-SA 4.0 (required) |
| `data/eval/` | Questions written for this project, plus retrieved and generated text quoting the corpus | CC BY-SA 4.0 (required where corpus text is quoted) |
| `*_report.json` files | Build statistics about the files above | CC BY-SA 4.0 (project's choice) |
| `src/`, `tests/`, `web/` | This project | MIT |

**`verses.jsonl`.** Each record holds `pali_mahasangiti` and `english_sujato`
(CC0), `interlinear_pali`, `interlinear_english` and `interlinear_notes`
(Ānandajoti 2017), and `narrative_pali`, `narrative_english` and
`story_group_ids` (Ānandajoti 2024). Because the Ānandajoti fields are
embedded, the combined file is share-alike. Only the two CC0 fields,
extracted on their own, are free of the condition.

Attribution for reuse of the derived data:

> Dhammapada corpus derived from: the Mahāsaṅgīti Pāli text and Bhikkhu
> Sujato's translation (SuttaCentral, CC0); Ānandajoti Bhikkhu's
> *Dhammapada* interlinear edition and his 2024 revision of E.W.
> Burlingame's *Buddhist Legends* (ancient-buddhist-texts.net, CC BY-SA 4.0).
> Compiled by Mihindupura Sujeewa, DhammapadaRAG, CC BY-SA 4.0.

## Permission

Ānandajoti Bhikkhu gave written permission on 2026-09-25 to use his texts and
to release the derived data under his licence, which he asked not to be
changed. His reply is recorded verbatim in
[`sources/PERMISSION.md`](sources/PERMISSION.md). It replaces the earlier
licence-by-inference for the narrative PDF, which states no licence in the
document itself.
