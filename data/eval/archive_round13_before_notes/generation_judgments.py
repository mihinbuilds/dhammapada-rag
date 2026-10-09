"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" -- no
IAA is claimed for these judgments.

ROUND 13 RE-JUDGE (2026-10-08), FROM SCRATCH. Made against a fresh
generation run after the SuttaCentral texts were removed: the verse layer,
the [VERSE] prompt block and the PALI SUPPORT rule now carry Ānandajoti's
interlinear Pali and English only, and the index is the 5,486-chunk rebuild.
Same 27-question systematic sample, same seed, same model
(qwen2.5:7b-instruct, num_ctx 16384). Annotator: Claude Opus 5.5. The
previous run and its judgments are archived in
data/eval/archive_round12_with_suttacentral/.

Every claim was checked against the FULL stored nidana/synopsis/vatthu/
desanavasane in data/processed/stories.jsonl and the verse's interlinear
text and notes in data/processed/verses.jsonl, not an excerpt.

FINDINGS THIS PASS
- Recurring failures recurred. Commentary content tagged 'verse'
  (anachronistic conflation) on q019#1 (the 8.3 vatthu's "robbers that are
  his own pollutants" presented as Dhp 103's teaching), q067#0 and q079#0
  (story sentences with the verse's Pali attached) -- all three seen in
  earlier rounds. q043#1 merges the daughters of Māra with the Brahmin
  Māgandiya again. q119/q120 (retrieval failures) again assert fabricated
  corpus anomalies; q120 now invents a "405" header for 26.21, which reads
  "Dhp 404".
- Fixed relative to the previous run: q093#1 now says "fifty" bhikkhus, as
  the nidana and synopsis do; q037#1 no longer misattributes who spoke to
  whom; q055#0 now glosses akata as Nibbāna, matching the verse's note.
- New: q001 retrieved the gold story (1.8, Dhp 11) at rank 1, but the model
  marked it not_relevant and answered from Dhp 347 instead, then linked the
  two in a false synthesis claim (#1). A generation-side misjudgment, not a
  retrieval failure.
- New: q013#1 is Dhp 109's verse text (from retrieved 8.8) cited to story
  17.5 / Dhp 225 and tagged 'commentary'. Content accurate, citation and
  tag wrong. VERSE_TEXT_AS_COMMENTARY could not fire, because it compares
  against the cited verse's own text (225), not the verse actually quoted.
- Context gap, not a model error: the four knots asked about in q037 are
  listed only in the interlinear note on Dhp 90, and the generation prompt
  never includes interlinear notes. q037#0's "not explicitly stated in the
  verse or commentary" is therefore accurate. The same gap bears on every
  philological question whose answer lives in a note (q043, q055).

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
        "The Story about the Brahmin Aggidatta explains Dhp 188-192 together -- matches 14.6's dhp_verses, correctly tagged."),
    ("q091", 1): Verdict(True, "commentary", False, True,
        "Aggidatta taught refuge in mountains, forests, groves and trees; the Buddha taught refuge in the Triple Gem -- matches vatthu and synopsis, correctly tagged."),

    # q093 alignment -- gold 6.11, retrieved rank-1.
    ("q093", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 87, 88, 89) match 6.11, correctly tagged."),
    ("q093", 1): Verdict(True, "commentary", False, True,
        "Fifty bhikkhus, Rains in Kosala, visited the Buddha in Sāvatthī -- matches nidana and synopsis. The previous run said 'five hundred', following the title; this one follows the narrative."),

    # q095 alignment -- gold 22.9, retrieved rank-1.
    ("q095", 0): Verdict(True, "alignment", False, True,
        "Title and range (Dhp 318, 319) match 22.9, correctly tagged."),
    ("q095", 1): Verdict(True, "commentary", False, True,
        "Children of sectarians forbidden to enter the monastery, taught by the Buddha -- matches synopsis/vatthu, correctly tagged."),

    # q097 alignment -- gold 25.5, retrieved rank-1. CITATION_IN_TEXT on 0.
    ("q097", 0): Verdict(True, "alignment", False, True,
        "'group_id 25.5 covers Dhp 365, 366 (2 verses)' -- prompt scaffolding copied verbatim (CITATION_IN_TEXT), but the fact is correct and correctly tagged."),
    ("q097", 1): Verdict(False, "alignment", False, True,
        "'The Story about a Treacherous Bhikkhu explains Dhp 365 and 366 together' -- the same alignment fact as claim 0, restated under 'synthesis'. The duplicate-under-wrong-tag pattern again, this time as synthesis rather than commentary."),
    ("q097", 2): Verdict(True, "commentary", False, True,
        "Veḷuvana; a bhikkhu stayed with Devadatta's faction for the offerings, returned, and was reproved -- matches nidana/synopsis/vatthu, correctly tagged."),

    # q099 alignment -- gold 14.5, retrieved rank-1.
    ("q099", 0): Verdict(False, "alignment", False, True,
        "Title and range (Dhp 186, 187) match 14.5, but tagged 'synthesis' -- it is an alignment fact."),
    ("q099", 1): Verdict(True, "commentary", False, True,
        "Inheritance of a hundred coins, thinking of returning to lay life, the Buddha showing that wealth never satisfies -- matches synopsis and vatthu (the pebble count and the Mandhātā story), correctly tagged."),

    # q119 corpus_anomaly -- gold 26.34/verse 416; retrieval WRONG
    # (6.10/11.8/3.5), as in every prior round. CITATION_IN_TEXT on 0.
    ("q119", 0): Verdict(True, "alignment", False, False,
        "'The verse in question is Dhp 85 and 86' -- asserts the two-story anomaly for 6.10, which has one story (the answer is Dhp 416, stories 26.33/26.34). Retrieval-failure-driven, same as the previous run."),
    ("q119", 1): Verdict(True, "commentary", False, False,
        "The street-residents narrative matches 6.10's synopsis, but 'the second story attached to Dhp 85 and 86' invents a second story that does not exist."),

    # q120 corpus_anomaly -- gold 26.17/verse 400; retrieval WRONG
    # (13.4/14.2/26.21).
    ("q120", 0): Verdict(False, "alignment", False, False,
        "Claims 26.21's header misstates its verse as 405, correct 404. The raw source header reads 'Dhp 404' (dhammapada-attakatha.txt l.41523) -- no typo; the actual one is 26.17's 'Dhp 40' for 400. A fabricated corpus-structure fact (alignment), tagged 'synthesis'."),
    ("q120", 1): Verdict(True, "commentary", False, True,
        "Matches 26.21's nidana (Jetavana, Pabbhāravāsī Tissa, 'Tissa Who Dwelt in a Mountain Cave'), correctly tagged -- for the wrong story."),

    # q111-q115 cross_recension (cst4_title_variant). All five titles checked
    # against stories.jsonl cst4_title; judged 'commentary' per the rubric-
    # continuity note in the docstring.
    ("q111", 0): Verdict(True, "commentary", False, True, "CST4 title 'Sāriputtattheravatthu' matches 1.8, correctly tagged."),
    ("q112", 0): Verdict(True, "commentary", False, True, "CST4 title 'Sāmāvatīvatthu' matches 2.1, correctly tagged."),
    ("q113", 0): Verdict(True, "commentary", False, True, "CST4 title 'Maghavatthu, the Story about Magha' matches 2.7, correctly tagged."),
    ("q114", 0): Verdict(True, "commentary", False, True, "CST4 title 'Cittagahapativatthu' matches 5.14, correctly tagged."),
    ("q115", 0): Verdict(True, "commentary", False, True, "CST4 title 'Āyuvaḍḍhanakumāravatthu' matches 8.8, correctly tagged."),

    # q001 doctrinal -- gold 1.8 retrieved at rank 1, but the model marked it
    # not_relevant and answered from 24.5 (Dhp 347).
    ("q001", 0): Verdict(True, "verse", False, True,
        "Dhp 347 near-verbatim, exact pali_support, correctly tagged -- but the question is answered by Dhp 11 (1.8, retrieved and dismissed)."),
    ("q001", 1): Verdict(True, "synthesis", False, False,
        "Says Dhp 347's spider-web image illustrates mistaking the inessential for the essential. Dhp 347 is about being impassioned by passion; the inessential/essential teaching is Dhp 11-12. A false link between two verses."),
    ("q001", 2): Verdict(True, "commentary", False, True,
        "Veḷuvana, Queen Khemā intoxicated with her beauty, the decaying image, Arahatship at the end -- matches 24.5's synopsis and desanavasane, correctly tagged."),

    # q007 doctrinal -- gold 7.9, retrieved rank-1.
    ("q007", 0): Verdict(True, "verse", False, True,
        "Dhp 98 verbatim (interlinear English), exact pali_support, correctly tagged."),
    ("q007", 1): Verdict(True, "commentary", False, True,
        "Jetavana, Elder Khadiravaniya Revata -- matches nidana, correctly tagged."),

    # q013 doctrinal -- gold 13.1 NOT retrieved (retrieved 17.5/7.1/8.8).
    ("q013", 0): Verdict(True, "synthesis", False, True,
        "'Does not explicitly advise against ... any specific four things in the verses provided' -- true of the retrieved context (Dhp 167 was not retrieved), correctly tagged."),
    ("q013", 1): Verdict(False, "verse", False, True,
        "The four things that increase (life, beauty, happiness, strength) are Dhp 109's own words (8.8, retrieved), presented as what the story of Dhp 225 (17.5) explains and tagged 'commentary'. Content accurate to Dhp 109; citation and tag wrong. Also leaks group_id/verse_number (CITATION_IN_TEXT)."),

    # q019 doctrinal -- gold 19.2 NOT retrieved (retrieved 19.3/1.8/8.3).
    ("q019", 0): Verdict(True, "verse", False, True,
        "Dhp 259 near-verbatim, exact pali_support, correctly tagged -- the neighbour verse; the question's verse is Dhp 258, not retrieved."),
    ("q019", 1): Verdict(False, "commentary", True, True,
        "'One who defeats the robbers that are his own pollutants is truly victorious' -- the Buddha's speech in the 8.3 vatthu, tagged 'verse' with Dhp 103's Pali attached. Anachronistic conflation, recurring from the previous run. The content is in the source, so faithful=True."),
    ("q019", 2): Verdict(True, "commentary", False, False,
        "Kuṇḍalakesī did throw the robber over the cliff and go forth under Sāriputta's influence, but she did not become an Arahat 'through mastering the thousand views': she mastered them as a wanderer, before Sāriputta defeated her; Arahatship came after her going forth among the bhikkhunīs."),

    # q025 doctrinal -- gold 25.6, retrieved rank-3.
    ("q025", 0): Verdict(True, "verse", False, True,
        "Dhp 367 verbatim (interlinear English), exact pali_support, correctly tagged."),
    ("q025", 1): Verdict(False, "alignment", False, True,
        "'The story about the Brahmin Pañcaggadāyaka explains the verse Dhp 367' -- a title-plus-verse fact (alignment), tagged 'commentary'. Accurate."),

    # q061 narrative -- gold 1.11, retrieved rank-1.
    ("q061", 0): Verdict(True, "commentary", False, True,
        "Dhammika asked for the Mindfulness discourse; the bhikkhus took his 'wait' as meant for them -- matches synopsis, correctly tagged."),

    # q067 narrative -- gold 7.4, retrieved rank-1.
    ("q067", 0): Verdict(False, "commentary", True, True,
        "'The Buddha and the bhikkhus gathered round to help make a robe' -- the synopsis's first sentence, tagged 'verse' with Dhp 93's full Pali attached. Conflation on this question in every round."),
    ("q067", 1): Verdict(True, "commentary", False, True,
        "Robes worn out, seeking cloth on refuse-heaps -- matches vatthu, correctly tagged."),

    # q073 narrative -- gold 13.10, retrieved rank-1.
    ("q073", 0): Verdict(True, "commentary", False, False,
        "'140 million of treasure ... in a single day' is verbatim and 'once ... for all the Buddhas' follows 'this happens once to all the Buddhas'. But 'the king outdoing the citizens in a series of increasingly lavish offerings' reverses the vatthu: for six rounds neither could outdo the other, and the king prevailed only through Queen Mallikā's plan. Partial misrepresentation -> faithful=False (borderline)."),

    # q079 narrative -- gold 19.4, retrieved rank-1.
    ("q079", 0): Verdict(False, "commentary", True, True,
        "'Went to wait upon the Buddha; as he was leaving, thirty forest bhikkhus saw him' -- vatthu narrative tagged 'verse' with Dhp 260's Pali attached. Conflation, recurring."),
    ("q079", 1): Verdict(True, "commentary", False, True,
        "The bhikkhus sat down; the Buddha, seeing them ripe for Arahatship, asked about an elder; they saw only a novice -- matches vatthu, correctly tagged."),

    # q085 narrative -- gold 25.11, retrieved rank-1.
    ("q085", 0): Verdict(True, "verse", False, True,
        "Dhp 381 paraphrased accurately (much happiness, attaining peace, stilling of conditions), correctly tagged."),
    ("q085", 1): Verdict(True, "commentary", False, True,
        "Obsessed with the Buddha's body, gave up meditation to gaze at him -- matches synopsis, correctly tagged."),

    # q031 philological -- gold 1.1, retrieved rank-2.
    ("q031", 0): Verdict(True, "verse", False, True,
        "'Thoughts and actions are fundamentally shaped by the state of one's mind' -- consistent with the verse's wording and full exact pali_support, correctly tagged. It does not reach the note's ethical reading (the quality of mind bringing suitable returns) and leans descriptive, but does not contradict the verse."),
    ("q031", 1): Verdict(True, "commentary", False, True,
        "Sāvatthī, Elder Cakkhupāla -- matches 1.1 (whose nidana uses the source's opening-story format: 'Where was this Dhamma teaching given? At Sāvatthī'). The purpose clause is interpretive."),

    # q037 philological -- gold 7.1, retrieved rank-1. CITATION_IN_TEXT on 1.
    ("q037", 0): Verdict(True, "synthesis", False, True,
        "'Not explicitly stated in the verse or commentary' -- accurate: neither Dhp 90 nor 7.1's narrative lists them. The four knots are in the interlinear note only, which the generation prompt does not include. Correctly tagged."),
    ("q037", 1): Verdict(True, "commentary", False, True,
        "Given in response to Jīvaka's question after Devadatta's rock injured the Buddha's foot -- matches nidana/synopsis/vatthu, correctly tagged. The previous run's Ānanda misattribution did not recur. Leaks group_id/verse_number (CITATION_IN_TEXT)."),

    # q043 philological -- gold 14.1, retrieved rank-1. PALI_QUOTE_TRUNCATED
    # (26% of Dhp 180) on 0.
    ("q043", 0): Verdict(True, "verse", False, True,
        "'apadaṁ' = the pathless one, 'padena' = the path or way of leading -- restates the verse's own translation, correctly tagged. Does not reach the note's wordplay (padāni = the states of craving), but does not contradict it."),
    ("q043", 1): Verdict(True, "commentary", False, False,
        "'Spoken by the Buddha to Māgandiya's daughters' -- the verse was spoken about the daughters of MĀRA and repeated to the Brahmin MĀGANDIYA (nidana). The same semantic-neighbour conflation as rounds 7 and 12."),

    # q049 philological -- gold 20.8, retrieved rank-1.
    ("q049", 0): Verdict(True, "commentary", False, True,
        "'The forest of lust, hatred, and delusion' -- verbatim from the Buddha's speech in the 20.8 vatthu, correctly tagged."),

    # q055 philological -- gold 26.1, retrieved rank-1. PALI_QUOTE_TRUNCATED
    # (23%) on 0.
    ("q055", 0): Verdict(True, "verse", False, True,
        "'akataññūsi' refers to the unconditioned, Nibbāna -- restates the verse's own words ('the destruction of the conditioned ... that which is not made') and matches the interlinear note ('What is not made is Nibbāna'), which the prompt does not carry. Judged 'verse' as a restatement of the verse; the previous run's claim said 'Arahatship' and was judged unfaithful."),
    ("q055", 1): Verdict(True, "commentary", False, True,
        "Jetavana, Brahmin Pasādabahula, urged to strive for Arahatship -- matches nidana and synopsis, correctly tagged."),
}
