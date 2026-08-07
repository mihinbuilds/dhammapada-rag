# Evaluation rubric (Phase 5)

Published before the gold set was drafted, per standard IR/annotation
practice (rubric first, then label against it -- not the other way around).
Governs `data/eval/gold_set.jsonl` and the generation-metrics judging in
`src/dhammapada_rag/eval/generation_metrics.py`.

## Annotator status -- read this first

**This gold set has exactly one annotator: Claude (Sonnet 5), assisting the
project owner, in a single pass.** `DhammapadaRAG.txt` calls for two
annotators with Pali competence and a reported Krippendorff's α or Cohen's κ.
That is **not what this document represents** and no IAA statistic is
computed or claimed anywhere in this repository -- computing one from a
single annotator would be meaningless, and presenting single-pass AI labels
as if they carried the credibility of human inter-annotator agreement would
be exactly the kind of unaudited, inflated number `DhammapadaRAG.txt` itself
warns against.

What this pass *is* good for: gold relevance judgments built by
**construction from a known answer** (see "Construction method" below), which
is a legitimate, if weaker, way to seed an IR eval set with a single
annotator -- correctness of the *relevance judgment* is high by construction
even without a second rater, because the question was written by looking at
the answer, not reverse-engineered after the fact. What it is *not* good for:
any claim about human-level agreement, or about how a naive/adversarial user
question would be judged. `docs/evaluation.md`'s numbers should be read with
this ceiling in mind throughout, and the repo's structure (`annotator_1`
field left in the schema, see below) exists specifically so a second human
pass can be added later without a schema change, at which point real
Krippendorff's α / Cohen's κ become computable.

## Construction method

Each gold question was written by first selecting a specific verse-group
(one or more Dhp verses + the story/stories explaining them) already known
from the corpus, then writing a question a real user might plausibly ask that
group specifically answers. The `gold_group_ids` / `gold_verse_numbers`
fields are therefore ground truth by construction, not a post-hoc judgment
call on a freely-written question. This trades some question naturalism
(a real user's question wasn't observed) for label reliability.

## Query types

| Type | Definition | What "relevant" means |
|---|---|---|
| **doctrinal** | Asks what the Dhammapada teaches about a concept/theme (heedfulness, craving, anger, the mind, etc.) -- answerable primarily from verse content, though commentary may add context | A verse-group is relevant if its verse text directly addresses the concept asked about |
| **philological** | Asks about the meaning, translation, or etymology of a specific Pali term or phrase | A verse-group is relevant if it contains that term and (ideally) has `interlinear_notes` scholarly commentary on it -- philological questions are deliberately drawn from the 114/423 verses that have notes, since those are where a real philological answer exists in the corpus |
| **narrative** | Asks about a story, character, event, or "who/what/why" behind a verse | A verse-group is relevant if its *story* (not just verse) directly answers the who/what/why asked |
| **cross-recension** | Asks about edition variants: PTS vs. this edition's differing story/verse counts (documented in the colophon), CST4 (Burmese) vs. PTS alternate titles, or multi-verse groupings (one story explaining several consecutive verses) | A verse-group is relevant if it is the specific case the question names; these questions have a narrower, more literal correct answer than the other three types |

## Relevance judgments (for Recall@k, nDCG@10, MRR)

- **Binary relevance** per verse-group (`gold_group_ids`): a verse-group is
  either the answer or it isn't. All ~120 questions were constructed to have
  exactly one gold verse-group, since retrieval metrics are cleanest to
  interpret and audit against a single unambiguous target -- this is a
  simplification versus real user queries, which can have multiple valid
  answers (documented as a limitation in `docs/evaluation.md`, not hidden).
- A retrieved verse-group counts as a hit if its `group_id` (or, for
  multi-verse-group stories, any `group_id` covering the gold verse number)
  matches `gold_group_ids` exactly.
