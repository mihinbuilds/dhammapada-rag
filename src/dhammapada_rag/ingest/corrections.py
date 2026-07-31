"""Hand-corrections to this source's own "Dhp N" story-header lines.

DhammapadaRAG.txt Phase 1 item 4: "hand-correct the rest and log your
correction rate -- that number belongs in the paper." These are exactly that:
each was found by validate.py flagging a missing/duplicated/out-of-range verse
number, then confirmed by reading the story's body text, which quotes the full
numbered Pali verse(s) independently of the header line. Evidence is recorded
per entry so the correction is auditable, not silent.

6 corrections / 305 stories = ~2% of stories needed hand-correction to pass
hard validation (423 verses, 26 vaggas, no gaps, no dupes).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Correction:
    group_id: str
    parsed_dhp_verses: list[int]
    corrected_dhp_verses: list[int]
    evidence: str


CORRECTIONS: dict[str, Correction] = {
    c.group_id: c
    for c in [
        Correction(
            group_id="2.1",
            parsed_dhp_verses=[21, 22],
            corrected_dhp_verses=[21, 22, 23],
            evidence=(
                "Header states 'Dhp 21-22' but the story body quotes verse 23 "
                "in full ('23. Te jhāyino sātatikā...') as part of the same "
                "'he pronounced the following verses' passage. Dhp 21-23 is "
                "also the canonical grouping named explicitly in "
                "DhammapadaRAG.txt's own Phase 1 example."
            ),
        ),
        Correction(
            group_id="3.1",
            parsed_dhp_verses=[33],
            corrected_dhp_verses=[33, 34],
            evidence=(
                "Header states 'Dhp 33' (synopsis says 'taught him with some "
                "verses', plural) but the body quotes verse 34 in full "
                "('34. Vārijo va thale khitto...') as well as 33. Dhp 33-34 "
                "is the well-known paired 'wavering mind' verses."
            ),
        ),
        Correction(
            group_id="17.7",
            parsed_dhp_verses=[227],
            corrected_dhp_verses=[227, 228, 229, 230],
            evidence=(
                "Header states 'Dhp 227' but the body quotes verses 228, 229, "
                "and 230 in full immediately after 227. This is the "
                "well-known Atula/'criticism is unavoidable' four-verse group."
            ),
        ),
        Correction(
            group_id="18.12",
            parsed_dhp_verses=[254],
            corrected_dhp_verses=[254, 255],
            evidence=(
                "Header states 'Dhp 254' but the body quotes verse 255 in "
                "full ('no path in the sky' pair) immediately after 254."
            ),
        ),
        Correction(
            group_id="26.17",
            parsed_dhp_verses=[40],
            corrected_dhp_verses=[400],
            evidence=(
                "Header states 'Dhp 40' -- a source typo (missing trailing "
                "zero): this story is in vagga 26 (Brahmanavagga, verses "
                "383-423) between stories for Dhp 399 and Dhp 405, and its "
                "body quotes '400. Akkodhanaṁ vatavantaṁ...' in full. Dhp 40 "
                "is a different verse in a different vagga (Cittavagga), "
                "already correctly covered by story 3.6."
            ),
        ),
        Correction(
            group_id="26.34",
            parsed_dhp_verses=[416408],
            corrected_dhp_verses=[416],
            evidence=(
                "Header reads 'Dhp 416408' -- a PDF text-extraction glitch "
                "with no clean single-number reading. A footnote on the "
                "preceding story (26.33, which explains Dhp 416) explicitly "
                "says 'the tale is only completed in the next story, which "
                "is also attached to Dhp 416' -- confirmed by the "
                "translator's introduction, which independently notes verse "
                "416 uniquely has two commentarial stories (26.33 and "
                "26.34). The '417.' verse line that appears further down the "
                "page belongs to the *next* story, 26.35 (header starts "
                "before that line), whose own 'Dhp 417' header already "
                "parses correctly without correction."
            ),
        ),
    ]
}


def apply_corrections(stories: list[dict]) -> list[dict]:
    applied = []
    for s in stories:
        c = CORRECTIONS.get(s["group_id"])
        if c is None:
            continue
        if s["dhp_verses"] != c.parsed_dhp_verses:
            # source text or parser changed since this correction was written;
            # don't silently apply a stale correction
            continue
        s["dhp_verses"] = list(c.corrected_dhp_verses)
        s["parse_flags"] = s.get("parse_flags", []) + ["dhp_verses_hand_corrected"]
        applied.append(c.group_id)
    return applied
