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

> **Current numbers (2026-09-23).** Every table further down this document
> is a dated record of the round that produced it, computed on an index of
> at most 5,876 chunks built *before* the September 2026 text-cleaning
> pass. The index now shipped (5,909 chunks) was re-embedded and both
> evaluations re-run against it on 2026-09-23. **These are the numbers that
> describe the current system:**
>
> | Retrieval (114 q) | R@1 | R@10 | nDCG@10 | MRR |
> |---|---|---|---|---|
> | baseline | 0.912 | 0.982 | **0.954** | 0.944 |
> | verse_only | 0.500 | 0.553 | 0.526 | 0.523 |
> | dense_only | 0.921 | 0.974 | 0.953 | 0.946 |
> | no_rerank | 0.886 | 0.974 | 0.937 | 0.926 |
> | flat | 0.912 | 0.982 | 0.951 | 0.941 |
>
> | Generation (27 q, 48 claims) | Value |
> |---|---|
> | Layer accuracy | 0.854 |
> | Macro-F1, 3 supported classes (4-class as printed) | 0.837 (0.628) |
> | Anachronistic conflation | 0.100 (4/40) |
> | Source fidelity (all claims) | 0.833 (40/48) |
> | Source fidelity, non-synthesis, 95% CI | 0.851 [0.717, 0.957] |
> | Pali quotes: exact / variant / fabricated | 8 / 3 / 0 of 11 |
> | Quote coverage rate | 0.807 |
> | Provenance errors | 2/48 claims |
>
> What changed, and why the generation numbers are not a like-for-like
> comparison with August, is in
> [Post-cleaning re-run (2026-09-23)](#post-cleaning-re-run-2026-09-23).

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

*Historical (post-fix pass, August 2026, pre-cleaning index). For current
numbers see the top of this document.*

114 questions, full pipeline (hybrid RRF → cross-encoder rerank →
parent-group assembly).

### Overall

| Condition | R@1 | R@3 | R@5 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|---|
| **baseline, post-fix** | 0.921 | 0.983 | 0.983 | 0.991 | **0.962** | 0.953 |
| baseline, pre-fix | 0.816 | 0.886 | 0.886 | 0.895 | 0.863 | 0.854 |
| verse_only | 0.500 | 0.526 | 0.535 | 0.553 | 0.526 | 0.523 |
| dense_only | 0.912 | 0.974 | 0.983 | 0.983 | 0.955 | 0.945 |
| no_rerank | 0.886 | 0.965 | 0.965 | 0.974 | 0.935 | 0.924 |
| flat (no assembly dedup) | 0.921 | 0.983 | 0.983 | 0.991 | 0.961 | 0.951 |

Overall nDCG@10 improved 0.863 → 0.962 post-fix. The by-type table below is
where most of that movement actually comes from — the alignment fix
(below), not a general retrieval improvement, since doctrinal/narrative/
philological/cross_recension are within rounding of an earlier post-fix
run (see git history of this file) and only alignment moved.

### By query type (baseline, post-fix)

| Type | n | R@1 | R@3 | R@10 | nDCG@10 |
|---|---|---|---|---|---|
| **cross_recension** | 8 | 1.000 | 1.000 | 1.000 | **1.000** |
| **alignment** | 14 | 1.000 | 1.000 | 1.000 | **1.000** |
| narrative | 30 | 0.967 | 1.000 | 1.000 | 0.988 |
| philological | 30 | 0.933 | 1.000 | 1.000 | 0.975 |
| doctrinal | 30 | 0.867 | 1.000 | 1.000 | 0.951 |
| corpus_anomaly | 2 | 0.000 | 0.000 | 0.000 | 0.151 |

**cross_recension went from this system's worst-performing type (0.539
nDCG@10 pre-fix) to a perfect 1.000.** The pre-fix document diagnosed this
correctly as "the number was measuring a missing chunk type, not a
retrieval weakness" (Fix 2's own docstring in `chunks.py`) — CST4 title
variants were never indexed, so 8 of that bucket's questions were
unanswerable by construction, not by retrieval failure. Indexing
`story_titles` (title_en/title_pali/cst4_title/burlingame_title) fixed it
completely, not partially.

