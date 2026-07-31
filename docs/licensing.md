# Licensing table

| Layer | Source | Stated status | Confidence | Notes |
|---|---|---|---|---|
| Burlingame's 1921 translation/narrative content (underlies `Dhammapada-Attakatha.pdf`) | E.W. Burlingame, *Buddhist Legends*, Harvard University Press, 1921 | Public domain | High | PDF title page states "Now Public Domain." US copyright on an unrenewed 1921 work has expired. |
| Ānandajoti Bhikkhu's 2024 revision layer in `Dhammapada-Attakatha.pdf` (retranslated verses, restored Pāli titles, AJ notes, italicized completed stories, CST4 titles) | *The Dhamma Verses Commentary*, Ānandajoti Bhikkhu, August 2024 | **CC BY-SA 3.0 Unported** (attribution required) | High, by inference | The PDF itself states no license. Resolved by checking the publishing site's copyright notice directly: `https://ancient-buddhist-texts.net/Miscellaneous/Copyright-Notice.htm` states the CC BY-SA 3.0 Unported license covers "everything except for those works covered in the [PTS-copyright / already-public-domain exception] listings... including the introductions, translations, studies, and notes." This work isn't in either exception list, so it falls under the general CC BY-SA 3.0 grant. This is inference from the site's blanket policy, not a statement naming this exact PDF by title -- for a public/Zenodo release, get written confirmation from Ānandajoti Bhikkhu directly rather than relying on this inference alone. |
| Pāli verse text as reprinted in `Dhammapada-Attakatha.pdf` | Same PDF | Same as above (editor's transcription) | High, by inference | Same basis as the row above. |
| **Pāli root text, all 423 verses** (`sources/external/mahasangiti_pali/`) | Mahāsaṅgīti edition (Dhamma Society, 2005) via `suttacentral/bilara-data`, `published` branch | **CC0 1.0 Universal** | Confirmed | `LICENSE.md` in the source repo, fetched directly: "All translations created in Bilara and supported by SuttaCentral are dedicated to the Public Domain by means of the Creative Commons Public Domain (CC0) license." See `sources/external/PROVENANCE.md`. |
| **English translation, all 423 verses** (`sources/external/sujato_en/`) | Bhikkhu Sujato, via the same `bilara-data` repo | **CC0 1.0 Universal** | Confirmed | Same license file, same repo. |
| **Interlinear Pāli-English gloss, all 423 verses** (`sources/external/anandajoti_interlinear/`) | Ānandajoti Bhikkhu, *Dhammapada* interlinear edition, 2nd ed., Nov 2017, `ancient-buddhist-texts.net` | **CC BY-SA 3.0 Unported** (attribution required) | High | Same copyright notice as row 2, fetched and read directly (not inferred by absence this time -- the notice explicitly covers "translations... and notes," which is exactly what this is). Note this is a *different, earlier* work by the same translator than the narrative-source PDF. |

## Resolution of the "licensing unconfirmed" flag

The original flag (Phase 1, first pass) was that the narrative source PDF has
no in-document license statement for Ānandajoti Bhikkhu's own contribution.
That's still technically true of the PDF file itself, but checking his
publishing site's copyright notice directly resolves it with high confidence:
his standard license for translation/commentary/notes work is CC BY-SA 3.0,
attribution to him, and nothing in the PDF suggests this particular work is
an exception (the notice's exception lists are for PTS-copyrighted material
and already-public-domain material, and this is Ānandajoti Bhikkhu's own
authored revision, not either of those).

**Remaining action item, unchanged:** before any public dataset release
(Zenodo DOI, HuggingFace dataset, etc.), get written confirmation from
Ānandajoti Bhikkhu naming this specific PDF, since the inference above -- while
well-supported -- is still an inference from a general site policy rather
than a statement about this exact document.

## What this means for the corpus now

With the three new CC0/CC-BY-SA sources ingested, **every one of the 423
verses now has a complete, unambiguously-licensed Pali text, English
translation, and phrase-level gloss**, independent of what the single
narrative-source PDF happens to reprint inline (previously ~74% of stories,
~53% of verses -- see `data/processed/verses_report.json`). The narrative
source's own quotations, where present, are kept as a separate field
(`narrative_pali`/`narrative_english`) rather than discarded, since a verse's
recitation context within its own story is meaningful and distinct from a
standalone critical-edition quotation of the same verse.
