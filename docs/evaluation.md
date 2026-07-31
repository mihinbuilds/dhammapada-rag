# Evaluation (Phase 5)

Numbers below are computed by `src/dhammapada_rag/eval/*.py` against
`data/eval/gold_set.jsonl`; regenerate before trusting a stale copy of this
file. **Read `docs/eval_rubric.md` first** -- in particular its "Annotator
status" section. Short version: this is a single AI-assisted annotation pass
(Claude, one sitting), not the two-Pali-competent-human-annotators process
`DhammapadaRAG.txt` calls for. No Krippendorff's α or Cohen's κ is computed
or claimed anywhere in this document, because computing one from a single
annotator would be meaningless. Every number here should be read as "what a
careful single AI pass found," not as human-validated ground truth.

## Gold set

120 questions, 30 each across doctrinal / philological / narrative /
cross-recension (`data/eval/build_gold_set.py`), built by
construction-from-known-answer (pick a verse-group, write a question it
specifically answers -- see the rubric). 114/120 are chunk-retrievable; the
remaining 6 are colophon facts (PTS vs. this-edition story/section counts)
that aren't chunk-indexed at all, kept in the gold set as documented,
answerable-from-source knowledge rather than silently dropped.

**Known limitation of the construction method, stated plainly**: because
questions were written from a known single answer, this gold set is
easier than a naturally-collected user-query set would be -- the
question's own wording tends to echo the target content. Absolute retrieval
numbers below should be read as an optimistic ceiling, not as "how this
system performs on real user questions." The *relative* comparisons
(per-type breakdown, ablation deltas) are far more trustworthy than the
absolute numbers, since the construction bias applies equally across
conditions.

## Retrieval metrics

114 questions, full pipeline (hybrid RRF search -> cross-encoder rerank ->
parent-group assembly), single relevant verse-group per question (so
nDCG@10's IDCG=1 -- see `retrieval_eval.py`'s docstring).

### Overall

| Condition | R@1 | R@3 | R@5 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|---|
| **baseline** (full pipeline) | 0.816 | 0.886 | 0.886 | 0.895 | 0.863 | 0.854 |
| verse_only | 0.439 | 0.500 | 0.544 | 0.544 | 0.493 | 0.482 |
| dense_only | 0.728 | 0.825 | 0.842 | 0.860 | 0.796 | 0.779 |
| no_rerank | 0.737 | 0.816 | 0.842 | 0.895 | 0.813 | 0.789 |
| flat (no assembly dedup) | 0.816 | 0.886 | 0.886 | 0.895 | 0.862 | 0.852 |

### By query type (baseline)

| Type | n | R@1 | R@3 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|---|
| doctrinal | 30 | 0.900 | 1.000 | 1.000 | 0.963 | 0.950 |
| narrative | 30 | 0.933 | 1.000 | 1.000 | 0.975 | 0.967 |
| philological | 30 | 0.867 | 0.933 | 0.933 | 0.909 | 0.904 |
| **cross_recension** | 24 | **0.500** | **0.542** | **0.583** | **0.539** | **0.528** |

