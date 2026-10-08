# Generation with enforced layer attribution (Phase 4) -- design notes and findings

Implements `docs/project_plan.md` Phase 4: "The prompt must force the
distinction your project exists to make... Require structured output where
every claim carries a layer tag (verse / commentary / synthesis) and a
group_id. Conflating the two layers is the failure mode; make the output
format make it visible."

> **Note (2026-09-23).** The Streamlit UI (`src/dhammapada_rag/ui/app.py`) that
> earlier rounds below refer to has since been removed. The frontend is now the
> Next.js app in `web/`, served by `api/main.py`. References to `ui/app.py` are
> kept as the record of what that round changed.

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

## The audit: presence, form, cross-reference, and (narrowly) content

`schemas.py`'s `audit(answer, bundles)`, current state after Round 4:

1. **Presence**: every `verse`/`commentary` claim must cite a `group_id` or
   `verse_number`.
2. **Form**: the cited `group_id` must reduce to canonical `vagga.story`.
   Resolvable drift (`"g13.2"` -> `"13.2"`) is a warning; unresolvable drift
   is an error.
3. **Validity** (needs the actual retrieved bundles): the cited `group_id`
   must be one of the sources actually shown to the model, and the cited
   `verse_number` must belong to *that* `group_id`'s own verses.
4. **Verse/commentary conflation, narrow and mechanical** (Round 4, Task F):
   a `commentary`-tagged claim whose wording is mostly the cited verse's own
   words is verse content relabelled, by construction -- `VERSE_TEXT_AS_COMMENTARY`.

Tier 3 exists because tiers 1-2 alone missed a real failure caught during
testing (below) -- fields were present and individually well-formed, but
stitched together from two different retrieved sources. Tiers 1-3 verify a
claim's citation is well-formed and traceable, not that its content is
correctly tagged against what the source text actually says -- that gap is
what the human-rated gold set and the "layer attribution accuracy" /
"anachronistic conflation rate" / "source fidelity" metrics in
`docs/eval_rubric.md` measure. Tier 4 narrows that gap without closing it:
it catches one specific direction (verse text tagged `commentary`) and only
where the reuse is near-verbatim, not paraphrased -- see
`docs/eval_rubric.md`'s conflation-rate section for what it does and does
not catch, measured against the actual generation sample.

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

## Round 3: presentation-layer fixes

Four defects, found comparing rendered output against the underlying
`LayeredAnswer`, none of which needed a re-run of the evaluation except the
prompt change:

- **Citation display showed the model's raw string, not the resolved one**
  (`render.py`): `group_id="Dhp 20.11"` displayed as `[Dhp 287, DhpA Dhp
  20.11]` instead of the normalized `[DhpA 20.11]`. Fixed by normalizing
  before display and dropping any citation component that doesn't resolve
  at all -- a citation the audit already rejected must not be shown as if
  it were fine.
- **Lead-in repeated on every claim** (`render.py`): consecutive
  same-layer claims each got their own "The commentary relates:" instead of
  one lead-in marking the transition into that layer. Fixed by tracking the
  previous claim's layer and grouping same-layer runs into one paragraph.
- **Angle brackets in warning messages silently eaten by Streamlit**
  (`schemas.py`, `ui/app.py`): a message reading `'<vagga>.<story>' form`
  rendered as `' form'` because `render_warning()`'s `unsafe_allow_html=True`
  block let the browser parse `<vagga>` as an HTML tag. Fixed at both ends:
  the literal brackets removed from the message text, and the message
  `html.escape()`-d before interpolation regardless, since it also embeds
  model output (a claim's `text`) that could contain `<` in the future.
- **Model wrote a verse number into `group_id`** (`prompt.py`):
  `group_id="Dhp 114"` -> `UNPARSEABLE_GROUP_ID`, correctly rejected (114 is
  the verse Dhp 8.13 explains, not the group_id itself). The two fields are
  numeric and adjacent in the prompt, and the model had just written "Dhp
  114" in its own prose; `CITATIONS` now explicitly contrasts the two
  fields with a worked negative example rather than describing each
  format in isolation.

## Round 4: the mirror-image conflation, and answering the question asked

**Verse text relabelled as commentary (Task F).** The same verbatim Dhp 222
sentence ([SuttaCentral text removed 2026-10-08]) was observed
tagged `verse` in response to one question and `commentary` in response to
another. Traced to Round 1's COVERAGE fix: requiring at least one
`commentary` claim per answer, with no escape hatch, gives the model a way
to satisfy that instruction by relabelling a verse when retrieval returns
little usable narrative -- fixing all-verse output induced its opposite.
`COVERAGE` now has an explicit escape hatch (state in a `synthesis` claim
that the commentary doesn't bear on the question, answer from the verse
alone) and names relabelling verse text as commentary as *worse* than
omitting a commentary claim. `schemas.py`'s `audit()` gained a matching
mechanical check, `VERSE_TEXT_AS_COMMENTARY` (see `docs/eval_rubric.md`'s
conflation-rate section for its measured flag rate and scope limits) --
same principle as `CITATION_IN_TEXT` before it: a prompt instruction alone
is not self-enforcing, and where a failure is mechanically detectable, it
should be caught structurally rather than left to a human annotator alone.

**Retrieval succeeded, the answer didn't respond to the question (Task
H).** "Which single story explains Dhp 320, 321, and 322 together?"
retrieved the correct story (23.1) but produced claims narrating its
content without ever naming the story or stating that it covers all three
verses. `DIRECT ANSWER` was added to `SYSTEM_PROMPT`: a "which story / which
verse / how many" question must be answered by name in the first claim,
before supporting detail.

