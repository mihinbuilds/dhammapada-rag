# Evaluation (post-fix)

Numbers below are computed by `src/dhammapada_rag/eval/*.py` against
`data/eval/gold_set.jsonl`, run against the pipeline **after** the
`dhammapada_fixes/CLAUDE_CODE_BRIEF.md` correction pass (14 bugs across
indexing, generation, and evaluation). The pre-fix numbers this pass
superseded are kept, not deleted, at
[`docs/evaluation_pre_fix.md`](evaluation_pre_fix.md); raw pre-fix outputs
are archived at `data/eval/archive_pre_fix/`. Every table below states both
numbers side by side so the effect of each fix is visible, not asserted.

**Read `docs/eval_rubric.md` first.** Same caveat as the pre-fix document:
single AI-assisted annotation pass (Claude, one sitting), no
Krippendorff's α or Cohen's κ computed or claimed anywhere here.

## The headline finding: fluent, cited, schema-valid, and hollow

Before this fix pass, two independent truncation bugs compounded silently:

1. **Generation-time**: Ollama's default `num_ctx=2048` was never overridden.
   A prompt carrying verse text plus commentary narrative routinely exceeded
   2048 tokens, and Ollama silently drops context that doesn't fit rather
   than erroring — the commentary, always assembled *after* the verse text
   in the prompt, was the first thing to fall off the end.
2. **Index-time**: `index/chunks.py` emitted each story's entire `vatthu`
   (narrative, 500-5000 words) as a single chunk, and `index/embed.py`
   encodes at `max_length=512` tokens. Measured against the current
   200-word rewindowing, only **16%** of total narrative text
   (59,997 / 374,773 words) was ever reachable by any query, at any *k*,
   under any fusion strategy — the rest silently never existed as far as
   retrieval was concerned.

Neither failure raised an exception, corrupted JSON, or produced a
schema-validation error. Both are invisible to every check this project had
before this pass: `LayeredAnswer` still parsed, citations still pointed at
real `group_id`s (whichever verse happened to survive truncation), claims
were still fluently written. The system reported 100% schema-valid output
throughout. **This is the most interesting finding in this project**: a
pipeline can pass every structural check it has and still be quietly
answering from a fraction of its own source material, because "the JSON
validates" and "the model saw the text worth citing" are different claims,
and only the fixes below made the gap between them visible and then closed
it.

## Gold set

Same 120 questions as pre-fix, but re-split by construction method rather
than treated as one 30-per-type bucket, since `build_gold_set.py`'s
resolver was itself bug #14 (see below): **alignment** (14, verse-grouping
questions previously lumped into a 30-question `cross_recension` bucket
alongside genuinely different question types), **cross_recension** (16 =
6 colophon + 8 CST4-title-variant, now actually indexed — see Fix 2 above),
**corpus_anomaly** (2), plus doctrinal/philological/narrative (30 each,
unchanged). 114/120 are chunk-retrievable; 6 colophon questions remain
intentionally not chunk-indexed (documented, not a bug).

## Retrieval metrics

114 questions, full pipeline (hybrid RRF → cross-encoder rerank →
parent-group assembly).

### Overall

| Condition | R@1 | R@3 | R@5 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|---|
| **baseline, post-fix** | 0.860 | 0.930 | 0.939 | 0.939 | **0.906** | 0.896 |
| baseline, pre-fix | 0.816 | 0.886 | 0.886 | 0.895 | 0.863 | 0.854 |
| verse_only | 0.500 | 0.526 | 0.535 | 0.553 | 0.526 | 0.523 |
| dense_only | 0.798 | 0.868 | 0.868 | 0.868 | 0.843 | 0.836 |
| no_rerank | 0.702 | 0.842 | 0.886 | 0.921 | 0.813 | 0.780 |
| flat (no assembly dedup) | 0.860 | 0.930 | 0.939 | 0.939 | 0.905 | 0.895 |

Overall nDCG@10 improved 0.863 → 0.906 post-fix, but the by-type table below
is where the fixes actually show up — the overall number moved for a
different reason than either fix, see next section.

### By query type (baseline, post-fix)

| Type | n | R@1 | R@3 | R@10 | nDCG@10 |
|---|---|---|---|---|---|
| **cross_recension** | 8 | 1.000 | 1.000 | 1.000 | **1.000** |
| narrative | 30 | 0.967 | 1.000 | 1.000 | 0.988 |
| philological | 30 | 0.933 | 1.000 | 1.000 | 0.967 |
| doctrinal | 30 | 0.867 | 1.000 | 1.000 | 0.951 |
| **alignment** | 14 | 0.500 | 0.643 | 0.643 | **0.581** |
| corpus_anomaly | 2 | 0.000 | 0.000 | 0.000 | 0.000 |

