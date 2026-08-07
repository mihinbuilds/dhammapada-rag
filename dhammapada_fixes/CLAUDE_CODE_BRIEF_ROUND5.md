# Task brief — round 5: constrain citations at the decoder, consolidate the prompt

Round 4 fixed the hard problems. Six probe runs confirm:

- The Kisā Gotamī fidelity inversion is corrected ("unable to find a single
  house where no son, daughter, or any other had yet died").
- Verse text is no longer mislabelled as commentary.
- The teleological framing note fires on "purpose of life".
- "Are Dhp 1 and Dhp 2 explained by the same story?" answers directly, No, with
  both correct stories retrieved.
- Angle brackets survive in warning messages.

Format compliance has meanwhile degraded badly, and the cause is that rounds
1–4 each appended instructions to `SYSTEM_PROMPT`. It is now long, and the
model complies unevenly. Observed in this batch:

| Field | Emitted value | Probe |
|---|---|---|
| `group_id` | `"g17.8"` (×5) | how to control anger |
| `group_id` | `"g26.40"` | purpose of life |
| `group_id` | `"inferred from Dhp 1 commentary"` | Dhp 1 and Dhp 2 |
| `text` | `"commentary: For once upon a time..."` | purpose of life |
| `text` | `"verse: Pubbenivāsaṁ yo vedī..."` | purpose of life |
| `group_id`/`verse_number` | both null on verse claims | purpose of life |

Do not fix these with more prompt text. That is what created the problem.

---

## Task K — Constrain group_id and verse_number at the decoder (headline)

**The idea.** `generate.py` already passes a JSON Schema to Ollama's `format`
parameter, which drives grammar-constrained decoding. Build that schema
**per request** from the retrieved bundles, with `group_id` and `verse_number`
as enums over the values actually in context. Malformed, invented, and
not-retrieved citations then become impossible to emit rather than detected
after the fact.

**Do.** In `Generator.generate()`, replace the static schema with:

```python
def _constrained_schema(bundles: list[dict]) -> dict:
    """JSON Schema with citation fields restricted to what is in context.

    Grammar-constrained decoding cannot emit a token sequence outside the
    grammar, so an enum here makes "g17.8", "Dhp 114", and
    "inferred from Dhp 1 commentary" unrepresentable. This moves citation
    validity from an instruction the model may ignore to a constraint it
    cannot violate.
    """
    schema = LayeredAnswer.model_json_schema()
    gids = sorted({s["group_id"] for b in bundles for s in b["stories"]})
    vnums = sorted({n for b in bundles for n in b["verse_numbers"]})

    # Pydantic v2 nests Claim under $defs; fall back to inline definitions.
    claim = schema.get("$defs", {}).get("Claim", schema).get("properties", {})
    if not claim:
        raise ValueError("Could not locate Claim properties in generated schema")

    claim["group_id"] = {
        "anyOf": [{"type": "string", "enum": gids}, {"type": "null"}],
        "description": "Story group_id from the provided sources. Null only for synthesis claims.",
    }
    claim["verse_number"] = {
        "anyOf": [{"type": "integer", "enum": vnums}, {"type": "null"}],
        "description": "Dhp verse number from the provided sources. Null only for synthesis claims.",
    }
    return schema
```

Call it in `generate()` in place of `LayeredAnswer.model_json_schema()`.

**Keep every audit code path.** `MALFORMED_GROUP_ID`, `UNPARSEABLE_GROUP_ID`,
`UNKNOWN_GROUP_ID`, and `GROUP_NOT_RETRIEVED` should drop to zero *by
construction*. That drop is the result to report — do not delete the checks
that prove it, and note in `docs/evaluation.md` that they are now
structurally unreachable rather than merely unobserved.

`VERSE_GROUP_MISMATCH` remains reachable: the enum constrains each field
independently, so a valid group_id can still be paired with a valid but wrong
verse_number. It is the only citation error the decoder cannot prevent, which
makes it worth reporting separately.

**Verify.** Re-run all six probes. Zero warnings with codes
`MALFORMED_GROUP_ID`, `UNPARSEABLE_GROUP_ID`, `UNKNOWN_GROUP_ID`,
`GROUP_NOT_RETRIEVED`. If Ollama rejects the schema, log the error and fall
back to the static schema rather than failing the request — but report the
rejection, since silently reverting would hide the whole change.

---

## Task L — Consolidate SYSTEM_PROMPT

Four rounds of appended instructions is why compliance drifted. Rewrite it as
one ordered document of roughly 350–450 words, in this sequence:

1. **Role and sources** — two layers, verse and commentary, ~8 centuries apart.
2. **Tagging** — the three layers, one sentence each.
3. **The failure to avoid** — commentary presented as the verse's plain sense;
   and its mirror, verse text relabelled as commentary.
4. **Coverage** — draw on both layers where both bear on the question; say so
   in a synthesis claim when the commentary does not; never relabel a verse to
   satisfy this.
5. **Framing** — name a category mismatch before answering.
6. **Direct answer** — questions asking which story / which verse / how many
   get answered explicitly in the first claim.
7. **Output discipline** — the `text` field is prose for a human reader. It
   must never begin with `verse:`, `commentary:`, `synthesis:`, `group_id:`, or
   `verse_number:`; the layer is carried by the `layer` field and the citation
   by its own fields.

Delete every instruction about group_id *format*. Task K makes it
unrepresentable, and the words are now dead weight competing for attention with
rules that still matter.

**Verify.** No claim's `text` begins with a layer name or field name. Add a
`LABEL_IN_TEXT` audit check at error severity for exactly this — it is cheap,
and a leaked label means the prose is unusable even when the fields are right.

---

## Task M — Diagnose the RRF arm imbalance

**The observation.** "What is the purpose of life according to the Dhammapada?"
retrieved Dhp 423 (the Brahmin Devahita story: the Buddha's humoral disorder,
a request for hot water). Dhp 166 (*sadattha*, "be intent on your own highest
good") and Dhp 182 did not appear. Dhp 423 contains "knows their former
**lives**" and "**birth's** destruction" — surface-token overlap with "life",
not conceptual relevance.

This is the second clean instance of the same pattern; the first was an early
run where every retrieved verse contained the word "live" or "life".

**Do.** Add `src/dhammapada_rag/eval/arm_diagnosis.py`. For a fixed set of
~10 conceptual queries (purpose of life, how to control anger, what is craving,
what is heedfulness, …), retrieve top-10 four ways — dense-only, sparse-only,
ColBERT-only, and RRF-fused — and print the four rankings side by side with
chunk_type and verse number.

Report: for each query, the rank at which the gold group appears under each
arm. If sparse-only reproduces the RRF result on conceptual queries while
dense-only ranks the gold group higher, the lexical arm is dominating the
fusion and the fix is either a weighted RRF (lower the sparse arm's
contribution) or query-type routing (keep sparse primary for Pali term lookup
and verse-number queries, where it is the right tool, and demote it for
conceptual ones).

**Do not change the fusion before running this.** The diagnosis is the
publishable part; a tuned weight without the diagnosis is just a number.

---

## Task N — Latency

Observed: 89.4s, 53.7s, 48.4s on ~5,000–8,800-token prompts with a 7B model.
That is slow enough to distort the model-size sweep's latency column.

Check whether Ollama is using GPU acceleration for generation (the reranker
already uses MPS per `rerank.py`; the generator may be on CPU). Record
`eval_count` and `eval_duration` from the Ollama response and report
tokens/second alongside wall-clock latency in the sweep — wall-clock alone
conflates model size with prompt length, and Task L will cut the prompt.

---

## Re-run after K and L

```bash
pytest tests/test_provenance.py -v
# then the six probes from dhammapada_probe_set.md
python -m dhammapada_rag.eval.generation_metrics    # re-judge with gold_layer + faithful
python -m dhammapada_rag.eval.aggregate_generation
python -m dhammapada_rag.eval.model_sweep --max-retries 0
python -m dhammapada_rag.eval.arm_diagnosis
```

Retrieval is unchanged by K, L, N — no need to re-run `retrieval_eval.py` until
after M produces a fusion change, if it does.

---

## Two things to verify against the corpus, not against plausibility

1. The Rohinī answer places the teaching at "Banyan Grove". Check the `nidana`
   field of story 17.1 in `data/processed/stories.jsonl`. If the source says
   otherwise, this is a fidelity error of exactly the G1 kind and belongs in
   the judgments as `faithful: False`.
2. Story 23.1's `title_en` ("The Story about Speaking and Rousing Oneself")
   still does not obviously match the Māgandiyā narrative retrieved under it.
   This was flagged in round 4 and has not been reported on. Check
   `ingest/parse_stories.py`'s title-to-body pairing before the next full eval.

---

## For the write-up

Task K is the most publishable thing in this round. The sequence is: prompt
instructions produced unreliable citations; more prompt instructions made it
worse through dilution; moving the constraint into grammar-constrained decoding
made four classes of citation error unrepresentable.

The general claim — for RAG systems where provenance matters, citation fields
should be constrained by the decoder against the retrieved set rather than
requested in the prompt and validated afterward — is architectural, transfers
to any domain, and you have before/after numbers for it from your own system.

## Do not

- Add more prompt text to fix a format problem. Constrain the decoder instead.
- Delete the audit checks that Task K makes unreachable. Their zero is evidence.
- Tune the RRF weights before running the arm diagnosis.
