# Task brief — round 9: quote fidelity

Retrieval and layer structure are working. On "what is the best thing in life
according to the Dhammapada" the system retrieved Dhp 194 and Dhp 273 — the two
verses that actually address it — cited each to its own correct story (14.8 and
20.1), and produced the right commentary (500 bhikkhus debating what is best in
the world).

The errors have moved to quote fidelity: what the Pali says and what the verse
is claimed to say. That is harder to catch than attribution and matters more for
a philological tool.

---

## Task AE — Check the corpus before changing any code

Two Pali quotes in that answer are truncated:

- Dhp 194: `Sukho buddhānamuppādo, sukhā saddhammadesanā` — two pādas. The verse
  has four; `sukhā saṅghassa sāmaggī, samaggānaṁ tapo sukho` is missing.
- Dhp 273: `Maggānaṭṭhaṅgiko seṭṭho, saccānaṁ caturo padā` — second half absent.

**Before assuming the model truncated, check whether the corpus is complete:**

```bash
python - <<'EOF'
import json
from pathlib import Path
rows = {json.loads(l)["verse"]: json.loads(l)
        for l in Path("data/processed/verses.jsonl").read_text(encoding="utf-8").splitlines()}
for n in (194, 273):
    v = rows[n]
    for f in ("pali_mahasangiti", "interlinear_pali"):
        t = v.get(f) or ""
        print(f"Dhp {n} {f}: {len(t)} chars\n  {t}\n")
EOF
```

If either field is itself short, this is a corpus extraction bug and belongs in
`docs/corpus_audit.md` as a new check — the audit's length-outlier check covers
`vatthu`, not verse fields. If the corpus is complete, the model truncated and
Task AF applies.

**Also resolve the second-half attribution of Dhp 273.** The quoted
`saccānaṁ caturo padā` should be verified against the corpus: check whether the
canonical second half of 273 is that phrase or `virāgo seṭṭho dhammānaṁ,
dvipadānañca cakkhumā`. If the quoted text belongs to a neighbouring verse in
the same retrieved group, that is a distinct error class — **cross-verse Pali
contamination**: real Pali from the retrieved group, attached to the wrong verse
within it.

Inspect how `audit()` builds the comparison string. If `pali_support` is matched
against the *group's* concatenated Pali rather than the *cited verse's* field,
this error is structurally undetectable. Match per cited verse only; fall back
to the group union only when `verse_number` is absent.

---

## Task AF — Detect truncated quotes

`pali_support` is validated by substring containment, so a half-quoted verse
passes clean: a truncation is a valid substring. A partial quote is not
fabrication, but presenting half a verse as the verse is a fidelity failure, and
it is currently invisible to every check.

**Do.** In `generate/schemas.py`, add `PALI_QUOTE_TRUNCATED` at warning
severity:

```python
# A quote shorter than this fraction of the cited verse is a partial citation.
# 0.6 is set so that quoting one of two half-verses (a common and sometimes
# legitimate move when only one half bears on the claim) is flagged for review
# rather than silently accepted, while a near-complete quote missing only a
# closing particle is not. Tune against data/eval/generation_raw.jsonl and
# report the value.
PALI_COVERAGE_THRESHOLD = 0.6
```

Compute coverage on the orthographically folded forms — raw character counts
would make hyphenation differences look like missing text:

```python
coverage = len(_pali_orthographic(claim.pali_support)) / len(_pali_orthographic(source_pali))
```

Emit the warning when a quote matches (exactly or as a variant) but covers less
than the threshold. Message must state the measured coverage so the number is
auditable.

Report a fourth rate alongside exact / variant / fabrication: **quote coverage
rate**, the mean fraction of the cited verse actually quoted. That number tells a
reader whether "the system shows the Pali" means the verse or a fragment.

---

## Task AG — Widen the label-leak check

Claim 3 read: *"The story explaining Dhp 194 **(group_id 14.8)** tells that…"*
The field name is in the prose and the citation is already in its own field.

`CITATION_IN_TEXT` currently matches `group_id:` with a colon. This form has a
space and a parenthesis. Widen to a case-insensitive match on `group_id`,
`verse_number`, `pali_support`, and `citation_fields` anywhere in `text`,
regardless of following punctuation. Keep it at error severity — a leaked field
name means the prose is unusable even when the fields are correct.

---

## Task AH — Verse claims that over-generalize the verse

Claim 1: *"The Dhammapada also states that the best thing in life is the
eightfold path"*, tagged `verse`, cited Dhp 273.

Dhp 273 says the eightfold path is best **among paths** (*maggānaṁ*) — a
comparative within a category, one line of a four-part parallel (best of paths,
of truths, of states, of beings). "The best thing in life" drops the qualifier
that makes it a claim about paths rather than about life.

Same class as the Dhp 135 error: correct layer, resolvable citation, and a
statement the verse does not make.

**Do — prompt.** Extend the verse-specificity instruction:

```
A verse claim must preserve the verse's own scope. If the verse says something
is best OF a category ("of paths", "of truths"), the claim must keep that
category. Widening "best of paths" to "the best thing in life" states something
the verse does not. Comparatives, conditionals, and negations must survive the
paraphrase intact.
```

**Do — rubric.** Add **scope-widening** as a named subtype in
`docs/eval_rubric.md`'s fidelity section, beside semantic-neighbour conflation.
Both are now attested more than once, and named subtypes predict where errors
cluster where a generic "hallucination" label does not.

**Verify.** Ask the same question and check that the Dhp 273 claim keeps
"among paths". Then probe two other comparatives — Dhp 354 (*sabbadānaṁ
dhammadānaṁ jināti*) and Dhp 103 — and check whether the scope survives.

---

## Re-run after AF–AH

```bash
pytest tests/ -v
# probe set, then:
python -m dhammapada_rag.eval.generation_metrics    # re-judge
python -m dhammapada_rag.eval.aggregate_generation
```

Report quote coverage rate alongside the existing three Pali tiers.

---

## Note for the write-up

The error profile has shifted across rounds and the trajectory is worth stating
plainly:

1. Rounds 1–3: the commentary layer was absent (context window, chunk truncation).
2. Rounds 4–6: attribution errors — verse tagged as commentary, citations
   malformed or missing.
3. Rounds 7–8: utilization — retrieved material going unused.
4. Round 9: quote fidelity — truncated Pali, scope-widened paraphrase,
   possible cross-verse contamination.

Each class became visible only after the previous one was fixed. That is a real
observation about evaluating layered RAG: the failure modes are stacked, and an
early-stage metric cannot see a late-stage error. It also argues that a system
reporting high citation accuracy may simply not yet have working retrieval —
the errors you can measure depend on which ones you have already eliminated.