**This is the aggregate-hides-the-interesting-result case `DhammapadaRAG.txt`
predicted, just not in the exact direction it guessed.** The spec expected
narrative queries to fail on verse-only retrieval and philological queries to
fail on narrative retrieval; what actually happened is that
**cross-recension questions fail hard across the board** (nDCG@10 0.539 vs.
0.91-0.98 for the other three types) while the other three types are all
uniformly strong. The overall nDCG@10 (0.863) looks good and completely
hides this. Why: cross-recension questions ("which single story explains Dhp
188-192 together?", "how does the CST4 title differ?") ask about the text's
*structure* -- verse groupings, edition variants, alternate titles -- not
about semantic content a dense/sparse embedding can match on. A question
whose answer is "story 14.6" has very little lexical or semantic overlap
with story 14.6's own verse/commentary text if the question is phrased
structurally rather than about what the story is *about*.

### Ablations

**verse-only vs. verse+commentary** (chunk-set restricted to `verse_*` chunk
types): the single largest effect in this evaluation. Overall nDCG@10 drops
0.863 -> 0.493 (-0.370). Broken out, this is not uniform at all:
- narrative: **0.975 -> 0.054** (near-total collapse -- narrative answers
  live almost entirely in the commentary layer, exactly as the project's
  core thesis predicts)
- cross_recension: **0.539 -> 0.060** (also collapses -- structural facts
  aren't in verse text either)
- doctrinal: 0.963 -> 0.882 (modest drop -- doctrinal questions are often
  answerable from verse text alone)
- philological: 0.909 -> 0.889 (barely moves -- philological questions are
  fundamentally about the verse's own words)

This is the strongest evidence in this evaluation for the project's
architectural claim: verse-only retrieval (what a naive Dhammapada RAG would
do) is catastrophic for exactly the query types -- narrative and, less
expectedly, cross-recension -- that need the commentary layer, while barely
mattering for the types that don't.

**dense-only vs. hybrid+RRF**: overall nDCG@10 drops 0.863 -> 0.796
(-0.066), a real but much smaller effect than the chunking ablation above.
Per-type, this ablation has a surprising direction on narrative questions:
dense-only scores *nDCG@10=1.000*, higher than the full hybrid+rerank
pipeline (0.975) -- on this gold set, dense embeddings alone are already
saturated for narrative retrieval, so hybrid fusion adds nothing there
(and rerank, if anything, introduces a small amount of noise). Hybrid+RRF's
value concentrates in cross_recension (0.305 dense-only -> 0.539 baseline)
and doctrinal (0.907 -> 0.963) instead.

**with vs. without cross-encoder rerank**: overall nDCG@10 drops 0.863 ->
0.813 (-0.050) without rerank; recall@10 is *unchanged* (0.895 either way) --
reranking mainly moves the right answer up within an already-good candidate
set rather than rescuing answers that RRF missed entirely. The one large
exception is cross_recension, where rerank contributes disproportionately
(R@1 0.292 -> 0.500 with rerank) -- the cross-encoder does real, targeted
work on exactly the query type that needs it most, even though it can't
close the gap to the other three types.

**flat chunking vs. parent-group assembly**: essentially no difference
(nDCG@10 0.862 vs. 0.863, a 0.001 delta). **This is a genuine null result,
reported as one rather than glossed over**: on this gold set, at the
reranked-top-30 stage, deduplicating chunks into verse-groups doesn't
change which group ends up highest-ranked -- the correct group's best chunk
was already going to outrank other groups' chunks regardless of dedup. This
doesn't mean parent-group assembly is worthless -- it's still what makes the
system *return* the full verse/commentary/translation bundle instead of a
bare chunk (Phase 3's actual deliverable), and it may matter more on harder,
naturally-sourced queries with more competing near-miss chunks than this
construction-biased gold set produces -- but the retrieval-*accuracy* case
for it, specifically, isn't supported by this data, and shouldn't be
oversold as if it were.

## Generation metrics

20-question stratified sample (5/type), manually judged (single annotator,
see rubric) against `data/eval/generation_raw.jsonl` -- one generation call
each, Qwen2.5-7B-Instruct, real retrieved context (not gold-forced). Full
judgments with reasoning: `data/eval/generation_judgments.py`.

| | Value |
|---|---|
| Layer attribution accuracy (all claims) | **20/42 = 0.476** |
| Anachronistic conflation rate (of 32 verse/commentary-tagged claims) | **10/32 = 0.312** |
| Structural provenance warnings (automated audit) | 18/42 claims |

### By query type

| Type | n claims | Accuracy | Conflation rate |
|---|---|---|---|
| doctrinal | 9 | 0.444 | **0.000** |
| philological | 9 | 0.556 | **0.000** |
| narrative | 9 | 0.556 | 0.286 |
| **cross_recension** | 15 | **0.400** | **0.727** |

Cross-recension is the worst performer on *both* retrieval and generation
metrics -- not a coincidence. Most of its generation sample's questions had
weak or failed retrieval (see below), so the model was often working from
irrelevant context; three of its five sampled questions show the model
answering fluently and confidently from the *wrong* retrieved story without
flagging that it couldn't find the right one, which is where most of its 8
conflation instances come from.

Doctrinal and philological show **zero** conflation in this sample -- not
because the model is careful there, but because most of its errors in those
categories are the *other* direction: verse content correctly derived but
mistagged `synthesis` or `commentary` instead of `verse` (a paraphrase-
tagging problem, not a conflation problem -- see "Tag confusion" below).

### Tag confusion

| Tagged as | Correct | Incorrect |
|---|---|---|
| `verse` | 8 | 12 |
| `commentary` | 7 | 5 |
| `synthesis` | 5 | 5 |

`verse` is the least reliable tag by a wide margin (40% precision). Two
distinct error patterns live inside that number, and they matter
differently for the project's actual purpose:

1. **The named failure mode, confirmed real**: commentary/narrative content
   tagged `verse` (10 conflation instances, e.g. q067 -- "the elder... was
   seeking fresh robes on refuse-heaps," pure vatthu narrative, tagged as if
   it were verse 93's content). This is exactly the anachronistic-conflation
   harm `DhammapadaRAG.txt` names.
2. **A second, un-named-by-the-spec pattern, also real**: verse paraphrase
   tagged `synthesis` or `commentary` instead of `verse` (e.g. q019 claim 1:
   "free of enmity and fear makes one astute" is a direct paraphrase of
   verse 258's own second half, tagged `commentary`). This doesn't
   misattribute a *later* layer as the verse's own words -- if anything it's
   the safer-looking error -- but it's still a layer-attribution-accuracy
   failure by the rubric's definition, and it's roughly as common as true
   conflation in this sample. Worth a name of its own for future work:
   call it *under-attribution* (verse content not credited as verse).

### A concrete, actionable gap found during judging, not just an LLM error

Several philological misses (q037, q043) trace to a real prompt-design
problem, not model weakness: `generate/prompt.py`'s context builder includes
`interlinear_pali`/`interlinear_english` but **not
`interlinear_notes`** -- the actual scholarly philological commentary
(word etymology, textual variants, translation disputes) that
`data/processed/verses.jsonl` carries for 114/423 verses and that
`PHILOLOGICAL` gold questions were specifically written from (see
`build_gold_set.py`). The model was answering philological questions with
the *notes it was written to test* withheld from its context. This is a
one-line fix to `format_verse_group()`, not a modeling problem, and it's the
single highest-leverage change identifiable from this evaluation pass.

### Retrieval-generation interaction: the model doesn't consistently know when to say "I don't know"

Two contrasting cases from the same 20-question sample:
- **q049** (philological, gold story not retrieved at all): the model
  correctly produced a single `synthesis` claim stating the commentary
  doesn't address the question -- exactly the right behavior when context is
  irrelevant.
- **q097** (cross-recension, gold story not retrieved at all): the model
  produced 10 fluent, detailed narrative claims lifted from a *different*,
  irrelevant retrieved story (verified against the corpus directly -- the
  content is real text from story 1.12, not invented from nothing, just
  answering a question that story doesn't address), with no indication it
  couldn't actually answer the question asked.

Same underlying failure (retrieval didn't surface the gold source), two
opposite generation responses. This inconsistency -- not the mere fact that
retrieval sometimes fails -- is itself a finding: whatever makes the model
decline sometimes and confabulate fluently other times isn't yet understood
well enough to rely on, and would be a natural target for the prompt.py
system-prompt refinement suggested by `docs/generation.md`.

## Model-size sweep

`src/dhammapada_rag/eval/model_sweep.py`: same 20-question sample, same
retrieved context (fetched once, reused across all three sizes so any
difference is attributable to the generator, not retrieval variance).
Automated metrics only (latency, claim count, structural provenance-warning
rate) -- manual layer-accuracy judging was performed only for the 7B model
above; re-running that judging 3x wasn't a good use of the one annotator
available this session (documented scope decision, `model_sweep.py`
docstring).

| Model | Success | Avg latency | Avg claims | Structural warning rate |
|---|---|---|---|---|
| qwen2.5:1.5b-instruct | 20/20 | 4.6s | 1.9 | **33/39 = 0.846** |
| qwen2.5:7b-instruct | 20/20 | 18.1s | 1.8 | 16/36 = 0.444 |
| qwen2.5:14b-instruct | 20/20 | 38.2s | 1.8 | **7/36 = 0.194** |

**Clean, monotonic result, and a genuine "compute constraint into a
finding" per the spec's own framing**: structural citation reliability
(does a claim cite a group_id/verse_number that's actually among the
retrieved sources) improves sharply and monotonically with model size --
1.5B fabricates or omits citations on 85% of claims, 7B on 44%, 14B on 19%
-- at a real, also-monotonic latency cost (roughly proportional to
parameter count on this hardware, no cliff or surprise). Two corrections to
earlier documented assumptions, both now resolved with data instead of
speculation:
- `docs/generation.md` originally assumed 14B wouldn't fit in this
  machine's 18GB RAM and wasn't attempted. It fits and runs fine -- the real
  constraint is latency (38s/query), not memory.
- Whether 1.5B counts as "a 1B model" the spec warns against using as the
  *primary* generator: yes, and this data explains concretely why that
  warning is right -- 85% structural failure is not usable as a system's
  main generator, though it may still be useful as a fast, cheap first-pass
  or as a deliberately weak baseline in future ablations.

## Summary

**What the evidence in this document supports:**
- The core architectural claim (verse+commentary beats verse-only,
  especially for narrative and structural queries) -- strongly, the largest
  effect measured.
- Schema-constrained decoding reliably enforces output *shape* (100% valid
  `LayeredAnswer` parses across every generation run this project has done).
- Bigger local models are meaningfully, monotonically more trustworthy at
  self-citation, at a proportional and non-prohibitive latency cost on
  consumer hardware.

**What it does not support, and where the honest gaps are:**
- No claim of human-validated inter-annotator agreement anywhere in this
  evaluation (see rubric).
- Layer-attribution accuracy (47.6%) and anachronistic conflation (31.2%)
  are real, unresolved problems in the current prompt/model combination, not
  incidental noise -- a system built on these numbers as-is would still
  regularly present commentary content as verse content.
- Parent-group assembly's retrieval-accuracy benefit is not supported by
  this data (null ablation result), though its role in output *format*
  (Phase 3's actual deliverable) is separate from that question.
- Cross-recension queries are this system's clear weak point on both
  retrieval and generation, and the two compound: bad retrieval feeds bad,
  overconfident generation more often than it triggers an honest "I don't
  know."
- The gold set's construction-from-known-answer method means every number
  above is likely optimistic relative to real user queries -- a caveat that
  applies to the whole document, not just one section.

**Highest-leverage next steps, in order of effort-to-signal ratio:**
1. Add `interlinear_notes` to the generation prompt (one-line fix,
   identified concretely during this evaluation).
2. Investigate why the model inconsistently declines vs. confabulates when
   retrieval fails (q049 vs. q097) -- likely a system-prompt refinement.
3. A second, independent human annotation pass over `gold_set.jsonl` and a
   sample of `generation_raw.jsonl`, to compute the real Krippendorff's
   α/Cohen's κ this document explicitly does not claim.
4. Investigate cross-recension retrieval specifically -- likely needs either
   a different chunk representation for structural facts, or a separate
   retrieval path (e.g. a small structured index over verse groupings and
   title variants) rather than relying on semantic embedding search for
   questions that aren't semantic in nature.