**Investigated, not a bug: story 23.1's title.** The same question surfaced
a second concern worth checking before any further eval run: story 23.1's
`title_en` ("The Story about Speaking and Rousing Oneself") reads
unconnected to its actual narrative (Queen Māgandiyā inciting a crowd to
abuse the Buddha). Checked against `data/raw/dhammapada-attakatha.txt`
directly (the extracted-but-unmodified source text, line 36510 onward):
title, Pali title (`Attānaṁ Ārabbha Kathikavatthu`), CST4 title, Burlingame's
title, synopsis, nidāna, and vatthu are all one contiguous block in the
source, correctly bounded before "23.2" begins -- `ingest/parse_stories.py`
paired them correctly. The apparent mismatch is a translation-idiom
artifact, not a parsing error: `Attānaṁ Ārabbha Kathikavatthu` translates
literally to something like "the story of talk concerning oneself," which
matches the nidāna's own "with reference to himself" (the Buddha, having
been insulted, discourses about his own self-restraint) -- Burlingame's
alternate title, "The Sectaries Insult the Buddha," names the same story's
*events* rather than its *occasion*, and CST4's `Attadantavatthu` ("the
story about one who tamed himself") names its *theme*. Three legitimate
titles for one story, emphasizing three different things -- exactly the
kind of cross-recension title variance this corpus already models on
purpose. No change made under `data/processed/`.

**Regression: null citations on a multi-verse question (Task I-1).** Both
claims in the Dhp 320/321/322 run above came back with `group_id` and
`verse_number` both null, unusable regardless of accuracy. `CITATIONS` now
states explicitly that a claim about a verse group cites the group's first
verse number and that a `verse`/`commentary` claim must never leave both
fields empty.

## Round 5: constrain citations at the decoder, consolidate the prompt

Round 4's fixes held on six probe runs, but citation format compliance had
meanwhile degraded badly: `group_id="g17.8"` (five times, one question),
`group_id="g26.40"`, `group_id="inferred from Dhp 1 commentary"`, claim text
opening with `"commentary: For once upon a time..."` or `"verse:
Pubbenivāsaṁ yo vedī..."`, and both citation fields left null on verse
claims. The cause: four rounds each appended instructions to `SYSTEM_PROMPT`
to fix one observed failure, and by round 5 it was long enough that the
model complied with any single instruction unreliably. More prompt text
was diagnosed as the cause, not treated as the fix.

**Task K -- constrain the decoder instead of instructing it (headline).**
`generate.py`'s `_constrained_schema()` builds the JSON Schema passed to
Ollama's `format` parameter fresh per request, restricting `group_id` and
`verse_number` to enums of the values actually present in the retrieved
`bundles`. Grammar-constrained decoding cannot emit a token sequence
outside the compiled grammar, so `"g17.8"`, `"Dhp 114"`, and `"inferred
from Dhp 1 commentary"` become unrepresentable rather than merely
discouraged -- citation *validity* moves from a prompt instruction the
model may ignore to a constraint it cannot violate. Re-running the two
worst-offending probes from the format-compliance table:

- "how to control anger?" (previously `g17.8` × 5): zero
  `MALFORMED_GROUP_ID`/`UNPARSEABLE_GROUP_ID`/`UNKNOWN_GROUP_ID`/
  `GROUP_NOT_RETRIEVED` warnings. Remaining warnings: `MISSING_PROVENANCE`
  on two claims (fields left null entirely) -- not something the decoder
  constraint can prevent, since null is a legal value (required for
  synthesis claims); `CITATIONS` still has to ask for completeness, and
  still isn't always obeyed.
- "what is the purpose of life according to the Dhammapada?" (previously
  `g26.40`, both label-prefix leaks, both fields null): zero warnings of
  any kind. `FRAMING` also fired correctly (a `synthesis` claim naming the
  teleological mismatch before answering), confirming this round's prompt
  consolidation didn't regress a Round 4 fix while shortening the prompt
  around it.

`VERSE_GROUP_MISMATCH` remains reachable by design: the two fields are
constrained independently, so a valid `group_id` can still be paired with a
valid-but-wrong `verse_number` from a different retrieved source -- the one
citation error left for the audit layer to catch, since decoder constraints
apply per-field, not across fields. If Ollama ever rejects the constrained
schema outright (a grammar-compilation failure), `generate()` falls back to
the static schema and records the rejection in `schema_status` rather than
reverting silently -- not observed in any run this round, but the fallback
exists and is reported precisely so a future occurrence isn't invisible.

**Task L -- consolidate `SYSTEM_PROMPT`, don't extend it again.** Rewritten
as a single ~440-word ordered document (role/sources, tagging, the failure
to avoid and its mirror, coverage, framing, direct answer, citations,
output discipline) in place of four rounds of appended instructions. Every
instruction about `group_id`/`verse_number` *format* is deleted outright --
Task K makes the format unrepresentable at the decoder, so describing it in
prose was pure dilution by Round 5. `schemas.py` gained `LABEL_IN_TEXT`
(error severity): a claim whose `text` opens with `"verse:"`,
`"commentary:"`, `"synthesis:"`, `"group_id:"`, or `"verse_number:"` instead
of composed prose is flagged mechanically, independent of the existing
`CITATION_IN_TEXT` check (which catches prompt scaffolding leaking
*anywhere* in text, not specifically as an opening label) -- same principle
as every other prompt rule in this project: state it, then verify it
structurally rather than trust compliance.

**Two things checked against the corpus, not against plausibility (per the
round 5 brief).**

1. A live answer stated the Rohinī teaching was given at "Banyan Grove."
   Checked against `data/processed/stories.jsonl` group `17.1`: its
   `nidana` field is `null` for this story (the occasion statement lives at
   the very start of `vatthu` instead, a corpus-structure quirk worth
   noting but not a bug) -- and that opening line reads verbatim "this
   Dhamma teaching was given by the Teacher while he was in residence at
   **Banyan Grove** with reference to the noble maiden Rohiṇī." The claim
   is faithful, not a fidelity error.