**alignment went from this system's worst-performing type with a real
sample (0.581 nDCG@10, when this document first split it out as its own
bucket — bug #14) to a perfect 1.000.** The diagnosis at the time was
correct: "which single story explains Dhp *X, Y, Z* together" questions ask
about verse-grouping structure, but grouping membership wasn't carried by
any single indexed field the way a title string is. The fix (a follow-on
pass, `index/chunks.py`'s `story_alignment` chunk type — one templated
sentence per story naming its verse numbers as retrievable text, 305 new
chunks, 5,667 → 5,972 total) is the same shape as Fix 2's `story_titles`
fix for cross_recension: the underlying metadata (`dhp_verses`) already
existed, it just wasn't indexed as text a query could match against. Spot
verification at the time (Dhp 320/321/322 → 23.1, Dhp 188–192 → 14.6, Dhp
153–154 → 11.8, all rank 1) is now confirmed by the full 14-question bucket
on this gold set, not just those three probes. corpus_anomaly (n=2) is
still too small to read anything into.

### Ablations

**verse-only vs. verse+commentary**: overall nDCG@10 drops 0.962 → 0.526
(delta 0.437, bootstrap 95% CI [0.346, 0.531], paired by question). Broken
out by type:

| Type | baseline | verse_only | Δ |
|---|---|---|---|
| doctrinal | 0.951 | **0.975** | **+0.025** |
| philological | 0.975 | 0.921 | -0.054 |
| cross_recension | 1.000 | 0.125 | -0.875 |
| alignment | 1.000 | 0.023 | -0.978 |
| narrative | 0.988 | 0.058 | -0.930 |

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

**dense-only vs. hybrid+RRF**: nDCG@10 0.962 → 0.955 (delta 0.008, CI
[-0.005, 0.023] — crosses zero, not distinguishable from no effect on this
gold set at this sample size, unlike the earlier post-fix run where hybrid
had a measurable edge; the alignment fix moved both conditions to
ceiling-adjacent territory and compressed the gap between them).

**no-rerank**: nDCG@10 0.962 → 0.935 (delta 0.027, CI [0.002, 0.057]).
Recall@10 barely moves (0.991 → 0.974) — reranking mainly reorders an
already-good candidate set, consistent with the pre-fix finding.

**flat chunking**: nDCG@10 0.962 → 0.961 (delta 0.001, CI [0.000, 0.003]).
Still a genuine null result, unchanged from pre-fix.

**`by_subtype` is now populated** (previously a known gap: `retrieval_eval.py`'s
output row never propagated `q["subtype"]` from the gold-set question; fixed
in a follow-on pass). `cross_recension`'s two subtypes diverge sharply:
`cst4_title_variant` (n=8, the chunk-indexed half) scores a perfect 1.000
nDCG@10, matching the type-level number exactly since the 6 `colophon_not_indexed`
questions are excluded from this 114-question retrievable set by
construction (they remain intentionally not chunk-indexed — see "Gold set"
above), not because they score poorly. `alignment`'s only subtype
(`verse_grouping`) is identical to the type-level row, since it is the type's
only subtype.

## Corpus rebuild (2026-08-04): retrieval re-run

`dhammapada_fixes/corpus_rebuild_design.md` replaced the corpus's field
provenance (each of `pali_mahasangiti` / `english_sujato` / `interlinear_*`
now traces to exactly one owning source — see
`docs/corpus_source_ownership.md` — instead of one PDF silently supplying
fields it didn't own) without changing chunk architecture, index size
(5,973 chunks, unchanged from the numbers above), or retrieval logic.
`docs/corpus_normalization.md` documents the three real corpus bugs the
rebuild's own validation caught in the process (a vagga-final colophon
folded into verse text, a second story's title header leaking into Dhp
416's shared segments, and a citation-vs-canonical swap for Dhp 51/327);
`docs/corpus_validation.md` records the Stage 5 gate run this cutover
passed (423/423 verses, 0 field-ownership violations, 0 control
characters). The index (`chunks.jsonl`, `dense.npy`/`sparse.pkl`/
`colbert.pkl`) was rebuilt from the new corpus and retrieval re-run per
the design doc's own instruction that "any metric from the old corpus is
not comparable."

| Type | n | old (post-fix, above) nDCG@10 | new (post-rebuild) nDCG@10 |
|---|---|---|---|
| alignment | 14 | 1.000 | 1.000 |
| cross_recension | 8 | 1.000 | 1.000 |
| narrative | 30 | 0.988 | 0.988 |
| doctrinal | 30 | 0.951 | 0.951 |
| philological | 30 | 0.975 | **0.963** |
| corpus_anomaly | 2 | 0.151 | 0.151 |
| **overall (baseline)** | 114 | 0.962 | **0.959** |

Ablation deltas (nDCG@10, baseline − variant) are within CI overlap of the
pre-rebuild run: verse_only +0.437 [0.346, 0.530] (was +0.437 [0.346,
0.531]), dense_only +0.005 [-0.007, 0.016] (was +0.008 [-0.005, 0.023]),
no_rerank +0.024 [-0.003, 0.053] (was +0.027 [0.002, 0.057]), flat +0.001
[0.000, 0.003] (unchanged). None of these differences look like a real
effect at n=114 — the architecture-level findings above are unaffected by
the corpus rebuild.

**The one real movement is philological, 0.975 → 0.963 (n=30).** This
bucket asks about verse-level Pali/translation detail, so it's the type
most exposed to the rebuild's field-content changes (the boundary-artifact
fix touched Pali text on 19 verses per `corpus_normalization.md`'s
"Measured effect" table). A per-question diff against the pre-rebuild run
isn't available: this round's raw `retrieval_results.jsonl` /
`retrieval_metrics.json` were overwritten by the re-run before being
separately archived (unlike the pre-fix→post-fix transition above, which
has `data/eval/archive_round1_post_fix/`) — noted here rather than left
silent, since a 30-question bucket moving 1.2 points is small enough to be
noise but not obviously so. Worth re-checking if a future round touches
philological-adjacent corpus fields again.

**Generation metrics below have not been re-run against the rebuilt
corpus** — they still reflect the pre-rebuild pipeline. Per the design
doc's own warning, treat them as informative but not a same-corpus
comparison until a fresh generation pass is run.

### Corpus audit Stage 0, run for real (2026-08-06): patch, not rebuild

`ingest/audit_corpus.py`'s Stage 0 checks (`docs/corpus_audit.md`) were run
against the rebuilt corpus above and found four narrow, patchable issues —
none of them corpus-wide damage, all now fixed:

1. **`\x0c` (form feed) in `desanavasane`/`body_raw`** on 22 vagga-final
   stories (44 field hits) — a PDF page-break character surviving
   extraction. Fixed at the source in `parse_stories.py`'s
   `clean_body_text()`.
2. **The Pali character-set gate's own premise was wrong**, not the
   corpus: it flagged 22 verses for curly quotes (U+201C/U+201D) and an em
   dash (U+2014) inside reported-speech phrases (e.g. Dhp 17's `"Pāpaṁ me
   katan"ti`) as if they were OCR residue. They're genuine source
   typography. `audit_corpus.py`'s `_PALI_CHARSET_RE` and
   `validation_gates.py`'s Stage 5 gate 3 now both allow them.
3. **Three of the four title/body-coherence flags were checker gaps, not
   corpus errors**, hand-checked against `stories.jsonl`: 16.4 ("the
   Licchavis") is a body-text pluralization mismatch (body says "the
   Licchavi princes"); 20.5 ("Elder Padhānakammika Tissa") names its
   subject only in `nidana`, which the check didn't read; 22.2 ("Fruits
   and Powers of People's Bad Conduct") paraphrases `nidana`'s own
   doctrinal frame and contains no actual proper noun despite title-case
   capitalization. `check_title_body_coherence()` now also checks `nidana`
   and tolerates a trailing-"s" plural. The fourth flag, 23.1, remains —
   it's the Round 4/5 false positive already on record, kept flagged
   deliberately (see the function's own docstring for why narrowing
   further isn't the right fix).
4. **The "0 boundary-artifact" result for check 4 is confirmed, not
   assumed**: an earlier draft of `docs/corpus_audit.md` carried
   leftover prose claiming Dhp 423 still held a colophon fragment, which
   contradicted the check's own computed count (0) and didn't match a
   direct read of `verses.jsonl` — the boundary-artifact fix from the
   2026-08-04 rebuild above is holding. The write-up is now generated from
   the live counts rather than a fixed paragraph, so it can't drift out of
   sync with its own numbers again.

Rebuilt `stories.jsonl` → `verses.jsonl` → `chunks.jsonl` → the dense/
sparse/colbert index and re-ran the Stage 5 gates (all seven pass) and the
full retrieval eval after these fixes. Every number is unchanged from the
2026-08-04 rebuild row above (overall nDCG@10 0.959, doctrinal 0.951,
narrative 0.988, philological 0.963) — expected, since none of the four
fixes touch retrievable text content in a way that would move an
embedding; corpus_anomaly moved 0.151 → 0.150, within rounding noise at
n=2. `docs/corpus_audit.md` and `docs/corpus_validation.md` reflect the
patched corpus; see the design doc's own verdict, reproduced there, for
why a full Stages 1–4 rebuild was not warranted by this pass.

## Generation metrics

*Historical (post-fix pass, August 2026). For current numbers see the top
of this document.*

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

## Round 4: the mirror-image conflation, and tag stability

Round 1's fix for all-`verse` output (require at least one `commentary`
claim per answer) induced its own opposite failure: a verbatim Dhp 222
sentence was observed tagged `verse` in response to one question and
`commentary` in response to another. `COVERAGE` now has an explicit escape
hatch and `schemas.py`'s `audit()` gained a mechanical check,
`VERSE_TEXT_AS_COMMENTARY`, for the case a machine can actually verify
without reading for meaning: a `commentary`-tagged claim whose content
words are mostly contained in the cited verse's own text (threshold 0.60;
see `docs/eval_rubric.md`'s conflation-rate section). Against the existing
27-question sample it flags 0/40 commentary claims -- a true negative, not
a sign the check does nothing, since the one known verse-tagged-`commentary`
case in that sample (`q019`) is a paraphrase, which this near-verbatim
check is not designed to catch.

### Tag-stability sweep (Task G) found a live instance, and a bug in the fix

`src/dhammapada_rag/eval/tag_stability.py` asks 3 differently-phrased
questions per verse for 15 verses (45 generations, 136 claims) and groups
claims that are ≥80% mutually contained, scoped per verse. Full method in
`docs/eval_rubric.md`'s "Layer-tag stability" section; results in
`data/eval/tag_stability_results.json`.

| | value |
|---|---|
| groups with >1 member | 24 |
| overall tag_stability | 0.875 |
| verse-majority groups | 19 (stability 0.842) |
| commentary-majority groups | 5 (stability 1.000) |
| unstable groups | 3 (Dhp 39, Dhp 89, Dhp 181) |

All 3 unstable groups are the Task F failure mode: verse content tagged
`verse` under one phrasing and `commentary` under another, in two cases
(Dhp 39, Dhp 181) with byte-identical claim text across the two tags.

**This sweep exposed a real bug in `VERSE_TEXT_AS_COMMENTARY` itself.**
The check was originally placed after the `MISSING_PROVENANCE` branch's
early `continue`, so a `commentary` claim that carried *no* citation at all
could never be checked for content mislabelling -- exactly backwards, since
a claim malformed on one axis (citation) is if anything the more likely
candidate for a failure on the other axis (content) too. The Dhp 39
instance found by this sweep had exactly that shape: verbatim verse text,
tagged `commentary`, with `group_id`/`verse_number` both null. Moved the
check to run independently of the citation-presence branches (both
warnings can now fire on the same claim) and added a regression test
(`test_verse_text_as_commentary_fires_even_with_no_citation_at_all`).

Regenerating all 3 unstable cases (same questions, same seed) and auditing
with the fixed check: **all 3 commentary-tagged claims involved are now
flagged by `VERSE_TEXT_AS_COMMENTARY`** (Dhp 39: 100% overlap; Dhp 181:
100% overlap; Dhp 89: 90% overlap, a paraphrase of half the verse rather
than a verbatim match, still cleared the 0.60 threshold). The honest
framing: the mechanism this round built to catch this failure mechanically
did not, in its first form, actually catch the first real instance found --
the instance was found by a *different* mechanical check (tag stability,
comparing independent generations to each other) than the one purpose-built
to catch it (single-answer content overlap). Both checks are now confirmed
working on the same live cases; neither alone would have been enough.

## Round 5: citations constrained at the decoder; retrieval arm diagnosis

Full account of Task K (decoder-level citation constraints) and Task L
(prompt consolidation) is in `docs/generation.md`'s "Round 5" section --
headline result: citing `"g17.8"`, `"g26.40"`, or `"inferred from Dhp 1
commentary"` is now unrepresentable rather than merely discouraged, and the
two worst-offending probes from the pre-fix format-compliance table produce
zero and zero-of-the-targeted-class warnings respectively on re-run.

### Task M: is fusion dominated by one retrieval arm on conceptual queries?

The motivating observation: "what is the purpose of life according to the
Dhammapada?" retrieved Dhp 423 (the Brahmin Devahita story -- the Buddha's
humoral disorder, a request for hot water) ahead of Dhp 166 (*sadattha*,
"be intent on your own highest good"), the verse that actually answers the
question. The brief's hypothesis: Dhp 423 shares surface tokens with "life"
("former **lives**", "**birth's** destruction"), and if the lexical
(sparse) arm reproduces the fused ranking while the dense arm ranks the
gold verse higher, the lexical arm is dominating fusion.

`src/dhammapada_rag/eval/arm_diagnosis.py` retrieves top-10 four ways
(dense-only, sparse-only, ColBERT-only, RRF-fused, via `index/search.py`'s
new `search_arms()` -- an additive refactor that does not touch `rrf_fuse()`
or change `search()`'s output) for 10 conceptual queries against a
single-verse gold anchor each. Full results:
`data/eval/arm_diagnosis_results.json`.

| arm | gold found in top-10 | mean rank when found |
|---|---|---|
| dense | 4/10 | 2.0 |
| sparse | 4/10 | 4.5 |
| colbert | 5/10 | 4.2 |
| **fused** | **3/10** | 1.0 |

**The hypothesis as stated does not hold, and the actual finding is more
specific and more useful.** Fusion finds the gold verse in top-10 *less*
often than any individual arm -- not because one arm dominates the others,
but because RRF rewards candidates ranked moderately well *across multiple
arms* over a candidate one arm ranks confidently but the others miss
entirely (see the `craving` query below: dense finds Dhp 216 at rank 3, but
it drops out of the fused top-10 entirely because sparse and ColBERT don't
surface it at all). This is a real, mechanical cost of RRF fusion, visible
only by decomposing it -- exactly what running this diagnosis before
touching any weights was for.

**The "purpose of life" failure specifically is not an arm-imbalance
problem at all.** All three arms independently fail to find Dhp 166 in
their own top-10, including dense (the arm the hypothesis predicted would
rank it correctly). Inspecting *what* dense, sparse, and ColBERT all
converge on instead: **Dhp 423 / story group 26.40 is the commentary's own
colophon** -- the closing epilogue that literally names every chapter
("Chapter about the Wise," "Chapter about Craving," "Chapter about Anger,"
"Chapter about the Mind," "Chapter about Heedfulness," ...) plus generic
eulogistic vocabulary ("purpose and benefit," "wisdom," "intelligence,"
"the four truths"). This single chunk is a near-universal lexical and
semantic near-match for almost *any* abstract Dhammapada-concept query --
it also surfaces prominently for the `wisdom`, `suffering`, `mind`, and
`meditation` probes in this same run, not just "life." The surface-token
explanation in the brief ("life"/"lives") was too narrow: the actual
attractor is a single structural artifact of the source document (a table
of contents / dedication, not narrative content answering any question),
and it affects every retrieval arm equally, not the lexical one specifically.

**Caveat on this diagnosis's own construction**: several "not found in
top-10" results (`wisdom`, gold Dhp 40) reflect the single-verse gold
anchor being too narrow, not a true retrieval failure -- Dhp 38, a different
wisdom verse, appears in multiple arms' top-10 for that query. This
diagnosis asks "does something relevant to the concept appear," which a
single fixed verse number only loosely operationalizes; treat the per-query
ranks as illustrative, the aggregate arm comparison and the colophon finding
as the load-bearing results.

**Per "do not tune weights before running this diagnosis": no fusion or
chunking change has been made.** The evidence-backed next step is not a
reweighted RRF (the brief's hypothesis) but excluding or down-weighting the
colophon chunk specifically, since it is a structural artifact rather than
content that answers any real question -- added to "highest-leverage next
steps" below.

**Follow-up: the colophon leak was fixed, and this diagnosis was re-run
against the rebuilt index.** Root cause traced to `ingest/parse_stories.py`:
story 26.40 is the *last* story in the source PDF, so the parser's
regex-based field extraction swept the book's entire closing colophon (an
enumeration of all 26 chapters' story counts plus a Buddhaghosa authorship
ascription -- 1107 words into `synopsis`, 671 into `desanavasane`, none of
it about Dhp 423) past the story's own actual boundary. `index/chunks.py`'s
`_truncate_at_page_break()` now drops everything from the source PDF's
page-break character (or, where that character was itself stripped by an
upstream extraction step, the colophon's own Pali heading, "Conclusion,
Nigamanakathā" -- confirmed unique across all 305 stories' narrative
fields) before windowing -- a corpus-wide rule, not a 26.40 special case; it
also cleans 21 other vagga-final stories' smaller next-chapter-heading
leaks as a side effect. `data/processed/stories.jsonl` itself is untouched,
consistent with the brief's "corpus regeneration is out of scope" rule --
this runs at chunk-build time only. Index rebuilt end to end (5,972 → 5,961
chunks; the 11-chunk drop is entirely 26.40's now-collapsed
`story_synopsis`/`story_desanavasane` windows).

Re-running `arm_diagnosis.py`'s identical 10-query probe against the
rebuilt index: **story 26.40 (Dhp 423) no longer appears in any arm's
top-10 for any of the 10 queries** (previously present for `purpose of
life`, `wisdom`, `suffering`, `mind`, and `meditation`) -- the universal
attractor is gone. The aggregate arm-comparison numbers barely move (dense
4/10 found, sparse 4/10, colbert 5/10, fused 3/10 -- unchanged from the
pre-fix run to the digit, since those 5 queries mostly didn't have Dhp 423
occupying their gold verse's own rank slot, just crowding the rest of the
top-10 with noise) and **`purpose of life` specifically still does not find
Dhp 166 under any arm.** That confirms the diagnosis's own original
reading: this query's failure was never about arm imbalance or even about
the colophon competing for the *correct* rank position -- it is that no
indexed chunk closely matches "purpose of life" well enough to outrank
*something*, and removing the wrong attractor does not manufacture a right
one. Fixing the false attractor was still worth doing on its own terms (a
structural artifact was answering unrelated questions across the whole
gold set, not just this one probe) but is not, and was never claimed to be,
a fix for `purpose of life` itself.

### Task N: latency and GPU utilization

`ollama ps` during a live generation call confirms `qwen2.5:7b-instruct`
runs at **100% GPU** (Metal) already -- the observed 89.4s/53.7s/48.4s
latencies are not a CPU-bound generation artifact. `generate()` now records
Ollama's own `eval_count`/`eval_duration` and reports tokens/second
alongside wall-clock latency (`Generator.generate()`'s return dict and the
CLI's summary line), since wall-clock conflates model size with prompt
length -- and prompt length varies by up to ~2x across the probes in this
document (4270 to 9034 tokens) before Task L's shorter `SYSTEM_PROMPT` even
factors in. Measured this round: 25.7-27.1 tokens/second across three
probes at varying prompt lengths, consistent with genuine GPU-bound
generation throughput for this model size, not a hidden CPU fallback.
`model_sweep.py` should report tokens/second alongside latency on its next
run so the size sweep's latency column isn't read as a compute-mode
artifact.

### Two corpus-fidelity checks from the Round 5 brief, resolved

The brief flagged two claims to verify against the corpus rather than
plausibility. Both check out; neither is a fidelity error.

1. **Rohinī / "Banyan Grove" (story 17.1).** `nidana` is `null` for this
   story, but `vatthu`'s opening sentence states the teaching was "given by
   the Teacher while he was in residence at Banyan Grove with reference to
   the noble maiden Rohiṇī" — the location is carried by `vatthu`, not
   `nidana`, and the generated answer's claim is faithful to it.
2. **Story 23.1's title vs. its Māgandiyā content.** `title_en` ("The Story
   about Speaking and Rousing Oneself") and `title_pali` ("Attānaṁ Ārabbha
   Kathikavatthu", literally "the story about speaking with reference to
   oneself") name the *doctrinal frame* — the Buddha's response to
   Māgandiyā's bribed hecklers is to speak about his own endurance ("I am
   like an elephant that has entered the fray"), not a story titled for its
   narrative antagonist. The alternate `cst4_title`
   ("Attadantavatthu, the Story about One Who Tamed Himself") reinforces the
   same frame, matching verse 322's `attadanto`. `parse_flags` is empty for
   this story; `ingest/parse_stories.py`'s title-to-body pairing is correct,
   not a mispairing bug.

## Round 6: edition variance vs. fabrication in Pali quoting, pipeline hygiene

Full mechanism-level account (Tasks O-S) is in `docs/generation.md`'s
Round 6 section. This section reports what changed and what it measured.

### Task O: the two Round 5 Pali-quote flags are edition variance, not fabrication

Round 5's `PALI_QUOTE_NOT_IN_SOURCE` flagged two of three verse claims on a
live run -- Dhp 221's `"sabbam-atikkameyya"` and Dhp 222's `"tam-ahaṁ"`/
`"bhantaṁ va"` did not match `pali_mahasangiti` byte for byte. Per the
brief's own required probe, run against the actual retrieved prompt for
"what does the Dhammapada say about anger?": both the hyphenated
(Ānandajoti) and unhyphenated (Mahasangiti) forms of each phrase are
present in the model's own context -- the hyphenated form via each story's
`vatthu` narrative text, which quotes the verse inline in Ānandajoti's
orthography, not via `pali_mahasangiti`. **This is the audit-bug branch,
not the memorization branch**: the model copied faithfully from a real
field in its context that `audit()` never checked, not from parametric
memory competing with a correct source in front of it. Recorded here per
the brief's explicit instruction not to skip this determination -- the two
cases support opposite claims about what the system is doing, and only one
of them is true of this corpus's actual prompt construction.

### Task P: three-tier Pali matching replaces the binary check

`generate/schemas.py` now reports three outcomes for a `pali_support`
quote instead of two: exact match (any available Pali field, silent),
orthographic-variant match (matches only after folding hyphenation,
niggahita glyph, pada-boundary case, and spacing conventions --
`PALI_QUOTE_ORTHOGRAPHIC_VARIANT`, **warning**), or no match at either tier
(`PALI_QUOTE_NOT_IN_SOURCE`, **error**, unchanged). The candidate set
widened per Task O's finding: `pali_mahasangiti` and `interlinear_pali`
from the verse record, plus `pali_verse` from every retrieved story
explaining it -- not `pali_mahasangiti` alone.

`aggregate_generation.py` now reports three rates over every `VerseClaim`
carrying a `pali_support` quote in a generation run:

```
exact-copy rate  = exact-tier claims   / all pali_support claims
variant rate     = variant-tier claims / all pali_support claims
fabrication rate = neither-tier claims / all pali_support claims
```

No generation-eval run with human judgments has been captured yet under
the Round 6 schema (the existing `data/eval/generation_raw.jsonl` predates
`pali_support` entirely, so `aggregate_generation.py` correctly reports "no
VerseClaim in this run carries pali_support" against it) -- the aggregate
23-claim-sample rates from a fresh `generation_metrics.py` run, re-judged,
are still open work for the next full eval pass, not claimed here.

**What is reported here is a live, unscripted confirmation on this
machine**, not a sampled rate: a fresh `/answer` call for "what is the
purpose of life according to the Dhammapada?" against `qwen2.5:7b-instruct`
produced a Dhp 20 verse claim quoting the full verse verbatim from
`interlinear_pali`, differing from `pali_mahasangiti` only by edition
orthography -- `PALI_QUOTE_ORTHOGRAPHIC_VARIANT` fired exactly as designed,
at warning rather than error severity, naming the matched field. A separate
"how to control anger?" run's `pali_support` quote matched exactly, no
warning. This is the finding the middle tier exists to make legible: **the
model is reading its own retrieved context, not always in the requested
edition** -- a variant rate well above zero with a fabrication rate near
zero is evidence of the former, not the latter, and the two would look
identical under Round 5's binary check.

### Task Q: the `\x01` corruption is a pipeline-boundary guard, not a corpus fix

`grep -P '[\x00-\x08\x0b\x0c\x0e-\x1f]'` across `data/processed/*.jsonl`,
`data/index/chunks.jsonl`, and `data/raw/*.txt` found zero occurrences of
`\x01` anywhere in the corpus. Per the brief, a clean corpus means this is
not an `ingest/` bug -- `prompt.py`'s `build_messages()` now strips control
characters (excluding `\t`/`\n`/`\r`) from both message contents as a
boundary guard against a future corpus edit or a poisoned `question`
argument, not a fix for an active corruption this repo's data ever
contained.

### Task R: unescaped claim text in the UI card (fixed before it was observed here)

> **Note (2026-09-23).** The Streamlit UI (`src/dhammapada_rag/ui/app.py`) that
> this section refers to has since been removed. The frontend is now the
> Next.js app in `web/`, served by `api/main.py`. References to `ui/app.py` are
> kept as the record of what that round changed.

`ui/app.py`'s `render_claim()` builds one complete f-string per card and
gates the Pali line on field presence, not layer -- both already correct.
`claim["text"]` and the citation string were not `html.escape()`d before
this round, though, which is the general form of the brief's unbalanced-
`</div>` symptom (any `<` in model output corrupting everything rendered
after it in the card). Both fixed; one regression caught in the same pass
(escaping doubled the `&` in a hardcoded `"&middot;"` HTML entity into
visible text -- replaced with the literal `"·"` character, which
`html.escape()` leaves alone) and verified against all three claim layers
before it reached a real run.

### Task S: PC migration

`index/rerank.py`'s `best_device()` (CUDA, then MPS, then CPU fp32) is now
shared by the reranker, `embed.py`'s corpus embedder, and -- found while
migrating, not one of the brief's two named call sites -- `search.py`'s
`ChunkIndex`, the query-time embedder that runs on every search rather
than once at index-build time. All three log their device choice at
startup.

**This machine has an NVIDIA GeForce RTX 5080** (`nvidia-smi` confirms),
but the project's `.venv` has a CPU-only torch build
(`torch==2.13.0+cpu`), so `best_device()` correctly returns `("cpu",
False)` -- correct behavior given the installed build, not a fix for the
underlying gap. `ollama ps`, polled through a live `/answer` call, confirms
`qwen2.5:7b-instruct` generation runs at 100% GPU throughout, consistent
with the original Apple Silicon machine's Round 5, Task N finding. **The
retrieval side (dense/sparse/ColBERT search plus reranking), not
generation, is this machine's actual latency bottleneck** -- a live
`/answer` call measured 2.9s of Ollama generation against an 18s wall-clock
total. Reinstalling torch with CUDA support would very likely close most
of that gap, given the confirmed GPU-bound generation path, but is a
`.venv`-mutating change flagged here rather than made silently mid-round.

Encoding and path-separator concerns from the brief did not find new
issues: every non-`Path` `open()` call in `src/` is binary-mode against a
`.pkl` file (correctly undeclared encoding), every `.read_text()`/
`.write_text()` call already passes `encoding="utf-8"` (`ingest/`
included), and no hardcoded `/` path separator exists outside query-label
strings and comments.

**A bug found verifying this round, not requested by it**: `/answer` 500ed
on any question whose answer contains a synthesis claim --
`api/schemas.py`'s `ClaimOut` was never updated for Round 4/5's
discriminated-union schema change, so `SynthesisClaim.model_dump()`'s
missing `group_id`/`verse_number` keys failed pydantic validation. Fixed
(`= None` defaults, matching what `str | None` already implied); `
pali_support` was also missing from the API's response schema entirely and
is added for the same reason Task J added it to `render.py` and
`ui/app.py`.

**Three probes re-run live on this machine** after all of the above:
"how to control anger?" -- canonical `group_id="17.8"` (no `g` prefix),
zero warnings; "what is the purpose of life" -- `FRAMING` fires as a
synthesis claim and `PALI_QUOTE_ORTHOGRAPHIC_VARIANT` fires on the
`interlinear_pali`-sourced claim, both now surfaced through `/answer`
instead of 500ing; "the woman whose child died" -- Kisā Gotamī's Dhp 287 /
114 / 113 retrieved exactly as documented since Phase 2. No regression
found; device-selection logging and the constrained-schema citation
behavior (Round 5, Task K) both hold on this machine's hardware.

### Still open from earlier rounds, checked against this round's brief

- **Story 23.1's title/body pairing**: already checked twice (Round 4,
  re-confirmed Round 5 above) against the source PDF directly, not just
  `ingest/parse_stories.py`'s output -- title and body are correctly
  paired, not a parsing bug. The Round 6 brief re-raised this as
  "unreported across three rounds"; it was reported in both, restated here
  a third time so the resolution is visible from this round's own section
  without requiring a cross-reference.
- **RRF arm diagnosis**: Round 5's Task M section above already is the
  four-way (dense/sparse/ColBERT/fused) comparison the Round 6 brief asks
  for, including a re-run after the colophon-leak fix it found. Nothing
  further to add this round.
- **Verse-claim specificity**: unchanged from Round 5's `SYSTEM_PROMPT`
  addition -- improved, not resolved. Not itself a Round 6 task.

## Round 7: answer completeness and the alignment layer

Full mechanism-level account (Tasks T-Y) is in `docs/generation.md`'s Round
7 section. This section reports what changed and what a fresh, fully
re-judged 27-question generation run measured -- the same systematic sample
used in every prior round, regenerated under the Round 7 prompt/schema and
judged from scratch (claim text and claim counts both changed; see
`data/eval/generation_judgments.py`'s own note on why judgments don't carry
over between rounds).

### Context utilization and layer-count distribution, reported first

Per the brief's own instruction, before any other number: **0 of 27
answers cite or explicitly dismiss every retrieved verse-group** (mean
utilization 0.346 -- roughly one of three retrieved groups accounted for
per question), and the `n_dismissed` count is **0 in every single
question**. `COMPLETENESS` asks the model to name and dismiss an
irrelevant retrieved group in a synthesis claim; on this sample it never
does -- retrieved material is silently ignored, not reasoned about and
set aside.

Layer-count distribution (how many of the four layers each answer draws
on): 12/27 use one layer, 13/27 use two, 2/27 use three, 0/27 use all
four. Compared to the identical 27-question sample under the pre-Round-7
prompt (15/9/3/0, using the three pre-existing layers only): fewer
single-layer answers, more two-layer answers -- the `COMPLETENESS`
instruction moved the distribution in the right direction but did not
close it. At 44% single-layer, this is close to but has not yet crossed
the brief's own diagnostic line ("if most answers still use one layer, the
completeness instruction did not take, and the next step is structural").

### Task T: the alignment layer, measured

Of 8 claims judged `gold_layer="alignment"` in this sample, the model
tagged 4 correctly and left 4 tagged `commentary` -- precision 1.000
(never applied to the wrong content), recall 0.500 (used only half the
time it should have been). Two of the four misses (`q093`, `q097`) are
alignment/cross-recension query-type questions where the model's own first
claim states "explains Dhp X and Y together" -- textbook alignment content
-- but still reaches for `commentary`. The tag exists and is never
misapplied; getting the model to reach for it consistently is unfinished.

### Task U: full verse-range statement, measured against three live probes

Dhp 4 (group 1.3, covers Dhp 3-4): correct on both counts -- tagged
`alignment`, states "Dhp 3 and 4 together". Dhp 21 (group 2.1, covers Dhp
21-23) and Dhp 153 (group 11.8, covers Dhp 153-154): both tagged
`alignment` correctly, both state only the single verse asked about, not
the group's full range -- `ALIGNMENT_RANGE_INCOMPLETE` (Task T's mechanical
backstop) caught both. 1 of 3 probes fully complied with the prose
instruction; the structural check, not the prompt text, is what makes the
other 2 visible rather than silently wrong.

### Task V: completeness, and the model that came back thin twice

"Who is Cakkhupāla?" produced 2 commentary claims (up from Round 6's 1) but
still zero verse claims and zero Pali, despite Dhp 1 sitting in its own
retrieved context. The brief's own exact original phrasing, "Who is
chakkhupala", reproduced the original 1-claim failure verbatim. Both
`COMPLETENESS` and `DIRECT ANSWER`'s full-range clause are prompt-only
fixes layered on the same architecture that Round 5 already found degrades
under prompt length -- consistent with that finding, compliance here is
partial, not absent and not universal.

### Task W: DUPLICATE_CLAIM

Unit-tested directly against the brief's own scenario (two `VerseClaim`s,
same layer and verse_number, text differing by one word) -- fires as
designed. Did not trigger on this round's 27-question sample; no
duplication of that shape was produced this run. A live-but-unexercised
check, not evidence the failure mode is gone.

### Task X: arm diagnosis, third instance

Full account and table: `docs/generation.md`'s Round 7 section. Headline:
"what does the Dhammapada say about life?" (gold Dhp 110, the six-verse
110-115 series) finds nothing in dense's top-10, sparse at rank 8 only,
and **fused finds nothing** -- worse than the better individual arm. Unlike
Round 5's "purpose of life" case (one structural chunk dominating all three
arms equally), here the dense arm fails outright on its own terms,
preferring Dhp 135 (contains the token "life") to the entire conceptual
series. Three instances now, three different mechanical causes (a
colophon artifact, a lexical near-miss, and this round's outright
semantic-arm miss) -- reported separately per the brief, not averaged into
one number that would hide which fix applies to which case.

### Task Y: two more fidelity errors, found without looking for them

The brief's own Dhp 135 worked example did not recur in this round's
sample (documented as a worked example in `docs/eval_rubric.md` regardless,
same treatment as the Kisā Gotamī case in every prior round). Ordinary
judging of the actual sample turned up two new instances of the identical
failure class unprompted: `q001`#2 misattributes a refusal-to-visit to "the
Chief Disciples" rather than Sañjaya (their former teacher, per the
nidana); `q043`#2 conflates Māra's daughters with the unrelated Māgandiyā
of a different story sharing a similar name. Both structurally clean, both
false. Source fidelity this round: 47/52 = 0.904 (5 unfaithful claims
across 4 questions) -- see `data/eval/generation_judgments.py` for the
full per-claim reasoning.

### Full metrics table (this round's 27-question sample, re-judged, 4-layer)

| Metric | Value |
|---|---|
| Context utilization (mean) | 0.346 |
| Answers fully accounting for retrieved groups | 0/27 |
| Layer-count distribution (1/2/3/4 layers used) | 12/13/2/0 |
| Mean claims/answer | 1.93 (min 1, max 4) |
| Accuracy (layer attribution) | 0.827 |
| Macro-F1 | 0.694 |
| Alignment precision / recall | 1.000 / 0.500 |
| Anachronistic conflation rate | 0.044 (2/45) |
| Source fidelity | 0.904 (47/52) |
| Provenance errors | 7/52 claims |
| Pali exact / variant / fabrication | 0.818 / 0.182 / 0.000 |

The two anachronistic-conflation instances (`q061`#0, `q067`#0) are the
identical claims flagged in every prior round's judged sample for these
exact question_ids -- reproduced unchanged, confirming Tasks T-W (none of
which target this failure mode) left it untouched, as expected.

### Still open from this round

- **Single-layer answers (44% of this sample)**: below the brief's own
  "most answers" threshold for triggering a structural fix, but close
  enough, and the underlying cause (retrieved material silently ignored,
  never explicitly dismissed) is now measured precisely enough to act on.
  A minimum-claims-per-answer or minimum-groups-accounted-for schema
  constraint is the indicated next step if this persists on a larger
  sample, per the brief's own contingency.
- **Alignment tag recall (0.500)**: the tag is never wrong when used, just
  under-used on exactly the query types (alignment, cross_recension) it
  was built for. A retry-on-zero-alignment-claims path, mirroring
  `generate.py`'s existing zero-commentary retry, is the natural parallel
  fix, not yet built.
- **The "life" retrieval failure (Task X)**: still unresolved, as with
  "purpose of life" before it. Three instances now support the general
  finding (lexical/structural/semantic-arm attractors beating conceptual
  relevance are three distinct failure modes, not one to patch generically)
  without yet prescribing a single fix for any of them individually.

## Round 8: structural disposition, alignment's own block, and the RRF mechanism

Full mechanism-level account (Tasks Z-AD) is in `docs/generation.md`'s
Round 8 section. This section reports the numbers, from a fresh, fully
re-judged run of the identical 27-question systematic sample (retrieval
confirmed unchanged, question-by-question, from Round 7 -- only generation
changed) plus a full 114-question RRF k-sweep.

### Task Z: source disposition, cross-tabulated against gold labels

27/27 questions carry a disposition for every retrieved group (required,
decoder-constrained field -- see `docs/generation.md`). Disposition
marginal: `used` 28/81 (0.346), `partially_relevant` 11/81 (0.136),
`not_relevant` 42/81 (0.519). `DISPOSITION_CONTRADICTS_CLAIMS` fired 0/81
times -- the model's stated disposition never disagreed with what its own
claims actually cited. Cross-tabulated against gold labels, the number the
brief asked for specifically: **0 of the 42 `not_relevant` dispositions
land on a gold group.** Every dismissal observed this round reflects
retrieval noise (a group that does not bear on the question) correctly
recognized, not generation misjudging a source that mattered. This is the
separation Round 7's heuristic utilization metric could not make -- it
could only measure "was every group accounted for," not "was the model
right to dismiss the ones it dismissed."

### Task AA: alignment recall, before and after the block restructure

| | precision | recall |
|---|---|---|
| Round 7 (verse-range facts inside `[COMMENTARY]`) | 1.000 | 0.500 (4/8) |
| Round 8 (separate `[ALIGNMENT]` block) | 0.875 | 0.778 (7/9) |

Recall clears the brief's own ~0.75 threshold; the escalation to a
structural constraint (require an alignment claim on `verse_grouping`-type
questions) is not indicated by this sample. All 7 of the core "explains X
and Y together" / corpus-structure claims are tagged `alignment` this
round, including `q093` and `q097`, Round 7's clearest misses. Precision
dropped slightly (1.000 -> 0.875) because of one new failure shape, not a
new kind of error: `q095` and `q097` each state their alignment fact
*twice* in one answer, once correctly tagged and once redundantly under
the wrong tag (`synthesis` and `commentary` respectively) -- `DUPLICATE_CLAIM`
does not catch this (scoped to same-layer `VerseClaim`/`CommentaryClaim`
pairs only), flagged as a gap for a future round rather than fixed this one.

### Task AB: the RRF k-sweep, full 114-question gold set

Checked first, per the brief: is Dhp 110 even a defensible single gold
answer for "what does the Dhammapada say about life?" No -- Dhp 135
("old age and death drive life out of beings," mortality) and Dhp 182
("hard to gain a human birth... the life of mortals is hard," the rarity
of human life) are both independently defensible answers to the same
question, addressing different facets of "life" than the 110-115 series.
Round 7's finding (no arm ranks Dhp 110 highly, fusion least of all) is
real evidence about arm coverage, not evidence the system "failed" a
question with one correct answer -- noted directly in `arm_diagnosis.py`.

| condition | alignment | corpus_anomaly (n=2) | cross_recension | doctrinal | narrative | philological | **overall** |
|---|---|---|---|---|---|---|---|
| rrf_k=10 | 1.000 | 0.000 | 1.000 | 0.9508 | 0.9877 | 0.9550 | **0.9544** |
| rrf_k=20 | 1.000 | 0.000 | 1.000 | 0.9508 | 0.9877 | 0.9631 | **0.9566** |
| rrf_k=40 | 1.000 | 0.1667 | 1.000 | 0.9508 | 0.9877 | 0.9631 | **0.9595** |
| rrf_k=60 (current default) | 1.000 | 0.1505 | 1.000 | 0.9508 | 0.9877 | 0.9631 | **0.9592** |
| score_fusion (min-max + sum) | 1.000 | 0.000 | 1.000 | 0.9298 | 0.9877 | 0.9631 | **0.9510** |

Overall nDCG@10 barely moves across k -- a <0.6-point range from 0.9544 to
0.9595 -- because this gold set (constructed so each question has exactly
one gold group, per `docs/eval_rubric.md`) sits at or near ceiling for
every type except `corpus_anomaly`. That type is the only one with
real k-sensitivity, and it is exactly the type too small to trust (n=2):
the direction observed (worse at low k, better at high k) runs opposite
the brief's own arithmetic prediction (lower k should soften the
absence-penalty and help single-arm discoveries), most plausibly because a
2-question stratum can flip on one query's rank crossing a log-scale
boundary, not because the mechanism is wrong. **No k was adopted; `rrf_fuse()`'s
default k=60 is unchanged.** Score-based fusion underperforms every swept
RRF k overall (0.9510), driven mainly by a doctrinal-type drop (0.9298 vs.
0.9508 at k=60) -- the arithmetic case for why RRF should penalize
single-arm discoveries holds up on inspection, but does not translate into
a practical win for score fusion on this specific corpus. Report both
numbers; neither was adopted as a change to production retrieval.

### Task AC: fidelity rate with CI, and semantic-neighbour conflation named

Scoped to verse+commentary+alignment claims (excludes synthesis, which has
no source to be faithful to): **0.933, 95% CI [0.851, 1.000]**, bootstrap
resampled by question (n=45 claims, 2000 resamples). Overall (all claims):
0.917 (44/48).

Two more fidelity errors this round, one of them a live, unprompted
confirmation of the pattern Task AC predicts: `q099` names an unnamed
bhikkhu "Aggidatta" -- a name belonging only to an adjacent retrieved
group the model itself marked `not_relevant` in the very same answer.
Named **semantic-neighbour conflation** in `docs/eval_rubric.md` (alongside
Round 7's Māra's-daughters/Māgandiyā case), with a refinement from this
round's designed test: a twelve-way "Elder Tissa" name collision, probed
directly with both a generic query (three Tissas retrieved at once) and a
compound question explicitly naming two Tissas by their distinguishing
epithet, produced **zero conflation** in either case -- including a
narrative detail (the Devala/Nārada past-life story) checked and confirmed
exactly against the source. The refined prediction: conflation clusters
where adjacency combines with an *under-specified* distinguishing detail
(an unnamed figure sitting next to a named one; two names that are
themselves near-identical), not from name-or-role adjacency alone. See
`docs/generation.md` for both probes in full.

### Task AD: the working tree is committed

Rounds 3-8 were sitting uncommitted in one working tree -- one accidental
`git checkout`/`reset` from losing this and every later round's work, and
impossible to bisect. `v0-prefix` tags the existing baseline commit
(`4e57cd9`, "Baseline: pre-fix state of DhammapadaRAG"). Per-round
boundaries for rounds 3-6 could not be reconstructed after the fact -- no
intermediate snapshot was ever saved between the last real commit (Round 2,
`0595613`) and this session, and later rounds' edits landed on the same
files rather than only appending to them, so there is no way to
mechanically separate "round 4's version of `schemas.py`" from "round 6's."
Rounds 3-8 are committed together as one commit, with the commit message
naming what each round's brief covered, rather than presenting a false
precision the history doesn't actually have. This is a real limitation,
not a preference: any future round's work is committed as its own commit
from this point forward, so this gap does not recur.

## Round 9: quote fidelity

Task-by-task detail (AE-AH) is in `docs/generation.md`'s Round 9 section;
the measured effect is in the post-cleaning re-run below (quote coverage
rate 0.807 over 11 Pali quotes; three genuine half-quotes caught by the new
`PALI_QUOTE_TRUNCATED` warning). In brief: the corpus carried all four pādas
of Dhp 194 and 273, so the observed truncation was the model's; `audit()`
was attaching a story's `pali_verse` to every verse in a multi-verse group,
a real cross-verse contamination blind spot, now matched per cited verse;
`CITATION_IN_TEXT` now catches bare field names such as `(group_id 14.8)`;
and the scope-widening prompt rule holds on single-comparative verses
(Dhp 103, 354) but not on a claim that compresses Dhp 273's four parallel
superlatives into one sentence.

### The error profile moves once each class is fixed

The failures found per round have moved in one direction:

1. Rounds 1-3: the commentary layer was absent (context window, chunk
   truncation).
2. Rounds 4-6: attribution errors -- verse tagged as commentary, citations
   malformed or missing.
3. Rounds 7-8: utilization -- retrieved material going unused.
4. Round 9: quote fidelity -- truncated Pali, scope-widened paraphrase,
   cross-verse Pali attribution.

Each class became visible only after the previous one was fixed. Until the
commentary reached the model, there was nothing to misattribute. Until
citations were well-formed, whether the model used what it retrieved could
not be measured. And until quotes were real, how much of the verse they
covered did not matter. This is a property of evaluating layered RAG, not
of this system alone: the failure modes are stacked, and a metric that
works at an early stage cannot see errors from a later one. It also cuts
the other way: a system reporting high citation accuracy may simply not yet
have working retrieval. Which errors you can measure depends on which ones
you have already eliminated, so a clean score at one layer is evidence
about that layer only.

## Post-cleaning re-run (2026-09-23)

`docs/status_report.md` found that every result in `data/eval/` predated
the September 2026 cleaning pass (`stories.jsonl` rewritten on all 305
lines, `chunks.jsonl` 5,876 → 5,909 rows), and that `chunks.jsonl` had been
rewritten nine minutes after the embeddings were built. This re-run closes
both gaps: `index/embed.py` re-embedded all 5,909 chunks (embeddings now
newer than `chunks.jsonl`; a spot check of 12 chunks re-encoded fresh gives
self-cosine ≥ 0.9997 on every one), then `retrieval_eval.py` +
`aggregate_retrieval.py` and `generation_metrics.py` +
`aggregate_generation.py` were re-run unchanged.

### Retrieval: one question moved

| Condition | nDCG@10 Aug → Sep | R@10 Aug → Sep |
|---|---|---|
| baseline | 0.9592 → 0.9537 | 0.9912 → 0.9825 |
| verse_only | 0.5227 → 0.5263 | 0.5526 → 0.5526 |
| dense_only | 0.9577 → 0.9525 | 0.9825 → 0.9737 |
| no_rerank | 0.9429 → 0.9374 | 0.9825 → 0.9737 |
| flat | 0.9563 → 0.9508 | 0.9912 → 0.9825 |

Exactly one of 114 questions changed its baseline rank: **q019** (doctrinal,
"what actually makes someone 'astute'…", gold 19.2 / Dhp 258), rank 2 → 27.
The whole overall drop is this one question. It is not index drift: 19.2's
chunks and Dhp 258's four verse chunks differ from the August text only in
whitespace, and their stored dense and sparse vectors match fresh encodings.
The mechanism is lexical. In the query, `'astute,'` (quoted, with a trailing
comma) tokenises as `ast` + `ute`; in `verse:258:en_sujato` "astute"
tokenises as `astu` + `te`. The query's highest-weighted term therefore
matches nothing in the verse, and the chunk sits at sparse rank 1,005 and
dense rank 31. What held it at rank 2 in August cannot be reconstructed,
because the August embeddings were overwritten. The finding that stands:
q019 was always passing on a thin margin, and a punctuation-sensitive
tokenisation split can decide it.

Ablation deltas (baseline − condition, nDCG@10) are unchanged in
substance: verse_only 0.427 [0.338, 0.522]; dense_only 0.001 [−0.008,
0.010]; no_rerank 0.016 [−0.010, 0.043]; flat 0.003 [0.000, 0.008]. The
saturation reading in `docs/status_report.md` §8 holds on the rebuilt
index: only removing the story chunks produces a measurable difference.

### Generation: re-judged from scratch

Same 27-question systematic sample, seed, model (`qwen2.5:7b-instruct`) and
`num_ctx` (16384). All 48 new claims were re-judged in
`data/eval/generation_judgments.py` by Claude Opus 5.5. The August
judgments were by Claude Sonnet 5 and are in git at `2a20bfd`. This pass
also checked each claim against the *full* stored nidāna, synopsis, vatthu
and desanāvasāna and the verse's interlinear notes, not only the ~800-char
excerpt that earlier rounds judged from. That makes it stricter, and part
of the fidelity movement below is the stricter check rather than a worse
model.

| | Aug (round 8) | Sep 23 |
|---|---|---|
| Accuracy | 0.854 | 0.854 |
| Macro-F1 | 0.824 | 0.837 over verse/commentary/alignment; 0.628 printed* |
| Conflation (commentary tagged `verse`) | 0.027 | **0.100** (4/40) |
| Source fidelity | 0.917 | **0.833** (40/48) |
| Fidelity, non-synthesis, 95% CI | 0.933 [0.851, 1.0] | 0.851 [0.717, 0.957] |
| Alignment recall | 0.778 | 0.778 |
| Pali exact / variant / fabricated | 6 / 0 / 1 of 7 | 8 / 3 / **0** of 11 |
| Quote coverage rate | 0.85 (n=6) | 0.807 (n=11) |
| Provenance errors | 6/48 | 2/48 |

\* No claim in this sample is gold `synthesis`, but one (q037#0) is
*tagged* synthesis. That gives the class F1 = 0 with support 0, which
`aggregate_generation.py` averages into macro-F1. The three-class figure is
the one comparable with August.

**What the judging found:**

- **Verse quotes attached to story sentences.** q067#0, q073#0 and q079#0
  each carry a real, correct `pali_support` of the verse (exact or variant)
  on a sentence that narrates the vatthu. The Pali makes the claim look
  verse-grounded while its text is commentary. That is anachronistic
  conflation with a quote attached as cover, and it accounts for three of
  the four conflations. A fourth, q019#1, presents the 8.3 vatthu's "robbers
  that are his own pollutants" as what "the Dhammapada also states" of
  Dhp 103.
- **Semantic-neighbour conflation came back on q043.** The model says the
  verse was spoken "to Māgandiya's daughters" who tried to tempt the
  Buddha. The nidāna says it was spoken about the daughters of *Māra* and
  repeated to the Brahmin *Māgandiya*. This is round 7's q043 error,
  absent in round 8 and present again. Round 8's q099 "Aggidatta" name
  migration did not recur.
- **Retrieval failures now produce confident false anomalies.** q119
  names "Dhp 85, 86" as the verse with two stories (the answer is Dhp 416:
  26.33 and 26.34). q120 claims 26.21's header misstates its verse as 403,
  but the raw header reads "Dhp 404"
  (`data/raw/dhammapada-attakatha.txt` l.41523). The real typo is 26.17's
  "Dhp 40" for 400 (l.41344). Round 8's answers to the same two questions
  described the wrongly retrieved story neutrally.
- **Philological glosses fail on text outside the excerpt.** q037 lists
  the four knots as "sorrow, the fetters…, suffering", words lifted from
  Dhp 90 itself, while the verse note names the actual four ganthas.
  q055 glosses *akata* as Arahatship where the note says Nibbāna.
- **Fixed or not recurring:** no fabricated Pali (0/11), the round-8
  q085 self-contradiction is gone, q055's term substitution is fixed (the
  gloss is right and the referent wrong), and `CITATION_IN_TEXT` fell from 4
  to 2 claims. The two remaining (q097#0, q037#1) are the space-separated
  `group_id 25.5` form that Round 9 Task AG widened the check to catch.
- **A source inconsistency, not a model error:** 6.11's title says "Five
  Hundred Visiting Bhikkhus" (CST4 *Pañcasata-*), while its nidāna and
  synopsis say "fifty".
- The round-9 truncation warning fires on three genuine half-quotes
  (q031 34%, q043 26%, q067 32% of the verse).

## Round 10: a harder gold set unmasks the reranker (2026-09-24/25)

`docs/status_report.md` §8 called v1 (114 scored questions) saturated:
baseline R@10 0.9825, and two of four ablations (`dense_only`, `no_rerank`)
had confidence intervals spanning zero -- undetectable, not necessarily
absent. Gold set v2 (`data/eval/build_gold_set_v2.py` ->
`gold_set_v2.jsonl`) adds 72 questions across six categories designed to be
harder than v1's (narrative_deep, paraphrase, pali_ascii, disambiguation,
multi_gold, situation_to_verse). v1 is unchanged and still reported
alongside it, not replaced. Both eval runs in this section are against the
same CUDA-rebuilt index (`"machine": "cuda (NVIDIA GeForce RTX 5080)"`, now
recorded directly in `retrieval_metrics.json` and `retrieval_metrics_v2.json`
by `aggregate_retrieval.py`, since v1's own numbers already moved slightly
between the Mac/MPS build and this one and a future reader should be able to
tell why without re-deriving it).

**The reranker result is the headline.** On v1 the cross-encoder rerank
stage was a null result: `no_rerank` delta +0.0195 nDCG@10, CI
[-0.0071, +0.0468] -- spanning zero, so v1 could not distinguish "the
reranker helps" from "the reranker does nothing." Same code, same model
(`bge-reranker-v2-m3`), run on v2's 72 harder questions: **+0.116
[+0.056, +0.179]**, an interval clear of zero. This is the cleanest
demonstration in the project that v1's null ablations were a property of
the question set being too easy, not of the components being inert -- the
reranker was doing real work all along that v1 could not see.

**Two ablations are still null on v2, and are reported as null rather than
omitted:**

| Ablation | v1 delta [CI] | v2 delta [CI] |
|---|---|---|
| `dense_only` | +0.0016 [-0.0076, +0.0101] | +0.0222 [-0.0113, +0.0625] |
| `no_rerank`  | +0.0195 [-0.0071, +0.0468] | **+0.1160 [+0.0563, +0.1787]** |
| `flat`       | +0.0029 [+0.0000, +0.0076] | **+0.0000 [+0.0000, +0.0000]** |

`dense_only` stays indistinguishable from zero even on the harder set:
adding sparse and ColBERT to the RRF fusion on top of dense retrieval buys
nothing measurable, at either difficulty level. `flat` goes from a
marginal, barely-nonzero delta on v1 to an *exact* zero on v2 -- parent-group
assembly (deduping ranked chunks into story/verse bundles) never changes
which bundle contains the first relevant hit, on either gold set. Read
together with the reranker result above, the implication is specific, not
generic: harder questions were enough to unmask the reranker's real effect,
but they did not unmask any effect from the extra fusion arms or from
assembly. On the current evidence, RRF fusion beyond dense and the
parent-group assembly step are complexity the pipeline is carrying without
a measurable retrieval-quality return; the reranker is not.

**`paraphrase` is the weak stratum, and it is diagnostic.** Of v2's six
categories it scores lowest (nDCG@10 0.824, next-lowest `pali_ascii` at
0.886, the rest 0.928-1.000), and it is the category *least* affected by
removing commentary/story chunks (`verse_only` delta +0.017, smallest of
the six -- multi_gold and narrative_deep both drop by roughly 0.9). That
rules out the commentary layer as the cause: paraphrase questions' gold is
already verse-anchored and reachable without it, so the gap is the
retriever failing to match reworded phrasing to the verse text itself, a
lexical-surface problem rather than an architectural one. It is also the
stratum reranking helps most in absolute terms (`no_rerank` nDCG@10 0.602
vs. baseline 0.824, a 0.222 drop, almost double the next-largest per-type
drop) -- consistent with the headline finding, since a cross-encoder is
exactly the component built to survive surface rewording that breaks
lexical and even dense-vector matching.

**Bug fixed while reading these results.** Both `retrieval_eval.py` and
`aggregate_retrieval.py` printed "the load-bearing cell is the doctrinal
row" unconditionally -- correct for v1, but v2 has no `doctrinal` stratum at
all, so the same printout would have pointed a v2 reader at a row that does
not exist. Both scripts now key the note off which stratum is actually
present in the gold set being scored, printing the doctrinal note for v1
and a paraphrase-focused note (summarizing the previous paragraph) for v2.

**Still open:** the annotation sheet for a second, blind annotator
(`src/dhammapada_rag/eval/annotation_sheet.py`, built alongside v2) has not
been run by anyone. That is the next item, and the one most likely to
matter to an external reviewer -- see `docs/eval_rubric.md`'s "Annotator
status".

## Round 13: SuttaCentral material removed (2026-10-08)

On 2026-10-08 SuttaCentral's Forum Management Committee answered a licensing
question asked on their forum: their translations may not be used in any
project that uses AI. Both SuttaCentral sources left the corpus: the Pali
root text and the English translation that had filled the verse layer
alongside Ānandajoti's interlinear since Phase 1. The record of the decision
(date, ruling, link, what was removed from history and what was not) is in
`data/raw/PROVENANCE.md`. This section covers what it did to the numbers.

**The verse layer is now Ānandajoti's 2017 interlinear alone.** It already
covered all 423 verses in both Pali and English, so this was a field
reassignment, not a new ingestion. `build_verses.py` now fails if any verse
lacks either field, rather than writing a null. None did.

**Index: 5,909 → 5,486 chunks.** The two SuttaCentral verse chunk types
(423 Pali, 423 English) are gone. Ānandajoti's interlinear Pali is indexed for
the first time as `verse_pali_interlinear` (423). Every other chunk type is
unchanged. Re-embedded on CUDA (RTX 5080). All 5,486 chunks fit within the
512-token limit.

**Retrieval, both gold sets re-run on the new index.** The corpus changed,
so the numbers were expected to change. Same code, same machine, same
questions, except one v1 question reworded (below).

| v1 (114 scored) | nDCG@10 before → after | R@1 before → after | R@10 before → after |
|---|---|---|---|
| baseline   | 0.954 → 0.932 | 0.912 → 0.877 | 0.983 → 0.983 |
| verse_only | 0.526 → 0.511 | 0.500 → 0.474 | 0.553 → 0.553 |
| dense_only | 0.952 → 0.928 | 0.921 → 0.886 | 0.974 → 0.965 |
| no_rerank  | 0.934 → 0.887 | 0.877 → 0.798 | 0.974 → 0.974 |
| flat       | 0.951 → 0.929 | 0.912 → 0.877 | 0.983 → 0.983 |

| v2 (72) | nDCG@10 before → after | R@1 before → after | R@10 before → after |
|---|---|---|---|
| baseline   | 0.925 → 0.920 | 0.861 → 0.847 | 0.972 → 0.972 |
| verse_only | 0.307 → 0.312 | 0.264 → 0.264 | 0.347 → 0.361 |
| dense_only | 0.903 → 0.897 | 0.819 → 0.806 | 0.972 → 0.972 |
| no_rerank  | 0.809 → 0.806 | 0.667 → 0.667 | 0.958 → 0.958 |
| flat       | 0.925 → 0.917 | 0.861 → 0.847 | 0.972 → 0.972 |

Ablation deltas, baseline − variant, nDCG@10 [95% CI]:

| Ablation | v1 before | v1 after | v2 before | v2 after |
|---|---|---|---|---|
| `verse_only` | +0.427 [+0.338, +0.522] ✱ | +0.421 [+0.331, +0.515] ✱ | +0.618 [+0.502, +0.726] ✱ | +0.608 [+0.492, +0.715] ✱ |
| `dense_only` | +0.002 [−0.008, +0.010] | +0.004 [−0.008, +0.017] | +0.022 [−0.011, +0.063] | +0.023 [−0.005, +0.058] |
| `no_rerank`  | +0.019 [−0.007, +0.047] | **+0.045 [+0.012, +0.078] ✱** | +0.116 [+0.056, +0.179] ✱ | +0.114 [+0.054, +0.176] ✱ |
| `flat`       | +0.003 [+0.000, +0.008] | +0.003 [+0.000, +0.008] | +0.000 [+0.000, +0.000] | +0.003 [+0.000, +0.008] |

<sub>✱ interval excludes zero.</sub>

**v2 barely moved; v1's drop is almost all in one stratum, and it is a
measurement artefact.** Five of v1's six types score exactly what they
scored before. All of the movement is in `doctrinal` (nDCG@10 0.942 → 0.859,
R@1 0.900 → 0.767). Six doctrinal questions changed rank (q008, q012, q013,
q016, q019, q025), and their wording explains why: they were written against
the SuttaCentral English and reuse its vocabulary ("supreme conqueror",
"astute", "mendicant"). With that translation gone from the index, those
words have nothing to match. The gold set was constructed from a translation
the index no longer holds. Ānandajoti's renderings use different words for
the same verses (Dhp 258: "wise", not "astute"), so this is not evidence that
retrieval got worse at doctrinal questions. In v2, whose questions were not
written that way, the only stratum that moved is `pali_ascii` (0.886 →
0.855): ASCII-folded Pali queries had been matching the removed edition's
unhyphenated orthography.

**The reranker is now visible on v1 too.** `no_rerank` on v1 went from a
null result (CI spanning zero) to +0.045 [+0.012, +0.078]. The change is
entirely in `doctrinal`: its baseline − `no_rerank` gap went from 0.072 to
0.168, and every other type's gap is identical to before. Without the
SuttaCentral wording to match, first-stage retrieval ranks the doctrinal gold
lower, and the cross-encoder recovers much of it (`no_rerank` doctrinal 0.691
against a baseline of 0.859). The Round 10 conclusion (the reranker does real work; v1 was too easy to show
it) now holds on both sets. `dense_only` and `flat` stay null on both, as
before.

**The doctrinal verse-only finding survives, smaller.** `verse_only` still
beats the full system on doctrinal questions: 0.881 against a baseline of
0.859 (Δ −0.022, was −0.046). Commentary retrieval still does not help
verse-anchored questions.

**One gold question reworded, one note.** v1's q006 (Dhp 89) reused nine
consecutive words of the SuttaCentral translation. It now reads "What does the Dhammapada say about
those who have developed the factors of awakening and given up grasping?" The
same change is applied wherever the question was stored
(`build_gold_set.py`, `gold_set.jsonl`, the archived pre-fix copy,
`tag_stability.py` and its results file). It ranks first before and after,
so it does not contribute to the doctrinal drop. A five-word-shingle scan of
both gold sets against all SuttaCentral text found no other question that
reuses its wording verbatim. One annotator note (q007, Dhp 98) quoted it and
now quotes Ānandajoti instead. Notes are not sent to retrieval, so no number
depends on it.

**Corpus checks.** Validation gate 6 and audit check 4 (cross-edition Pali
agreement) are retired: they compared the SuttaCentral Pali with
Ānandajoti's, and one edition cannot disagree with itself. Gate 3 and check
3 (Pali character set) now run on the interlinear Pali, with the allowed set
widened to Ānandajoti's breve vowels (ĕ, ŏ) and the punctuation he uses (en
dash, colon, ?, !, parentheses). Those were measured as the only characters
outside the old set, and every hard gate passes. Gate 5 (metre, warn-only)
now flags 56 of 1,454 segments, where it flagged 0 on the old field. That is
not damage: Ānandajoti often leaves a pāda boundary unpunctuated, so two
pādas read as one segment. Audit check 5 (each story's quoted Pali against
the verse record) went from 98 distinct of 226 to **0 distinct**. Ānandajoti's
2024 commentary quotes and his 2017 interlinear agree on every verse both
contain (217 exact, 9 partial "teaser" quotes). Before, this check had been
comparing his quotes against the other editor's text.

