# Task brief — round 2: readable output, citation leak, verse-number retrieval

Round 1 worked. A test query now reports `~6157 tok / num_ctx 16384` and
produces a `commentary`-tagged claim, so the context-window bug (round 1, bug
#1) is confirmed fixed. Three problems remain, found by inspecting the output
of that run.

Do these in order: **B and C change what the model sees and what the index
contains, so any evaluation run before both are done is wasted.**

---

## Task A — Render claims as prose (no eval impact, do first)

**Symptom.** The UI shows a list of tagged claim cards and no readable answer.
A reader sees no response at all.

**Cause.** `generate/schemas.py` deliberately gives the model no free-text
summary field — an untagged paragraph is the escape hatch a conflated
verse/commentary claim would slip through. That decision is correct and stays.
But the client-side renderer it assumes was never written.

**Do.**

1. Copy in `src/dhammapada_rag/generate/render.py` (provided).
2. In `src/dhammapada_rag/ui/app.py`, put prose above the existing cards and
   demote the cards to an audit view:

   ```python
   from dhammapada_rag.generate.render import render_markdown

   st.markdown(render_markdown(result["answer"]))
   with st.expander("Claim-by-claim (provenance view)"):
       ...existing claim cards...
   ```

3. In `generate/generate.py`'s `main()`, print `render_plain(result["answer"])`
   above the existing claim dump.
4. Fix the claim-card contrast while you are in `app.py` — the text currently
   renders near-white on pale blue and is unreadable.

**Do not** flatten the layers into undifferentiated prose. `render.py` keeps
the distinction in the sentence itself ("The verse states…" vs "The commentary
relates…") because a coloured badge disappears the moment someone copies the
text into an essay. Preserve that.

**Verify.** Ask "why did the Buddha teach Kisa Gotami about mustard seeds?"
and confirm a readable paragraph appears above the cards, with inline
`[Dhp N, DhpA x.y]` citations.

---

## Task B — Stop the citation leaking into claim text

**Symptom.** A commentary claim came back with `text` beginning
`"group_id: 15.6; verse_number: 204 The story of the Gifts beyond Compare…"`
while the actual `group_id` and `verse_number` fields were null. The audit
fired `MISSING_PROVENANCE`, correctly.

**Cause.** `generate/prompt.py` renders a literal line `group_id: 13.2` inside
each commentary block. The model copied that string into its prose. This is a
regression introduced by round 1's prompt rewrite.

**Do.** In `generate/prompt.py`, inside `format_verse_group()`, replace:

```python
lines.append(f"group_id: {s['group_id']}")
lines.append(f"cite this commentary as verse_number: {first_verse}")
```

with:

```python
lines.append(f"<<citation_fields group_id={s['group_id']} verse_number={first_verse}>>")
```

Then append to the `CITATIONS.` paragraph of `SYSTEM_PROMPT`:

```
Put these values ONLY in the JSON group_id and verse_number fields. The `text`
field is prose for a human reader: it must never contain "group_id:",
"verse_number:", or a <<citation_fields>> marker. A claim whose text begins
with its own citation is malformed.
```

**Verify.** Re-run the same question. No claim's `text` may contain the
substrings `group_id`, `verse_number`, or `citation_fields`. Add a cheap
assertion in `tests/test_provenance.py`:

```python
def test_claim_text_carries_no_citation_markers():
    for bad in ("group_id", "verse_number", "citation_fields"):
        assert bad not in Claim(text="The verse states X", layer="verse",
                                group_id="8.13", verse_number=114).text
```

…and, more usefully, a runtime check in `audit()`: emit a new
`CITATION_IN_TEXT` warning at **error** severity when a claim's `text` contains
any of those three substrings. A model that writes its citation into prose has
produced an untraceable claim even when the fields happen to be populated too.

---

## Task C — Index verse numbers so alignment questions can retrieve

**Symptom.** The question "which single story explains Dhp 320, 321, and 322
together?" retrieved stories 2.1, 15.6, and 13.10. The correct answer is 23.1.
Nothing relevant was returned.

**Cause.** Verse numbers appear nowhere in any chunk's text. Chunks hold Pali,
English translation, or narrative prose; the literal string "320" is in none of
them. Every query phrased by verse number has nothing to match against — and
that is the shape of all 14 `verse_grouping` questions in the gold set. Those
questions have been scoring against an index that cannot represent what they
ask.

**Do.** In `index/chunks.py`, inside the `for s in stories:` loop, add a
dedicated alignment chunk alongside the existing `story_titles` chunk:

```python
verses_str = ", ".join(f"Dhp {n}" for n in dv)
alignment_text = (
    f"{verses_str} {'are' if len(dv) > 1 else 'is'} explained by a single "
    f"commentarial story: story {gid}, {s['title_en']}. "
    f"This story covers {len(dv)} verse(s): {verses_str}."
)
chunks.append(_chunk(f"story:{gid}:alignment", "story_alignment",
                     alignment_text, dhp_verses=dv, group_id=gid))
```

Document `story_alignment` in the module docstring's chunk-type list.

**Verify.**

```bash
python -m dhammapada_rag.index.chunks     # story_alignment count ≈ 305
python -m dhammapada_rag.index.embed
python -m dhammapada_rag.index.search "which single story explains Dhp 320, 321, and 322 together?"
```

Story 23.1 must appear at rank 1. Also spot-check two more from the gold set:
Dhp 188–192 → 14.6, and Dhp 153–154 → 11.8.

---

## After all three: re-run the evaluation

Tasks B and C both invalidate any metric collected between round 1 and now.
Re-run in this order:

```bash
pytest tests/test_provenance.py -v
python -m dhammapada_rag.eval.retrieval_eval
python -m dhammapada_rag.eval.aggregate_retrieval
python -m dhammapada_rag.eval.generation_metrics       # then re-judge
python -m dhammapada_rag.eval.aggregate_generation
python -m dhammapada_rag.eval.model_sweep --max-retries 0
```

Report the `verse_grouping` subtype row from `aggregate_retrieval` before and
after Task C. That delta is the cleanest single measurement in the project:
same questions, same model, one chunk type added.

---

## Write this up

This is the third instance of one pattern. The corpus contained the answer and
the indexing layer did not expose it — first the narrative bodies (truncated at
512 tokens), then the story titles (never chunked), now the verse-number
alignment (never expressed as text). Three independent variations on *the data
was there and the retriever could not see it*.

Add a subsection to `docs/evaluation.md` making that the argument, with the
three before/after numbers as evidence. It is a more useful finding for a
digital-humanities audience than any individual fix, because it generalises:
building RAG over a structured textual corpus, the failure mode is not the
model and not the embedding — it is silent loss between the corpus and the
index, and none of it is visible in output that looks fluent and cited.

## Do not

- Add a free-text summary field to `LayeredAnswer`. The prose is composed
  client-side from tagged claims, on purpose.
- Tune retrieval parameters. Fix correctness only; tuning after a correctness
  fix on the same eval set is overfitting.
- Regenerate `data/processed/*.jsonl`. The corpus is sound; only the index
  derived from it was lossy.
