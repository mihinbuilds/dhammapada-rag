# Task brief — round 4: catch the conflation mechanically

Round 2's Task C worked: "which single story explains Dhp 320, 321, and 322
together?" now retrieves story 23.1 at rank 1, covering exactly those three
verses. Round 3's tasks A, B, and C are **not applied yet** — do those first,
they are unchanged.

This round addresses a new failure found by comparing two runs, plus two
regressions.

---

## Task F — Detect verse text presented as commentary (highest value)

**The observation.** The same sentence appears in two runs with two different
layer tags:

- Query "what does the Dhammapada say about anger?" → tagged **verse**
- Query "how to control anger?" → tagged **commentary**

The sentence is *"When anger surges like a lurching chariot, keep it in check.
That's what I call a charioteer; others just hold the reins."* That is Dhp 222,
verbatim canonical verse. Tagging it `commentary` presents the Buddha's words
as Buddhaghosa's 5th-century gloss — the exact inversion this project exists to
prevent, and the mirror image of the failure the layer tags were designed to
catch.

**The cause is our own prompt.** Round 1 added a COVERAGE requirement ("produce
at least one commentary claim") to stop all-verse output. When retrieval
returns verse-heavy groups with little usable narrative, the model satisfies
that instruction by relabelling a verse. We fixed one failure and induced its
opposite.

**Why this matters more than the bug.** It is mechanically detectable. A claim
tagged `commentary` whose wording overlaps heavily with the retrieved verse
text is, by construction, verse content mislabelled. No annotator needed. This
turns a semantic error into a structural check — the thing `audit()` was
previously unable to do.

**Do — part 1: the check.** Add to `generate/schemas.py`:

```python
import re
import unicodedata

# A commentary claim whose wording is mostly lifted from the verse is verse
# content mislabelled. 0.60 is deliberately conservative: commentary legitimately
# quotes and glosses the verse it explains, so a moderate overlap is expected and
# only a dominant one is evidence of mislabelling. Tune against
# data/eval/generation_raw.jsonl, and report the threshold in the paper.
VERSE_OVERLAP_THRESHOLD = 0.60
MIN_CONTENT_WORDS = 6

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "in",
    "to", "and", "or", "that", "this", "with", "as", "for", "by", "on", "at",
    "it", "its", "one", "who", "not", "but", "from", "his", "her", "their",
}


def _content_words(text: str) -> set[str]:
    s = unicodedata.normalize("NFC", text).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return {w for w in s.split() if w not in _STOPWORDS and len(w) > 2}


def _containment(claim_text: str, source_text: str) -> float:
    """Fraction of the claim's content words that appear in the source.

    Containment rather than Jaccard: the verse is short and the claim may be
    shorter still, so a symmetric measure would be dominated by length
    difference rather than by shared wording.
    """
    c = _content_words(claim_text)
    if len(c) < MIN_CONTENT_WORDS:
        return 0.0
    s = _content_words(source_text)
    return len(c & s) / len(c)
```

Add the code `VERSE_TEXT_AS_COMMENTARY` at **error** severity. Inside
`audit()`, build a verse-text lookup from the bundles once:

```python
verse_text_by_number: dict[int, str] = {}
all_verse_text: list[str] = []
if bundles is not None:
    for b in bundles:
        for v in b["verses"]:
            parts = [v.get("pali_mahasangiti"), v.get("english_sujato"),
                     v.get("interlinear_english")]
            joined = " ".join(p for p in parts if p)
            verse_text_by_number[v["verse"]] = joined
            all_verse_text.append(joined)
```

Then, for each claim where `c.layer == "commentary"`, compare against the cited
verse if `verse_number` is set and resolvable, otherwise against the union of
retrieved verse text. If containment exceeds the threshold, emit the error with
the measured value in the message so the number is auditable, not just a verdict.

**Do — part 2: make COVERAGE conditional.** In `generate/prompt.py`, replace
the unconditional commentary requirement with one that has an explicit escape
hatch, so the model is never forced to manufacture a commentary claim:

```
COVERAGE. Each source below carries both layers. Draw on both where both bear
on the question. If the retrieved commentary genuinely does not address the
question, say so in a "synthesis" claim and answer from the verse alone. Never
relabel verse text as commentary to satisfy this instruction: restating a verse
and tagging it "commentary" is a serious error, worse than producing no
commentary claim at all.
```

**Verify.** Run both anger queries. The Dhp 222 sentence must be tagged `verse`
in both, or if tagged `commentary`, must trigger `VERSE_TEXT_AS_COMMENTARY`.
Then check the detector against `data/eval/generation_raw.jsonl` and report how
many existing commentary claims it flags — that number goes in the paper.

---

## Task G — Measure layer-tag stability

The same claim receiving different tags across queries is measurable, and no
published RAG system reports it, because none has a layer-tagged architecture
to measure.

**Do.** Add `src/dhammapada_rag/eval/tag_stability.py`. For each of 15 verses
that appear in the gold set, construct 3 differently-phrased questions that
should surface it. Generate all 45 answers. Group claims whose text has ≥0.8
containment with each other, and report:

```
tag_stability = (groups where every member shares one layer tag) / (groups with >1 member)
```

Report per layer. Instability concentrated in one layer is a more specific
finding than an overall rate. This is a small, self-contained script and a
genuinely novel metric — give it a subsection in `docs/evaluation.md`.

---

## Task H — Answer the question that was asked

**Symptom.** "Which single story explains Dhp 320, 321, and 322 together?"
retrieved story 23.1 correctly and then produced two claims narrating the
story's content — without ever naming the story or stating that it explains all
three verses. The retrieval succeeded and the answer did not respond to the
question.

**Do.** Add to `SYSTEM_PROMPT`:

```
DIRECT ANSWER. If the question asks which story, which verse, or how many —
answer it directly in your first claim, naming the story or verse explicitly,
before adding supporting detail. A question about the structure of the text
("which single story explains verses X, Y, Z?") is asking for the story's
identity and title, not a retelling of its narrative.
```

**Verify.** Re-run the Dhp 320/321/322 question. The first claim must name
story 23.1 and its title.

**Also check.** Story 23.1's stored `title_en` reads "The Story about Speaking
and Rousing Oneself", but the narrative retrieved under it concerns Queen
Māgandiyā inciting abuse against the Buddha. Verify against
`sources/Dhammapada-Attakatha.pdf` whether the title and body were correctly
paired by `ingest/parse_stories.py`. If a parsing error misaligned them, that
affects the corpus and must be found before any further eval run. **Report
before changing anything under `data/processed/`.**

---

## Task I — Two regressions

**I-1. `MISSING_PROVENANCE` on multi-verse questions.** Both claims in the
Dhp 320/321/322 run came back with null `group_id` and `verse_number`. Likely
cause: the claim concerns three verses at once and the model, unable to choose
one, emitted nothing. Add to the CITATIONS section:

```
A claim about a verse group cites the group's FIRST verse number. Never leave
group_id or verse_number empty on a verse or commentary claim — an uncited
claim is unusable regardless of how accurate it is.
```

**I-2. Factual inversion, still present.** The Kisā Gotamī answer states she
found no medicine "because no household had ever seen a death." The commentary's
point is the reverse: every household had. This passes every structural check —
correct layer, resolvable citation, traceable provenance — and is false.

Add `faithful: bool` to every entry in `data/eval/generation_judgments.py`
(alongside `gold_layer`) and have `aggregate_generation.py` report **source
fidelity rate** separately from layer attribution accuracy. Document in
`docs/eval_rubric.md` that structural provenance checking cannot detect semantic
infidelity, using this claim as the worked example.

---

## Task J — Surface the Pali (do last, own eval pass)

The corpus has `pali_mahasangiti` for all 423 verses, the prompt shows it, and
no Pali reaches the reader. A system built on the verse/commentary distinction
displays neither verse in its original language.

1. Add `pali_support: str | None` to `Claim`, documented as: for a verse claim,
   the pāda from the provided Pali that this claim rests on, copied exactly.
2. Prompt the model to populate it on verse claims.
3. Validate in `audit()`: NFC-normalize both sides and require the quoted string
   to be a substring of the cited verse's `pali_mahasangiti`. A non-matching
   quote is a fabricated primary source — error severity, code
   `PALI_QUOTE_NOT_IN_SOURCE`.
4. Render it in `render.py` as an indented line beneath the verse claim.

This touches schema, prompt, audit, and renderer together, and needs its own
eval pass. Do not bundle it with F–I.

---

## Re-run after F, H, I-1 (all change the prompt)

```bash
pytest tests/test_provenance.py -v
python -m dhammapada_rag.eval.generation_metrics    # then re-judge with gold_layer + faithful
python -m dhammapada_rag.eval.aggregate_generation
python -m dhammapada_rag.eval.model_sweep --max-retries 0
python -m dhammapada_rag.eval.tag_stability
```

Retrieval is unchanged by this round — no need to re-run `retrieval_eval.py`.

## For the write-up

Round 1 fixed all-verse output by requiring commentary engagement. Round 4 found
that the requirement induces the opposite error: verse text relabelled as
commentary. Report both, in sequence, with the detector and its flag rate.

The honest framing is that a prompt instruction to use a source layer creates
pressure to *claim* that layer regardless of content, and that the resulting
error is invisible to citation-based checking — the citation is correct, the
provenance is traceable, and the attribution is backwards. That is a general
result about layer-attributed RAG, not a quirk of this corpus, and it is the
strongest thing this project has to say.

## Do not

- Drop the COVERAGE requirement entirely. Round 1 showed what happens without
  it. Make it conditional, not absent.
- Tune `VERSE_OVERLAP_THRESHOLD` to minimise flags. Set it on inspection of
  actual claims and report the value.
- Touch `data/processed/` without reporting first (see Task H).