**cross_recension went from this system's worst-performing type (0.539
nDCG@10 pre-fix) to a perfect 1.000.** The pre-fix document diagnosed this
correctly as "the number was measuring a missing chunk type, not a
retrieval weakness" (Fix 2's own docstring in `chunks.py`) — CST4 title
variants were never indexed, so 8 of that bucket's questions were
unanswerable by construction, not by retrieval failure. Indexing
`story_titles` (title_en/title_pali/cst4_title/burlingame_title) fixed it
completely, not partially.

**alignment is now the worst-performing type with a real sample**
(corpus_anomaly's n=2 is too small to read anything into). This bucket —
"which single story explains Dhp *X, Y, Z* together" — was previously
folded into the old 30-question `cross_recension` bucket and its weakness
was averaged away; splitting it out (bug #14) is what makes this visible.
Alignment questions ask about verse-grouping structure the same way
CST4-title questions ask about edition-title structure, but grouping
membership isn't carried by any single indexed field the way a title
string is — this is a real, currently open gap, not yet fixed by anything
in this pass (out of scope: the brief's "do not tune retrieval parameters"
rule applies, and this needs a structural fix, not a parameter one).

### Ablations

**verse-only vs. verse+commentary**: overall nDCG@10 drops 0.906 → 0.526
(delta 0.380, bootstrap 95% CI [0.292, 0.473], paired by question). Broken
out by type:

| Type | baseline | verse_only | Δ |
|---|---|---|---|
| doctrinal | 0.951 | **0.975** | **+0.025** |
| philological | 0.967 | 0.921 | -0.047 |
| cross_recension | 1.000 | 0.125 | -0.875 |
| narrative | 0.988 | 0.058 | -0.930 |
| alignment | 0.581 | 0.023 | -0.559 |

**Read this row by row, not by the overall number.** The brief predicted
the doctrinal row would be "the real evidence" for the architectural claim,
on the reasoning that narrative's collapse is near-mechanical (the
condition deletes the only chunks narrative's gold answer is reachable
through, so of course it collapses — that's not evidence the commentary
layer *matters*, just that it *exists*). **That prediction is not borne out
by this data.** Doctrinal — the type whose questions are, per the pre-fix
document's own framing, "often answerable from verse text alone" — does not
drop under verse-only retrieval. It very slightly *improves* (+0.025, and
given n=30 this is well within noise, not a real effect either direction).
The honest reading: this gold set does not contain a query type where
removing the commentary layer produces a small, real, *positive* case for
the architecture the way the brief expected. What it shows instead is a
sharper, less flattering version of the pre-fix finding — narrative,
cross_recension, and alignment all depend on commentary/title chunks
existing at all (mechanically, as the brief itself noted), while doctrinal
and philological genuinely don't need them. That's still a real
architectural finding — three of five query types are unanswerable without
the commentary layer — it's just not the *particular* doctrinal-row
evidence the brief predicted, and reporting the prediction as confirmed
when the data goes the other way would be exactly the kind of invented
result ground rule 3 exists to prevent.

**dense-only vs. hybrid+RRF**: nDCG@10 0.906 → 0.843 (delta 0.064, CI
[0.027, 0.108]).

**no-rerank**: nDCG@10 0.906 → 0.813 (delta 0.094, CI [0.053, 0.136]).
Recall@10 barely moves (0.939 → 0.921) — reranking mainly reorders an
already-good candidate set, consistent with the pre-fix finding.

**flat chunking**: nDCG@10 0.906 → 0.905 (delta 0.001, CI [0.000, 0.003]).
Still a genuine null result, unchanged from pre-fix.

**Known gap, not a stop-gate failure**: `by_subtype` in
`retrieval_metrics.json` is empty — `retrieval_eval.py`'s output row never
propagates `q["subtype"]` from the gold-set question. The `by_type` numbers
above are unaffected (they use `q["type"]`, which is populated), but a
finer-grained subtype breakdown (e.g. splitting cross_recension into its
colophon vs. CST4-title-variant halves) isn't currently reportable from the
saved JSON. Minor, unresolved, flagged rather than silently left out.

## Generation metrics

27-question stratified sample, 53 claims total, judged against a
**gold layer tag per claim** (`verse` / `commentary` / `synthesis`) rather
than a bare correct/incorrect accuracy — see
`data/eval/generation_judgments.py` for all 53 individual judgments with
reasoning. This is a stricter and more informative rubric than the pre-fix
document's, so headline numbers are not directly comparable; the pre-fix
document's own accuracy number (47.6%) already flagged layer-attribution
accuracy as broken, and this pass fixes the two truncation bugs the pre-fix
document could not have known were the actual cause.

| | Value |
|---|---|
| Accuracy | **0.830** |
| Macro-F1 | 0.753 |
| Conflation rate (commentary content tagged `verse`) | **0.020** (1/53 claims) |
| Provenance errors (automated audit, `severity="error"`) | 5/53 claims |
| Format warnings (`severity="warning"`/`"info"`) | 17/53 claims |

Pre-fix: layer attribution accuracy 47.6%, anachronistic conflation rate
31.2% (10/32 verse/commentary-tagged claims). Conflation — the actual named
failure mode this system exists to catch, commentary content presented as
if it were the verse's own words — dropped from roughly 1-in-3 claims to
1-in-50. This is consistent with the num_ctx fix specifically: when the
commentary silently falls out of the prompt, the model cannot conflate
verse and commentary because it never sees the commentary to conflate with
— it either says nothing about the narrative, or worse, the retry-on-empty
logic (Fix in `generate.py`/`schemas.py`, see below) pushes it toward
generating *something* commentary-shaped from the verse text alone, which
would show up as low precision on `commentary`, not as conflation. That
this pass shows both high commentary recall (0.966) *and* low conflation
suggests the commentary genuinely reached the model this time, not that the
model got better at guessing.

### Confusion matrix (rows = gold, columns = predicted)

| | pred: verse | pred: commentary | pred: synthesis |
|---|---|---|---|
| **gold: verse** (n=16) | 13 | 3 | 0 |
| **gold: commentary** (n=29) | 1 | 28 | 0 |
| **gold: synthesis** (n=8) | 1 | 4 | 3 |

### Per-class precision / recall / F1

| Layer | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| verse | 0.867 | 0.813 | 0.839 | 16 |
| commentary | 0.800 | 0.966 | 0.875 | 29 |
| synthesis | **1.000** | **0.375** | 0.546 | 8 |

Marginals: predicted verse 28%/commentary 66%/synthesis 6%, gold verse
30%/commentary 55%/synthesis 15%. The model over-produces commentary
claims relative to gold and under-produces synthesis — when it *does* tag
something `synthesis` it is always right (perfect precision), but it
folds a lot of synthesis-shaped reasoning ("this connects to X because...")
into commentary or verse claims instead of flagging it as its own
category. This is the generation-quality analogue of the pre-fix
document's "under-attribution" pattern, not a new failure mode — just
measured with a rubric precise enough to name which direction it goes.

One conflation instance remains (q061, claim 0) and one degenerate output
(q119: claims are literally the strings `"verse"`/`"commentary"`/
`"synthesis"` with no real content) — both documented with full reasoning
in `generation_judgments.py` rather than smoothed into the aggregate.

### A second bug found mid-evaluation, not in the original 14

`format_verse_group()` in `prompt.py` rendered only `title_en` in the
`[COMMENTARY]` block, never `title_pali`/`cst4_title`/`burlingame_title` —
even after Fix 2 made those fields *retrievable* (cross_recension nDCG@10
→ 1.000), the generator had never actually *seen* a CST4 title in its
context, so every CST4-title generation answer sampled during judging was
wrong or fabricated, for a prompt-completeness reason, not a model
capability reason. Fixed in the same file STOP GATE 3 already touched once;
the 27-question sample was regenerated after this fix, before judging —
judging output known to be broken by an unfixed bug would have produced a
meaningless number.

## Model-size sweep

`model_sweep.py`, same 27-question sample and retrieved context reused
across all three sizes, run twice (`--max-retries 0` and `--max-retries 1`).
Primary metric: **clean rate** = fraction of ALL attempts (including
outright failures) with zero provenance errors — not fraction of
successful attempts, so a model that fails outright doesn't get to drop out
of the denominator.

| Model | max_retries=0 | max_retries=1 | Avg latency (0 / 1) |
|---|---|---|---|
| qwen2.5:1.5b-instruct | 0.074 | **0.037** | 5.4s / 6.6s |
| qwen2.5:7b-instruct | 0.852 | 0.852 | 21.0s / 23.5s |
| qwen2.5:14b-instruct | 1.000 | 1.000 | 47.7s / 52.3s |

Pre-fix (different metric — structural-warning rate on successes only, not
directly comparable, but directionally the same story): 1.5B 85% warning
rate, 7B 44%, 14B 19%.

**Structural citation validity still improves sharply and monotonically
with model size** at a proportional latency cost — this holds post-fix,
confirming it's a real capacity effect rather than an artifact of the
truncation bugs.

**Retrying on failure does not reliably help, and can hurt.** 1.5B's clean
rate gets *worse* with a retry enabled (7.4% → 3.7%), not better; 7B and
14B are unchanged either way. A model too weak to cite correctly the first
time is not, on this data, made more likely to succeed by a second attempt
at the same task — retries are not a substitute for model capacity, and
should not be assumed to be a cheap fix for a small model's citation
failures without evidence, which this sweep now provides in the negative
direction.

**No degenerate constant-predicting classifier** in any model/type
combination sampled — max single-class share observed was 68%, well under
what a collapsed "always predict verse" generator would produce.

### Live re-verification, Kisā Gotamī question

STOP GATE 3's own criterion (zero `severity="error"` warnings, at least one
`commentary` claim, prompt comfortably under num_ctx) was re-run fresh for
this document rather than trusted from an earlier single demonstration, on
`"why did the Buddha teach Kisa Gotami about mustard seeds?"`,
qwen2.5:7b-instruct, top_k=3 (3 verse-groups retrieved, two of which both
concern Kisā Gotamī — Dhp 114/group 8.13 and Dhp 287/group 20.11):