**Stored records of earlier runs.** The research-validation grid, tag
stability and the model sweep were not re-run. They describe the pipeline as
it was, when the prompt carried the SuttaCentral Pali and English for every
retrieved verse and the PALI SUPPORT rule asked the model to copy from the
SuttaCentral Pali line. Their stored records (the three
`research_validation_*.jsonl` files, `tag_stability_results.json`, and the
two older `generation_raw.jsonl` archives) have had every SuttaCentral string
replaced with the marker `[SuttaCentral text removed 2026-10-08]`. That covers
full verse texts and any verbatim span of 30 or more characters, including
model outputs quoting them. The source labels in the stored prompts and
warnings (the edition and translator names, and the two field names) now read
"SuttaCentral". Nothing else in those records changed, and their metrics
stand as a record of that pipeline.

**Generation, re-run on the new prompt (2026-10-08).** The previous run, its
judgments and its metrics are archived in
`data/eval/archive_round12_with_suttacentral/`. A fresh run used the same
27-question systematic sample, seed, model (`qwen2.5:7b-instruct`, num_ctx
16384) and annotator procedure: every claim re-judged from scratch against
the full stored source text (`data/eval/generation_judgments.py`).

| Metric | Before (SuttaCentral in prompt) | After |
|---|---|---|
| Claims | 48 | 49 |
| Layer accuracy | 0.854 | 0.837 |
| Macro-F1 | 0.628 | 0.773 |
| Anachronistic conflation | 4/40 = 0.100 | 3/38 = 0.079 |
| Source fidelity | 40/48 = 0.833 | 42/49 = 0.857 |
| Source fidelity, verse+commentary+alignment [95% CI] | 0.851 | 0.884 [0.762, 0.977] |
| Pali quotes copied exactly | 8/11 = 0.727 | **11/11 = 1.000** |
| Pali quotes in another edition's orthography | 3/11 = 0.273 | 0/11 |
| Pali quote coverage | 0.807 | 0.863 |
| Alignment recall | 0.778 | 0.556 |

