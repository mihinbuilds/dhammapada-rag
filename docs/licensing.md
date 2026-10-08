# Licensing table

| Layer | Source | Stated status | Confidence | Notes |
|---|---|---|---|---|
| Burlingame's 1921 translation/narrative content (underlies `Dhammapada-Attakatha.pdf`) | E.W. Burlingame, *Buddhist Legends*, Harvard University Press, 1921 | Public domain | High | PDF title page states "Now Public Domain." US copyright on an unrenewed 1921 work has expired. |
| Ānandajoti Bhikkhu's 2024 revision layer in `Dhammapada-Attakatha.pdf` (retranslated verses, restored Pāli titles, AJ notes, italicized completed stories, CST4 titles) | *The Dhamma Verses Commentary*, Ānandajoti Bhikkhu, August 2024 | **CC BY-SA 4.0** (attribution required) | Confirmed | The PDF itself states no license. Confirmed in writing by Ānandajoti Bhikkhu on 2026-09-25 (`sources/PERMISSION.md`): permission to use the texts, licence CC BY-SA 4.0 as stated on `https://ancient-buddhist-texts.net/tt/Dhammapada/index.htm` ("previously 3.0"), not to be changed. Before that reply this row gave version 3.0 Unported, "high confidence by inference", from the site-wide notice at `https://ancient-buddhist-texts.net/Miscellaneous/Copyright-Notice.htm`, which covers his "introductions, translations, studies, and notes" and does not list this work as an exception. |
| Pāli verse text as reprinted in `Dhammapada-Attakatha.pdf` | Same PDF | Same as above (editor's transcription) | Confirmed | Same basis as the row above. |
| **Interlinear Pāli-English gloss, all 423 verses** (`sources/external/anandajoti_interlinear/`) | Ānandajoti Bhikkhu, *Dhammapada* interlinear edition, 2nd ed., Nov 2017, `ancient-buddhist-texts.net` | **CC BY-SA 4.0** (attribution required) | Confirmed | Confirmed by the same 2026-09-25 reply (`sources/PERMISSION.md`). This project's records gave version 3.0 Unported until then: that was the version on the site when the edition was fetched (2026-07-30), and he has since moved to 4.0. Note this is a *different, earlier* work by the same translator than the narrative-source PDF. |

Until 2026-10-08 this table had two more rows: a Pāli root text and an English
translation, both published by SuttaCentral. SuttaCentral asked that their
material not be used in any project that uses AI, and both were removed from
the corpus and from the repository's history. The record of that decision is
in `data/raw/PROVENANCE.md`.

## Resolution of the "licensing unconfirmed" flag

The original flag (Phase 1, first pass) was that the narrative source PDF has
no in-document license statement for Ānandajoti Bhikkhu's own contribution.
Until September 2026 this was resolved only by inference from his publishing
site's copyright notice, which covered his translations and notes under
version 3.0 of the licence and listed no exception for this work.

**Resolved in writing, 2026-09-25.** Ānandajoti Bhikkhu replied to a direct
enquiry: "yes, you may use the texts", under CC BY-SA 4.0 ("previously 3.0"),
and "You should not change that." The reply is kept verbatim in
`sources/PERMISSION.md`. Two consequences:

- **Version.** Every statement of version 3.0 in this project was out of date
  and now reads 4.0. The derived data was already CC BY-SA 4.0 and stays so.
  Under his condition, no Ānandajoti-derived file may be relicensed to MIT,
  CC0 or anything else.
- **Upstream corrections.** He updates his files when he finds mistakes, so
  the pinned snapshot matters. Its date and checksums are in
  `data/raw/PROVENANCE.md`.

Permission to use the editions does not verify them. Story grouping still has
a single witness.

## What this means for the corpus now

With the interlinear edition ingested, **every one of the 423 verses has a
complete, unambiguously-licensed Pali text, English translation, and
phrase-level gloss**, independent of what the single
narrative-source PDF happens to reprint inline (previously ~74% of stories,
~53% of verses -- see `data/processed/verses_report.json`). The narrative
source's own quotations, where present, are kept as a separate field
(`narrative_pali`/`narrative_english`) rather than discarded, since a verse's
recitation context within its own story is meaningful and distinct from a
standalone critical-edition quotation of the same verse.
