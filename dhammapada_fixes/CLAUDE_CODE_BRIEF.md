# Task brief: fix DhammapadaRAG

You are working in the DhammapadaRAG repo. An external code review found 14
bugs. Two of them mean the system has never actually done the thing it was
built to do: the commentary layer is being silently dropped, both at index
time and at generation time. Every number in `docs/evaluation.md` was produced
by that broken pipeline.

Replacement files are provided at `<PATH_TO>/dhammapada_fixes/`, laid out in
this repo's directory structure. `APPLY.md` there has the destination map.

## Ground rules

1. **Never make a failing test pass by weakening the assertion.** If
   `tests/test_provenance.py` fails, the code is wrong, not the test.
2. **Do not delete existing eval outputs.** Move `data/eval/*.json`,
   `*.jsonl`, and `docs/evaluation.md` to `data/eval/archive_pre_fix/` and
   `docs/evaluation_pre_fix.md` first. The before/after comparison is a
   deliverable, not clutter.
3. **Do not invent, estimate, or carry forward any metric.** If a number
   hasn't been recomputed on the fixed pipeline, it does not go in a doc.
4. **Work in dependency order.** Later steps consume earlier outputs. Do not
   parallelise across phases.
5. **Stop and report at each STOP GATE.** Do not proceed past one that fails.
6. Commit after each phase with the bug numbers in the message.

## Phase 0 — Baseline and archive

```bash
git checkout -b fix/commentary-pipeline
mkdir -p data/eval/archive_pre_fix
git mv data/eval/*.json data/eval/*.jsonl data/eval/archive_pre_fix/ 2>/dev/null || true
git mv docs/evaluation.md docs/evaluation_pre_fix.md
wc -l data/index/chunks.jsonl        # record this; it should be ~2769
```

Record the pre-fix chunk count. You will compare against it.

## Phase 1 — Provenance audit (bugs 4, 5, 6, 7)

Copy in `src/dhammapada_rag/generate/schemas.py` and `tests/test_provenance.py`.

The old `audit()` compared raw citation strings against bundle IDs, so a model
emitting `"g13.2"` against a corpus storing `"13.2"` was reported as a
fabricated citation. Every provenance warning in the archived results is a
false positive. The new version canonicalises before comparing, returns
structured `AuditWarning` objects with `code` and `severity`, fixes an `elif`
that skipped the stitched-provenance check, and validates verse-only citations
that previously passed unchecked.

In `tests/test_provenance.py`, wire `test_prompt_renders_canonical_ids` to the
real renderer (`from dhammapada_rag.generate.prompt import ...`) and remove the
`xfail` marker. Point `test_corpus_ids_are_all_canonical` at the real
`data/processed/stories.jsonl`.

```bash
pytest tests/test_provenance.py -v
```

**STOP GATE 1:** all tests pass, including the two you wired up. If any
corpus `group_id` is non-canonical, report it — do not normalise the corpus
silently.

## Phase 2 — Indexing (bugs 2, 3)

Copy in `src/dhammapada_rag/index/chunks.py`, `embed.py`, `assemble.py`.

Two problems. `chunks.py` emitted each story's entire `vatthu` as one chunk
while `embed.py` caps at 512 tokens, so most of every long narrative was never
embedded and was unretrievable at any k. And `chunks.py` never emitted story
titles at all — `title_en`, `title_pali`, `cst4_title`, `burlingame_title`,
`cast`, `keywords` were absent from the index, which is why the eight CST4 gold
questions could not be answered by construction.

```bash
python -m dhammapada_rag.index.chunks
python -m dhammapada_rag.index.embed        # ~10-20 min; raises if anything overflows
```

**STOP GATE 2:** chunk count is substantially higher than the pre-fix number,
`story_titles` appears in the type histogram with a count near 305, and the
coverage line reports previously-embeddable well under 100%. `embed.py` must
not raise. If it does, lower `chunks.WINDOW_WORDS` and rebuild — do **not**
raise `MAX_LENGTH`.

Sanity-check that titles are now reachable:

```bash
python -m dhammapada_rag.index.search "Suddhodana"
python -m dhammapada_rag.index.search "Sariputtattheravatthu"
```

## Phase 3 — Generation (bugs 1, 11, 12)

Copy in `src/dhammapada_rag/generate/prompt.py`, `generate.py`,
`src/dhammapada_rag/api/schemas.py`, `api/main.py`.

**This is the root cause.** The old `generate.py` passed only
`options={"temperature": ...}` to Ollama, which defaults `num_ctx` to 2048.
The prompt carries three full narratives. The commentary was truncated away
before the model saw it — which is why 100% of claims came back tagged
`verse` and none tagged `commentary`.