2. Story 23.1's title/body pairing, re-flagged as unreported: it was
   reported, in this file's Round 4 section above, after checking
   `data/raw/dhammapada-attakatha.txt` directly rather than
   `ingest/parse_stories.py`'s output alone -- title, synopsis, nidāna, and
   vatthu are one contiguous, correctly-bounded block in the source. No
   parsing bug; restated here since the round 5 brief that requested this
   round's other work was apparently written without that finding in view.

## Round 6: edition variance vs. fabrication, pipeline hygiene, PC migration

Round 5's Pali validation (Task J) flagged two of three verse claims on a
live run: Dhp 221's `pali_support="sabbam-atikkameyya"` and Dhp 222's
`"tam-ahaṁ"`/`"bhantaṁ va"` did not match `pali_mahasangiti` byte for byte.
The round 6 brief's own table named what these actually are before any code
was written: Ānandajoti's sandhi-hyphenated, differently-capitalized
rendering of the *same words* the Mahasangiti edition prints unhyphenated
("sabbamatikkameyya", "Tamahaṁ", "bhantaṁva") -- edition variance, the
phenomenon this project exists to represent, not an invented quote. A
binary match/fabricate check cannot tell the two apart, and was wrong to
try.

**Task O -- where the variant orthography comes from (done first, since it
changes what the rest of the round means).** The brief's own probe,
run against `format_verse_group()`'s actual output for "what does the
Dhammapada say about anger?": both `"sabbam-atikkameyya"` (hyphenated,
Ānandajoti) and `"sabbamatikkameyya"` (unhyphenated, Mahasangiti) are
present in the prompt, and likewise for Dhp 222's two forms. Tracing which
line carries each: `format_verse_group()` prints `pali_mahasangiti` under
"Pali (Mahasangiti)" as intended, but each story's narrative text --
`vatthu`, rendered under "Narrative" a few lines later, in this case
Burlingame's translation quoting the verse inline before Rohiṇī's story
concludes -- carries the verse in `interlinear_pali`/`narrative_pali`'s
Ānandajoti orthography, and that text reaches the model's context too. Per
the brief's own branch logic, this is the **audit-bug branch**: the model
copied faithfully from a field genuinely in front of it, one `audit()`
never checked. Notably, `SYSTEM_PROMPT`'s existing PALI SUPPORT rule
already warns against exactly this ("Copy only from the Mahasangiti line
printed in this prompt, never from memory... other editions join or
hyphenate words differently") -- the model still drew from the narrative
quote regardless, which says less about prompt compliance than about two
legitimate-looking sources sitting in one context with no way for the model
to know only one is being checked.

**Task P -- three-tier Pali matching.** Replaced the single
`pali_mahasangiti`-only substring check with `_pali_exact()` (NFC only) and
`_pali_orthographic()` (additionally folds hyphenation, niggahita glyph
variants ṃ/ṅ→ṁ, pada-boundary capitalisation, and punctuation/spacing --
edition-level conventions, not lexical content), checked via
`_match_pali_quote()` against every Pali field actually reaching the
model's context for the cited verse: `pali_mahasangiti`, `interlinear_pali`,
and each retrieved story's own `pali_verse` (Task O's finding: not
`pali_mahasangiti` alone). Three outcomes, not two: an exact match against
any candidate field is silent; a match that requires orthographic folding
is `PALI_QUOTE_ORTHOGRAPHIC_VARIANT` (**warning**, new this round); no match
at either tier is `PALI_QUOTE_NOT_IN_SOURCE` (**error**, unchanged
severity, tightened wording to name every field checked, not just one).

Re-running the motivating query live against this machine's index and
`qwen2.5:7b-instruct`: a "what is the purpose of life" answer's Dhp 20
claim quoted the full verse verbatim from `interlinear_pali`, differing
from `pali_mahasangiti` only in hyphenation/spacing/capitalisation --
`PALI_QUOTE_ORTHOGRAPHIC_VARIANT` fired exactly as designed, naming the
matched field and the claim it supports, at warning rather than error
severity. A separate "how to control anger?" run produced a `pali_support`
quote that matched exactly, no warning at all. Both are now distinguishable
from a third case this round's tests construct directly (`schemas.py`
has no live example yet): a quote matching no available field at either
tier, which still raises `PALI_QUOTE_NOT_IN_SOURCE`. `aggregate_generation.py`
reports all three as separate rates -- **exact-copy rate**, **variant
rate**, **fabrication rate** -- over every `VerseClaim` in a generation run
that carries a `pali_support` quote; see docs/evaluation.md's Round 6
section for why the middle tier, not the exact-copy rate alone, is where
the finding lives. Per the brief: report three rates, never collapse to
one, and never loosen the exact tier to flatter the numbers -- the gap
between exact and variant is the measurement, not noise to average away.

**Task Q -- the `\x01` corruption, traced separately from the Pali metric.**
Per the brief's own instruction, checked before writing any fix:
`grep -P '[\x00-\x08\x0b\x0c\x0e-\x1f]'` across `data/processed/*.jsonl`,
`data/index/chunks.jsonl`, and `data/raw/*.txt` found **zero** occurrences
of `\x01` specifically anywhere in the corpus (`data/raw/*.txt` does carry
ordinary `\x0c` form-feed page breaks from PDF extraction -- expected,
unrelated). The corpus is clean, so per the brief this is not an ingest bug;
it can only enter at prompt rendering or in Ollama's JSON round-trip.
`prompt.py` gained `_strip_control_chars()`, applied to both the system and
user message content inside `build_messages()` -- a boundary guard, not a
fix for an active corruption this repo's own data ever contained. `\t`/`\n`/
`\r` are deliberately excluded from the stripped range: legitimate prompt
structure, not corruption. Tested directly (`test_provenance.py`'s three
`test_build_messages_*` tests): a poisoned `question` argument and a
poisoned bundle field both come out clean, and ordinary newlines survive.

