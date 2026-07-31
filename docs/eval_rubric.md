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

- **Correct** if the claim's tag (`verse`/`commentary`/`synthesis`) matches
  where its content actually originates, judged against the gold verse-group's
  `pali_mahasangiti`/`english_sujato`/`interlinear_english` (verse layer) and
  `nidana`/`vatthu`/`desanavasane`/`synopsis` (commentary layer) text.
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
