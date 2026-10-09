"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" -- no
IAA is claimed for these judgments.

ROUND 14 RE-JUDGE (2026-10-08), FROM SCRATCH. Made against a fresh
generation run after the fifth layer, `note`, was added: Ānandajoti
Bhikkhu's interlinear notes now reach the prompt in their own [NOTES] block,
and a claim drawn from one is tagged `note` (docs/eval_rubric.md, "The fifth
layer"). Same 27-question systematic sample, seed, model
(qwen2.5:7b-instruct, num_ctx 16384) and index as Round 13. Annotator:
Claude Opus 5.5. The Round 13 run and its judgments are archived in
data/eval/archive_round13_before_notes/.

Every claim was checked against the FULL stored nidana/synopsis/vatthu/
desanavasane in data/processed/stories.jsonl and the verse's interlinear
text and notes in data/processed/verses.jsonl, not an excerpt.

FINDINGS THIS PASS
- The note layer works where the answer is in a note. q037 (the four knots)
  and q055 (akata = Nibbāna) are each answered by a correctly tagged,
  verbatim-faithful `note` claim. In Round 13 the model could not see either
  note.
- Note content is also misattributed, in both directions the new layer
  exists to catch: q043#0 gives the note's gloss (padāni = the states of
  craving) as what the verse says, and q013#1 and q043#1 present note content
  as "the commentary". Without the fifth layer these would have been
  invisible -- the content is accurate to the note, so they would have
  scored as correct verse/commentary claims.
- Semantic-neighbour merges: q019 renders Dhp 259's "Dhamma-bearer" as
  "astute", the word the question took from Dhp 258 (not retrieved); q031#2
  credits Dhp 2's "wholesome mind leads to happiness" to the Cakkhupāla
  story, which only illustrates Dhp 1.
- Recurring: conflation on q067#0 and q079#0 (story sentences tagged 'verse'
  with the verse's Pali attached); fabricated anomalies on q119 and q120
  (retrieval failures); q001 again dismisses the retrieved gold story 1.8
  and links Dhp 347 to the question with a false synthesis claim.