- Rank position for nDCG@10/MRR is the position in the deduplicated,
  assembled verse-group ranking (`index/assemble.py`'s output), not the raw
  chunk ranking, since verse-groups are the unit the system actually returns.

## Layer attribution accuracy (generation metric)

For each claim in a generated `LayeredAnswer`:

- **Correct** if the claim's tag (`verse`/`commentary`/`alignment`/
  `synthesis`) matches where its content actually originates, judged against
  the gold verse-group's `pali_mahasangiti`/`english_sujato`/
  `interlinear_english` (verse layer), `nidana`/`vatthu`/`desanavasane`/
  `synopsis` (commentary layer), and the fact that a given story explains a
  given verse group (alignment layer -- see "The fourth layer" below).
- **Verse paraphrase is scored as "verse," not "synthesis"** -- restating a
  verse's content in different words, without adding anything not in the
  verse, counts as a correct `verse` tag. (`docs/generation.md` flagged this
  boundary as ambiguous in earlier testing; this rubric resolves it in favor
  of the more literal reading, since a paraphrase that adds nothing new is
  not synthesis by any ordinary sense of the word.)
- **Synthesis is only correct if the claim genuinely isn't stated in either
  source** -- connecting the verse to the question, drawing an inference, or
  generalizing. A claim that restates commentary content in different words
  is a `commentary` claim, not `synthesis`, by the same logic as above.
