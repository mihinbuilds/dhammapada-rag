# Task brief — round 7: answer completeness and the alignment layer

The pipeline is working. Latency is down to 3.5–9.3s from 38–90s (GPU
migration), fuzzy name matching resolves "chakkhupala" → Cakkhupāla, and the
three-tier Pali matcher discriminated `pācenti` from `pājenti` — a single
consonant — rejecting the wrong spelling and accepting the right one in the
same answer. Log that as a worked example in `docs/evaluation.md`.

The bottleneck has moved. Answers are now too thin to demonstrate the
architecture.

| Query | Groups retrieved | Groups cited | Claims |
|---|---|---|---|
| which single story explains Dhp 4? | 3 | 1 | 1 |
| Who is chakkhupala | 3 | 1 | 1 |
| what is the dhammapada says about the life? | 3 | 1 | 3 |

"Who is Cakkhupāla?" produced one sentence: no Dhp 1, no Pali, no statement
that the verse was occasioned by him. A single-layer commentary search would
have produced identical output. The multi-layer architecture is invisible on
that query.

---

## Task T — Add `alignment` as a fourth layer

**The observation.** Asked which story explains Dhp 4, the system answered "The
Story about the Elder Thulla Tissa explains Dhp 4", tagged `commentary`.

That is not a commentary claim. The aṭṭhakathā does not say "story 1.3 explains
Dhp 4" — that is a fact about the **alignment**, editorial apparatus rather
than text. The three-layer taxonomy has no slot for it, so the model forced it
into the nearest one, which quietly corrupts the layer-attribution metric:
every structural fact counts as a commentary claim.

**Do.** Add a fourth variant to the discriminated union:

```python
class AlignmentClaim(BaseModel):
    """A statement about the corpus's editorial structure, not its content.

    Which story explains which verses, how many verses a group covers, whether
    editions differ on a grouping. These are facts about the alignment table --
    a modern editorial artifact -- and belong to neither the 3rd-century BCE
    verse nor the 5th-century commentary. Tagging them 'commentary' attributes
    to Buddhaghosa a claim he never made, and inflates the commentary layer in
    every metric.
    """
    layer: Literal["alignment"]
    text: str
    group_id: str
    verse_numbers: list[int]   # the FULL group, not a single verse
```

Note `verse_numbers` (plural). An alignment claim is about a group, and forcing
it to name one verse is what produced the next problem.

Update `LAYER_DESCRIPTIONS`, the prompt's tagging section, `render.py` (lead-in:
"The alignment table records that…"), the UI badge, and
`aggregate_generation.py`'s confusion matrix to 4×4. Existing judgments tagged
`commentary` for structural facts need re-judging — flag them rather than
silently remapping.

---

## Task U — State the full verse group

**The observation.** "Which single story explains Dhp 4?" → "The Story about the
Elder Thulla Tissa explains Dhp 4." Story 1.3 explains **Dhp 3 and 4 together**.
That pairing is the most valuable thing the alignment table knows about Dhp 4,
and it was omitted.

**Do.** Add to the prompt's DIRECT ANSWER section:

```
When answering which story explains a verse, always state the story's FULL
verse range, not only the verse asked about. "Story 1.3 explains Dhp 3 and 4
together" is complete; "Story 1.3 explains Dhp 4" omits the grouping, which is
the point of the question.
```

**Verify.** "Which single story explains Dhp 4?" names both verses. Also test
Dhp 21 (group 21–23) and Dhp 153 (group 153–154).

---

## Task V — Answer completeness

**The observation.** One claim for "Who is Cakkhupāla?" — a question whose full
answer spans all three layers.

**Do — part 1, the prompt.** Add a section:

```
COMPLETENESS. A complete answer uses the layers the question calls for.
- "Who is X?" -> who they were (commentary), the verse their story occasioned
  (verse, with pali_support), and what became of them (commentary, from the
  closing section) where the source gives it.
- "What does the text say about X?" -> the relevant verses with their Pali,
  plus at least one commentary claim giving an occasion, where one was
  retrieved.
- "Which story explains X?" -> the alignment fact with the full verse range,
  plus a one-line indication of what the story concerns.
Every retrieved source group is either cited or, if irrelevant, dismissed in a
single synthesis claim naming it. Do not silently ignore retrieved material.
```