| Run | Layer counts (v/c/s) | Errors | Attempt | Prompt tok / num_ctx |
|---|---|---|---|---|
| 1 | 1 / 1 / 0 | 1 (`UNPARSEABLE_GROUP_ID`) | 2 | 5365 / 16384 |
| 2 | 2 / 3 / 1 | 5 (`UNPARSEABLE_GROUP_ID`) | 1 | 5365 / 16384 |
| 3 | 2 / 3 / 1 | 5 (`UNPARSEABLE_GROUP_ID`) | 1 | 5365 / 16384 |

**The commentary-engagement fix holds reliably**: all 3 fresh runs produced
at least one `commentary` claim — the original failure mode (zero
commentary claims, the reason STOP GATE 3 existed) did not recur once.
**Citation-format correctness does not hold reliably on this specific
question**: all 3 runs produced `UNPARSEABLE_GROUP_ID` errors, the model
citing `"Dhp 114"` / `"Dhp 287"` (a verse number) instead of the canonical
`group_id` (`8.13` / `20.11`) it was shown. This is consistent with, not
contradicted by, the 27-question sample's aggregate 7B clean rate of 85.2%
— this question, with two Kisā-Gotamī-related groups retrieved together,
appears to be a harder-than-average case for this specific citation
failure, not a new regression. Reported here as observed rather than
selecting the single cleanest run to represent "the" result, per ground
rule 3.