**One clear effect: the Pali quotes.** With two Pali editions in the prompt,
three of the model's eleven Pali quotes were Ānandajoti's orthography where
the rule asked for the other edition's line: real text, wrong copy. With one
edition, all eleven are exact copies. The Round 6 three-tier check was built
to tell those cases apart. Simplifying the context removed the case.

**The rest is within what 27 questions can show.** Macro-F1 rises mostly
because the previous run had no synthesis claims at all: that class scored 0
on zero support and pulled the average down. It is not a real improvement.
Accuracy, conflation and fidelity move by one or two claims each. Alignment
recall fell because three alignment facts were tagged 'synthesis' (q097,
q099, q120), a tagging pattern not seen before.

Errors carried over from earlier rounds: conflation on q019, q067 and q079,
the Māra/Māgandiya merge on q043, and fabricated anomalies on q119 and q120.
Fixed: q093's count of bhikkhus, q037's speaker, and q055's gloss of *akata*.

Two new findings:

- **q001 dismissed its own answer.** Retrieval put the gold story (1.8,
  Dhp 11) at rank 1. The model marked it `not_relevant`, answered from Dhp 347
  instead, and then claimed Dhp 347 teaches the question's point. This is the
  first logged case of the disposition field recording a generation
  misjudgment on a gold group.