**Task R -- unescaped claim text in the UI's claim card.** `ui/app.py`'s
`render_claim()` already builds each card as one complete f-string (not
separate open/close `st.markdown()` calls) and already gates the Pali line
on `claim.get("pali_support")` truthiness rather than on layer -- both
already correct by the time this round reached the code, so the brief's
literal unbalanced-`</div>` reproduction did not reproduce here. What
remained: `claim["text"]` and `cite` were interpolated into the card's HTML
unescaped, with `unsafe_allow_html=True` -- exactly the failure mode the
brief describes (a stray `<`/`</div>` in model output corrupting everything
rendered after it in the card), just not yet triggered by an observed
claim. Both are now `html.escape()`d, matching `render_warning()`'s
existing treatment of `w.message` a few lines below. One regression caught
and fixed in the same pass: `cite` was joined with the HTML entity
`"&middot;"`; escaping the joined string doubled its own `&` into visible
`"&amp;middot;"` text. Switched to the literal Unicode `"·"` character,
which `html.escape()` leaves untouched. Verified live for all three claim
layers (a commentary claim carrying `</div><script>...`, a synthesis claim
with no citation, a verse claim with a `<`-laced `pali_support`) via a
`st.markdown` capture harness -- no unescaped tag in any card, and the
middle dot still renders as a dot, not text.

