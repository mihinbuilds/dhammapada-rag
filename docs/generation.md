# Generation with enforced layer attribution (Phase 4) -- design notes and findings

Implements `DhammapadaRAG.txt` Phase 4: "The prompt must force the
distinction your project exists to make... Require structured output where
every claim carries a layer tag (verse / commentary / synthesis) and a
group_id. Conflating the two layers is the failure mode; make the output
format make it visible."

## Model

**Qwen2.5-7B-Instruct**, served locally via Ollama (`qwen2.5:7b-instruct`,
Q4_K_M quantization, 4.7GB). This is a deliberate choice per the spec's own
instruction: "Use a real generator, not a 1B model." Ollama was already
installed on this machine with several other models pulled, which made it
the lowest-friction way to get a real local generator running with almost no
setup, and it happens to also solve the enforcement mechanism (next section)
for free.

**Compute-constraint finding, updated after Phase 5's model-size sweep**
(the spec explicitly asks to turn this into a reported result rather than
hide it): at the time this section was first written, Qwen2.5-14B-Instruct
hadn't been attempted, on the assumption that Q4 quantization's ~9-10GB of
weights would be too tight on this 18GB-RAM machine alongside the rest of
the stack (BGE-M3 embedder + reranker). That assumption turned out to be
wrong -- the Phase 5 sweep (`src/dhammapada_rag/eval/model_sweep.py`,
results in `docs/evaluation.md`) ran all three sizes (1.5B/7B/14B)
successfully, 60/60 generations, no OOM. The real constraint is **latency,
not memory**: mean generation latency scales roughly linearly with size on
this hardware (1.5B: 4.6s, 7B: 18.1s, 14B: 38.2s), which matters for a live
API's usability, not for whether the model can be loaded at all. The
`Generator(model=...)` abstraction (swap via `--model` on the CLI or
`"model"` in the `/answer` request body) made running that sweep mechanical
once the gold set existed, exactly as anticipated here.

## Enforcement mechanism: schema-constrained decoding, not prompted JSON

`generate.py` passes `LayeredAnswer.model_json_schema()` (source of truth:
`generate/schemas.py`) as Ollama's `format` parameter. Ollama compiles this
into a grammar that constrains token generation directly -- the model
*cannot* emit text outside the JSON structure, unlike asking a model to
"please respond in JSON" and hoping. Across every test run this session, the
response parsed as valid `LayeredAnswer` on the first attempt (no retry ever
triggered) -- the schema constraint enforces *shape* reliably. It does not,
and cannot, enforce that the *content* inside that shape is accurate --
that's the audit layer and the gap discussed below.

## Two-tier audit: presence, then cross-reference against retrieval

`schemas.py`'s `audit(answer, bundles)`:

1. **Presence**: every `verse`/`commentary` claim must cite a `group_id` or
   `verse_number`.
2. **Validity** (needs the actual retrieved bundles): the cited `group_id`
   must be one of the sources actually shown to the model, and the cited
   `verse_number` must belong to *that* `group_id`'s own verses.

Tier 2 exists because tier 1 alone missed a real failure caught during
testing (below) -- fields were present and individually well-formed, but
stitched together from two different retrieved sources. Neither tier
verifies a claim's tag is *semantically* correct against the source text
(e.g. that a "commentary" claim doesn't quietly misstate what the story
says) -- that requires the human-rated gold set and the "layer attribution
accuracy" / "anachronistic conflation rate" metrics `DhammapadaRAG.txt`
Phase 5 defines, which don't exist yet. This audit is a structural check,
reported as exactly that, not a substitute for those metrics.

## Findings from testing (qualitative, n small -- not a substitute for Phase 5's gold-set evaluation)

**Query**: "why did the Buddha teach Kisa Gotami about mustard seeds?"
(retrieval correctly surfaces two distinct Kisā Gotamī stories: 8.13, the
mustard-seed parable explaining Dhp 114, and 20.11, a different story
explaining Dhp 287 -- see `docs/indexing.md`.)

- **Repeated failure**: the model cited `verse_number=287` together with
  `group_id="8.13"` (or a mangled `"sourced_group_8.13"`) -- mixing
  provenance from the two different retrieved sources into one claim. This
  is a real, reproducible instance of the exact problem this architecture
  exists to make visible, just one level down from where the spec
  anticipated it: not the model conflating *verse* with *commentary*, but
  conflating *which* commentary a correct claim actually came from. The
  tier-2 audit catches it every time it occurs; tier-1 (presence-only) does
  not, since the fields aren't empty, just wrong.
- **Success case**: query "what does the verse about the wheel following the
  ox's foot mean, and what story explains it?" (single source, Dhp 1 / story
  1.1) produced two claims: the wheel/consequence content tagged `synthesis`
  and the "wicked physician" past-life backstory tagged `commentary`. The
  second is exactly right -- narrative backstory correctly kept out of the
  verse layer, not presented as the verse's plain sense.
- **Genuine ambiguity, not a bug**: the first claim above (paraphrasing what
  the verse means) was tagged `synthesis` rather than `verse`. Both are
  defensible -- it's a faithful paraphrase (arguably `verse`) built by
  restating the content in the model's own words (arguably `synthesis`).
  This boundary is fuzzier in practice than the verse/commentary boundary,
  which is worth flagging for Phase 5's rubric design: annotators will need
  explicit guidance on whether verse *paraphrase* counts as `verse` or
  `synthesis`, since the model's own behavior here isn't obviously wrong,
  just underspecified by the current prompt.
- Provenance-field omission (tier-1 warnings, claim tagged `commentary` with
  no `group_id`/`verse_number` at all) occurred in roughly half of single-run
  test queries at `temperature=0.1` -- not rare. Worth tightening the prompt
  or lowering temperature further before treating `/answer` output as
  reliably self-citing without checking `warnings`.

**Takeaway for the paper**: schema-constrained decoding solves the
*structural* half of layer attribution (100% valid shape, zero parse
failures) but not the *provenance-accuracy* half (citations were wrong or
missing in a meaningful fraction of runs) -- these are different problems
requiring different fixes, and reporting them separately (as this project's
"layer attribution accuracy" metric should) is more honest than a single
pass/fail number would be.
