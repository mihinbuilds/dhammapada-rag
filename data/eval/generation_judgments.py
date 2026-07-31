"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" -- no
IAA is claimed for these judgments.

Re-made from scratch against the Phase 5 (post-fix) generation run, per
CLAUDE_CODE_BRIEF.md's instruction: the archived judgments (data/eval/
archive_pre_fix/) scored claims from a truncated-context run where 100% of
claims came back tagged 'verse' and do not apply to this output.

REQUIRED JUDGMENT SHAPE (per aggregate_generation.py):
    tag_correct: bool    predicted layer (the claim's own `layer` field)
                          matches gold_layer
    gold_layer:  str     "verse" | "commentary" | "synthesis" -- what the
                          claim's content actually is, independent of what it
                          was tagged
    is_conflation: bool  gold_layer == "commentary" and predicted == "verse"
                          (the narrow, named failure: presenting Buddhaghosa's
                          gloss as the plain sense of the verse)

Judging rule used throughout (see notes on individual entries for edge
cases): gold_layer is decided by where the claim's content is actually
sourced from, not by sentence form. A full-sentence claim that directly
restates a fact literally present in the retrieved commentary (e.g. a CST4
title) is still 'commentary' -- sentence-wrapping a cited fact does not make
it synthesis. A claim asserting a relationship the source text does not
itself state (e.g. "story X explains verses Y and Z together", answering an
alignment/corpus_anomaly question's premise) is 'synthesis': it is the
model's own inference/construction, not a restatement of retrieved content,
even when it happens to be correct.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    tag_correct: bool
    gold_layer: str
    is_conflation: bool
    note: str


JUDGMENTS: dict[tuple[str, int], Verdict] = {
    # q091 alignment -- gold 14.6 retrieved correctly.
    ("q091", 0): Verdict(False, "synthesis", False,
        "Asserts a structural relationship ('provides a unified context for Dhp 188-192') not itself stated in the retrieved synopsis -- the model's own inference connecting the story to the alignment question. Tagged 'commentary'; should be 'synthesis'."),

    # q093 alignment -- gold 6.11 retrieved correctly.
    ("q093", 0): Verdict(True, "commentary", False, "Verbatim story title, correctly tagged 'commentary'."),
    ("q093", 1): Verdict(True, "commentary", False, "Paraphrase of the story's nidana/vatthu opening (fifty bhikkhus visiting after the Rains Retreat), correctly tagged 'commentary'."),
    ("q093", 2): Verdict(True, "commentary", False, "Narrative framing leading into the verse recitation, correctly tagged 'commentary'."),

    # q095 alignment -- retrieval failed (gold 22.9 not retrieved; retrieved 5.1/5.12/18.9).
    ("q095", 0): Verdict(True, "verse", False, "Verbatim quote of verse 251 (from the wrongly-retrieved bundle 18.9, but genuinely verse-layer content), correctly tagged 'verse'."),
    ("q095", 1): Verdict(False, "synthesis", False,
        "Asserts '18.9 explains both Dhp 318 and 319' -- factually wrong (18.9 explains verse 251) and not stated anywhere in the retrieved text; the model's own (incorrect) inference. Tagged 'commentary'; should be 'synthesis'."),

    # q097 alignment -- gold 25.5 retrieved correctly.
    ("q097", 0): Verdict(True, "commentary", False, "Verbatim story title of the gold story, correctly tagged 'commentary'. (No citation fields -- MISSING_PROVENANCE, a separate structural issue from the tag itself.)"),

    # q099 alignment -- gold 14.5 retrieved correctly.
    ("q099", 0): Verdict(True, "commentary", False, "Verbatim story title of the gold story, correctly tagged 'commentary'. Same missing-citation issue as q097."),

    # q119 corpus_anomaly -- retrieval failed (gold 26.34/Dhp416 not retrieved;
    # retrieved 4.12/26.40/26.18). Generation degenerated: every claim's text
    # is literally just the word "verse"/"commentary"/"synthesis" -- a
    # distinct failure mode (schema-valid, zero real content), not a layer-
    # attribution error in the usual sense. Flagged explicitly in the report,
    # not silently folded into ordinary tag-accuracy statistics.
    ("q119", 0): Verdict(False, "synthesis", False, "DEGENERATE OUTPUT: claim text is literally the string 'verse', no actual content. Not a real verse-layer claim to judge; scored as a synthesis-layer failure by default (no content is attributable to any real source)."),
    ("q119", 1): Verdict(False, "synthesis", False, "DEGENERATE OUTPUT: claim text is literally the string 'commentary', no actual content. Same as above."),
    ("q119", 2): Verdict(True, "synthesis", False, "DEGENERATE OUTPUT: claim text is literally the string 'synthesis'. Coincidentally tag-consistent with the default bucket, but this is a broken generation, not a correct synthesis claim."),

    # q120 corpus_anomaly -- retrieval failed (gold 26.17/Dhp400 not retrieved;
    # retrieved 13.10/8.9/17.3).
    ("q120", 0): Verdict(False, "synthesis", False,
        "Asserts the wrong story (8.9) has a header-line typo confusing verse 177 with 110 -- neither of which is the real anomaly (26.17 confusing 40 with 400). A constructed, incorrect inference; tagged 'commentary', should be 'synthesis'."),

    # q111-q115 cross_recension -- all 5 gold stories retrieved correctly.
    # These are the direct payoff of the mid-Phase-5 prompt.py fix (CST4/
    # title_pali/burlingame_title now rendered in the [COMMENTARY] block,
    # previously omitted): every one of these 5 claims correctly and
    # accurately states the real CST4 title (verified against
    # data/eval/build_gold_set.py's own hand-recorded CST4 notes).
    ("q111", 0): Verdict(True, "commentary", False, "Correct CST4 title ('Sariputtattheravatthu'), directly restating the now-rendered cst4_title field. Correctly tagged 'commentary'."),
    ("q112", 0): Verdict(True, "commentary", False, "Correct CST4 title ('Samavativatthu, the Story about Samavati'), directly restating the cst4_title field even though phrased as a full sentence -- provenance, not sentence form, decides the layer. Correctly tagged 'commentary'."),
    ("q113", 0): Verdict(True, "commentary", False, "Correct CST4 title ('Maghavatthu, the Story about Magha'). Correctly tagged 'commentary'."),
    ("q114", 0): Verdict(True, "commentary", False, "Correct CST4 title ('Cittagahapativatthu'). Correctly tagged 'commentary'."),
    ("q115", 0): Verdict(True, "commentary", False, "Correct CST4 title ('Ayuvaddhanakumaravatthu, the Story about the Youth whose Lifespan Increased'). Correctly tagged 'commentary'."),

    # q001 doctrinal -- gold 1.8 retrieved correctly.
    ("q001", 0): Verdict(True, "verse", False, "Paraphrase of verse 11 itself, correctly tagged 'verse'."),
    ("q001", 1): Verdict(False, "verse", False,
        "Restates verse 11's own meaning again ('fail to understand what is truly important... wrong thoughts') in different words -- not the Sariputta/Moggallana narrative at all. Tagged 'commentary'; should be 'verse' (under-attribution, not conflation -- the reverse direction)."),

    # q007 doctrinal -- gold 7.9 retrieved correctly.
    ("q007", 0): Verdict(True, "verse", False, "Paraphrase of verse 98, correctly tagged 'verse'."),
    ("q007", 1): Verdict(True, "commentary", False, "Genuine narrative content (Elder Revata's story), correctly tagged 'commentary'."),

    # q013 doctrinal -- gold 13.1 retrieved correctly.
    ("q013", 0): Verdict(True, "verse", False, "Paraphrase of verse 167, correctly tagged 'verse'."),
    ("q013", 1): Verdict(True, "commentary", False, "Genuine narrative content matching the synopsis (the young bhikkhu insulted by Visakha's granddaughter), correctly tagged 'commentary'."),

    # q019 doctrinal -- gold 19.2 retrieved correctly.
    ("q019", 0): Verdict(True, "verse", False, "Paraphrase of verse 258's first half, correctly tagged 'verse'."),
    ("q019", 1): Verdict(False, "verse", False,
        "Paraphrases verse 258's own second half ('secure, free of enmity and fear... astute') -- not the Group-of-Six narrative at all. Tagged 'commentary'; should be 'verse' (under-attribution)."),

    # q025 doctrinal -- gold 25.6 retrieved correctly.
    ("q025", 0): Verdict(True, "verse", False, "Paraphrase of verse 367, correctly tagged 'verse'."),
    ("q025", 1): Verdict(True, "commentary", False, "Genuine narrative content (the Brahmin Pancaggadayaka), correctly tagged 'commentary'."),

    # q061 narrative -- gold 1.11 retrieved correctly. The one genuine
    # anachronistic-conflation instance in this sample.
    ("q061", 0): Verdict(False, "commentary", True,
        "Narrative detail (Dhammika's illness, 'vital forces began to decay') is pure vatthu content -- verse 16 is about rejoicing in good deeds, unrelated. Tagged 'verse'. Textbook anachronistic conflation."),
    ("q061", 1): Verdict(True, "commentary", False, "Genuine narrative content (chanting, celestial chariots), correctly tagged 'commentary'."),

    # q067 narrative -- gold 7.4 retrieved correctly. Same claim content as
    # the Phase 4 (pre-fix) pass's q067, which was mistagged 'verse' then;
    # now correctly tagged 'commentary'.
    ("q067", 0): Verdict(True, "commentary", False, "Narrative detail (seeking robes on refuse-heaps), correctly tagged 'commentary' -- this exact claim was mistagged 'verse' (a conflation instance) in the pre-fix Phase 4 sample."),

    # q073 narrative -- gold 13.10 retrieved correctly.
    ("q073", 0): Verdict(True, "commentary", False, "Narrative detail on the scale of the Gifts-beyond-Compare ceremony, correctly tagged 'commentary'."),
    ("q073", 1): Verdict(True, "commentary", False, "Narrative detail on the tradition's frequency, correctly tagged 'commentary'."),

    # q079 narrative -- gold 19.4 retrieved correctly.
    ("q079", 0): Verdict(True, "commentary", False, "Narrative content (the thirty bhikkhus, the Buddha's question), correctly tagged 'commentary'."),

    # q085 narrative -- gold 25.11 retrieved correctly. All 7 claims correct;
    # the strongest single result in this sample.
    ("q085", 0): Verdict(True, "verse", False, "Paraphrase of verse 381, correctly tagged 'verse'."),
    ("q085", 1): Verdict(True, "commentary", False, "Narrative content (Vakkali's background), correctly tagged 'commentary'."),
    ("q085", 2): Verdict(True, "commentary", False, "Narrative content (seeing the Buddha, going forth), correctly tagged 'commentary'."),
    ("q085", 3): Verdict(True, "commentary", False, "Narrative content (gazing at the Buddha, neglecting practice), correctly tagged 'commentary'."),
    ("q085", 4): Verdict(True, "commentary", False, "Narrative content (the Buddha's admonition), correctly tagged 'commentary'."),
    ("q085", 5): Verdict(True, "commentary", False, "Narrative content (Vakkali's continued attachment), correctly tagged 'commentary'."),
    ("q085", 6): Verdict(True, "commentary", False, "Narrative content (the Buddha's decision to act), correctly tagged 'commentary'."),

    # q031 philological -- gold 1.1 retrieved (top-2; top-1 is 1.2).
    ("q031", 0): Verdict(True, "verse", False, "Verbatim verse 1 quote, correctly tagged 'verse'."),
    ("q031", 1): Verdict(True, "verse", False, "Verbatim verse 1 continuation, correctly tagged 'verse'."),
    ("q031", 2): Verdict(True, "commentary", False, "Nidana-style framing (where/with reference to whom), correctly tagged 'commentary'. (Does not engage the actual philological nuance asked -- a relevance/completeness gap, not a tag error; interlinear_notes still isn't in the generation prompt.)"),

    # q037 philological -- gold 7.1 retrieved correctly.
    ("q037", 0): Verdict(True, "verse", False, "Paraphrase of verse 90, correctly tagged 'verse'."),
    ("q037", 1): Verdict(True, "commentary", False, "Narrative content (Devadatta's rock), correctly tagged 'commentary'."),
    ("q037", 2): Verdict(True, "synthesis", False, "Honest inference ('the narrative does not explicitly state what the knots are, but...') -- correctly tagged 'synthesis', and appropriately hedged rather than fabricating the four ganthas the interlinear_notes (not in context) would supply."),

    # q043 philological -- gold 14.1 retrieved correctly.
    ("q043", 0): Verdict(True, "verse", False, "Verbatim verse 179 quote, correctly tagged 'verse'."),
    ("q043", 1): Verdict(True, "commentary", False, "Nidana-style content (spoken to Magandiya), correctly tagged 'commentary'. Still doesn't address the apadam/padani wordplay itself -- relevance gap, not a tag error."),

    # q049 philological -- gold 20.8 retrieved correctly (fixed since Phase 4,
    # where retrieval failed for this exact question).
    ("q049", 0): Verdict(True, "verse", False, "Verbatim verse 283 quote, correctly tagged 'verse'."),
    ("q049", 1): Verdict(False, "verse", False,
        "Paraphrases verse 284's own content ('vine... mind remains trapped, like a calf suckling its mother') -- not narrative/vatthu content. Tagged 'commentary'; should be 'verse' (under-attribution)."),
    ("q049", 2): Verdict(True, "synthesis", False,
        "'The forest of lust, hatred, and delusion' -- matches the actual philological gloss (interlinear_notes: 'ragadikilesavanam') despite that note not being in this prompt's context; a genuine correct inference (or partial parametric knowledge), not a restatement of shown text. Correctly tagged 'synthesis'."),

    # q055 philological -- gold 26.1 retrieved correctly.
    ("q055", 0): Verdict(True, "commentary", False, "Narrative content (Brahmin Pasadabahula), correctly tagged 'commentary'."),
    ("q055", 1): Verdict(True, "verse", False, "Paraphrase of verse 383, correctly tagged 'verse'."),
}