**Task S -- PC migration.** `torch.backends.mps.is_available()` (the
Apple-Silicon-only check `rerank.py` had) and `embed.py`'s hardcoded
`devices=["cpu"]` both silently miss an NVIDIA GPU. `rerank.py` now exports
`best_device() -> (device, use_fp16)` -- CUDA, then MPS, then CPU fp32 --
shared by `CrossEncoderReranker`, `embed.py`'s corpus-embedding step, and
(found while migrating, not itself in the brief's two named call sites)
`search.py`'s `ChunkIndex`, which hardcoded the identical `devices=["cpu"]`
for the *query-time* embedder -- the one of the three that runs on every
single search, not once at index-build time. All three now log their
chosen device to stderr at startup.

On this machine: `nvidia-smi` reports an NVIDIA GeForce RTX 5080, but
`torch.cuda.is_available()` returns `False` -- the installed torch build in
this project's `.venv` is CPU-only (`torch==2.13.0+cpu`), not a hardware or
code problem `best_device()` can fix. `best_device()` correctly falls back
to `("cpu", False)` given that build; the fix for the retrieval-side
latency this causes is a CUDA-enabled torch reinstall, a `.venv`-mutating
change outside a code-review round's scope, flagged here rather than done
silently. `ollama ps`, polled every 2s through a live `/answer` call,
confirms `qwen2.5:7b-instruct` generation runs at **100% GPU** throughout --
consistent with the pre-migration finding on the original Apple Silicon
machine (Round 5, Task N) -- so retrieval (dense/sparse/ColBERT search plus
reranking, on the CPU-only torch build) is this machine's actual latency
bottleneck, not generation. A live `/answer` call: 2.9s generation
against an 18s wall-clock total.

Also checked: every `open()` call without explicit `encoding=` in `src/` is
binary-mode (`"rb"`/`"wb"` against `.pkl` files, which correctly should not
declare a text encoding); every `.read_text()`/`.write_text()` call already
passes `encoding="utf-8"` explicitly, `ingest/` included. No hardcoded `/`
path-separator string was found outside of query-label text, format
strings, and comments -- the codebase already routes all file I/O through
`Path`. `PYTHONUTF8=1` is now called out in the README for Windows
terminals: cp1252 cannot print Pali diacritics and crashes outright on them
(hit repeatedly while running this round's own live probes) rather than
degrading to `?` the way some encodings do.

**A bug found verifying this round, not requested by it.** Running a live
`/answer` probe against this machine's API surfaced a 500 on every question
whose answer includes a synthesis claim (e.g. any `FRAMING` claim, which is
most "purpose of life"-shaped questions) -- `api/schemas.py`'s `ClaimOut`
declared `group_id: str | None` / `verse_number: int | None` with no `=
None` default, which in pydantic means the *key* must still be present,
merely nullable. Round 4/5's Task K/L amendment made `SynthesisClaim` a
distinct model with no `group_id`/`verse_number` fields at all, so
`SynthesisClaim.model_dump()` (`api/main.py`'s `run_answer`) never produces
those keys, and `ClaimOut(**c.model_dump())` failed pydantic's "Field
required" check for every such claim -- the API layer was never migrated
alongside the schema refactor it followed. Fixed with `= None` on both
fields, matching what `str | None` already implied. `pali_support` was
also missing from `ClaimOut` entirely (Round 4's Task J never reached this
file) and is added here for the same reason `render.py` and `ui/app.py`
carry it: an API client asking for a generated answer got no Pali at all
otherwise, the same failure Task J exists to prevent, just for one more
consumer of the schema.

**Live re-verification, three probes on this machine.** "How to control
anger?": `group_id="17.8"` (canonical, no `g` prefix -- the pre-Task-K
failure this exact probe was chosen to catch), zero warnings of any kind.
"What is the purpose of life according to the Dhammapada?": `FRAMING` fires
correctly as a synthesis claim, and `PALI_QUOTE_ORTHOGRAPHIC_VARIANT` fires
on the one claim that draws from `interlinear_pali` (see Task P above) --
both now surfaced through `/answer` instead of 500ing. Retrieval smoke test
("the woman whose child died") continues to surface Kisā Gotamī's Dhp 287 /
Dhp 114 / Dhp 113 exactly as documented since Phase 2.

## Round 7: a fourth layer, answer completeness, and two more fidelity errors

The bottleneck named by the round 7 brief: answers had become structurally
clean (schema-valid, correctly cited) but too thin to demonstrate the
multi-layer architecture -- "Who is Cakkhupāla?" produced one sentence, no
Dhp 1, no Pali, no occasion. A single-layer commentary search would have
produced identical output.

**Task T -- `alignment` as a fourth claim variant.** Asked which story
explains Dhp 4, round 6's system answered "The Story about the Elder Thulla
Tissa explains Dhp 4," tagged `commentary` -- attributing to Buddhaghosa a
structural fact he never stated, and inflating the commentary layer in every
metric this project reports. `generate/schemas.py` gained `AlignmentClaim`
(`group_id` + `verse_numbers`, plural -- the group's FULL range, not one
verse) as a fourth discriminated-union variant, with its own citation-
validity branch in `audit()` (mirrors `VerseClaim`/`CommentaryClaim`'s
group_id checks, since `AlignmentClaim` has no singular `verse_number` to
fall through the existing branch on) plus a new mechanical check,
`ALIGNMENT_RANGE_INCOMPLETE` (warning): a group_id that resolves but whose
cited `verse_numbers` is not the group's full range. `render.py`,
`ui/app.py`'s badge, `api/schemas.py`, and `aggregate_generation.py`'s
confusion matrix all widened from 3x3 to 4x4 -- `LAYERS` is a single tuple
threaded through every loop in `aggregate_generation.py`, so this was a
one-line change there, not a rewrite.

Three existing judgments (`q095`#0, `q097`#0, and `q119`#0, all "story X
explains Y and Z" or corpus-structure claims originally forced into
`synthesis` for lack of a better slot) were re-judged `alignment` this
round, flagged with a note rather than silently remapped, per the brief's
explicit instruction.

**Live verification, three "which story explains" probes.** Dhp 4 (group
1.3, covers Dhp 3-4): first claim tagged `alignment`, states "Dhp 3 and 4
together" -- both the new tag and Task U's full-range instruction worked.
Dhp 21 (group 2.1, covers Dhp 21-23): tagged `alignment` correctly, but the
claim states only "Dhp 21" -- `ALIGNMENT_RANGE_INCOMPLETE` fired exactly as
designed, naming the gap (cited `[21]`, full range `[21, 22, 23]`). Dhp 153
(group 11.8, covers Dhp 153-154): same pattern, tagged correctly, range
incomplete, caught mechanically. **The tag itself is reliable (3/3); the
full-range prose instruction is not (1/3) -- which is exactly why Task T
asked for a mechanical backstop rather than trusting Task U's prompt text
alone.** The fresh 27-question sample confirms this is not probe-selection
luck: of 8 claims judged `alignment` this round, 4 were tagged `alignment`
by the model and 4 were still tagged `commentary` despite stating the same
kind of fact (`q093`#0, `q097`#0) -- alignment precision is 1.000 (never
wrongly applied) but recall is only 0.500 on this sample.

**Task V -- completeness, and where it did and didn't take.** `SYSTEM_PROMPT`
gained a `COMPLETENESS` section (per-question-type guidance: "who is X"
needs commentary + verse + outcome; "which story explains X" needs the
alignment fact with full range; every retrieved group is cited or
dismissed by name). Live probes were mixed: "Who is Cakkhupāla?" produced
2 commentary claims (up from round 6's 1, but still zero verse claims and
zero Pali despite Dhp 1 being retrieved); "Who is chakkhupala" (the brief's
own original phrasing) reproduced the *original* 1-claim failure exactly.
The fresh 27-question sample's layer-count distribution: 12/27 answers use
only one layer, 13/27 use two, 2/27 use three, 0/27 use all four -- an
improvement over the pre-round-7 sample's 15/1/9/2/3/0 split on the same
question set (fewer single-layer answers, more two-layer), but the brief's
own diagnostic threshold ("if most answers still use one layer, the
completeness instruction did not take") is close to being crossed: 44% of
answers are still single-layer. Per the brief, the next step if this
persists across a larger sample is structural (a minimum-claims constraint
in the schema), not another paragraph of prompt.

Context utilization -- the other half of Task V -- makes a sharper version
of the same point: **0 of 27 answers cite or dismiss every retrieved
group**, and mean utilization is 0.346 (roughly one of the three retrieved
groups per question is accounted for). Critically, the `n_dismissed` count
is 0 across every single question -- the model never once produced a
synthesis claim explicitly naming and dismissing an irrelevant retrieved
group, despite `COMPLETENESS` asking for exactly that. Silently ignoring
retrieved material, not reasoned dismissal, is what's actually happening.

**Task W -- `DUPLICATE_CLAIM`.** Added to `audit()`: two `VerseClaim`/
`CommentaryClaim` claims sharing a layer and `verse_number` with >80% text
containment are flagged (never auto-merged), reproducing the brief's own
`pācenti`/`pājenti` scenario in a direct unit test. Did not fire on this
round's 27-question sample (no such duplication was produced this run) --
a "not observed this time" result, not evidence the check is unreachable in
practice; it remains a live check for the next run that reproduces it.

**Task X -- the retrieval finding, a third instance, still unresolved.**
Added "What does the Dhammapada say about life?" (gold Dhp 110, first of
the six-verse "better to live one day X than a hundred years Y" series,
Dhp 110-115) to `arm_diagnosis.py`. Result: **dense finds nothing in
top-10, sparse finds it at rank 8, fused finds nothing** -- worse than
either individual arm, and unlike Round 5's "purpose of life" case (which
turned out to be one structural chunk, the colophon, dominating all three
arms equally), here even the dense (semantic) arm fails outright, ranking
Dhp 135's cowherd-and-cattle simile (which merely contains the token
"life") above the entire conceptual series. This rules out the simplest
fix (reweight sparse down) for at least this instance: the problem is not
one arm dominating, it is that no arm's embedding of "life" as a query
concept lands near a six-verse series about *how to live*, and RRF fusion
compounds rather than corrects that. Publishable, per the brief -- three
independent instances of surface-token/single-chunk matching beating
conceptual relevance in a hybrid retrieval system over translated
religious text, each with a different mechanical cause (a colophon
structural artifact, a lexical near-miss, and now an outright dense-arm
miss), reported separately rather than averaged into one number.

**Task Y and two more fidelity errors found without targeted probing.**
The brief's own worked example (Dhp 135, "living beings desire rebirth
despite the suffering it brings" against a verse actually about aging and
death driving beings *out of* life) did not recur in this round's
27-question systematic sample -- documented in `docs/eval_rubric.md` as a
second worked example regardless, the same treatment the Kisā Gotamī case
received when it, too, fell outside every round's sample. What the ordinary
judging pass over this round's *actual* sample turned up instead, without
any targeted probing: `q001`#2 misattributes a refusal to see the Buddha to
"the Chief Disciples" when the nidana names Sañjaya, their former teacher,
as the one who refused; `q043`#2 conflates Māra's daughters (who tempted
the newly-awakened Buddha) with the unrelated Māgandiyā of a different
story, apparently because both narratives touch a name close to "Māgandiya".
Both are correctly tagged, cite a real retrieved `group_id`, and are false
-- the same structural-checks-cannot-reach-this class as the Kisā Gotamī and
Dhp 135 cases, found in ordinary sampling rather than by hunting for them.
Source fidelity on this round's sample: 47/52 = 0.904, five unfaithful
claims across four questions.