- Claims citing a `group_id`/`verse_number` not among the retrieved sources
  (caught automatically by `generate/schemas.py`'s `audit()`) are scored
  **incorrect** regardless of tag, since a fabricated citation cannot be
  correctly attributed to anything.

Reported as: (correct claims) / (total claims), and separately as
tag-confusion counts (e.g. how many `verse`-tagged claims actually contained
commentary content) -- the confusion breakdown is more informative than the
single accuracy number, per `DhammapadaRAG.txt`'s own preference for
per-stratum results over aggregates that hide the interesting failure.

## Anachronistic conflation rate (generation metric)

Defined narrowly, per `DhammapadaRAG.txt`: **a claim tagged `verse` whose
content is actually derived from the commentary** (i.e., presents
Buddhaghosa's narrative gloss, dated centuries after the verse, as if it were
the verse's own plain sense). This is a strict subset of "layer attribution
accuracy" failures above -- specifically the direction of error the project
exists to prevent (the reverse direction, a `commentary`-tagged claim that's
actually just verse content, is a real error too, but not the anachronism
the metric is named for, since verse content presented as commentary doesn't
misattribute a later interpretive layer as ancient).

Reported as: (claims meeting this definition) / (total verse-or-commentary-tagged claims).

### The mirror-image failure, and the one piece of it a machine can catch (Round 4, Task F)

Round 1 made commentary engagement mandatory to stop all-`verse` output.
That fix induced its own mirror-image failure: the same sentence -- "when
anger surges like a lurching chariot, keep it in check... that's what I call
a charioteer; others just hold the reins," verbatim Dhp 222 -- was observed
tagged `verse` in response to one question and `commentary` in response to
another. When retrieval returns verse-heavy groups with little usable
narrative, the model can satisfy the COVERAGE instruction by relabelling a
verse sentence instead of writing a genuine commentary claim. This is
**not** what "anachronistic conflation" (above) is defined as -- it is the
opposite direction, verse content presented as the *later* interpretive
layer rather than commentary presented as the *earlier* one -- but it is
the same underlying failure (the layer tags not tracking where the content
actually came from) and belongs in the same discussion.

Unlike the human-judged metrics above, this specific direction is
mechanically checkable without an annotator: `generate/schemas.py`'s
`audit()` now includes `VERSE_TEXT_AS_COMMENTARY`, which flags a
`commentary`-tagged claim whose content words are mostly contained in the
cited verse's own text (threshold 0.60, set by inspecting actual claims in
`data/eval/generation_raw.jsonl`, not tuned to minimize flags). Run against
that 27-question sample, it flags **0/40** commentary claims -- consistent
with the human-judged verse-tagged-`commentary` count of 1 (`q019`, a
*paraphrase*, not a verbatim quote), since this detector only catches
near-verbatim reuse by construction and does not attempt paraphrase
detection. It is a narrow, mechanical net under one specific failure mode,
not a replacement for the human-judged rate above.

The tag-stability sweep below (Task G) found 3 live instances of exactly
this failure and, in the process, found the check itself had a real
ordering bug (a claim with no citation at all bypassed the content check
entirely, backwards, since it's if anything the more likely candidate for a
content error too). Fixed and re-verified against all 3 cases -- see
`docs/evaluation.md`'s "Round 4" section for the full account. The 0/40
figure above predates that fix but is unaffected by it: the fix only
changes behavior for claims missing a citation, and none of the
27-question sample's commentary claims are both citation-less and
high-overlap.

## The fourth layer: alignment (Round 7, Task T)

The original three-layer taxonomy (verse/commentary/synthesis) has no slot
for a fact about the corpus's own editorial structure -- which story
explains which verse(s), how many verses a group covers, whether editions
differ on a grouping. `data/processed/alignment_table.json` is a modern
editorial artifact this project produced; neither the 3rd-century-BCE verse
nor Buddhaghosa's 5th-century commentary states it. Observed failure:
asked which story explains Dhp 4, the system answered "The Story about the
Elder Thulla Tissa explains Dhp 4," tagged `commentary` -- attributing to
Buddhaghosa a structural claim he never made, and silently inflating the
commentary layer in every metric this rubric measures. `generate/schemas.py`
now defines `AlignmentClaim` (`layer="alignment"`, `group_id`, and
`verse_numbers` -- plural, the group's FULL range) as a fourth variant of
the discriminated union, and `gold_layer` in `generation_judgments.py`
accepts `"alignment"` as a fourth value.

**Re-judging existing entries, not silently remapping them.** Three claims
judged before this layer existed had been forced into the nearest available
tag -- `q095`#0 and `q097`#0 (originally judged `synthesis`: "is the single
story that explains both Dhp X and Dhp Y," a relationship not stated in any
rendered prose) and `q119`#0 (a wrong-but-structural claim about a
verse-to-story anomaly, also originally `synthesis`). All three are now
`gold_layer="alignment"` in `generation_judgments.py`, each carrying a
"ROUND 7 RE-JUDGE" note stating the prior judgment and why it changed.
`tag_correct` is `False` on all three re-judged entries: the claims
themselves were generated before `AlignmentClaim` existed, so nothing in
that run could have been tagged `alignment` regardless of how well the
system now would do -- this is a fact about when the judgment was made, not
a new model failure, and the confusion matrix's `alignment` row will read
as 0% recall on that older sample for exactly this reason. A fresh
generation run against the Round 7 prompt (which now asks for the
`alignment` tag explicitly) is required before `alignment`'s precision/
recall numbers mean anything as a system evaluation rather than as a
demonstration that the re-judging mechanism works.

## Source fidelity (generation metric, Task E)

Layer attribution (above) and `generate/schemas.py`'s structural `audit()`
both ask a **structural** question: is this claim shaped correctly, tagged
to a plausible layer, and citing a `group_id`/`verse_number` that was
actually retrieved? Neither asks a **semantic** question: does the claim
accurately represent what the source it cites actually says? A claim can
pass every structural check and still be wrong.

