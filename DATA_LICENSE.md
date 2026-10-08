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
| `sources/external/anandajoti_interlinear/` | Ānandajoti Bhikkhu, *Dhammapada* interlinear edition, 2nd ed., 2017 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `sources/Dhammapada-Attakatha.pdf` | Ānandajoti Bhikkhu's 2024 revision of E.W. Burlingame's *Buddhist Legends* (1921, public domain) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), confirmed in writing ([`sources/PERMISSION.md`](sources/PERMISSION.md)) |

## Derived data

The whole `data/` tree is released under
**[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**. Every
text in it is built from an Ānandajoti source, so that is a requirement:
share-alike carries through to adaptations, and he asked that the licence not
be changed.

| File | Derived from | Licence |
|---|---|---|
| `data/processed/stories.jsonl` | Ānandajoti 2024 aṭṭhakathā | CC BY-SA 4.0 (required) |
| `data/processed/interlinear_gloss.jsonl` | Ānandajoti 2017 interlinear | CC BY-SA 4.0 (required) |
| `data/processed/alignment_table.json` | Ānandajoti 2024 (story numbering and grouping) | CC BY-SA 4.0 (required) |
| `data/processed/verses.jsonl` | Ānandajoti 2017 and 2024, see note | CC BY-SA 4.0 (required) |
| `data/normalized/aj_stories.jsonl`, `alignment_table.json`, `alignment_table.csv` | Ānandajoti 2024 aṭṭhakathā | CC BY-SA 4.0 (required) |
| `data/normalized/aj_interlinear.jsonl` | Ānandajoti 2017 interlinear | CC BY-SA 4.0 (required) |
| `data/normalized/verses_joined.json` | Ānandajoti 2017 interlinear, Ānandajoti 2024 grouping | CC BY-SA 4.0 (required) |
| `data/raw/dhammapada-attakatha.txt`, `dhammapada-attakatha-cleaned.txt` | Text extraction of the Ānandajoti 2024 PDF | CC BY-SA 4.0 (required) |
| `data/index/chunks.jsonl` | Story and verse text from the files above | CC BY-SA 4.0 (required) |
| `data/eval/` | Questions written for this project, plus retrieved and generated text quoting the corpus | CC BY-SA 4.0 (required where corpus text is quoted) |
| `*_report.json` files | Build statistics about the files above | CC BY-SA 4.0 (project's choice) |
| `src/`, `tests/`, `web/` | This project | MIT |

**`verses.jsonl`.** Each record holds `interlinear_pali`,
`interlinear_english` and `interlinear_notes` (Ānandajoti 2017), and
`narrative_pali`, `narrative_english` and `story_group_ids` (Ānandajoti
2024). The whole file is share-alike.

Attribution for reuse of the derived data:

> Dhammapada corpus derived from: Ānandajoti Bhikkhu's
> *Dhammapada* interlinear edition and his 2024 revision of E.W.
> Burlingame's *Buddhist Legends* (ancient-buddhist-texts.net, CC BY-SA 4.0).
> Compiled by Sujeewa Mihindupura, DhammapadaRAG, CC BY-SA 4.0.

## Permission

Ānandajoti Bhikkhu gave written permission on 2026-09-25 to use his texts and
to release the derived data under his licence, which he asked not to be
changed. His reply is recorded verbatim in
[`sources/PERMISSION.md`](sources/PERMISSION.md). It replaces the earlier
licence-by-inference for the narrative PDF, which states no licence in the
document itself.

## SuttaCentral material (removed 2026-10-08)

Until 2026-10-08 this table also listed the Mahāsaṅgīti Pāli text and
Bhikkhu Sujato's English translation, both published by SuttaCentral under
CC0, and files derived from them. On 2026-10-08 SuttaCentral's Forum
Management Committee
[answered a licensing question](https://discourse.suttacentral.net/t/licensing-question-retrieval-over-cc0-texts-does-this-fall-under-your-ai-request/45514)
from this project: "You cannot use Bhante Sujato's translations in any
project which uses AI." Removal was by their request, not a legal obligation.
Both sources, and everything derived from them, were removed from the data
and the code, and the source files from the repository's history with
`git filter-repo`. The exception is files that are still part of the project
but whose earlier versions carried the text inside them, such as
`verses.jsonl`. Their history was documented rather than rewritten. Details:
[`data/raw/PROVENANCE.md`](data/raw/PROVENANCE.md).
