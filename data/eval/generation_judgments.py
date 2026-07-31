"""Single-annotator (Claude) judgments of every claim in generation_raw.jsonl
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria. See docs/eval_rubric.md "Annotator status" --
no IAA is claimed for these judgments.

Each entry: (question_id, claim_index) -> verdict. `tag_correct` = does the
claim's layer tag match where its content actually originates (checked
against gold_context in generation_raw.jsonl, and where relevant against the
full corpus directly, e.g. q097 below). `is_conflation` = the narrow
DhammapadaRAG.txt definition: a claim tagged "verse" whose content is
actually commentary. `note` records the reasoning, particularly for
non-obvious calls, so the judgment is auditable, not just asserted.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    tag_correct: bool
    is_conflation: bool
    note: str


JUDGMENTS: dict[tuple[str, int], Verdict] = {
    # q001 -- both claims are verse-11/12 content (paraphrase of "essential/
    # inessential" and, separately, verse-256/257 content) but tagged/cited
    # inconsistently with their own content.
    ("q001", 0): Verdict(False, False, "Paraphrases Dhp11 (gold verse) but tagged synthesis and cited to v=256 (wrong verse, from a different retrieved bundle). Should be 'verse'."),
    ("q001", 1): Verdict(False, False, "Paraphrases Dhp256/257 verse content ('astute... judges without haste') but tagged 'commentary'. Should be 'verse'."),
    ("q007", 0): Verdict(False, False, "Direct paraphrase of Dhp376 verse text (spiritual friends passage) tagged 'synthesis'. Should be 'verse'. (Also ignores the actual gold verse, Dhp98 -- a relevance failure, not scored here.)"),
    ("q013", 0): Verdict(True, False, "Accurate paraphrase of gold verse 167, correctly tagged 'verse'. Citation malformed ('group_13.1' vs '13.1') but points to the right story."),
    ("q013", 1): Verdict(False, False, "Restates the same verse's four items as a list; still verse content, tagged 'synthesis'. Should be 'verse'."),
    ("q019", 0): Verdict(True, False, "Accurate paraphrase of gold verse 258, correctly tagged 'verse'. No citation at all (structural warning)."),
    ("q019", 1): Verdict(False, False, "Second half of the same verse 258 ('free of enmity and fear... astute'), tagged 'commentary'. Should be 'verse'."),
    ("q019", 2): Verdict(True, False, "Paraphrase of verse 102 (a different retrieved bundle, 8.3) but genuinely verse-layer content, correctly tagged 'verse'."),
    ("q025", 0): Verdict(True, False, "Verbatim gold verse 367 quote, correctly tagged 'verse'. Citation malformed ('sourced_from_25.6') but resolvable."),
    # q031: all three claims paraphrase intention/cetana content that matches
    # Dhp1/2 (gold) but are cited to group 26.18 (a different, unrelated
    # retrieved verse about mustard seeds) -- fabricated citation, but the
    # TAG type (verse paraphrase) is defensible for all three. None engage
    # the actual philological nuance asked (ethical vs Abhidhammic reading) --
    # a relevance/completeness failure, not scored as a tag error here.
    ("q031", 0): Verdict(True, False, "Paraphrases intention/cetana content consistent with Dhp1-2 verse text; tag type 'verse' defensible despite wrong citation (26.18)."),
    ("q031", 1): Verdict(True, False, "Same as claim 0: verse-paraphrase content, wrong citation."),
    ("q031", 2): Verdict(True, False, "Same as claim 0: verse-paraphrase content, wrong citation."),
    ("q037", 0): Verdict(True, False, "Paraphrases gold verse 90's actual text ('no fever is found in them'), correctly tagged 'verse'. Incomplete (doesn't name the four knots) but not mistagged."),
    ("q037", 1): Verdict(False, False, "Claims the commentary doesn't name the four knots specifically -- but this is the model's own inference/generalization (the vatthu shown, about Devadatta's rock, says nothing about ganthas at all), not something stated in the provided commentary text. Should be 'synthesis'. Root cause: interlinear_notes (which DOES enumerate the four ganthas) is not included in the generation prompt at all -- see generate/prompt.py; a real prompt-design gap, not just a model error."),
    ("q043", 0): Verdict(False, False, "Correctly identifies the apadam/padani wordplay (matching the actual interlinear note, though that note wasn't given to the model -- inferred from the verse text's 'track/trackless' language instead) but tagged 'commentary'; the given commentary text (about Mara pursuing the Bodhisatta) says nothing about wordplay. Should be 'synthesis'. Content is philologically correct despite the tag error."),
    ("q043", 1): Verdict(False, False, "Same as claim 0: model's own interpretive elaboration, tagged 'commentary', should be 'synthesis'."),
    ("q049", 0): Verdict(True, False, "Gold verse 283 wasn't even in the retrieved context (retrieval failure for this query); model correctly declined rather than fabricating, tagged 'synthesis' -- exactly right per the rubric/prompt instruction to flag unanswerable questions this way."),
    ("q055", 0): Verdict(False, False, "Cites a fabricated Pali term 'akataññūsi' that does not appear in the actual Mahasangiti text shown ('akataṁ') or anywhere in the corpus -- a philological hallucination, not a mere paraphrase. Tagged 'verse'; content itself is not trustworthy regardless of tag."),
    ("q061", 0): Verdict(False, False, "Specific narrative detail ('attacked by disease, vital forces began to decay') reads as direct commentary/vatthu content, tagged 'synthesis'. Should be 'commentary'."),
    ("q061", 1): Verdict(False, False, "Specific narrative detail with a direct quote ('Send me eight or sixteen bhikkhus') -- commentary content, tagged 'synthesis'. Should be 'commentary'."),
    ("q061", 2): Verdict(True, False, "Narrative dialogue ('Wait! Wait!'), correctly tagged 'commentary'. Citation malformed ('g1_11') but resolvable."),
    ("q067", 0): Verdict(False, True, "Narrative detail (elder seeking robes on refuse-heaps) is pure commentary/vatthu content, not verse content -- verse 93 is about liberation via signlessness/emptiness, unrelated. Tagged 'verse'. Textbook anachronistic conflation: commentary narrative presented as the verse's own content."),
    ("q073", 0): Verdict(False, True, "Narrative detail about the scale of the Gifts-beyond-Compare ceremony is commentary content (verse 177 is about miserliness/giving generally, not this specific event). Tagged 'verse'. Anachronistic conflation."),
    ("q073", 1): Verdict(True, False, "Commentary-layer claim about the once-in-a-lifetime nature of the event, correctly tagged 'commentary' ('managed by a woman' is an embellishment not clearly stated in the synopsis shown, a minor accuracy issue distinct from the tag itself)."),
    ("q079", 0): Verdict(True, False, "Narrative detail (going to wait upon the Teacher, thirty bhikkhus), correctly tagged 'commentary'."),
    ("q079", 1): Verdict(True, False, "Narrative detail from a different retrieved bundle (6.6, not gold, but genuinely that bundle's commentary content), correctly tagged 'commentary'."),
    ("q085", 0): Verdict(True, False, "Narrative detail (gazing at the Buddha, abandoning meditation), correctly tagged 'commentary'."),
    # q097: retrieval completely failed for this query (gold=14.6 Aggidatta
    # not retrieved at all; retrieved bundles were 11.2/6.11/1.12). Verified
    # against the actual corpus (data/processed/stories.jsonl) that bundle
    # 1.12's real vatthu text does contain the Kalabu/Pingala narrative the
    # model describes -- so this is NOT invented from nothing, it's real
    # content from the (wrong, off-topic) retrieved story 1.12, deployed
    # without any framing connecting it to the actual question. Independent
    # of the retrieval failure, the claims' *tagging* within that content is
    # scored on its own terms below.
    ("q097", 0): Verdict(True, False, "Meta-narrative framing ('the discussion reverting to... he related the Birth Story about...') is commentary-layer content, correctly tagged 'commentary'."),
    ("q097", 1): Verdict(False, True, "Narrative content (crowd celebrating Devadatta's death) tagged 'verse'. Anachronistic conflation."),
    ("q097", 2): Verdict(False, True, "Narrative content (Buddha's response to bhikkhus) tagged 'verse'. Anachronistic conflation."),
    ("q097", 3): Verdict(True, False, "Meta-narrative framing (introducing the Mahapingala birth story), correctly tagged 'commentary'."),
    ("q097", 4): Verdict(False, True, "Narrative content (King Pingala's cruelty) tagged 'verse'. Anachronistic conflation."),
    ("q097", 5): Verdict(False, True, "Narrative content (king's death, succession) tagged 'verse'. Anachronistic conflation."),
    ("q097", 6): Verdict(False, True, "Narrative content (doorkeeper dialogue setup) tagged 'verse'. Anachronistic conflation."),
    ("q097", 7): Verdict(False, True, "This is an actual verse quotation (a birth-story verse, not a Dhammapada verse) but tagged/cited as if it were Dhp verse content in this context, and the source is the wrong story entirely -- scored as conflation since it's presented indistinguishably from primary Dhammapada verse content in the answer."),
    ("q097", 8): Verdict(False, True, "Narrative content (doorkeeper's explanation) tagged 'verse'. Anachronistic conflation."),
    ("q097", 9): Verdict(False, True, "Another birth-story verse quotation, same issue as claim 7 -- presented as undifferentiated 'verse' content. Anachronistic conflation."),
    ("q101", 0): Verdict(False, False, "Meta-answer to a 'which story' question, factually wrong (names 'Elder Sariputta'; gold story 22.9 is about sectarian disciples' children, not Sariputta) and mistagged 'verse' for what is structurally an inference/meta-claim, not verse content. Should be 'synthesis'."),
    ("q101", 1): Verdict(True, False, "Identical text to claim 0, this time tagged 'synthesis' -- the more defensible tag for a meta-claim of this kind, though content is still factually wrong (not scored here, tag-type only)."),
    ("q105", 0): Verdict(True, False, "Meta-answer ('which story') tagged 'synthesis', the right type for this kind of claim regardless of the underlying fact being wrong (retrieval failed for this query too; gold=14.5 not retrieved)."),
    ("q109", 0): Verdict(True, False, "Incomplete/truncated meta-answer, but 'synthesis' is the right tag type. Retrieval failed for this query (gold=23.1 not retrieved)."),
    ("q113", 0): Verdict(True, False, "Substantively accurate elaboration of the actual CST4 title's meaning ('Sakka's past-life as Prince Magha' matches the synopsis's Magha/Sakka rebirth content), tagged 'synthesis' -- reasonable for a paraphrased/elaborated answer rather than a verbatim title quote."),
}