- **The generation prompt never shows the interlinear notes.** The four knots
  asked about in q037 are listed only in Ānandajoti's note on Dhp 90, so the
  model's "not explicitly stated" is accurate to what it was shown. The same
  gap affects every philological question whose answer lives in a note. That
  is a design choice in `prompt.py`'s [VERSE] block, worth revisiting.

**Annotation sheets.** The blind second-annotator sheets
(`annotation_v2_blank.csv`, `annotation_v2_sample30.csv`) showed each
candidate's verses in the SuttaCentral English. That column now shows
Ānandajoti's English. Questions, candidates and row order are unchanged, so
the κ calibration point in `docs/eval_rubric.md` still applies.

## Round 14: a fifth layer for the editor's notes (2026-10-08)

Round 13 found that the generation prompt never showed Ānandajoti's
interlinear notes. A question whose answer lives in a note (the four knots
of Dhp 90; what *akata* means in Dhp 383) could not be answered. The notes
are a modern editor's philological work, neither the verse nor Buddhaghosa,
so they could not simply go into the `[VERSE]` block. That would invite the
model to present a note as the verse. Filing them under `commentary` would
attribute them to Buddhaghosa. They get their own layer, `note`
(`docs/eval_rubric.md`, "The fifth layer").

**What changed.**

