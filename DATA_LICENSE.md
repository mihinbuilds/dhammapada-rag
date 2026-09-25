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
| `sources/external/anandajoti_interlinear/` | Ānandajoti Bhikkhu, *Dhammapada* interlinear edition, 2nd ed., 2017 | CC BY-SA 3.0 Unported |
| `sources/Dhammapada-Attakatha.pdf` | Ānandajoti Bhikkhu's 2024 revision of E.W. Burlingame's *Buddhist Legends* (1921, public domain) | CC BY-SA 3.0 Unported, **by inference** (see below) |

## Derived data

Everything under `data/` (`raw/`, `normalized/`, `processed/`,
`index/chunks.jsonl`, `eval/`) is built from the sources above, including
the two CC BY-SA ones. It is therefore released under
**[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**. CC BY-SA
3.0 §4(b) allows adaptations to be licensed under a later version with the
same licence elements.

Attribution for reuse of the derived data:

> Dhammapada corpus derived from: the Mahāsaṅgīti Pāli text and Bhikkhu
> Sujato's translation (SuttaCentral, CC0); Ānandajoti Bhikkhu's
> *Dhammapada* interlinear edition and his 2024 revision of E.W.
> Burlingame's *Buddhist Legends* (ancient-buddhist-texts.net, CC BY-SA 3.0).
> Compiled by Mihindupura Sujeewa, DhammapadaRAG, CC BY-SA 4.0.

The CC0 layers (the Pāli verse text and Sujato's translation) can still be
used on their own without restriction. The share-alike condition comes from
the Ānandajoti layers.

## Open caveat

The narrative-source PDF does not state a licence in the document itself.
CC BY-SA 3.0 is inferred from the publisher's site-wide copyright notice,
which covers his translations and notes and does not list this work as an
exception. That is well supported, but it is an inference. Before any
public dataset release (Zenodo, Hugging Face), get written confirmation from
Ānandajoti Bhikkhu that names this specific PDF.