That last sentence matters most: an uncited group should be an explicit
judgement, not an omission. It also gives you a signal the model believes the
retrieval was wrong, which is diagnostic information you currently throw away.

**Do — part 2, the metric.** Add to `eval/aggregate_generation.py`:

```python
# Context utilization: fraction of retrieved verse-groups the answer either
# cites or explicitly dismisses. A system that retrieves three groups, uses
# one, and says nothing about the others is not doing multi-layer synthesis --
# and no existing metric catches that, because every claim it does produce is
# correctly tagged and correctly cited.
utilization = (n_groups_cited + n_groups_dismissed) / n_groups_retrieved
```

Report it alongside layer attribution and source fidelity. Track claims per
answer and the layer-count distribution too — how many answers use one layer,
two, three, four. An architecture built on layer separation should be able to
show what fraction of its answers actually separate layers.

**Verify.** "Who is Cakkhupāla?" produces at least three claims spanning at
least two layers, with Pali on the verse claim.

---

## Task W — Deduplicate near-identical claims

**The observation.** Image 2 emitted two `verse` claims both citing Dhp 135
with near-identical Pali, differing mainly in one consonant (`pācenti` /
`pājenti`) — one flagged, one passed.

**Do.** In `audit()`, add `DUPLICATE_CLAIM` at warning severity: two claims in
one answer sharing a layer and a `verse_number` whose text containment exceeds
0.8. Do not deduplicate automatically — the pair here is evidence that the
model produced the same verse twice with different orthography, which is worth
seeing. Surface it, count it, leave it in.

---

## Task X — The retrieval finding now has three instances

"What does the Dhammapada say about life?" retrieved Dhp 135, which contains
*āyuṁ*. Dhp 110–115 — the "better to live one day than a hundred years…"
series, which is directly about how life should be lived — did not surface.

Prior instances: "purpose of life" → Dhp 423 ("former **lives**", "**birth's**
destruction"); an early run where every retrieved verse contained "live" or
"life".

Three clean instances of surface-token matching beating conceptual relevance.
**Run the arm diagnosis (round 5, Task M).** Retrieve top-10 four ways —
dense-only, sparse-only, ColBERT-only, RRF — for ~10 conceptual queries, and
report where the gold group ranks under each. If sparse-only reproduces the RRF
result while dense-only ranks the gold group higher, the lexical arm dominates
and the fix is weighted RRF or query-type routing.

This is a publishable result about hybrid retrieval over translated religious
text — that lexical matching on an English translation tracks the translator's
word choice rather than the source's semantics. It has been outstanding for two
rounds.

---

## Task Y — Another fidelity error, for the judgments

"Living beings desire rebirth despite the suffering it brings", tagged `verse`,
cited Dhp 135. Dhp 135 says aging and death drive beings' lives as a cowherd
drives cattle to pasture. Nothing about desiring rebirth.

Correct layer, resolvable citation, valid Pali attached, and false. Same class
as the Kisā Gotamī inversion. Add it to the judged set as `faithful: False`
and cite it in `docs/eval_rubric.md` as a second worked example — one instance
reads as an anomaly, two establish a pattern that structural checks cannot
reach.

---

## Verify after T, U, V

Run the full probe set (`dhammapada_probe_set.md`), then:

```bash
python -m dhammapada_rag.eval.generation_metrics    # re-judge; 4 layers now
python -m dhammapada_rag.eval.aggregate_generation  # 4x4 confusion matrix
python -m dhammapada_rag.eval.arm_diagnosis
```

Report context utilization and the layer-count distribution before anything
else. If most answers still use one layer, the completeness instruction did not
take and the next step is structural — a minimum-claims constraint in the
schema — rather than another paragraph of prompt.

## Do not

- Auto-merge duplicate claims. The `pācenti`/`pājenti` pair is evidence.
- Retag existing `commentary` judgments as `alignment` without re-judging.
- Add the completeness instruction and skip the utilization metric. Without the
  number you cannot tell whether it worked.