## Round 8: structural disposition, alignment's own block, and the RRF mechanism

**Task Z -- source_disposition, and why 0/27 became measurable instead of
just visible.** Round 7's `COMPLETENESS` instruction asked the model to
dismiss irrelevant retrieved groups in a synthesis claim; measured
utilization was 0.346 and the dismissal count was 0/27 -- an instruction
the model did not act on, the same wall citation *format* hit before Task
K's decoder-level enum. `LayeredAnswer` gained a required
`source_disposition: dict[str, Literal["used", "partially_relevant",
"not_relevant"]]` field, and `generate.py`'s `_constrained_schema()`
constrains it to an object with *exactly* the retrieved group_ids as keys
(`additionalProperties: False`, every key required) -- a schema-valid
answer cannot omit a group. `audit()` gained three matching checks
(`MISSING_DISPOSITION`, `UNKNOWN_DISPOSITION_GROUP`,
`DISPOSITION_CONTRADICTS_CLAIMS`) that never fired on the fresh 27-question
run: 27/27 questions carry a disposition for every retrieved group, and 0
disagreements between what a group was marked and what the claims actually
cited. The `not_relevant` rate is 42/81 = 0.519 -- roughly half of retrieved
groups, consistent with top_k=3 against single-gold questions -- and
**zero of those 42 are gold groups**: the model never once dismissed the
correct source. Cross-tabulated against gold labels per the brief's own
instruction, this cleanly separates two things Round 7 could not: every
`not_relevant` disposition observed this round reflects retrieval noise
correctly recognized, not generation misjudging a source that mattered.

**Task AA -- alignment recall, measured before and after.** Round 7:
alignment precision 1.000, recall 0.500 (4/8). Suspected cause: verse-range
and title data were rendered inside `[COMMENTARY]`, alongside Buddhaghosa's
actual narrative, so the model had no visual cue that a verse-range fact
belonged to a different taxonomy than the paragraph it sat in.
`format_verse_group()` now renders a separate `[ALIGNMENT -- modern
editorial apparatus, neither verse nor commentary]` block per source group,
before `[COMMENTARY]`, carrying the group_id/verse-range/title/synopsis
facts and its own `<<citation_fields group_id=... verse_numbers=...>>`
marker; `[COMMENTARY]` now renders only nidana/vatthu/desanavasane.
Re-measured on the identical 27-question sample: **alignment recall rose to
0.778 (7/9)**, precision 0.875 -- clears the brief's own ~0.75 bar, so the
prompt/rendering fix was sufficient on its own and the escalation to a
structural constraint (require an alignment claim on `verse_grouping`-type
questions) is not indicated by this sample. All 7 of the core "explains X
and Y together" / corpus-structure claims (`q091`, `q093`, `q095`, `q097`,
`q099`, `q119`, `q120`) are now tagged `alignment` -- `q093` and `q097`
specifically were Round 7's clearest misses and are hits this round.

**A new failure shape appeared in the same place the old one used to be.**
`q095` and `q097` each state their alignment fact TWICE in one answer: once
correctly (tagged `alignment`), once redundantly under the wrong tag
(`q095`'s second claim tagged `synthesis`, `q097`'s tagged `commentary`).
Not a missed alignment claim -- a duplicated one. `schemas.py`'s
`DUPLICATE_CLAIM` (Task W) does not catch this: it is scoped to
`VerseClaim`/`CommentaryClaim` pairs sharing a `verse_number`, and neither
of these cross-layer pairs has one (an `AlignmentClaim` and a
`SynthesisClaim`/`CommentaryClaim` stating the same fact). Flagged here as
a gap for a future round, not fixed this one -- extending duplicate
detection across layers is a different, looser containment problem than
Task W's same-layer check.