```bash
python -m dhammapada_rag.generate.generate \
  "why did the Buddha teach Kisa Gotami about mustard seeds?"
```

**STOP GATE 3 — the decisive test.** The output prints layer counts and a
prompt-token / `num_ctx` ratio. Required:

- at least one claim tagged `commentary`
- `prompt_tokens` comfortably under `num_ctx`
- zero `severity="error"` warnings

If commentary claims still do not appear, **stop and report**. Check in this
order: does the retrieved bundle actually contain `vatthu` text; does
`build_context()` include it; is `prompt_tokens` near the ceiling. Do not
proceed to evaluation with a generator that cannot produce commentary claims —
the metrics would be meaningless.

Then start the API and confirm `/answer` serialises:

```bash
uvicorn dhammapada_rag.api.main:app --app-dir src --port 8000 &
curl -sX POST localhost:8000/answer -H 'Content-Type: application/json' \
  -d '{"question":"what does the Dhammapada say about anger?","top_k":2}' | jq '.layer_counts, .warnings'
```

## Phase 4 — Gold set (bug 14)

Apply `data/eval/build_gold_set_PATCH.py` by hand to
`data/eval/build_gold_set.py`. **Keep all six question constant lists exactly
as they are** — the questions are hand-written and correct. Only the resolver
functions and `main()` change, adding a `subtype` field and splitting the
14 alignment-table questions out of `cross_recension` into their own type.

```bash
python data/eval/build_gold_set.py
```

**STOP GATE 4:** still 120 questions; `by_subtype` shows
`verse_grouping=14`, `cst4_title_variant=8`, `colophon_not_indexed=6`,
`corpus_anomaly=2`.

## Phase 5 — Evaluation (bugs 8, 9, 10, 13)

Copy in the five files under `src/dhammapada_rag/eval/`.

`verse_only` and `dense_only` claimed to run with reranking and did not, so
both ablation deltas were confounded. `compute_group_keys` used
`story_group_ids[0]` while `assemble()` uses all of them, so the eval scored a
unit the system never returns.

Before running the generation metrics, add a `gold_layer` field
(`"verse"` / `"commentary"` / `"synthesis"`) to every entry in
`data/eval/generation_judgments.py`. `aggregate_generation.py` raises a clear
error without it. **The judgments must be re-made against the new output** —
the archived ones judged claims from a truncated-context run and do not apply.

```bash
python -m dhammapada_rag.eval.retrieval_eval        # ~3x slower now
python -m dhammapada_rag.eval.aggregate_retrieval
python -m dhammapada_rag.eval.generation_metrics    # then re-judge, then:
python -m dhammapada_rag.eval.aggregate_generation
python -m dhammapada_rag.eval.model_sweep --max-retries 0
python -m dhammapada_rag.eval.model_sweep --max-retries 1
```

**STOP GATE 5:** report the layer marginals from `aggregate_generation.py`
before anything else. If one class exceeds 85% of predictions, the model is
constant-predicting and no accuracy figure should be quoted.

## Phase 6 — UI and docs

`src/dhammapada_rag/ui/app.py`: warnings are now objects. Render
`w["severity"]`, `w["code"]`, `w["message"]`, styling errors differently from
format warnings. Also fix the claim-card contrast — the text currently renders
near-white on pale blue and is unreadable.

Write a new `docs/evaluation.md` that reports the fixed numbers **and** keeps
the pre-fix ones alongside, with the diagnosis. Do not quietly replace the old
table. A 2048-token default deleting the commentary layer, and a 512-token
encoder limit unindexing most of every long narrative, are failures that
produce fluent, cited, schema-valid output that is hollow — that is the most
interesting finding this project has, and it should be written up as one.

Update `README.md`: the model sweep measures **structural citation validity**,
not "citation reliability."

## Report back with

1. Chunk count before → after, and the narrative-coverage percentage.
2. The Phase 3 layer counts for the Kisā Gotamī question.
3. Layer marginals and the 3×3 confusion matrix.
4. `verse_only` ablation per query type, with the doctrinal row called out —
   that row is the real evidence; the narrative collapse is near-mechanical
   since the condition deletes the only chunks its gold is reachable through.
5. Anything that failed a stop gate, unresolved.

## Do not

- Add the Udānavarga / Gāndhārī / Patna sources. Out of scope here.
- Change `vaggas.py`, `models.py`, `index/search.py`, `index/rerank.py`, or
  anything under `ingest/`. No bug was found in them.
- Tune retrieval parameters to improve the numbers. Fix correctness only;
  tuning after a correctness fix, on the same eval set, is overfitting.
- Regenerate `data/processed/*.jsonl`. The corpus is sound.