- `schemas.py`: a `NoteClaim` (`layer="note"`, `verse_number` only, since a
  note belongs to a verse, not a story).
- `audit()`: a new error, `NOTE_NOT_IN_CONTEXT`, for a note claim citing a
  verse with no note in the retrieved context.
- `generate.py`: the decoder's `verse_number` enum is limited to retrieved
  verses that have notes, and the `NoteClaim` variant is dropped from the
  schema when none do.
- `prompt.py`: a `[NOTES]` block per source, and the layer added to
  TAGGING, CITATIONS and OUTPUT DISCIPLINE.
- `render.py`: note claims read "The editor's note explains …", cited
  "[Dhp N, note]".
- The web app has the fifth layer and colour; 13 new tests
  (`tests/test_note_layer.py`). The Round 13 run is archived in
  `data/eval/archive_round13_before_notes/`.

**Generation, re-run and re-judged from scratch.** Same 27 questions, seed,
model and index.

| Metric | Round 13 | Round 14 |
|---|---|---|
| Claims | 49 | 52 |
| Layer accuracy | 0.837 | 0.769 |
| Macro-F1 (5 classes) | 0.773 (4 classes) | 0.712 |
| Anachronistic conflation | 3/38 = 0.079 | 2/39 = 0.051 |
| Source fidelity | 42/49 = 0.857 | 39/52 = 0.750 |
| Source fidelity, cited layers [95% CI] | 0.884 [0.762, 0.977] | 0.761 [0.615, 0.889] |
| Pali quotes copied exactly | 11/11 | 11/11 |
| `note` precision / recall | — | 1.000 / 0.400 (n=5) |