**A new label-leak pattern, not yet covered by any check.** `q119`'s
commentary claims open with `"Opening: ..."` and `"Close: ..."` -- copied
verbatim from `[COMMENTARY]`'s own field labels (`format_verse_group()`
renders `f"Opening: {nidana}"` / `f"Close: {desanavasane}"`), the same
copy-the-scaffolding failure `CITATION_IN_TEXT` and `LABEL_IN_TEXT` exist
to catch for `group_id:`/`verse_number:`/`verse:`/`commentary:` -- except
`_LABEL_PREFIXES` only lists layer/field-name labels, not the descriptive
labels used inside a rendered block. The claims' actual content is
faithful; the label is dead scaffolding a reader would have to mentally
strip, same complaint as every prior instance of this failure family. Worth
a mechanical check in a future round, not added this one (out of Round 8's
explicit scope).

**Task AC -- semantic-neighbour conflation, confirmed live without looking
for it, and a designed probe that did NOT reproduce it.** Ordinary judging
of this round's sample turned up a clean instance unprompted: `q099`
retrieves group 14.5 (an unnamed "certain discontented bhikkhu") alongside
group 14.6 (the Brahmin Aggidatta, marked `source_disposition:
not_relevant`) -- and the generated commentary claim names the 14.5
bhikkhu "Aggidatta," a name that belongs only to the dismissed neighbor.
The name migrated from a source the model itself correctly marked
irrelevant. This is the same failure class as `q043`'s Round 7 Māra's-
daughters/Māgandiyā conflation, found the same way (ordinary sampling, not
targeted probing) -- see `docs/eval_rubric.md`'s "Semantic-neighbour
conflation" section for the naming and the general prediction.

