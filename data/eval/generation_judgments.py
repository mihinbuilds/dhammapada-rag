"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" -- no
IAA is claimed for these judgments.

ROUND 8 RE-JUDGE, FROM SCRATCH. Re-made against the round-8 generation run
(CLAUDE_CODE_BRIEF_ROUND8.md, Tasks Z/AA applied: source_disposition,
the separate [ALIGNMENT] prompt block), same 27-question systematic sample,
same seed. Retrieval is unchanged from round 7 (retrieved_group_ids are
identical, question-by-question, confirmed directly) -- only generation
changed, so claim content had to be re-read against source, not assumed
comparable to round 7's judgments.

ROUND 8, TASK AA -- ALIGNMENT RECALL MEASURED. Round 7 found alignment
precision 1.000 / recall 0.500 (4/8 "explains X and Y together" claims
tagged 'alignment', the other 4 still 'commentary'). This round: all 7 of
the core verse-grouping/corpus-structure claims (q091, q093, q095, q097,
q099, q119, q120) are tagged 'alignment' -- recall 1.000 on that set. Two
NEW misses appeared instead, of a different shape: q095 and q097 each
produce the SAME alignment fact a second time, once correctly (claim 0,
tagged 'alignment') and once redundantly under the wrong tag (q095#1
'synthesis', q097#1 'commentary') -- not a missed tag, a duplicated one.
See docs/generation.md's Round 8 section for the full account, including
why cross_recension title-only claims (q111-115) are NOT folded into the
'alignment' gold label here despite Task AA's prompt block also carrying
title data -- kept consistent with round 7's rubric so alignment recall
means the same thing in both rounds; see the note on q111 below.

ROUND 8 FINDING -- A LIVE, UNPROMPTED CONFIRMATION OF SEMANTIC-NEIGHBOUR
CONFLATION (Task AC). q099#1 names the discontented bhikkhu of story 14.5
"Aggidatta" -- but 14.5's own source never names him, and "Aggidatta" is
the protagonist of the ADJACENT retrieved story 14.6 (also in this
question's own bundle, disposition 'not_relevant'). The name migrated from
a retrieved-but-dismissed neighbor into a claim about a different,
unnamed-in-source figure. This is the same failure class as q043's Māra's-
daughters/Māgandiyā conflation (Round 7) and confirms Task AC's prediction
that these errors cluster around structurally-or-lexically adjacent
figures -- found in ordinary judging of this round's sample, not by the
Task AC live probe (see docs/generation.md, which also reports that probe's
own -- negative -- result on a deliberately constructed Tissa/Tissa pair).

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
'commentary' by form even where not independently verifiable against the
~800-character vatthu excerpt available for judging (out of rubric scope,
see eval_rubric.md). A claim that only restates the cited verse's own
content, adding no narrative/occasion/philological fact beyond it, is
judged 'verse' regardless of its "the commentary/Buddha taught..." framing
-- sentence-wrapping alone does not make verse content commentary, the same
principle the rubric already applies to alignment facts and CST4 titles.
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
        "Full range (Dhp 188-192) matches gold_verse_numbers exactly, correctly tagged 'alignment'."),
    ("q091", 1): Verdict(True, "commentary", False, True,
        "Occasion narrative (Aggidatta, chaplain to Pasenadi) matches vatthu; second half paraphrases the verses' own refuge teaching in the same sentence -- commentary by form, not flagged mechanically (same pattern as round 7)."),

    # q093 alignment -- gold 6.11, retrieved rank-1. group_id leaked into
    # claim 0's text (CITATION_IN_TEXT, structural, not a layer/fidelity issue).
    ("q093", 0): Verdict(True, "alignment", False, True,
        "Full range (Dhp 87, 88, 89) matches gold_verse_numbers, correctly tagged 'alignment' -- a miss in round 7, a hit here."),
    ("q093", 1): Verdict(True, "commentary", False, True,
        "Matches nidana/vatthu (Jetavana, fifty visiting bhikkhus who passed the rains in Kosala), correctly tagged."),

    # q095 alignment -- gold 22.9, retrieved rank-1.
    ("q095", 0): Verdict(True, "alignment", False, True,
        "'group_id 22.9 covers Dhp 318, 319 (2 verses)' -- full range matches gold, correctly tagged."),
    ("q095", 1): Verdict(False, "alignment", False, True,
        "Restates the IDENTICAL fact as claim 0 ('The Story about the Sectarian Disciples explains both Dhp 318 and Dhp 319') -- same alignment content, produced a second time under a different (wrong) tag. Not a missed alignment claim; a duplicated one, tagged 'synthesis' instead of 'alignment'. Title matches gold_context ('The Story about the Sectarian Disciples'); the fact itself is correct."),
    ("q095", 2): Verdict(True, "commentary", False, True,
        "Matches nidana (sectarian disciples' children) plus a gloss of the verses' own right-view/wrong-view content in the same sentence -- commentary by form, correctly tagged."),

    # q097 alignment -- gold 25.5, retrieved rank-1.
    ("q097", 0): Verdict(True, "alignment", False, True,
        "'group_id 25.5 covers Dhp 365, 366 (2 verses)' -- full range matches gold, correctly tagged."),
    ("q097", 1): Verdict(False, "alignment", False, True,
        "'The Story about a Treacherous Bhikkhu explains both Dhp 365 and Dhp 366' -- the same alignment fact as claim 0, restated a second time under 'commentary' instead. Same duplicate-under-wrong-tag pattern as q095#1. Title and range both correct."),

    # q099 alignment -- gold 14.5, retrieved rank-1 (also retrieved 14.6,
    # not_relevant per source_disposition). Claim 0 carries CITATION_IN_TEXT
    # (structural).
    ("q099", 0): Verdict(True, "alignment", False, True,
        "Full range (Dhp 186, 187) matches gold_verse_numbers, correctly tagged 'alignment'."),
    ("q099", 1): Verdict(True, "commentary", False, False,
        "Names the discontented bhikkhu 'Aggidatta' -- but story 14.5's own source (nidana/vatthu) never names him ('a certain discontented bhikkhu'). 'Aggidatta' is the protagonist of the ADJACENT retrieved story 14.6 (also in this bundle, marked source_disposition='not_relevant'), retrieved because both stories are about verses 186-192's surrounding cluster. The name migrated from a retrieved-but-dismissed neighbor into a claim about a different, unnamed figure -- a live, unprompted instance of the semantic-neighbour conflation pattern named in docs/eval_rubric.md (Task AC), not the Task AC live probe's own (negative) result. Rest of the claim (inheritance, considering lay life) matches the actual vatthu."),

    # q119 corpus_anomaly -- gold 26.34/verse 416; retrieval WRONG
    # (6.10/11.8/14.1, none match) -- same retrieval failure as every prior round.
    ("q119", 0): Verdict(True, "alignment", False, True,
        "'group_id 6.10 covers Dhp 85, 86 (2 verses), titled...' -- accurate about the (wrongly) retrieved group 6.10, correctly tagged 'alignment'. Answers the wrong story due to retrieval failure, not a layer or fidelity error on its own terms."),
    ("q119", 1): Verdict(True, "commentary", False, True,
        "Opens with the literal prompt label 'Opening:' copied verbatim from the [COMMENTARY] block's own nidana rendering -- a new label-leak pattern _LABEL_PREFIXES does not yet cover (that list catches 'commentary:' etc., not the descriptive field labels 'Opening:'/'Narrative:'/'Close:' used inside the block). Content past the label matches group 6.10's actual nidana. Flagged as a finding for a future round, not scored as a layer error since the label doesn't name a layer or citation field."),
    ("q119", 2): Verdict(True, "commentary", False, True,
        "Same label-leak pattern ('Close:' copied from the desanavasane rendering); content matches group 6.10's actual close. Same finding as claim 1."),

    # q120 corpus_anomaly -- gold 26.17/verse 400; retrieval WRONG
    # (13.4/14.2/26.21, none match). Both claims carry CITATION_IN_TEXT (structural).
    ("q120", 0): Verdict(True, "alignment", False, False,
        "Asserts group 13.4's header misstates its verse number and the correct one is Dhp 171 -- a corpus-anomaly/parsing claim, correctly tagged 'alignment' under Task T's taxonomy (a fact about editorial/parsing structure). Not independently confirmed against parse_report.json, answers the wrong story (gold is 26.17/400, an unrelated anomaly) due to retrieval failure -- most plausibly a retrieval-failure-driven fabrication, same conclusion as round 7's analogous claim."),
    ("q120", 1): Verdict(True, "commentary", False, True,
        "Matches group 13.4's nidana/synopsis (Veḷuvana, Prince Abhaya, dancing girl's death), correctly tagged even though it answers the wrong (retrieval-failure-driven) story."),

    # q111-q115 cross_recension (cst4_title_variant). NOTE ON RUBRIC
    # CONTINUITY: Task AA's [ALIGNMENT] block now renders title variants
    # alongside verse-range data, which could argue for reclassifying these
    # as 'alignment' -- deliberately NOT done here, so that "alignment
    # recall" measures the same thing in round 7 and round 8 (the original
    # 7-8 verse-grouping/corpus-structure claims), rather than silently
    # changing what the metric counts. q113's own claim below, which the
    # MODEL tagged 'alignment' this round, is scored against that same
    # unchanged rubric -- see its note.
    ("q111", 0): Verdict(True, "commentary", False, True, "CST4 title restatement (Sāriputta), correctly tagged."),
    ("q112", 0): Verdict(True, "commentary", False, True, "CST4 title restatement (Sāmāvatī), correctly tagged."),
    ("q113", 0): Verdict(False, "commentary", False, True,
        "CST4 title restatement (Magha) only -- no verse-range statement, so judged 'commentary' per this file's rubric-continuity note above, not 'alignment'. The model tagged it 'alignment' this round (round 7's analogous claim was tagged 'commentary') -- a minor over-generalization of the new tag to a bare title fact, worth watching but not counted as a hit for alignment recall. Title itself is accurate."),
    ("q113", 1): Verdict(True, "commentary", False, True,
        "Matches synopsis (Sakka was human Magha in a past life, good deeds led to his status), correctly tagged."),
    ("q114", 0): Verdict(True, "commentary", False, True, "CST4 title restatement (Citta), correctly tagged."),
    ("q115", 0): Verdict(True, "commentary", False, True, "CST4 title restatement (Āyuvaḍḍhana), correctly tagged."),

    # q001 doctrinal -- gold 1.8, retrieved rank-1.
    ("q001", 0): Verdict(True, "verse", False, True, "Matches Dhp 11 closely, correctly tagged, valid pali_support."),
    ("q001", 1): Verdict(True, "commentary", False, True,
        "'Chief Disciples of Sañjaya' -- accurate this round (Sāriputta/Moggallāna were literally Sañjaya's disciples before converting), unlike round 7's version of this claim which misattributed Sañjaya's own refusal to the Chief Disciples themselves. That specific inversion did not recur here."),

    # q007 doctrinal -- gold 7.9, retrieved rank-1 (also 26.29, 7.10).
    ("q007", 0): Verdict(True, "verse", False, True, "Matches Dhp 98 closely, correctly tagged."),
    ("q007", 1): Verdict(True, "verse", False, True,
        "Matches Dhp 99's content ('free of greed will delight there, not those who seek sensual pleasures'), correctly tagged. pali_support is corrupted ('Vītarāgāni' for 'Vītarāgā') -- PALI_QUOTE_NOT_IN_SOURCE already flags this structurally; the claim's English content is faithful regardless."),
    ("q007", 2): Verdict(False, "verse", False, True,
        "'The story of Dhp 98 explains that the place is delightful wherever Arahats live' restates the verse's own content, tagged 'commentary' -- VERSE_TEXT_AS_COMMENTARY fired on this claim. Content accurate; layer wrong. Wrong direction for is_conflation's narrow definition."),

    # q013 doctrinal -- gold 13.1, retrieved rank-1.
    ("q013", 0): Verdict(True, "verse", False, True, "Matches Dhp 167, correctly tagged."),
    ("q013", 1): Verdict(True, "commentary", False, True, "Matches vatthu (young bhikkhu, Visākhā's granddaughter's laugh), correctly tagged."),

    # q019 doctrinal -- gold 19.2, retrieved (rank-2, present).
    ("q019", 0): Verdict(True, "verse", False, True, "Matches Dhp 258, correctly tagged."),
    ("q019", 1): Verdict(False, "verse", False, True,
        "'The Buddha taught that a wise person is patient and free from hatred and fear, not just someone who speaks much' restates the verse's own content with a 'the Buddha taught' frame, adding no occasion or narrative fact (contrast round 7's version of this claim, which correctly named the Group of Six) -- tagged 'commentary', judged 'verse'. Content accurate."),

    # q025 doctrinal -- gold 25.6, retrieved rank-1.
    ("q025", 0): Verdict(True, "verse", False, True, "Matches Dhp 367 verbatim, correctly tagged."),
    ("q025", 1): Verdict(True, "commentary", False, True, "Matches synopsis (Brahmin Pañcaggadāyaka, first-fruits), correctly tagged."),

    # q061 narrative -- gold 1.11, retrieved rank-1. Only one claim this
    # round (down from 3) -- the recurring anachronistic-conflation instance
    # for this exact question, present in every prior round's sample, did
    # NOT reproduce this run (no verse claim at all was produced).
    ("q061", 0): Verdict(True, "commentary", False, True,
        "Matches vatthu (Dhammika's request for bhikkhus, celestial chariots, 'Wait! Wait!'), correctly tagged. No verse claim in this answer at all -- the round-over-round-recurring conflation for this question is absent this run, not fixed by any Round 8 task and not evidence it won't recur."),

    # q067 narrative -- gold 7.4, retrieved rank-1. Same question_id and
    # same specific conflation as every prior round, unchanged.
    ("q067", 0): Verdict(False, "commentary", True, True,
        "'The Buddha and the bhikkhus gathered round to help make a robe for Elder Anuruddha' is vatthu/synopsis content, not Dhp 93's verse text (about ended defilements) -- tagged 'verse'. The same conflation instance documented in every prior round's write-up for this exact question, recurring unchanged again."),
    ("q067", 1): Verdict(True, "commentary", False, True, "Matches vatthu (worn-out robes, refuse-heaps), correctly tagged."),

    # q073 narrative -- gold 13.10, retrieved rank-1.
    ("q073", 0): Verdict(True, "commentary", False, True,
        "Matches synopsis (king/citizens competing in generosity); 'once in a lifetime' framing not independently checkable against the 800-char excerpt -- faithful=True unverified."),
    ("q073", 1): Verdict(True, "commentary", False, True,
        "Traditional detail (occurs once per Buddha, arranged by a woman) not checkable against the visible excerpt -- commentary-shaped by form, faithful=True unverified."),

    # q079 narrative -- gold 19.4, retrieved rank-1.
    ("q079", 0): Verdict(True, "commentary", False, True, "Matches vatthu (waiting on the Teacher, thirty forest bhikkhus), correctly tagged."),

    # q085 narrative -- gold 25.11, retrieved rank-1.
    ("q085", 0): Verdict(True, "synthesis", False, False,
        "'The Dhammapada does not explicitly state why the Buddha sent Elder Vakkali away' -- directly contradicted by the model's own claim 1 in the same answer (which does state the reason, matching the corpus synopsis) and by the synopsis itself. Correctly tagged 'synthesis' as a framing-type claim, but false -- an internal-consistency failure structural checks cannot catch (nothing compares one claim's assertion against another's)."),
    ("q085", 1): Verdict(True, "commentary", False, True,
        "Matches synopsis exactly (obsessed with the Buddha's body, gave up meditation), correctly tagged -- and directly contradicts claim 0's 'not stated' framing."),

    # q031 philological -- gold 1.1, retrieved (present, not rank-1).
    ("q031", 0): Verdict(True, "verse", False, True, "Paraphrases Dhp 1's content, correctly tagged per the paraphrase-as-verse rule."),
    ("q031", 1): Verdict(True, "synthesis", False, True,
        "'One should cultivate wholesome intentions to avoid suffering' -- actually engages the question's own ethical-reading framing this round (contrast round 7's version, which didn't), correctly tagged synthesis."),
    ("q031", 2): Verdict(True, "commentary", False, True, "Matches nidana/synopsis (Cakkhupāla, at all costs even his eyes), correctly tagged."),

    # q037 philological -- gold 7.1, retrieved rank-1.
    ("q037", 0): Verdict(False, "verse", False, True,
        "Restates Dhp 90's own content ('abandoned all the knots... released on all sides') without the specific philological gloss the question asks for (the four ganthas: abhijjhā/byāpāda/sīlabbataparāmāsa/idaṃsaccābhinivesa, absent from the visible Jīvaka/Devadatta vatthu excerpt) -- tagged 'commentary', judged 'verse' since it adds no narrative or philological fact beyond the verse's own wording. Not contradictory, so faithful=True."),

    # q043 philological -- gold 14.1, retrieved rank-1.
    ("q043", 0): Verdict(True, "commentary", False, True,
        "Word-gloss (apadaṁ = trackless, kena padena = by what track) matching Dhp 180's actual wordplay, commentary-shaped by form per round 7's identical precedent for this question. Notably, the Māra's-daughters/Māgandiyā conflation from round 7's version of this claim did NOT recur -- this run produced only this one claim, with no narrative/occasion content to conflate at all."),

    # q049 philological -- gold 20.8, retrieved rank-1.
    ("q049", 0): Verdict(True, "commentary", False, True,
        "'The forest of lust, hatred, and delusion' -- extremely terse (a sentence fragment, not a full claim), but matches the classic kilesa-vana commentarial gloss, same as every prior round for this question. faithful=True unverified (not checkable against the visible excerpt)."),

    # q055 philological -- gold 26.1, retrieved rank-1.
    ("q055", 0): Verdict(True, "commentary", False, False,
        "Discusses 'akataññūsi' (= 'ungrateful') again instead of 'akata' (= 'not made/unconditioned'), the term the question actually asks about -- the same term-substitution confusion as round 7's identical claim for this question, recurring unchanged."),
}
