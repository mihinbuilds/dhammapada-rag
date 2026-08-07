# Task brief — round 8: structural disposition, and the RRF mechanism

Round 7 landed. `AlignmentClaim` is correct where used (precision 1.000), the
Pali matcher discriminates single consonants, and two new fidelity errors
surfaced in ordinary judging rather than targeted probing — which is what a
working eval loop looks like.

Three results need follow-up, and one of them changes the retrieval story.

---

## Task Z — Source disposition as a required field

**The observation.** Context utilization 0.346. Zero of 27 answers explicitly
dismissed an irrelevant retrieved group, despite the COMPLETENESS section
instructing exactly that.

Zero is not a low rate. It is an instruction the model does not act on, and it
is the third consecutive round where a prompt paragraph produced marginal
movement on a structural behaviour. This is the same wall citations hit before
the enum constraint, and it takes the same fix.

**Do NOT add a minimum-claims constraint.** That produces padding — the model
elaborates rather than engaging more sources, and utilization stays flat while
claims-per-answer rises.

**Do.** Add a required field to `LayeredAnswer`:

```python
class LayeredAnswer(BaseModel):
    question: str
    claims: list[Claim]
    source_disposition: dict[str, Literal["used", "partially_relevant", "not_relevant"]] = Field(
        ...,
        description=(
            "One entry for EVERY retrieved source group, keyed by group_id. "
            "'used' = at least one claim draws on it. 'not_relevant' = it does "
            "not bear on the question. Every group must appear."
        ),
    )
```

In `_constrained_schema()`, constrain it against the retrieved set so the model
cannot omit a group:

```python
gids = sorted({s["group_id"] for b in bundles for s in b["stories"]})
schema["properties"]["source_disposition"] = {
    "type": "object",
    "properties": {g: {"enum": ["used", "partially_relevant", "not_relevant"]} for g in gids},
    "required": gids,
    "additionalProperties": False,
}
```

Add `DISPOSITION_CONTRADICTS_CLAIMS` at warning severity: a group marked
`not_relevant` that is nevertheless cited by a claim, or marked `used` and cited
by none. Then compute utilization directly from the field rather than inferring
it from citations.

**Why this is worth more than the metric.** A `not_relevant` disposition is the
model telling you retrieval was wrong on that group. You currently discard that
signal. Cross-tabulate it against the gold labels: where the model says
`not_relevant` and the gold set agrees, retrieval failed and generation caught
it; where the model says `not_relevant` and the group *is* gold, generation
failed. Those are different problems and you have not been able to separate
them.

**Verify.** Every answer carries a disposition for every retrieved group. Report
the `not_relevant` rate — if it is high, retrieval precision is the real
problem, not answer completeness.

---

## Task AA — Give alignment its own block in the prompt

**The observation.** Alignment precision 1.000, recall 0.500. Correct whenever
used; used half the time it should be. Classic under-adoption of a new label.

**Likely cause.** Check whether the verse-range information a model needs for an
alignment claim is currently rendered inside the `[COMMENTARY]` block in
`prompt.py`. If it is, the model is inferring the taxonomy from where the
information sits rather than from the tagging description — and it will keep
filing structural facts under commentary regardless of how the instruction is
worded.

**Do.** Render a separate block per source group, before the commentary block:

```
[ALIGNMENT -- modern editorial apparatus, neither verse nor commentary]
group_id 1.3 covers Dhp 3, 4 (2 verses), titled "The Story about the Elder Thulla Tissa"
```

Move the `<<citation_fields>>` marker and the covered-verse list here. The
commentary block then carries only nidāna / vatthu / desanāvasāne — the actual
aṭṭhakathā text.

The context's visual structure teaches layer separation more reliably than a
paragraph describing it. This is the same reasoning behind labelling `[VERSE]`
and `[COMMENTARY]` separately in the first place; alignment was left out.

**Verify.** Alignment recall on the same 27-question sample. If it does not rise
above ~0.75, the next step is a structural one — require an alignment claim on
questions whose type is `verse_grouping` — not another instruction.

---

## Task AB — The RRF finding is sharper than the brief predicted

