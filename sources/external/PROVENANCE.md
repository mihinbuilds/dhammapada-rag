# Provenance: sources/external/

Fetched 2026-07-30 to close three gaps flagged after the first Phase 1 pass
(see `docs/datasheet.md` "Known limitations" as it stood before this fetch,
and `docs/licensing.md`): incomplete Pali verse coverage, no pada-gloss
layer, and unconfirmed licensing on the narrative source's revision layer.

## mahasangiti_pali/ -- complete Pali root text, all 423 verses

- Source: `suttacentral/bilara-data`, `published` branch,
  `root/pli/ms/sutta/kn/dhp/dhp{range}_root-pli-ms.json` (26 files, one per
  vagga's verse range, e.g. `dhp1-20_root-pli-ms.json`).
- Fetched via: `curl` from
  `https://raw.githubusercontent.com/suttacentral/bilara-data/published/...`
- Text basis: Mahāsaṅgīti edition (the exact edition `docs/project_plan.md`'s
  original plan specified), collated by the Dhamma Society, as adopted and
  segment-ID-tagged by SuttaCentral.
- License: **CC0 1.0 Universal (public domain dedication)**. Confirmed by
  fetching `LICENSE.md` from the same repo/branch: "All translations created
  in Bilara and supported by SuttaCentral are dedicated to the Public Domain
  by means of the Creative Commons Public Domain (CC0) license." Root/segment
  Pali text is included under the same repo-wide license. See
  https://suttacentral.net/licensing for the canonical statement.
- Format: JSON, `{"dhp<verse>:<line>": "Pali text "}`, plus `dhp<verse>:0.N`
  header segments giving nikāya/vagga/story-title context per verse.

## sujato_en/ -- second independent English translation, all 423 verses

- Source: same repo/branch,
  `translation/en/sujato/sutta/kn/dhp/dhp{range}_translation-en-sujato.json`.
- Translator: Bhikkhu Sujato.
- License: CC0, same basis as above.
- Not one of the four gaps this fetch targeted, but directly fills
  `docs/project_plan.md`'s original Phase 1 item 1 ask for "two English
  translations," which the single-PDF prototype had been deviating from.
  Ingested as a bonus since it was zero extra licensing risk once the Pali
  fetch was already in progress.

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