Separately, a **designed** test of the same hypothesis did not reproduce
it. The corpus carries twelve distinct "Elder Tissa" stories
(`group_id`s 1.3, 2.9, 3.7, 5.15, 7.7, 9.10, 12.3, 15.7, 18.3, 18.8, 20.5,
26.21); "who is elder Tissa?" retrieves three of them simultaneously
(1.3, 3.7, 20.5). A live generation on that query produced one claim,
correctly scoped to the one story its citation named, with no detail
migration. A second, harder probe -- a compound question explicitly naming
two Tissas by their distinguishing epithet ("the obstinate Elder Tissa,
the Buddha's relative" vs. "the Elder Tissa whose body developed sores") --
produced four claims, kept the two figures fully distinct, and one
commentary claim recounted a specific, checkable narrative detail (the
Devala/Nārada past-life story, including that Nārada trod on Devala's
matted locks twice) that matched the source vatthu exactly. **No
conflation on either Tissa probe.** The difference from `q043`/`q099`
worth naming: both real instances involved a retrieved-but-secondary group
whose *identifying name* was the only thing distinguishing it from the
target (Māgandiya the brahmin vs. Māgandiyā the woman; unnamed-bhikkhu vs.
named-neighbor Aggidatta), where the Tissa probes gave the model an
unambiguous distinguishing epithet for each figure in the question itself.
This narrows semantic-neighbour conflation's predicted trigger: it is not
mere name-or-role adjacency alone, but adjacency *combined with* an
under-specified or missing distinguishing detail in what the model has to
work with. Worth stating as a refined, falsifiable prediction rather than
leaving the broader claim unqualified.

**Task AB -- the RRF mechanism, checked against the full 114-question set,
not just the one "life" query.** Full account and the k-sweep table:
`docs/evaluation.md`'s Round 8 section. Two things checked before running
anything: first, whether Dhp 110 is even a defensible single gold answer
for "what does the Dhammapada say about life?" -- it is not; Dhp 135 and
Dhp 182 are both independently defensible answers to the same question
(mortality and the rarity of human life, respectively, against Dhp
110-115's "how to live"), so the Round 7 finding that no arm ranks Dhp 110
highly should not be read as "the system failed," only as evidence about
arm coverage on a genuinely multi-answer query -- noted directly in
`arm_diagnosis.py` rather than left implicit. Second, the k-sweep itself:
overall nDCG@10 barely moves across `rrf_k` in {10, 20, 40, 60} (0.9544 /
0.9566 / 0.9595 / 0.9592) -- ceiling effects dominate this gold set almost
everywhere. The one query type with any real sensitivity, `corpus_anomaly`
(nDCG@10 0.0 at k=10/20, 0.1667/0.1505 at k=40/60), has n=2 questions --
too small to support a directional claim, and the movement observed runs
opposite the arithmetic argument's naive prediction (which favors *lower*
k for single-arm discoveries), most plausibly sampling noise on 2
questions rather than a real effect. Score-based fusion (min-max normalize
each arm's raw score, then sum) underperforms every swept RRF k overall
(0.9510 vs. 0.9544-0.9595), driven mostly by a doctrinal-type drop
(0.9298 vs. 0.9508) -- the theoretical argument for why RRF *should*
penalize single-arm discoveries is arithmetically sound and independently
verified, but does not translate into a practical win for the fusion
alternative on this corpus. No k or fusion method was adopted; per the
brief, `rrf_fuse()`'s default `k=60` is unchanged.

## Round 9: quote fidelity

**Task AE -- corpus checked before any code changed.** Both flagged quotes
were checked against `data/processed/verses.jsonl` directly: Dhp 194's
`pali_mahasangiti` (93 chars) and `interlinear_pali` (94 chars) both carry
all four pādas, as does Dhp 273's (94 chars each). The corpus is complete;
the truncation observed in the brief's example answer was the model's, not
an extraction gap -- Task AF applies, not a `docs/corpus_audit.md` addition.
The suspected cross-verse attribution of `saccānaṁ caturo padā` was also
checked directly: it is genuinely the first line of Dhp 273's own text
(`Maggānaṭṭhaṅgiko seṭṭho, saccānaṁ caturo padā, virāgo seṭṭho dhammānaṁ,
dipadānañ-ca Cakkhumā.` -- Ānandajoti's text; the edition quoted here
originally was SuttaCentral's, removed 2026-10-08), not a neighbouring verse's words -- not cross-verse
contamination in this instance.

Inspecting `audit()`'s Pali matching per the brief's instruction found a
real, distinct instance of the *class* of bug asked about, though not the
one first suspected: a story's `pali_verse` field quotes only one verse of
its (possibly multi-verse) group -- `pali_verse_number` records which -- but
`audit()` was attaching it as a valid candidate to *every* verse in
`dhp_verses`. Live example: group 20.1 covers Dhp 273-276 with
`pali_verse_number=273`; before the fix, a claim citing Dhp 274 with
`pali_support` actually equal to Dhp 273's text would validate cleanly --
real Pali from the retrieved group, attached to the wrong verse within it,
exactly the failure mode the brief named. Fixed to match per cited verse
only (`pali_candidates_by_number` keyed by `pali_verse_number`, not every
verse in the group), falling back to the group union only when
`pali_verse_number` is absent, per the brief's own instruction. Regression
tests: `test_pali_verse_not_attributed_to_sibling_verse_in_multi_verse_group`,
`test_pali_verse_still_validates_against_its_own_verse_number`,
`test_pali_verse_falls_back_to_group_union_when_verse_number_absent`.

**Task AF -- `PALI_QUOTE_TRUNCATED`.** Added at `PALI_COVERAGE_THRESHOLD =
0.6`, computed on the orthographically folded forms, checked against
whichever field the quote actually matched at exact/variant tier (fabricated
quotes are excluded -- there is no verse text to measure coverage against).
The brief's own two examples, checked against the live coverage formula:
Dhp 194 truncated to its first two pādas measures 0.500 coverage; Dhp 273
truncated to its first line measures 0.494 -- both below threshold,
confirming 0.6 catches the observed failure without needing to be tuned
tighter. `aggregate_generation.py` now reports `quote_coverage_rate`
alongside the existing exact/variant/fabrication tiers, computed against
each cited verse's own `pali_mahasangiti` (the canonical field, regardless
of which field `audit()` matched at generation time, since the aggregation
script works from `generation_raw.jsonl`'s claims alone and has no bundle to
re-derive the matched field from). On the existing 27-question
`generation_raw.jsonl`: 6/7 pali_support quotes resolve (1 fabrication,
excluded), mean coverage 0.850 -- no quote in that run is anywhere near the
0.6 floor, so this run's Pali quotes, where genuine, are substantially
complete, not merely non-fabricated.

**Task AG -- widened `CITATION_IN_TEXT`.** The colon-suffixed markers
(`"group_id:"`, `"verse_number:"`) never matched the observed leak shape,
`"(group_id 14.8)"` -- a space and a parenthesis, not a colon. Widened to
bare field names (`group_id`, `verse_number`, `pali_support`,
`citation_fields`) matched case-insensitively anywhere in the text,
regardless of what follows. `pali_support` was added to the marker set on
the same reasoning: the field name itself, not its punctuation context, is
what makes prose unusable. Live-confirmed on a fresh run of the exact
question from the brief ("what is the best thing in life according to the
Dhammapada"): two commentary claims read `"The story about the five hundred
bhikkhus (group_id 20.1) explains..."` and `"The story about Sakka
(group_id 24.10) explains..."` -- both now caught (`CITATION_IN_TEXT`,
error); neither would have tripped the pre-Round-9 marker set.

**Task AH -- scope-widening, prompt fix, and an honest partial result.**
VERSE CLAIM SPECIFICITY extended per the brief's instruction (comparatives/
conditionals/negations must survive the paraphrase). Re-running the exact
question live (qwen2.5:7b-instruct, same retrieval): the Dhp 103 probe
("who is the supreme conqueror?") produced a claim that correctly keeps the
comparative's bound -- [SuttaCentral text removed 2026-10-08] -- with zero warnings. The Dhp 273 claim's fourth clause also
now correctly keeps its bound ("the Visionary as the best of **humans**",
i.e. *dvipadānaṁ*, two-footed beings). But the same claim's first three
clauses did not: *"the best thing in life is the eightfold path, the four
noble truths, dispassion, and the Visionary as the best of humans"* still
frames path/truths/dispassion under the unqualified "best thing in life"
container, only now listing all four parallel items instead of one. The
Dhp 354 probe (`sabbadānaṁ dhammadānaṁ jināti`) fared better: "the ending of
craving... overcomes all suffering" keeps the verse's actual bound (*all
suffering*, not *everything*). **Net: the prompt fix measurably reduces but
does not eliminate scope-widening in this run** -- it succeeds cleanly on
single-comparative verses (103, 354) and on the last clause of a
four-part-parallel verse (273's cakkhumā line), but a claim compressing all
four parallel members of Dhp 273 into one sentence still drops three of the
four qualifiers. This is consistent with the rubric's characterization
(`docs/eval_rubric.md`'s new Scope-widening subtype) as a paraphrase failure
requiring semantic judgment, not a mechanically closable gap -- a single
LLM-authored prompt sentence narrowed the failure surface without closing
it, and a claim compressing several parallel comparatives into one sentence
remains the harder case. Not escalated to a structural check in this round:
unlike `source_disposition` or citation completeness, "did this claim keep
every category qualifier its source verse states" has no schema-level
representation to constrain against.
