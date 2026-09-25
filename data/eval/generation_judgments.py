"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" -- no
IAA is claimed for these judgments.

POST-CLEANING RE-JUDGE (2026-09-23), FROM SCRATCH. Re-made against the
generation run on the September 2026 cleaned corpus and re-embedded index
(5,909 chunks), same 27-question systematic sample, same seed, same model
(qwen2.5:7b-instruct, num_ctx 16384). Annotator for this pass: Claude Opus
5.5 (the round-8 judgments this file replaces were made by Claude Sonnet 5;
they remain in git history at 2a20bfd). Retrieval changed for exactly one
sampled question: q019 lost its gold group 19.2 (rank 2 -> 27 in the
retrieval eval), so its answer is about Dhp 259/103, not Dhp 258.

Unlike earlier rounds, every claim was checked against the FULL stored
nidana/synopsis/vatthu/desanavasane and the verse's interlinear notes in
data/processed/, not the ~800-char excerpt -- several "faithful=True
unverified" calls from round 8 (q049, q073) are now verified, and three
claims (q037#1, q043#1, q055#0) are judged unfaithful on text that sits
outside that excerpt.

FINDINGS THIS PASS
- Semantic-neighbour conflation recurred on q043#1: the verse is said to be
  spoken "to Māgandiya's daughters", merging the daughters of MĀRA (the
  original occasion) with the Brahmin MĀGANDIYA (to whom it was repeated) --
  the same conflation as round 7's q043, absent in round 8, back again.
  The q099 Aggidatta name-migration from round 8 did NOT recur.
- Anachronistic conflation (commentary content tagged 'verse') on four
  claims: q067#0 (recurring every round), q073#0, q079#0, and q019#1. The
  q067/q073/q079 claims all attach a real, correct pali_support of the verse
  to a sentence that narrates the story -- the Pali quote makes the claim
  look verse-grounded while its text is vatthu. q019#1 presents the
  commentary's gloss ("robbers that are his own pollutants", from the
  Buddha's speech in the 8.3 vatthu) as what "the Dhammapada states".
- Retrieval-failure answers (q119, q120) now assert the anomaly outright for
  the wrong story ("the verse in question is Dhp 85, 86"; 26.21's header
  "incorrectly titled 403") rather than describing the retrieved group
  neutrally as in round 8 -- judged unfaithful. 26.21's header in
  data/raw/dhammapada-attakatha.txt reads "Dhp 404" (l.41523); the real
  typo is 26.17's "Dhp 40" (l.41344).
- Source inconsistency, not a model error: story 6.11 is titled "Five
  Hundred Visiting Bhikkhus" (CST4 Pañcasata-) but its nidana and synopsis
  say "fifty". q093#1's "five hundred" is supported by the title.

REQUIRED JUDGMENT SHAPE (per aggregate_generation.py):
    tag_correct: bool    predicted layer (the claim's own `layer` field)
                          matches gold_layer
    gold_layer:  str     "verse" | "commentary" | "alignment" | "synthesis"
                          -- what the claim's content actually is,
                          independent of what it was tagged
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
judged 'verse' regardless of its "the commentary/Buddha taught..." framing
-- sentence-wrapping alone does not make verse content commentary, the same
principle the rubric already applies to alignment facts and CST4 titles.
CST4 title restatements stay 'commentary' (round 8's rubric-continuity
note), so alignment recall means the same thing across rounds.
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
    ("q091", 0): Verdict(True, "alignment", False, True,
        "Story of Aggidatta explains Dhp 188-192 together -- matches 14.6's dhp_verses, correctly tagged."),
    ("q091", 1): Verdict(True, "commentary", False, True,
        "Matches nidana (Jetavana, Aggidatta, Brahmin chaplain of the King of Kosala) and vatthu (went forth as an ascetic), correctly tagged."),

    # q093 alignment -- gold 6.11, retrieved rank-1.
    ("q093", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 87, 88, 89) match 6.11, correctly tagged."),
    ("q093", 1): Verdict(True, "commentary", False, True,
        "Jetavana, bhikkhus who passed the Rains in Kosala -- matches nidana/synopsis. 'Five hundred' follows the story's own title (CST4 Pañcasata-); the nidana and synopsis say 'fifty'. A source inconsistency, not a model error."),

    # q095 alignment -- gold 22.9, retrieved rank-1.
    ("q095", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 318, 319) match 22.9, correctly tagged. The round-8 duplicate-under-wrong-tag claim did not recur."),
    ("q095", 1): Verdict(True, "commentary", False, True,
        "Children of sectarians forbidden to enter the monastery -- matches synopsis/vatthu, correctly tagged."),

    # q097 alignment -- gold 25.5, retrieved rank-1. Claim 0 carries
    # CITATION_IN_TEXT (structural, not a layer/fidelity issue).
    ("q097", 0): Verdict(True, "alignment", False, True,
        "'group_id 25.5 covers Dhp 365, 366 (2 verses)' -- prompt scaffolding copied verbatim (CITATION_IN_TEXT), but the fact is correct and correctly tagged."),
    ("q097", 1): Verdict(False, "alignment", False, True,
        "'The Story about a Treacherous Bhikkhu explains Dhp 365 and 366 together' -- the same alignment fact as claim 0, restated under 'commentary'. Same duplicate-under-wrong-tag pattern as round 8's q095#1/q097#1, recurring here."),

    # q099 alignment -- gold 14.5, retrieved rank-1 (14.6 also retrieved,
    # not_relevant).
    ("q099", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 186, 187) match 14.5, correctly tagged."),
    ("q099", 1): Verdict(True, "commentary", False, True,
        "Matches nidana/synopsis (Jetavana, discontented bhikkhu, inheritance, thought of returning to lay life). The round-8 'Aggidatta' name migration from neighbour 14.6 did NOT recur -- the bhikkhu is left unnamed, as in the source."),

    # q119 corpus_anomaly -- gold 26.34/verse 416; retrieval WRONG
    # (6.10/11.8/3.5), as in every prior round.
    ("q119", 0): Verdict(True, "alignment", False, False,
        "'The verse in question is Dhp 85, 86' -- asserts the two-story anomaly for 6.10, which has one story (the answer is Dhp 416, stories 26.33/26.34). Title and range of 6.10 are accurate, but the claim answers the question with a false corpus-structure fact. Retrieval-failure-driven; round 8's version described 6.10 neutrally and was judged faithful."),
    ("q119", 1): Verdict(True, "commentary", False, False,
        "The residents-of-a-street narrative matches 6.10's synopsis, but framing it as 'the second story attached to Dhp 85, 86' invents a second story that does not exist."),

    # q120 corpus_anomaly -- gold 26.17/verse 400; retrieval WRONG
    # (13.4/14.2/26.21).
    ("q120", 0): Verdict(True, "alignment", False, False,
        "Claims 26.21's header misstates its verse as 403. The raw source header reads 'Dhp 404' (dhammapada-attakatha.txt l.41523) -- no typo there; the actual one is 26.17's 'Dhp 40' for 400. A fabricated anomaly, correctly tagged 'alignment' (corpus-structure fact)."),
    ("q120", 1): Verdict(True, "commentary", False, True,
        "Matches 26.21's nidana (Jetavana, Pabbhāravāsī Tissa, 'Tissa Who Dwelt in a Mountain Cave'), correctly tagged -- for the wrong story."),

    # q111-q115 cross_recension (cst4_title_variant). All five titles checked
    # against stories.jsonl cst4_title; judged 'commentary' per the rubric-
    # continuity note in the docstring.
    ("q111", 0): Verdict(True, "commentary", False, True, "CST4 title 'Sāriputtattheravatthu' matches 1.8, correctly tagged."),
    ("q112", 0): Verdict(True, "commentary", False, True, "CST4 title 'Sāmāvatīvatthu' matches 2.1, correctly tagged."),
    ("q113", 0): Verdict(True, "commentary", False, True,
        "CST4 title 'Maghavatthu, the Story about Magha' matches 2.7. Tagged 'commentary' this time (round 8 tagged the same fact 'alignment')."),
    ("q114", 0): Verdict(True, "commentary", False, True, "CST4 title 'Cittagahapativatthu' matches 5.14, correctly tagged."),
    ("q115", 0): Verdict(True, "commentary", False, True, "CST4 title 'Āyuvaḍḍhanakumāravatthu' matches 8.8, correctly tagged."),

    # q001 doctrinal -- gold 1.8, retrieved rank-1.
    ("q001", 0): Verdict(True, "verse", False, True, "Paraphrases Dhp 11, exact pali_support, correctly tagged."),
    ("q001", 1): Verdict(False, "alignment", False, True,
        "'The story ... is titled The Story about the Chief Disciples and covers Dhp 11 and 12' -- a title-plus-verse-range fact, i.e. alignment content, tagged 'commentary'. Accurate."),

    # q007 doctrinal -- gold 7.9, retrieved rank-1.
    ("q007", 0): Verdict(True, "verse", False, True,
        "Dhp 98 near-verbatim, correctly tagged. pali_support is the interlinear edition's orthography (PALI_QUOTE_ORTHOGRAPHIC_VARIANT, warning) -- not a fabrication."),
    ("q007", 1): Verdict(True, "commentary", False, True,
        "Jetavana, Elder Khadiravaniya Revata -- matches nidana, correctly tagged. Round 8's VERSE_TEXT_AS_COMMENTARY on this question did not recur."),

    # q013 doctrinal -- gold 13.1, retrieved rank-1.
    ("q013", 0): Verdict(True, "verse", False, True, "Dhp 167's four things, exact pali_support, correctly tagged."),
    ("q013", 1): Verdict(True, "commentary", False, True,
        "Visākhā's granddaughter called the young bhikkhu a 'cut-head' -- matches vatthu/synopsis, correctly tagged."),

    # q019 doctrinal -- gold 19.2 NOT retrieved this run (retrieved
    # 19.3/1.8/8.3); see docstring. The answer never reaches Dhp 258.
    ("q019", 0): Verdict(True, "verse", False, True,
        "Dhp 259 (Dhamma-bearer, not by speaking much) paraphrased accurately and correctly tagged -- but it is the neighbour verse; the question's 'astute' is Dhp 258, not retrieved."),
    ("q019", 1): Verdict(False, "commentary", True, True,
        "'The Dhammapada also states that one who defeats the robbers that are his own pollutants is the true victor' -- Dhp 103 speaks of conquering oneself; 'the robbers that are his own pollutants' is the Buddha's speech in the 8.3 vatthu, just before the verses. Commentary gloss presented as the verse's own statement -- anachronistic conflation. The content is in the source, so faithful=True."),
    ("q019", 2): Verdict(True, "commentary", False, True,
        "Kuṇḍalakesī killed her husband, joined the wanderers, converted by Sāriputta with a simple teaching -- matches 8.3's synopsis, correctly tagged."),

    # q025 doctrinal -- gold 25.6, retrieved rank-1.
    ("q025", 0): Verdict(True, "verse", False, True, "Dhp 367 closely paraphrased, exact pali_support, correctly tagged."),
    ("q025", 1): Verdict(True, "commentary", False, True,
        "Brahmin Pañcaggadāyaka, Jetavana -- matches nidana, correctly tagged."),

    # q061 narrative -- gold 1.11, retrieved rank-1.
    ("q061", 0): Verdict(True, "commentary", False, True,
        "Dhammika asked for the Mindfulness discourse; the bhikkhus took his 'Wait! Wait!' as meant for them -- matches vatthu/synopsis, correctly tagged. No verse claim this run either."),

    # q067 narrative -- gold 7.4, retrieved rank-1. PALI_QUOTE_TRUNCATED
    # (32% of Dhp 93) on claim 0.
    ("q067", 0): Verdict(False, "commentary", True, True,
        "Worn-out robes, refuse-heaps -- vatthu content, tagged 'verse' with a half-quote of Dhp 93 attached. The same conflation on this question as in every prior round; the Pali quote now makes the story sentence look verse-grounded."),
    ("q067", 1): Verdict(True, "commentary", False, True,
        "Robe-making for Anuruddha at Veḷuvana -- matches nidana/synopsis, correctly tagged."),

    # q073 narrative -- gold 13.10, retrieved rank-1.
    ("q073", 0): Verdict(False, "commentary", True, False,
        "Vatthu content tagged 'verse' with Dhp 177's Pali attached -- conflation. '140 million of treasure in a single day' is verbatim, but 'no one could say this or that is lacking' describes the CITIZENS' competing offerings in the vatthu, not the king's gifts; what made the king's gifts 'beyond compare' is that no later donor could equal them. Partial misattribution -> faithful=False (borderline)."),
    ("q073", 1): Verdict(True, "commentary", False, True,
        "'Once to all the Buddhas, and a woman always manages this' -- verbatim from the vatthu (unverified in round 8, verified here). Correctly tagged."),

    # q079 narrative -- gold 19.4, retrieved rank-1.
    ("q079", 0): Verdict(False, "commentary", True, True,
        "Near-verbatim synopsis (young-looking dwarf, thirty bhikkhus, 'did you see an elder') tagged 'verse' with Dhp 260's Pali attached -- conflation. Content accurate."),
    ("q079", 1): Verdict(True, "commentary", False, True,
        "'We saw a certain novice' and the Buddha's reply -- matches vatthu; the eldership gloss is the Buddha's speech there. Correctly tagged."),

    # q085 narrative -- gold 25.11, retrieved rank-1.
    ("q085", 0): Verdict(True, "commentary", False, True,
        "Obsessed with the Buddha's body, neglected meditation -- matches synopsis, correctly tagged. Round 8's self-contradicting 'not explicitly stated' synthesis claim did not recur."),
    ("q085", 1): Verdict(True, "commentary", False, True,
        "'Unless this bhikkhu receives a shock, he will never come to understand' -- the vatthu's own words, correctly tagged."),
    ("q085", 2): Verdict(True, "commentary", False, True,
        "Sent away at the Rains, the Buddha appeared to him, he attained Arahatship -- matches synopsis and vatthu, correctly tagged."),

    # q031 philological -- gold 1.1, retrieved (rank-2). PALI_QUOTE_TRUNCATED
    # (34% of Dhp 1) on claim 0.
    ("q031", 0): Verdict(True, "verse", False, True,
        "Ethical paraphrase of Dhp 1 (intentions shape actions and consequences), correctly tagged. The pali_support is only the first two pādas -- a genuine partial quote, correctly flagged by PALI_QUOTE_TRUNCATED."),
    ("q031", 1): Verdict(True, "commentary", False, True,
        "Sāvatthī, Elder Cakkhupāla -- matches nidana, correctly tagged; the 'to emphasize intentions' clause is interpretive but not contradicted."),

    # q037 philological -- gold 7.1, retrieved rank-1. CITATION_IN_TEXT on
    # claim 1.
    ("q037", 0): Verdict(False, "verse", False, False,
        "Lists the knots as 'sorrow, the fetters ..., physical and emotional suffering' -- items lifted from Dhp 90's own wording (grieves not, released on all sides, no fever) and misread as the knot list. The verse's interlinear note gives the four ganthas (abhijjhā, byāpāda, sīlabbataparāmāsa, idaṁsaccābhinivesa); none is named. Content derives from the verse, tagged 'synthesis'; unfaithful."),
    ("q037", 1): Verdict(True, "commentary", False, False,
        "Jīvaka, the foot wound, returning late -- matches vatthu, but 'spoken by the Buddha to Elder Ānanda in response to a question from Jīvaka' is wrong: the Buddha only told Ānanda to remove the bandage; the verse answered Jīvaka's own question (nidana). Also leaks 'group_id 7.1' (CITATION_IN_TEXT)."),

    # q043 philological -- gold 14.1, retrieved rank-1. PALI_QUOTE_TRUNCATED
    # (26% of Dhp 180) on claim 0.
    ("q043", 0): Verdict(True, "verse", False, True,
        "'apadaṁ' = the pathless one, 'kena padena' = by what track -- restates the verse's own translation, so 'verse', correctly tagged. Does not reach the note's actual wordplay (padāni = the states of craving by which the one beyond them could be led), but does not contradict it."),
    ("q043", 1): Verdict(True, "commentary", False, False,
        "'Spoken by the Buddha to Māgandiya's daughters, who were trying to tempt the Buddha' -- the verse was originally spoken about the daughters of MĀRA and repeated to the Brahmin MĀGANDIYA (nidana). The two figures are merged -- the same semantic-neighbour conflation as round 7's q043, recurring after its absence in round 8."),

    # q049 philological -- gold 20.8, retrieved rank-1.
    ("q049", 0): Verdict(True, "commentary", False, True,
        "'The forest of lust, hatred, and delusion' -- a sentence fragment, but verbatim from the 20.8 vatthu (and the note's 'rāgādikilesavanaṁ'). Verified this round (round 8: unverified)."),

    # q055 philological -- gold 26.1, retrieved rank-1.
    ("q055", 0): Verdict(True, "commentary", False, False,
        "Glosses 'akataññūsi' correctly ('know that which is not made') -- round 8's term substitution is fixed -- but says it refers to Arahatship. The verse note says 'What is not made is Nibbāna'; Arahatship appears in the vatthu as the goal of the exhortation, not as the referent of akata."),
}