## Summary

**What the evidence in this document supports:**
- The two root-cause fixes (num_ctx, narrative windowing) produced a real,
  measured improvement in the metric each was diagnosed against: conflation
  rate 31.2% → 2.0%, cross_recension retrieval nDCG@10 0.539 → 1.000.
- The commentary-engagement retry logic (STOP GATE 3's fix) reliably
  prevents the zero-commentary-claims failure mode across independent
  fresh runs.
- Bigger local models remain meaningfully, monotonically more trustworthy
  at self-citation post-fix, at a proportional latency cost — this holds up
  as a genuine capacity effect, not an artifact of the bugs fixed here.
- Retrying a failed generation is not a reliable mitigation for a
  small model's citation failures — a negative result, reported as one.

**What it does not support, and where the honest gaps are:**
- The brief's specific prediction that the doctrinal row would show the
  "real evidence" for the verse-only ablation is not borne out — doctrinal
  does not drop when commentary chunks are removed, on this gold set.
- `alignment` (verse-grouping structural questions) is now this system's
  clear weak point on retrieval, unaddressed by anything in this fix pass
  and not previously visible because it was averaged into a larger,
  differently-composed bucket.
- Citation-format correctness (canonical `group_id` vs. a plausible-looking
  substitute like a bare verse number) remains imperfect and
  question-dependent even for the 7B model, as shown by both the aggregate
  27-question sample (5/53 provenance errors) and the live Kisā Gotamī
  re-verification above.
- `by_subtype` retrieval breakdown is not currently populated
  (`retrieval_eval.py` gap, not a stop-gate failure, flagged above).
- Same construction-from-known-answer caveat as pre-fix: absolute numbers
  are an optimistic ceiling relative to real user queries; relative
  comparisons (ablation deltas, by-type breakdown) remain more trustworthy
  than absolute numbers.

**Highest-leverage next steps:**
1. A structural fix for `alignment`-type retrieval (verse-grouping
   membership isn't carried by any single indexed field the way a title
   string is) — likely needs a dedicated small index over verse-group
   membership rather than relying on semantic embedding search.
2. Wire `q["subtype"]` through `retrieval_eval.py`'s output rows so
   `by_subtype` is actually populated.
3. Investigate why citation-format correctness degrades specifically when
   multiple verse-groups sharing a similar theme are retrieved together
   (the Kisā Gotamī re-verification above is one concrete, reproducible
   case to start from).
4. A second, independent human annotation pass, to compute the real
   Krippendorff's α/Cohen's κ this document still does not claim.