**The observation.** For "what does the Dhammapada say about life?": dense finds
nothing, sparse finds it at rank 8, **fusion finds nothing**. Fusion is worse
than its best arm.

**The mechanism.** RRF scores an item as Σ 1/(k + rank) over the lists it
appears in, with k=60. An item at rank 8 in one list and absent from two scores
1/68 ≈ 0.0147. An item at rank 30 in all three scores 3/90 ≈ 0.0333 — more than
double. RRF systematically suppresses items only one arm can find, and at k=60
the penalty for absence dominates rank quality within a list.

This corrects the earlier hypothesis. The problem is not that the lexical arm
dominates; it is that **rank-based fusion with a large k penalises single-arm
discoveries**, which is precisely the failure mode when arms have uneven
coverage over a heterogeneous corpus — Pali, English translation, narrative
prose, and editorial metadata, with no arm strong on all four.

**Do, in order.**

1. **Check the gold label first.** Is there a defensible single gold group for
   this query? Dhp 110–115, 135, and 182 are all plausible. If the question is
   genuinely thematic, single-gold nDCG is the wrong instrument and it belongs
   in a multi-gold stratum — fix that before building an argument on the result.
2. **Sweep k** ∈ {10, 20, 40, 60} over the full 114-question eval, reporting
   nDCG@10 per query type. Lower k sharpens within-list rank sensitivity and
   softens the absence penalty.
3. **Try score-based fusion** as a comparison: min-max normalize each arm's
   scores and sum. Rank-based fusion discards score magnitude, which is what
   makes it blind to "found confidently by one arm".
4. Report the sweep as a table. Do not silently adopt the best k — state the
   value chosen, on what evidence, and that it was selected on the eval set
   (which means it needs a held-out check before any headline claim).

This is a publishable observation about hybrid retrieval over heterogeneous
scholarly corpora, and it is stronger than the lexical-dominance story because
it has an arithmetic mechanism rather than an intuition.

---

## Task AC — Report fidelity as a rate, and name the subtype

Four errors are now on record: the Kisā Gotamī inversion, the Dhp 135
misattribution, q001's misattributed refusal, and q043's Māra's-daughters /
Māgandiyā conflation.

**Do.** Compute source fidelity rate over verse + commentary + alignment claims
(exclude synthesis — it has no source to be faithful to), with a bootstrap CI
by question. Report it beside layer attribution and context utilization.

**Name the q043 subtype.** Māra's daughters and Māgandiyā are both women who
oppose or tempt the Buddha. That is not random confabulation — it is conflation
of narratives sharing a structural role. Call it **semantic-neighbour
conflation** in `docs/eval_rubric.md` and note that it predicts where errors
will cluster: paired ascetics, the several Tissas, the multiple stories
involving a rich man's son. A generic "hallucination" label predicts nothing.

Worth testing directly: ask about two structurally similar figures whose stories
your corpus keeps distinct and see whether details migrate between them.

---

## Task AD — Commit the work

Rounds 3–7 are uncommitted in one working tree. That is one `git checkout` from
losing several weeks, and it makes bisecting impossible when a regression
appears.

1. Reconstruct commit boundaries per round if you can; one commit per round with
   the bug numbers in the message.
2. Tag the pre-fix state (`v0-prefix`) so the before/after diff stays
   recoverable.
3. Record the git commit hash in every eval output JSON. When the paper asks
   which corpus and code version produced a number, that field is the answer.

---

## On 0/27 four-layer answers

Round 7's write-up treats this as a shortfall. It probably is not. Four layers
in one answer means verse + commentary + alignment + synthesis simultaneously,
and most questions do not warrant that — "Who is Cakkhupāla?" needs two or
three. A target here would manufacture padding.

Report the layer-count distribution descriptively. The meaningful figures are
single-layer answers (12/27) and context utilization (0.346); do not set a goal
on the tail.

## Do not

- Add another prompt paragraph for a behaviour that is at zero. Three rounds of
  evidence say that does not work.
- Adopt a tuned RRF k without stating that it was selected on the eval set.
- Chase four-layer answers.