**The layer does what it was added for.** The two questions whose answer
is in a note are answered from it, correctly tagged, and verbatim-faithful:
q037 names the four knots, which Round 13 said were "not explicitly stated",
and q055 glosses *akata* as Nibbāna. Both `note` claims are correct
(precision 1.000).

**It also makes a new error visible.** Three claims carry note content
under the wrong tag. q043#0 gives the note's gloss (padāni = "the states of
craving") as what the verse says. q013#1 and q043#1 present note content as
"the commentary". The content of all three is accurate to the note, so
without the fifth layer they would have scored as correct verse and
commentary claims. Recall 0.400 is how often the model reaches for the new
tag; it is the alignment layer's Round 7 problem again (recall 0.500 when
first added), and its Round 8 fix (structure, not instruction) is the
obvious next thing to try.

**The fidelity drop is not attributable to the notes.** Fidelity fell from
0.857 to 0.750, but most of the new errors are on questions with no note in
context:

- q113: a CST4 title that does not exist, correct in every earlier round;
- q114: the wrong person in the nidāna;
- q019: Dhp 258's "astute" merged into Dhp 259;
- q031: Dhp 2's story credited to Dhp 1's;
- q037#1: who healed whom, reversed.

The system prompt changed, so every one of the 27 prompts changed, and at a
fixed seed a 7B model's answers move with its prompt. The two intervals
overlap. This reads as the run-to-run spread of the generator on a
27-question sample, which every earlier round's single run has also
carried and never measured. Measuring it is the step that would make any
of these generation comparisons trustworthy: the same configuration run
under several seeds, judged the same way.

## Round 15: how much does wording alone move the generation numbers? (2026-10-08)

Round 14's fidelity fell from 0.857 to 0.750. Most of the new errors were on
questions with no note in context, so the note layer could not explain them.
Every round's generation comparison has rested on one run per
configuration, and none has measured how much a run moves for reasons
unrelated to the change being tested. This round measures it.

**Repeat runs barely move.** Generation runs at temperature 0, so the seed
does nothing. The planned "several seeds" check would have measured nothing,
and was replaced. Re-running the exact Round 14 configuration gave 25 of 27
answers word-for-word identical, and the other two differed by a few words
(`data/eval/prompt_sensitivity/rerun_identical.jsonl`). At a fixed prompt,
noise is negligible.

**Wording does move them.** The Round 14 system prompt was run under three
variants, each changing a single thing and keeping every rule's wording intact:

- **A:** the rules reordered;
- **B:** headings as Markdown;
- **C:** typography only (`--` as an em dash, `->` as an arrow).

The variant files and runs are in `data/eval/prompt_sensitivity/`. All 122
new claims were judged from scratch under the Round 14 rules
(`judgments.py` there); a claim identical to one already judged reused its
verdict. Scored by `eval/prompt_sensitivity.py`, with the same metric
definitions as `aggregate_generation.py`:

| Run | Claims | Accuracy | Macro-F1 | Conflation | Fidelity | Note recall |
|---|---|---|---|---|---|---|
| Round 14 prompt | 52 | 0.769 | 0.712 | 0.051 | 0.750 | 0.40 |
| A, reordered | 57 | 0.772 | 0.679 | 0.047 | 0.842 | 0.43 |
| B, Markdown | 50 | 0.800 | 0.690 | 0.051 | 0.780 | 0.29 |
| C, typography | 53 | 0.717 | 0.628 | 0.073 | 0.755 | 0.29 |
| **Range** | 50–57 | **0.717–0.800** | 0.628–0.712 | 0.047–0.073 | **0.750–0.842** | 0.29–0.43 |

**What this changes.**

- **Round 14's fidelity drop is within the wording spread.** Fidelity moves
  by up to 0.09 when nothing but the wording changes. Round 13 → 14 moved it
  by 0.107, through a prompt change that also altered the wording. This run
  cannot attribute that drop to the notes, and neither could Round 14.
- **The same holds for every earlier single-run comparison of the
  generator.** On this 27-question sample, a difference smaller than about
  0.08 in layer accuracy or 0.09 in fidelity between two prompts is not
  distinguishable from rewording noise. That covers several "small" movements
  reported in Rounds 7–14, which are better read as no evidence either way.
  The large, structural results are not affected:
  - Round 5's decoder-enforced citations (errors unrepresentable, not rarer);
  - Round 8's 0/27 → 27/27 source disposition;
  - Round 13's 8/11 → 11/11 exact Pali copies, a mechanism (one edition in
    the prompt) rather than a rate;
  - the retrieval ablations, which are deterministic.
- **Specific behaviours depend on wording too.** q001's retrieved gold verse
  (Dhp 11) was dismissed under two of the four wordings and used correctly
  under the other two. q043's note gloss was tagged `note` in none of the four
  runs: verse, commentary or synthesis every time. That is a stable failure
  worth fixing, unlike most of the movement above.
- **The note layer's effect is the stable part.** Every run answered q037 and
  q055 from the notes. All 9 claims tagged `note` across the four runs are
  correct (precision 1.00 under every wording). The misattribution of note
  content also appeared in every run, and note recall (0.29–0.43) is low under
  every wording.

**For future rounds:** compare generation configurations across several
wordings, not one, and report the range. A change is real when it moves the
range, not a single run. `--system-prompt` on `generation_metrics.py` and
`eval/prompt_sensitivity.py` exist for that.

## Round 16: restructuring the notes block (2026-10-08)

Round 15 left the note layer with low recall under every wording
(0.29–0.43). The model drew on the editor's notes but tagged them `verse`,
`commentary` or `synthesis`. The alignment layer had the same problem when it
was added (recall 0.500, Round 7). Round 8 fixed it with structure, not more
instructions: its own block, a header saying what it is, and a
`<<citation_fields>>` marker carrying the citation beside the text. That
took recall to 0.778. This round applies the same fix to the notes.

**What changed, and what didn't.** `format_verse_group()` now opens the
block with "[NOTES -- Ānandajoti Bhikkhu's modern editorial notes, neither
verse nor commentary; a claim drawn from them is a "note" claim]" and puts a
`<<citation_fields layer=note verse_number=N>>` marker before each verse's
notes. The system prompt is unchanged, so Round 15's three wordings still
apply. The comparison is four runs against four runs, same wordings, with
only the block different (`data/eval/note_block/`; 104 new claims judged
from scratch, `judgments.py` there).

| | Note block v1 (Round 15) | Note block v2 (Round 16) |
|---|---|---|
| Note recall, pooled | 9/26 = 0.35 | 11/23 = 0.48 |
| Note recall, range over wordings | 0.29–0.43 | 0.33–0.60 |
| Note recall, paired by wording | | higher in **4 of 4** |
| Layer accuracy, range | 0.717–0.800 | 0.764–0.833 |
| Source fidelity, range | 0.750–0.842 | 0.818–0.878 |
| Conflation, range | 0.047–0.073 | 0.022–0.075 |

**Reading it.** Note recall rose under every wording, which no single-run
comparison could have shown. The counts are small (5–7 note claims per
run), so this is consistent evidence of a modest gain, not a large one.
Accuracy and fidelity also moved up on average, but their ranges overlap
Round 15's, and nothing in the change should affect fidelity, so neither is
claimed.

**What did not move.** q043's note gloss (padāni = "the states of craving")
was still never tagged `note`, under any wording. It is answered from the
note every time, under one of the other four tags. That is now 8 runs out
of 8, a fixed behaviour of this model on this question, and the clearest
remaining target.

**A check for what the prompt doesn't prevent.** `audit()` gains
`NOTE_TEXT_AS_OTHER_LAYER` (error), the note-layer counterpart of
`VERSE_TEXT_AS_COMMENTARY`. It flags a non-note claim whose content words
come mostly from a retrieved note, when the claim overlaps the note more
than the verse. The threshold, 0.50, was set from the Round 15 judgments:
it caught 6 of 17 mis-tagged note claims there, with no false alarm among
the other 159. In the Round 16 runs it fired 3 times, all correct, out of
12 mis-tagged note claims. Like the verse check, it catches near-verbatim
copying only. Paraphrase still needs a human judge. Audit errors do not
trigger a regeneration, so the check did not change any answer measured
here.

## Round 17: facts about the edition, and a story assembly dropped (2026-10-08)

The two `corpus_anomaly` questions had failed retrieval in every round
since the gold set was built: which verse has two stories (q119), and which
story's header misstates its verse (q120). Every answer then invented an
anomaly for whatever was retrieved. Both answers were already in the repo:

- the two-story verse (Dhp 416: 26.33 and 26.34) is what the alignment
  table's duplication check reports;
- the header typo (26.17's "Dhp 40" for Dhp 400) is one of the six entries,
  with evidence, in `ingest/corrections.py`.

No indexed text stated either. This is the gap Round 2 found for verse
numbering, a third time: the corpus has the fact, the index never says it.

**Two changes.**

1. **Corpus facts as text.** `index/corpus_facts.py` turns those two
   sources into sentences, generated rather than written by hand. Examples:
   "Dhp 416 is explained by 2 separate commentarial stories: story 26.33 …
   and story 26.34 … It is the only verse in this edition explained by more
   than one story"; "Story 26.17's header line in the source, as extracted,
   reads Dhp 40, but the verses quoted in the story's own body are Dhp 400
   …". They are indexed as a new chunk type, `story_corpus_fact` (8 chunks;
   5,486 → 5,494), and shown as "Corpus note:" lines in that story's
   `[ALIGNMENT]` block. They are structural facts, stated by neither the
   verse nor the commentary. The wording says only what is recorded: for
   26.34, `corrections.py` cannot tell whether "Dhp 416408" is a source typo
   or an extraction glitch, so no sentence blames the source.
2. **An assembly bug, found by the first change.** With the facts indexed,
   q120 reached rank 1 but q119 still missed, while the `flat` condition,
   which skips assembly, ranked its answer 2nd. A chunk from a story
   resolved to that story alone, and `query()` deduplicates bundles by verse
   range. Dhp 416's two stories share one range, so whichever ranked first
   kept the slot and the other could never be returned at any rank. That
   contradicts `assemble.py`'s own docstring ("every story that explains
   them"). A story chunk now brings every story explaining its verses,
   matched story first. The rule lives in one function,
   `assemble.resolve_story_ids`, which `eval/retrieval_eval.py` now imports
   instead of keeping its own copy. Only Dhp 416 is affected.

**Retrieval** (deterministic; per question, before → after):

