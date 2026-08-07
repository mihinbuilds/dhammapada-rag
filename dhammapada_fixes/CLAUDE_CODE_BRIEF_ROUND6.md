# Task brief — round 6: orthographic variants, HTML leak, PC migration

The Pali layer now renders and the substring check is live. It flagged two of
three verse claims. **Both flags are orthographic variants of the correct
verse, not fabrications**, and treating them as fabrications makes the metric
meaningless.

| Claim | Model wrote | Mahāsaṅgīti has | Difference |
|---|---|---|---|
| Dhp 221 | `sabbam-atikkameyya` | `sabbamatikkameyya` | one hyphen |
| Dhp 222 | `bhantaṁ va`, `tam-ahaṁ` | `bhantaṁva`, `Tamahaṁ` | space, hyphen, case |
| Dhp 223 | (exact) | (exact) | passed |

The hyphenation is Ānandajoti's sandhi-splitting convention. The model is
reproducing a **different edition's orthography of the right verse**. That is
edition variance — the phenomenon this project exists to represent — not an
invented quote.

---

## Task O — Determine the source of the variant orthography (do first)

This changes what the rest of the round means, so establish it before writing
any code.

```bash
python - <<'EOF'
from pathlib import Path
import sys; sys.path.insert(0, "src")
from dhammapada_rag.index.assemble import query
from dhammapada_rag.generate.prompt import build_messages
root = Path(".")
b = query("what does the Dhammapada say about anger?", top_k=3, root=root)
msgs = build_messages("what does the Dhammapada say about anger?", b)
text = "\n".join(m["content"] for m in msgs)
for probe in ("sabbam-atikkameyya", "sabbamatikkameyya", "tam-ahaṁ", "Tamahaṁ"):
    print(f"{probe!r:28s} in prompt: {probe in text}")
EOF
```

**If the hyphenated forms appear in the prompt** — `interlinear_pali` or a
story's `pali_verse` is reaching the context. The model copied faithfully from
a field the audit doesn't check. This is an audit bug: fix by widening the
comparison set (Task P).

**If they do not appear** — the model is reciting Ānandajoti's edition from
parametric memory while the Mahāsaṅgīti text sits in front of it. This is a
substantive finding: retrieval-augmented generation, with the correct source in
context, producing a memorized variant instead. Report it as such, and it
becomes the headline result of the Pali work rather than a validation detail.

Record which it is in `docs/evaluation.md` before proceeding. Do not skip this
step — the two cases support opposite claims.

---

## Task P — Three-tier Pali matching

Whatever Task O finds, a binary match/fabricate check is wrong. Replace it with
three outcomes.

**Do.** In `generate/schemas.py`:

```python
import re
import unicodedata

def _pali_exact(s: str) -> str:
    """NFC only. Catches byte-identical copying."""
    return unicodedata.normalize("NFC", s)


def _pali_orthographic(s: str) -> str:
    """Fold the conventions that differ between editions but not the words.

    Editions of the Pali canon differ systematically in how they mark sandhi
    (Anandajoti hyphenates 'sabbam-atikkameyya' where Mahasangiti writes
    'sabbamatikkameyya'), in niggahita glyph (ṁ vs ṃ), in capitalisation at
    pada boundaries, and in punctuation. None of these change the text; all of
    them defeat a substring test. Folding them separates "quoted a different
    edition" from "invented a quote" -- a distinction that matters more in this
    project than in most, since edition variance is part of the subject matter.
    """
    s = unicodedata.normalize("NFC", s).lower()
    s = s.replace("ṃ", "ṁ").replace("ṅ", "ṁ")   # niggahita variants
    s = s.replace("-", "").replace("’", "").replace("'", "")
    s = re.sub(r"[.,;:!?\"“”]", "", s)
    return re.sub(r"\s+", "", s)                 # spacing is not lexical here
```

Add code `PALI_QUOTE_ORTHOGRAPHIC_VARIANT` at **warning** severity. Keep
`PALI_QUOTE_NOT_IN_SOURCE` at error. In `audit()`, compare each
`pali_support` against **every** Pali field available for the cited verse —
`pali_mahasangiti`, `interlinear_pali`, and the story's `pali_verse` where
present — and record which field matched:

- exact substring of any field → no warning; record `matched_field`
- orthographic-normalized substring of any field → warning, message naming
  the field matched and the specific difference
- neither → error, unchanged

Report three rates, not one: **exact-copy rate**, **variant rate**, and
**fabrication rate**. Exact-copy rate is the real measure of whether the model
is reading its context. A high variant rate with a near-zero fabrication rate
means the model knows the text but is not copying it — which is the finding.