- New: q113 gives a CST4 title that does not exist ("The Story about Magha's
  Questions"; CST4 is "Maghavatthu"). Every earlier round got this right.
- Alignment facts again tagged other than 'alignment' (q091, q097#1, q099#0,
  q119#0), and one CST4 title tagged 'alignment' (q114#0).

REQUIRED JUDGMENT SHAPE (per aggregate_generation.py):
    tag_correct: bool    predicted layer (the claim's own `layer` field)
                          matches gold_layer
    gold_layer:  str     "verse" | "commentary" | "alignment" | "note" |
                          "synthesis" -- what the claim's content actually
                          is, independent of what it was tagged
    is_conflation: bool  gold_layer == "commentary" and predicted == "verse"
                          (the narrow, named failure: presenting Buddhaghosa's
                          gloss as the plain sense of the verse)
    faithful: bool       does the claim's content accurately represent the
                          source text it is grounded in, independent of
                          whether it was tagged/cited to the *right* source?

Judging rule used throughout: gold_layer is decided by where the claim's
content is actually sourced from, not by sentence form. A claim asserting a
relationship the source text does not itself state ("story X explains
verses Y and Z together", or a corpus-structure/anomaly fact) is
'alignment'. A claim framed as explaining commentary content is judged
'commentary' by form. A claim that only restates the cited verse's own
content, adding no narrative/occasion/philological fact beyond it, is
judged 'verse' regardless of its "the commentary/Buddha taught..." framing.
Content from a verse's interlinear notes is 'note' (Round 14). CST4 title
restatements stay 'commentary' (round 8's rubric-continuity note), so
alignment recall means the same thing across rounds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    tag_correct: bool
    gold_layer: str
    is_conflation: bool
    faithful: bool
    note: str


JUDGMENTS: dict[tuple[str, int], Verdict] = {
    # q091 alignment -- gold 14.6, retrieved rank-1.
    ("q091", 0): Verdict(False, "alignment", False, True,
        "'The story of Aggidatta ... explains Dhp 188 through 192 together' -- an alignment fact (with a correct nidana detail), tagged 'commentary'."),

    # q093 alignment -- gold 6.11, retrieved rank-1.
    ("q093", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 87, 88, 89) match 6.11, correctly tagged."),
    ("q093", 1): Verdict(True, "commentary", False, True,
        "Jetavana, bhikkhus after the Rains Retreat in Kosala -- matches nidana/synopsis, correctly tagged."),

    # q095 alignment -- gold 22.9, retrieved rank-1.
    ("q095", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 318, 319) match 22.9, correctly tagged."),
    ("q095", 1): Verdict(True, "commentary", False, True,
        "Children of sectarians forbidden to enter the monastery, taught by the Buddha -- matches synopsis/vatthu, correctly tagged."),

    # q097 alignment -- gold 25.5, retrieved rank-1. CITATION_IN_TEXT on 0, 1.
    ("q097", 0): Verdict(True, "alignment", False, True,
        "'group_id 25.5 covers Dhp 365, 366 (2 verses)' -- scaffolding copied (CITATION_IN_TEXT), fact correct, correctly tagged."),
    ("q097", 1): Verdict(False, "alignment", False, True,
        "The same alignment fact restated under 'commentary', again leaking group_id."),

    # q099 alignment -- gold 14.5, retrieved rank-1.
    ("q099", 0): Verdict(False, "alignment", False, True,
        "Title and range (Dhp 186, 187) match 14.5, tagged 'synthesis' -- an alignment fact."),
    ("q099", 1): Verdict(True, "verse", False, True,
        "Dhp 186 verbatim (interlinear English, with the prompt's 'Dhp 186 --' prefix), exact pali_support, correctly tagged."),
    ("q099", 2): Verdict(True, "verse", False, True,
        "Dhp 187's second half verbatim -- accurate; its pali_support covers half the verse (PALI_QUOTE_TRUNCATED), as the claim does."),
    ("q099", 3): Verdict(True, "commentary", False, True,
        "Jetavana, inheritance of a hundred coins, thought of returning to lay life -- matches nidana/synopsis, correctly tagged."),

    # q119 corpus_anomaly -- gold 26.34/verse 416; retrieval WRONG
    # (6.10/11.8/3.5), as in every prior round.
    ("q119", 0): Verdict(False, "alignment", False, False,
        "Asserts Dhp 85-86 have two commentarial stories -- a false corpus-structure fact (the answer is Dhp 416), tagged 'verse' with Dhp 85's Pali attached. Retrieval-failure-driven."),
    ("q119", 1): Verdict(True, "commentary", False, False,
        "The street-residents narrative matches 6.10's synopsis, but 'the second story' invents a second story that does not exist."),

    # q120 corpus_anomaly -- gold 26.17/verse 400; retrieval WRONG
    # (13.4/14.2/26.21).
    ("q120", 0): Verdict(True, "alignment", False, False,
        "Claims 26.21's header is 'incorrectly labeled'; its header reads 'Dhp 404', the verse it quotes. A fabricated anomaly (the real one is 26.17's 'Dhp 40' for 400), correctly tagged 'alignment'."),
    ("q120", 1): Verdict(True, "commentary", False, True,
        "Jetavana, Pabbhāravāsī Tissa, the deity in the rock cave -- matches 26.21's nidana/synopsis, correctly tagged, for the wrong story."),

    # q111-q115 cross_recension (cst4_title_variant). Titles checked against
    # stories.jsonl cst4_title; judged 'commentary' per the rubric-continuity
    # note in the docstring.
    ("q111", 0): Verdict(True, "commentary", False, True, "CST4 title 'Sāriputtattheravatthu' matches 1.8, correctly tagged."),
    ("q112", 0): Verdict(True, "commentary", False, True,
        "CST4 title 'Sāmāvatīvatthu' matches 2.1, correctly tagged; Sāmāvatī and Māgandiyā are both queens in that story."),
    ("q113", 0): Verdict(True, "commentary", False, False,
        "Gives the CST4 title as 'The Story about Magha's Questions'. 2.7's cst4_title is 'Maghavatthu, the Story about Magha' -- the answer invents a title by blending the two editions'. Correct in every earlier round."),
    ("q114", 0): Verdict(False, "commentary", False, True,
        "CST4 title 'Cittagahapativatthu' matches 5.14 -- correct, but tagged 'alignment'; CST4 titles are judged 'commentary' (rubric continuity)."),
    ("q114", 1): Verdict(True, "commentary", False, False,
        "Jetavana is right, but the nidana says the verses were given 'with reference to the Elder Sudhamma', not the householder Citta."),
    ("q115", 0): Verdict(True, "commentary", False, True, "CST4 title 'Āyuvaḍḍhanakumāravatthu' matches 8.8, correctly tagged."),

    # q001 doctrinal -- gold 1.8 retrieved at rank 1, marked not_relevant
    # again; answered from 24.5 (Dhp 347).
    ("q001", 0): Verdict(True, "verse", False, True,
        "Dhp 347 verbatim, exact pali_support, correctly tagged -- but the question is answered by Dhp 11 (1.8, retrieved and dismissed)."),
    ("q001", 1): Verdict(True, "synthesis", False, False,
        "Says Dhp 347's spider-web image describes those who mistake the inessential for the essential. Dhp 347 is about passion; the inessential/essential teaching is Dhp 11-12. False link, as in Round 13."),
    ("q001", 2): Verdict(True, "commentary", False, True,
        "Queen Khemā, intoxicated with her beauty, the image of a woman's decay, Stream-entry -- matches the 24.5 vatthu (Stream-entry at the first verse; Arahatship came later, at Dhp 347). Correctly tagged."),

    # q007 doctrinal -- gold 7.9, retrieved rank-1.
    ("q007", 0): Verdict(True, "verse", False, True,
        "Dhp 98 closely paraphrased, exact pali_support, correctly tagged."),
    ("q007", 1): Verdict(True, "commentary", False, True,
        "Jetavana, Elder Khadiravaniya Revata -- matches nidana, correctly tagged."),

    # q013 doctrinal -- gold 13.1 NOT retrieved (retrieved 17.5/7.1/8.8).
    ("q013", 0): Verdict(True, "synthesis", False, False,
        "'The Dhammapada does not explicitly advise against ... four things in a single verse' -- false of the Dhammapada (Dhp 167 does exactly that; it was not retrieved). Round 13's version limited itself to 'the verses provided'."),
    ("q013", 1): Verdict(False, "note", False, False,
        "The four knots are listed in the interlinear note on Dhp 90, not in the commentary; the claim says 'the commentary ... explains' and calls them 'khandha' (they are gantha). Note content misattributed to Buddhaghosa, with a wrong term."),

    # q019 doctrinal -- gold 19.2 NOT retrieved (retrieved 19.3/1.8/8.3).
    ("q019", 0): Verdict(True, "verse", False, False,
        "Cites Dhp 259 but says 'speaking much is not what makes one astute'. Dhp 259 is about a Dhamma-bearer; 'not wise merely by speaking much' is Dhp 258 (not retrieved), whose word the question used. Two neighbouring verses merged."),
    ("q019", 1): Verdict(False, "verse", False, False,
        "Dhp 259's own content (hears a little, sees the Dhamma) tagged 'commentary', with the same 'astute' substitution."),

    # q025 doctrinal -- gold 25.6, retrieved rank-3.
    ("q025", 0): Verdict(True, "verse", False, True,
        "Dhp 367 verbatim, exact pali_support, correctly tagged."),
    ("q025", 1): Verdict(True, "commentary", False, True,
        "A Brahmin who gave the first fruits of his harvest before eating -- matches 25.6's synopsis, correctly tagged."),

    # q061 narrative -- gold 1.11, retrieved rank-1.
    ("q061", 0): Verdict(True, "commentary", False, True,
        "Dhammika asked for the Mindfulness discourse; the bhikkhus took his words as meant for them -- matches synopsis, correctly tagged."),

    # q067 narrative -- gold 7.4, retrieved rank-1.
    ("q067", 0): Verdict(False, "commentary", True, True,
        "The synopsis's first sentence, tagged 'verse' with Dhp 93's Pali attached. Conflation on this question in every round."),
    ("q067", 1): Verdict(True, "commentary", False, True,
        "Robes worn out, seeking cloth on refuse-heaps -- matches vatthu, correctly tagged."),

    # q073 narrative -- gold 13.10, retrieved rank-1.
    ("q073", 0): Verdict(True, "commentary", False, True,
        "A series of offerings growing in scale, culminating in perfumes, fans and water-lilies -- all in the vatthu. Incomplete: it never says how often such gifts occur, nor that no later donor could equal them, but nothing stated is false."),

    # q079 narrative -- gold 19.4, retrieved rank-1.
    ("q079", 0): Verdict(False, "commentary", True, True,
        "'Went to wait upon the Teacher' -- vatthu narrative tagged 'verse' with Dhp 260's Pali attached. Conflation, recurring."),
    ("q079", 1): Verdict(True, "commentary", False, True,
        "'As he was leaving, thirty forest bhikkhus saw him' -- verbatim vatthu, correctly tagged."),

    # q085 narrative -- gold 25.11, retrieved rank-1.
    ("q085", 0): Verdict(False, "commentary", False, True,
        "Attached to the Buddha's body, neglecting meditation -- the synopsis, tagged 'synthesis'. Content accurate."),
    ("q085", 1): Verdict(True, "commentary", False, True,
        "Sent away for the three months of the Rains so that a shock would bring him to understand -- matches the vatthu, correctly tagged."),
    ("q085", 2): Verdict(True, "commentary", False, True,
        "The Buddha sent forth a radiant image, joy arose, Vakkali attained Arahatship -- in the vatthu, though compressed: Arahatship came after the verses, as he suppressed that joy. Correctly tagged."),

    # q031 philological -- gold 1.1, retrieved rank-2.
    ("q031", 0): Verdict(True, "verse", False, True,
        "'The quality of one's mind determines the quality of one's actions and their consequences' -- the ethical reading the note gives, and consistent with the verse; full exact pali_support. Correctly tagged."),
    ("q031", 1): Verdict(True, "synthesis", False, True,
        "'One should cultivate a wholesome mind' -- an inference from the verse, correctly tagged."),
    ("q031", 2): Verdict(True, "commentary", False, False,
        "Credits the Cakkhupāla story with teaching that a wholesome mind leads to happiness. That is Dhp 2 and its own story (1.2); 1.1 illustrates only the base mind and suffering. Neighbouring-story merge."),

    # q037 philological -- gold 7.1, retrieved rank-1. CITATION_IN_TEXT on 1.
    ("q037", 0): Verdict(True, "note", False, True,
        "The four knots, verbatim from the interlinear note on Dhp 90, tagged 'note'. Unanswerable in Round 13, when the note was not in the prompt."),
    ("q037", 1): Verdict(True, "commentary", False, False,
        "'The Buddha healing Jīvaka after Jīvaka had applied medicine to the Buddha's foot' reverses who healed whom; Jīvaka's worry about the dressing is right. Also leaks group_id (CITATION_IN_TEXT)."),

    # q043 philological -- gold 14.1, retrieved rank-1. PALI_QUOTE_TRUNCATED
    # (26%) on 0.
    ("q043", 0): Verdict(False, "note", False, True,
        "'padāni refers to the states of craving' and 'apadaṁ' as the state beyond them -- the interlinear note's gloss, accurately, but tagged 'verse'. The verse itself does not say this."),
    ("q043", 1): Verdict(False, "note", False, False,
        "Presents the note's gloss as 'the commentary explains', and adds that Māra's daughters 'are padāni', which neither the note nor the 14.1 vatthu says."),
    ("q043", 2): Verdict(True, "synthesis", False, True,
        "Contrasting the Buddha's freedom with the daughters' craving is a fair inference: in the vatthu the daughters are named Taṇhā (craving), Aratī and Ragā. Correctly tagged."),

    # q049 philological -- gold 20.8, retrieved rank-1.
    ("q049", 0): Verdict(True, "commentary", False, True,
        "'The forest of lust, hatred, and delusion' -- verbatim from the Buddha's speech in the 20.8 vatthu, correctly tagged."),

    # q055 philological -- gold 26.1, retrieved rank-1. CITATION_IN_TEXT on 1.
    ("q055", 0): Verdict(True, "note", False, True,
        "'akata refers to Nibbāna' -- the interlinear note on Dhp 383 ('What is not made is Nibbāna'), correctly tagged 'note'."),
    ("q055", 1): Verdict(True, "commentary", False, True,
        "Pasādabahula invited bhikkhus and addressed them as Arahats, which displeased them -- matches synopsis, correctly tagged. Leaks group_id/verse_number (CITATION_IN_TEXT)."),
}