| | Baseline rank before → after |
|---|---|
| q119 (Dhp 416, second story 26.34) | not in top 10 → **1** |
| q120 (26.17's header) | 9 → **1** |
| any other question, either gold set | unchanged (one `verse_only` rank on v2 moved from 66 to 54) |

v1 baseline nDCG@10 goes from 0.932 to 0.947, entirely from these two
questions; v2 is unchanged. The ablation deltas moved slightly, by the same
two questions (README table updated).

**Generation, under the same four wordings.** Only prompts whose sources
include one of the seven stories with a fact changed, so only q119, q120
and one reworded q091 claim needed new judgments
(`data/eval/corpus_facts/`).

| | Round 16 (4 wordings) | Round 17 (4 wordings) |
|---|---|---|
| q119: names Dhp 416 | 0 of 4 | **4 of 4** |
| q119: names the second story (Jotika, 26.34) | 0 of 4 | 1 of 4 |
| q120: names 26.17 (Dhp 40 for 400) | 0 of 4 | **3 of 4** |
| Source fidelity, range | 0.818–0.878 | 0.865–0.898 |
| Layer accuracy, range | 0.764–0.833 | 0.741–0.845 |

**Reading it.**

- **The gain is real but partly circular.** The two questions were written
  from these same facts, so answering them is near-tautological. The lasting
  change is that a question about the edition's structure is now answered
  from a stated fact instead of an invented one; before this round, every
  answer to either question was a fabrication.
- **Two remaining errors are informative.** Three of four runs name Jaṭila
  (26.33) as the "second" story: the fact lists the stories in order but
  never says which is first, and the model guessed. The fact's wording is
  not being tuned to the question's phrasing; that would be fitting the
  test. The fourth q120 run names 3.1, whose header ("Dhp 33" for 33–34) is
  genuinely wrong too. The question assumes a single answer, but the corpus
  has six corrected headers.
- **Fidelity rises across all four wordings,** almost entirely because these
  answers stopped fabricating. Accuracy's range overlaps Round 16's, so no
  accuracy change is claimed.

**The canonical generation run is now the current system.** Until this
round, `generation_raw.jsonl` and the metrics the dashboard reads came from
Round 14, before the Round 16 and 17 changes. The Round 17 base-prompt run
replaces it; the Round 14 run is archived in
`data/eval/archive_round14_note_layer/`. Its verdicts are not new: each
claim's verdict is the from-scratch one already given to the identical
claim in Rounds 14–17, assembled with its original note into
`generation_judgments.py`. The canonical metrics reproduce the scorer's
figures for that run: accuracy 0.741, conflation 3/40 = 0.075, fidelity
47/54 = 0.870 (cited layers 0.878, 95% CI [0.755, 0.962]), Pali quotes
copied exactly 12/12, `note` recall 3/6. As Round 15 showed, these are one
wording's numbers; the four-wording ranges above are the better guide.

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
- (Round 4) Requiring commentary engagement to fix all-verse output induces
  a mirror-image failure, verse text relabelled as commentary, at a
  measured 3/24 (12.5%) rate among tag-stability groups with more than one
  member -- fixable with an explicit prompt escape hatch and mechanically
  detectable (post-fix) for the near-verbatim case, but not for paraphrase.
- (Round 5) Malformed, invented, and not-retrieved `group_id`/`verse_number`
  values (`MALFORMED_GROUP_ID`, `UNPARSEABLE_GROUP_ID`, `UNKNOWN_GROUP_ID`,
  `GROUP_NOT_RETRIEVED`) are structurally unreachable once citation fields
  are constrained to an enum built from the retrieved context at request
  time -- re-verified at zero occurrences on the two worst-offending probes
  from the pre-fix format-compliance table. Citation *completeness* (the
  model choosing to leave a field null) is a separate failure the decoder
  cannot constrain against, and persists.
- (Round 5) The "purpose of life" retrieval failure is not the RRF-arm
  imbalance it was hypothesized to be -- all three retrieval arms
  independently converge on the same wrong answer, a single colophon chunk
  that lexically resembles almost any abstract-concept query. A predicted
  mechanism (sparse dominating fusion) turned out to be the wrong
  diagnosis; the actual cause (a structural, non-narrative chunk acting as
  a universal attractor) is a different and more direct fix target.
- (Round 6) A binary Pali-quote match/fabricate check was measuring the
  wrong thing: two flagged quotes were a different edition's orthography of
  the *correct* verse, reaching the model's own context via each story's
  narrative text, not memorized or invented. The three-tier replacement
  (exact / orthographic-variant / fabrication) separates "knows the text,
  quoted a different edition" from "invented a quote" -- confirmed live on
  this machine, not just by construction: a real `/answer` call produced an
  exact edition-variant match (`PALI_QUOTE_ORTHOGRAPHIC_VARIANT`, warning)
  on the same class of quote Round 5 would have scored as a fabrication
  error.
- (Round 6) This machine's actual latency bottleneck is retrieval, not
  generation -- Ollama confirmed at 100% GPU throughout a live call (2.9s),
  against an 18s wall-clock total, because the project's `.venv` has a
  CPU-only torch build despite the machine having an NVIDIA RTX 5080.
  `best_device()`'s CUDA/MPS/CPU selection is correct given the installed
  build; the build itself is the fix, and is out of scope for a code round.
- (Round 7) A fourth layer for corpus-structure facts (`alignment`) is never
  misapplied once added (precision 1.000) but is still under-used on
  exactly the query types it targets (recall 0.500) -- the tag existing is
  necessary but not sufficient; getting the model to reach for it reliably
  is unfinished work. The `COMPLETENESS` prompt instruction moved the
  layer-count distribution in the right direction (single-layer answers
  15/27 → 12/27 on an identical sample) without closing it, and context
  utilization -- a new metric this round -- shows why: 0/27 answers account
  for every retrieved group, and the model never once explicitly dismisses
  an irrelevant one, it just omits it. Two more source-fidelity errors
  (correct layer, real citation, false content) turned up in ordinary
  sampling, not targeted probing, reinforcing Round 5's Kisā Gotamī finding
  that this failure class is a recurring property of the system, not an
  isolated anecdote.
- (Round 8) Rendering alignment facts in their own prompt block (not just
  giving them their own tag) moved recall from 0.500 to 0.778 on an
  identical sample, past the brief's own threshold for treating the
  prompt-level fix as sufficient -- confirms that Round 7's under-adoption
  was substantially a *where information sits* problem, the same lesson
  Task K established for citation format one level down. A required,
  decoder-constrained `source_disposition` field replaced an inferred
  utilization metric that measured 0/27 with a direct one that separates
  retrieval noise from generation misjudgment: 0 of 42 dismissals this
  round land on a gold group, meaning every observed dismissal was
  retrieval noise correctly caught, not a real source wrongly thrown away.
  A full 114-question sweep found RRF's k barely matters on this gold set
  (ceiling effects dominate) and that score-based fusion, despite a sound
  arithmetic argument for why it should help, does not beat RRF here in
  practice -- a negative result for the alternative fusion method, reported
  as one rather than reframed as a win. Semantic-neighbour conflation, named
  this round, was confirmed live in ordinary sampling (a name migrating from
  a dismissed neighbor) and refined by a designed test that did NOT
  reproduce it: the trigger is adjacency combined with an under-specified
  distinguishing detail, not name-or-role adjacency by itself.
- (Round 9) Substring matching said whether a Pali quote was real, not
  whether it was the verse: a half-verse passed clean. Measured coverage
  (0.807 mean over 11 quotes, 2026-09-23 run) now distinguishes the two.
  Scope-widening is reduced by the prompt rule but not eliminated, and has
  no structural check. Across rounds, each error class became measurable
  only once the one before it was fixed (see "The error profile moves once
  each class is fixed").
- (Round 10) v1's null ablations were an artifact of a saturated gold set,
  not evidence the components are inert: on the harder v2 set, the
  reranker's effect becomes measurable (+0.116 [+0.056, +0.179] nDCG@10,
  vs. a CI spanning zero on v1), while `dense_only` and `flat` stay null on
  both sets -- RRF fusion beyond dense and parent-group assembly still show
  no measurable return even under a harder test. The weakest v2 stratum,
  paraphrase, is barely affected by removing commentary (smallest
  `verse_only` delta of six), isolating a lexical-surface retrieval gap
  rather than an architectural one.

**What it does not support, and where the honest gaps are:**
- The brief's specific prediction that the doctrinal row would show the
  "real evidence" for the verse-only ablation is not borne out — doctrinal
  does not drop when commentary chunks are removed, on this gold set.
- Citation-format correctness (canonical `group_id` vs. a plausible-looking
  substitute like a bare verse number) remains imperfect and
  question-dependent even for the 7B model, as shown by both the aggregate
  27-question sample (5/53 provenance errors) and the live Kisā Gotamī
  re-verification above.
- Same construction-from-known-answer caveat as pre-fix: absolute numbers
  are an optimistic ceiling relative to real user queries; relative
  comparisons (ablation deltas, by-type breakdown) remain more trustworthy
  than absolute numbers.

**Highest-leverage next steps:**
1. ~~A structural fix for `alignment`-type retrieval (verse-grouping
   membership isn't carried by any single indexed field the way a title
   string is)~~ -- addressed: `index/chunks.py`'s `story_alignment` chunk
   type (one templated sentence per story naming its verse numbers, 305 new
   chunks) makes grouping membership retrievable as text the same way
   `story_titles` fixed cross_recension. `alignment` now scores a perfect
   1.000 nDCG@10 on the full 14-question bucket (was 0.581). See "By query
   type" above.
2. ~~Wire `q["subtype"]` through `retrieval_eval.py`'s output rows so
   `by_subtype` is actually populated.~~ -- done; see "`by_subtype` is now
   populated" above.
3. ~~Investigate why citation-format correctness degrades specifically when
   multiple verse-groups sharing a similar theme are retrieved together~~ --
   addressed by Round 5's Task K: constraining `group_id`/`verse_number` to
   an enum of the retrieved context makes the *format* failure this item
   was about unrepresentable regardless of cause. The Kisā Gotamī
   re-verification's specific failure (citing `verse_number=287` with
   `group_id="8.13"`, a real citation stitched from the wrong source) is
   `VERSE_GROUP_MISMATCH` -- the one citation error Task K's per-field
   constraint cannot prevent (see `docs/generation.md`'s Round 5 section) --
   and remains open, worth a fresh re-verification with the constrained
   schema in place.
4. A second, independent human annotation pass, to compute the real
   Krippendorff's α/Cohen's κ this document still does not claim.
5. (Round 4) Extend `VERSE_TEXT_AS_COMMENTARY` beyond near-verbatim overlap
   to catch the paraphrase case (Dhp 89 above cleared the threshold only
   because half the verse's own vocabulary survived the paraphrase; a
   heavier rewording would not) -- likely needs a semantic-similarity check
   against the verse embedding rather than a lexical containment measure,
   trading the current check's zero-annotator-needed auditability for
   recall on rephrased verse content.
6. (Round 5) Exclude or down-weight the colophon chunk (story group_id
   `26.40`'s enumeration-of-chapters content) from retrieval -- it is a
   structural artifact of the source document, not narrative content that
   answers any real question, and Task M found it dominating multiple
   unrelated conceptual queries across every retrieval arm. Try this
   *before* any RRF reweighting: the diagnosis found a specific bad chunk,
   not a systematically miscalibrated fusion formula, and removing one
   attractor chunk is lower-risk than reweighting the whole fusion for
   every future query.
7. (Round 5) Re-run `retrieval_eval.py`'s full gold-set ablations after (6),
   not before -- Task M's 10-query diagnostic sample is illustrative, not a
   substitute for the 120-question gold set, and the brief's own
   instruction not to tune before diagnosing applies equally to not
   declaring a fix validated before re-running the real eval.
8. (Round 5, done) `model_sweep.py` now records `eval_count`/
   `eval_duration_ns`/`tokens_per_second` per row and reports mean tok/s
   alongside latency in its per-model summary -- next actual sweep run
   should be read with that column, not latency alone, since Task L changed
   `SYSTEM_PROMPT` length and any future context-budget change would
   otherwise be invisible in latency alone.
9. ~~(Round 6) Reinstall this machine's `.venv` torch with CUDA support.~~
   -- done: `.venv` now has `torch==2.11.0+cu128`; `embed.py` and
   `rerank.py` both confirmed running `device='cuda' fp16=True` during the
   2026-08-06 corpus-audit re-index and eval re-run below, not just
   selectable in principle.
10. (Done 2026-09-23: 11 Pali claims measured, 8 exact / 3 variant / 0
   fabricated; see "Post-cleaning re-run" above.) (Round 6) Run a fresh `generation_metrics.py` pass and re-judge it under
   the Round 6 schema so `aggregate_generation.py`'s three Pali rates
   (exact/variant/fabrication) get a real sampled measurement instead of
   this round's live-but-unsampled confirmation. The existing
   `generation_raw.jsonl` predates `pali_support` entirely and cannot be
   reused for this.
11. (Round 6) Compare `qwen2.5:7b-instruct` and `qwen2.5:14b-instruct`
   exact-copy rates on the same probe, per the brief -- if the larger model
   copies its context where the smaller one recalls from memory, that is a
   scaling result with a specific mechanism (context-copying fidelity, not
   just citation-format compliance) behind it, not yet measured.
12. ~~Run `ingest/audit_corpus.py`'s Stage 0 checks against the rebuilt
   corpus and act on what it finds.~~ -- done (2026-08-06): see "Corpus
   audit Stage 0, run for real" above. Four narrow issues found and fixed
   (a stray control character, an over-strict Pali charset gate, two
   checker gaps that were mis-flagging correct title/body pairs, and stale
   report prose contradicting its own computed numbers); zero measurable
   retrieval effect. Items 10 and 11 above are still open.