**Verify.** Dhp 221 and 222 move from error to warning. Dhp 223 stays clean.
Then run the same probe on `qwen2.5:14b-instruct` and compare exact-copy rates;
if the larger model copies where the smaller recalls, that is a scaling result
with a mechanism behind it, and worth more than the latency curve.

---

## Task Q — The `\x01m` corruption is separate; trace it

A literal `\x01` byte is a pipeline artifact, not a model behaviour. Do not fold
it into the Pali metric. Trace where it enters:

```bash
grep -Pn '[\x00-\x08\x0b\x0c\x0e-\x1f]' data/processed/*.jsonl | head
grep -Pn '[\x00-\x08\x0b\x0c\x0e-\x1f]' data/index/chunks.jsonl | head
```

If control characters are present in `data/processed/`, the corruption is
upstream in `ingest/`, some Pali chunks were embedded corrupted, and retrieval
has been quietly degraded on those verses — report before changing anything.
If the corpus is clean, the corruption enters at prompt rendering or in
Ollama's JSON round-trip; add a control-character strip at the boundary and a
test asserting no control characters survive `build_messages()`.

---

## Task R — Raw `</div>` leaking into the commentary card

**Symptom.** The commentary claim card renders a code block containing
`</div>`.

**Cause.** `SynthesisClaim` and `CommentaryClaim` have no `pali_support` field
(correct — only verse claims carry Pali), so the template's conditional emits a
closing tag with no opening one. Unbalanced HTML with
`unsafe_allow_html=True`.

**Do.** In `ui/app.py`, build the card as one complete string per claim rather
than emitting open and close tags in separate `st.markdown()` calls, and gate
the Pali block on `getattr(claim, "pali_support", None)` rather than on layer.
Escape claim text with `html.escape()` before interpolation — claim text is
model output and may contain `<` at any time.

**Verify.** No raw tags in any card, for all three layer types.

---

## Task S — PC migration: device selection

The project was developed on Apple Silicon. `rerank.py` checks
`torch.backends.mps.is_available()` and otherwise falls back to CPU fp32;
`embed.py` hardcodes `devices=["cpu"]`. On a PC with an NVIDIA GPU both will
run on CPU, and neither will use the hardware.

**Do.** Add to `index/rerank.py` and reuse in `index/embed.py`:

```python
def best_device() -> tuple[str, bool]:
    """Return (device, use_fp16).

    fp16 is a win on CUDA and MPS and typically a loss on CPU, where most
    hardware does not accelerate it -- hence the paired return rather than a
    bare device string.
    """
    import torch
    if torch.cuda.is_available():
        return "cuda", True
    if torch.backends.mps.is_available():
        return "mps", True
    return "cpu", False
```

Use it in both modules. Log the selected device at startup so a silent CPU
fallback is visible rather than inferred from slow runs.

**Also check on the new machine.**

1. `ollama ps` while a query runs — confirm the model reports GPU, not 100%
   CPU. The 38–90s latencies observed on the old machine should drop
   substantially; if they do not, generation is still on CPU.
2. Console encoding. Windows terminals default to cp1252 and will mangle
   diacritics on print. Set `PYTHONUTF8=1`, and confirm every file read/write
   in the codebase passes `encoding="utf-8"` explicitly (most already do —
   verify `ingest/` too).
3. Path separators: `Path` handles this, but grep for any hardcoded `/` in
   string paths.
4. Re-run `pytest` and the six probes on the new machine before trusting any
   number produced there. A device change alters float precision and can shift
   retrieval ranks at the margin; if any probe result changes, record it —
   cross-platform reproducibility is worth a line in the paper.

---

## Still open from earlier rounds

- **Story 23.1 title/body mismatch** — flagged in round 4, unreported across
  three rounds. Title reads "The Story about Speaking and Rousing Oneself";
  the narrative retrieved under it concerns Māgandiyā inciting abuse. If
  `ingest/parse_stories.py` misaligned a title with a body, the alignment
  table — the project's most citable artifact — has an error in it. Check and
  report before the next full eval.
- **RRF arm diagnosis** (round 5, Task M) — two clean instances of lexical
  surface matching beating conceptual relevance are on record. The four-way
  comparison turns an anecdote into a result.
- **Verse-claim specificity** — "The Dhammapada advises to abandon all anger"
  is still a summary about the book rather than a statement of what Dhp 221
  says. Improved but not resolved.

## Do not

- Report a single "Pali match rate". Report exact / variant / fabrication
  separately; the middle tier is where the finding lives.
- Loosen the exact-match tier to make the numbers look better. The gap between
  exact and variant is the measurement.
- Fold the `\x01` corruption into the Pali metric. Different failure, different
  cause.
