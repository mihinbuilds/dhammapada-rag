# Task brief — round 3: presentation defects

Rounds 1 and 2 worked. On "the woman whose child died" the system retrieves
Dhp 287 (Kisā Gotamī, story 20.11), Dhp 114 (Kisā Gotamī, story 8.13), and
Dhp 113 (Paṭācārā, story 8.12) — three relevant groups, no junk — and renders
readable prose at ~5218 tok / num_ctx 16384. Retrieval and generation are
behaving.

Four defects remain. Three are presentation-layer; one is a real model error
the audit caught correctly. None require re-running the evaluation **except**
Task D, which changes the prompt.

---

## Task A — Renderer prints raw group_id instead of the normalized one

**Symptom.** A citation renders as `[Dhp 287, DhpA Dhp 20.11]`. "DhpA Dhp
20.11" is malformed; it should read `DhpA 20.11`.

**Cause.** The model emitted `group_id="Dhp 20.11"`. `normalize_group_id()`
reduces that to `"20.11"` correctly, which is why it appears under format
warnings rather than errors. But `render.py`'s `_cite()` interpolates the raw
`c.group_id`, so the display shows the model's typo rather than the resolved
value.

**Do.** In `src/dhammapada_rag/generate/render.py`, normalize before display
and drop any citation component that cannot be resolved:

```python
from dhammapada_rag.generate.schemas import normalize_group_id

def _cite(c: Claim) -> str:
    parts = []
    if c.verse_number is not None and 1 <= c.verse_number <= 423:
        parts.append(f"Dhp {c.verse_number}")
    gid = normalize_group_id(c.group_id)
    if gid is not None:
        parts.append(f"DhpA {gid}")
    return f" [{', '.join(parts)}]" if parts else ""
```

An unresolvable `group_id` must not be printed at all. Showing a citation the
system knows is broken is worse than showing none: the reader has no way to
tell that the audit already rejected it. The warning panel is where that
belongs.

**Verify.** Same question; every citation matches `[Dhp N]`,
`[DhpA v.s]`, or `[Dhp N, DhpA v.s]`. No citation contains the substring
`DhpA Dhp`.

---

## Task B — Lead-in repeats on every claim

**Symptom.** "The verse states… **The commentary relates**: … **The commentary
relates**: …" — the same lead-in twice in a row, in one run-on paragraph.

**Cause.** My `render.py` applies a lead-in per claim. It should mark the
*transition* between layers. Within a run of same-layer claims, only the first
needs one.

**Do.** In `render_markdown()`, track the previous claim's layer and pass a
flag so `_sentence()` emits a lead only when the layer changes (or on the first
claim). Continuation sentences in the same run render plain, still with their
own inline citation. Keep the existing behaviour of starting a new paragraph on
each layer change — the screenshot shows verse and commentary claims running
together in one block, so confirm the `\n\n` join is actually reaching the
markdown output.

Target shape:

> **The verse states** that the person whose mind is attached to cattle and
> children is snatched away by death as a sleeping village by a flood.
> [Dhp 287, DhpA 20.11]
>
> **The commentary relates** that Kisā Gotamī, daughter of a wealthy merchant,
> lost her only child shortly after he learned to walk. [Dhp 287, DhpA 20.11]
> She went house to house seeking medicine for him and found none, because no
> household had never been untouched by a death. [Dhp 114, DhpA 8.13]

**Verify.** No two consecutive sentences begin with the same lead-in phrase.

---

## Task C — Angle brackets in warning messages are eaten by Streamlit

**Symptom.** The error panel reads `does not reduce to canonical '.' form`.
The actual message is `'<vagga>.<story>'`; Streamlit's markdown parses those as
HTML tags and strips them.

**Do — both ends.**

1. In `generate/schemas.py`, remove angle brackets from every warning message.
   Use `'vagga.story'` (for example: `does not reduce to canonical
   'vagga.story' form`). Grep the file for `<` in message strings; there is
   also `<<citation_fields>>` referenced in prompt text.
2. In `ui/app.py`, escape warning text before rendering — `html.escape(...)`,
   or render with `st.code()` / `unsafe_allow_html=False`. Message strings
   embed model output, so any future `<` in a claim would silently corrupt the
   panel the same way.

**Verify.** Force an unparseable citation and confirm the message displays the
full expected-format string.

---

## Task D — Model puts a verse number in group_id

**Symptom.** `claim 2: group_id='Dhp 114'` → `UNPARSEABLE_GROUP_ID`. The audit
is right: `114` is a verse number, and the story explaining Dhp 114 is `8.13`.
The model conflated the two citation fields.

**Cause.** Both fields are numeric and adjacent in the prompt, and the model
has just written "Dhp 114" in its prose. The current instruction names the
format but does not contrast the two fields against each other.

**Do.** In `generate/prompt.py`, extend the `CITATIONS.` paragraph of
`SYSTEM_PROMPT`:

```
These are two DIFFERENT numbers and they are never interchangeable:
- verse_number is a single integer, 1 to 423. Example: 114
- group_id is two integers joined by a period, vagga.story. Example: 8.13
A verse number in the group_id field is invalid. "Dhp 114", "114", and
"Dhp 8.13" are all wrong; only "8.13" is correct. Copy each value from the
<<citation_fields>> marker of the source you are citing.
```

**Verify.** Re-run "the woman whose child died" three times. Zero
`UNPARSEABLE_GROUP_ID` errors. Then re-run the generation eval and the sweep,
since the prompt changed:

```bash
python -m dhammapada_rag.eval.generation_metrics    # then re-judge
python -m dhammapada_rag.eval.aggregate_generation
python -m dhammapada_rag.eval.model_sweep --max-retries 0
```

---

## Still outstanding, not in scope for this round

**No Pali reaches the reader.** The corpus has `pali_mahasangiti` for all 423
verses, the prompt shows it, and `Claim` has no field to carry it — so a system
built on the verse/commentary distinction never displays the verse in its own
language. Fixing it means adding an optional `pali_support: str | None` to
`Claim`, instructing the model to quote the relevant pāda on verse claims, and
validating the quoted string against the retrieved Pali (substring match after
Unicode NFC normalization; a non-matching quote is a fabrication and should be
an error-severity warning). Do this as its own round — it touches the schema,
the prompt, the audit, and the renderer, and it will need its own eval pass.

## Do not

- Print a citation the audit could not resolve. Drop it and let the warning
  panel carry the failure.
- Suppress or downgrade `UNPARSEABLE_GROUP_ID`. It fired correctly; the model
  was wrong.
- Tune retrieval. Nothing in this round touches it.