**Worked example.** Live testing on the question "why did the Buddha teach
Kisa Gotami about mustard seeds?" (see `docs/generation.md`, `docs/
evaluation.md` "Live re-verification") produced a generated claim stating
Kisā Gotamī found no mustard seed *"because no household had ever seen a
death."* Story 8.13's actual point (`data/processed/stories.jsonl`
synopsis) is the exact inverse: the Buddha sent her looking for a seed from
a house that had *never* seen death, and the teaching is that she could not
find one because **every** household had. This claim would have passed both
existing checks:

- **Structural audit**: it cites a real, retrieved `group_id`; its fields
  are individually well-formed (tier 1) and internally consistent, sourced
  from a single retrieved group (tier 2) -- see `docs/generation.md`'s two-
  tier description.
- **Layer attribution**: it is narrative-shaped, about the right story, and
  would very plausibly be judged `commentary` correctly under the rubric
  above -- "what kind of content is this" is answered right even though
  "what does it actually say" is inverted.

**Worked example 2 (Round 7, Task Y).** A generated claim tagged `verse`,
citing Dhp 135, stated *"living beings desire rebirth despite the suffering
it brings."* Dhp 135's actual content (`data/processed/verses.jsonl`,
`english_sujato`): *"As a cowherd drives the cows to pasture with the rod,
so too old age and death drive life from living beings"* -- a simile about
aging and death driving beings *out of* life, with no mention of desire for
rebirth in either direction, let alone despite suffering. This is not a
paraphrase that adds unstated content (which would be a layer-attribution
question, `verse` vs. `synthesis`); it asserts something the cited verse
does not say at all. Same class of error as worked example 1 -- correct
layer, resolvable citation, and (had a `pali_support` quote been attached)
potentially valid Pali, and still false. One instance of this pattern reads
as an anomaly; two, on two unrelated questions and two unrelated verses,
establish it as a pattern structural checks cannot reach by construction --
`audit()` has no way to compare a claim's asserted meaning against its
source's actual meaning, only whether the citation resolves. Recorded as
`faithful: False` in `data/eval/generation_judgments.py` for whichever
question in the judged sample this claim recurs in.

Structural provenance checks verify that a claim's *form* is well-behaved
(present fields, internally consistent citation, tagged to a plausible
layer). They cannot and do not verify a claim's *content* against the
source text it claims to come from -- catching an inversion like either
worked example above requires actually reading the claim against the cited
source, which is a semantic check, not a structural one. That is what
`faithful` (below) adds.

- **`faithful: bool`**, recorded per claim alongside `tag_correct`/
  `gold_layer`/`is_conflation` in `data/eval/generation_judgments.py`: does
  the claim's content accurately represent -- rather than contradict or
  invert -- the source text it is grounded in? This is judged independently
  of layer attribution: a claim can be `tag_correct` (right layer) and
  structurally valid (real, present `group_id`) and still be unfaithful.
- A claim that is merely *unsourced* -- synthesis inferring something not
  literally stated, but not contradicting anything either (e.g. an
  `alignment`-question claim asserting a true verse-grouping relationship
  the retrieved prose never states outright) -- is not unfaithful by this
  definition. Ungrounded-but-true is an attribution/citation question,
  already captured by `tag_correct`/`gold_layer`; fidelity is specifically
  about contradiction/inversion.
- Where a claim's specific content is not independently checkable against
  the excerpt available for judging (the same philological/interlinear-
  notes gap noted throughout this rubric), it is marked `faithful=True` with
  a per-claim note flagging it as unverified rather than confirmed -- a
  documented gap, not a silently resolved one, consistent with this
  rubric's existing scope limits on philological fact-checking.

Reported as: (faithful claims) / (total claims), overall and by query type,
in `aggregate_generation.py`'s output and `generation_metrics.json`'s
`source_fidelity_rate`.

**Scoped rate, with a confidence interval (Round 8, Task AC).** The rate
above is computed over every claim, including `synthesis` -- but a synthesis
claim has no source to be faithful *to* by definition (`LAYER_DESCRIPTIONS`:
"not directly stated in either the verse or the commentary text provided"),
so including it dilutes the rate with claims the metric does not apply to.
`aggregate_generation.py` additionally reports `source_fidelity_scoped`: the
same rate computed over `verse`/`commentary`/`alignment` claims only, with a
95% bootstrap confidence interval resampled **by question**, not by claim --
claims within one answer share retrieval and generation context and are not
independent draws, the same reasoning `model_sweep.py`'s own bootstrap
already applies (see that file's Round 5, Task N correction). Report the
interval alongside the point estimate; a single-run rate on a 20-27-question
sample invites more precision than the sample supports.

### Semantic-neighbour conflation (Round 8, Task AC)

Four fidelity errors are on record across two rounds: the Kisā Gotamī
inversion (mustard seeds -- inverted why she couldn't find one), the Dhp 135
misattribution (a cowherd simile turned into a claim about desiring rebirth),
`q001`'s misattributed refusal (Sañjaya's refusal reassigned to the Chief
Disciples), and `q043`'s Māra's-daughters/Māgandiyā conflation. The first two
are not obviously related to each other in content; the second two share a
specific, nameable structure worth distinguishing from generic
"hallucination," which predicts nothing about *where* errors will occur.

**Māra's daughters** (Taṇhā, Aratī, Ragā -- who tempt the newly-awakened
Buddha) and **Māgandiyā** (the woman spurned by the Buddha in an unrelated
story, group 2.1) are not the same figures, but both are women in an
oppose-or-tempt-the-Buddha narrative role, and the retrieved story
group 14.1 is *about* a Brahmin also named Māgandiya (the man the Māra's-
daughters teaching was later retold to) -- three genuinely distinct entities
sharing two names and one structural role. The model merged them. This is
not random confabulation; it is **conflation of narratives that share a
structural role in the text**, and the corpus is full of exactly this kind
of cluster: paired ascetics who make the same vow, the several bhikkhus
named Tissa, the multiple stories involving a rich man's son who loses his
wealth. A generic "hallucination" label treats every fidelity error as
equally likely everywhere; **semantic-neighbour conflation** predicts a
non-uniform distribution -- errors should cluster on questions touching
these structurally-similar-figure groups specifically, checkable by
constructing gold questions that target them directly (see
`docs/generation.md`'s Round 8 section for a live test of exactly this).

## Layer-tag stability (generation metric, Task G)

A different question from either metric above: not "is this claim's tag
correct" but "does the same underlying claim get the *same* tag across
independently-phrased questions that surface it." Layer attribution
accuracy and source fidelity are both judged per answer, in isolation; tag
stability is the only metric here that requires generating multiple answers
about the same content and comparing them to each other. No annotator
judgment is involved -- this is fully mechanical, per
`src/dhammapada_rag/eval/tag_stability.py`.

**Method.** For each of 15 verses drawn from the gold set, ask 3
differently-worded questions constructed to each surface that verse-group
(one is the verse's actual gold question; two are hand-written alternate
phrasings grounded in the verse's own content, the same construction
principle the gold set itself uses). Collect every claim from the resulting
3 answers. Two claims across different phrasings count as the same
underlying claim if either one's content words are ≥80% contained in the
other (reusing `generate/schemas.py`'s own containment measure); grouping
is scoped per verse, never across verses.

    tag_stability = (groups where every member shares one layer tag)
                    / (groups with more than one member)

A group with only one member (the claim surfaced under only one of the 3
phrasings) is excluded from the denominator -- there is nothing to be
stable or unstable about a fact only one phrasing produced.

Reported overall and per layer (a group's layer bucket is its majority
tag) in `data/eval/tag_stability_results.json`; results and discussion in
`docs/evaluation.md`. Note the ceiling this shares with every other metric
in this document: a 15-verse, 3-phrasing sample is small enough to name
individual unstable cases, not to estimate a population rate with any
precision.

## What this rubric does not cover

- Whether a generated answer is *helpful* or *well-written* -- out of scope
  for a layer-attribution-focused evaluation.
- Retrieval quality for questions with more than one valid answer -- excluded
  by construction (see above).
- Anything requiring genuine Pali philological expertise beyond what's in the
  sourced `interlinear_notes` -- the annotator (Claude) is not a Pali
  scholar; philological questions and their gold answers are drawn directly
  from Ānandajoti Bhikkhu's own notes, not independently verified against
  primary grammatical sources.
- Source fidelity for content outside the excerpt available for judging (see
  "Source fidelity" above) -- `faithful` catches contradictions/inversions
  checkable against the ~400-character vatthu excerpt or a verifiable corpus
  fact; it is not a guarantee that every claim's content is correct against
  the full source text or primary Pali sources.
