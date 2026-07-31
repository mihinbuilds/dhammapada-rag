"""Compose a tagged `LayeredAnswer` into reader-facing prose.

`generate/schemas.py` deliberately withholds a free-text summary field from
the model -- an untagged paragraph is the escape hatch a conflated
verse/commentary claim would slip through untagged (see that module's
docstring). This module is the client-side half of that decision: prose is
composed here, from already-tagged claims, after generation and after
audit() has already run.

The layer distinction is kept in the sentence itself ("The verse states..."
vs "The commentary relates...") rather than living only in a UI badge or
color, because a badge disappears the moment someone copies the text into
an essay or a paper -- the sentence form is what travels with the text.
Do not collapse this back into undifferentiated prose; a reader who never
sees the app still needs to be able to tell which layer a sentence came
from.
"""

from __future__ import annotations

from dhammapada_rag.generate.schemas import Claim, LayeredAnswer

# Reported-speech openers, not fragments spliced into a shared sentence --
# claims are written as complete standalone statements (schema: "One claim,
# in the model's own words"), so "The verse states: <claim>" is grammatical
# regardless of how the model phrased the claim itself.
_OPENERS = {
    "verse": "The verse states",
    "commentary": "The commentary relates",
    "synthesis": "By way of synthesis",
}


def _citation(c: Claim) -> str:
    # Synthesis claims should carry no citation (schemas.audit() flags one
    # that does, SYNTHESIS_WITH_CITATION) -- callers skip this for synthesis
    # claims rather than relying on both fields being None here.
    if c.verse_number is not None and c.group_id is not None:
        return f" [Dhp {c.verse_number}, DhpA {c.group_id}]"
    if c.verse_number is not None:
        return f" [Dhp {c.verse_number}]"
    if c.group_id is not None:
        return f" [DhpA {c.group_id}]"
    return ""


def _sentence(c: Claim, *, bold_opener: bool) -> str:
    text = c.text.strip()
    if not text:
        return ""
    opener = _OPENERS.get(c.layer)
    citation = "" if c.layer == "synthesis" else _citation(c)
    if opener is None:
        return f"{text}{citation}"
    label = f"**{opener}**" if bold_opener else opener
    return f"{label}: {text}{citation}"


def render_markdown(answer: LayeredAnswer) -> str:
    """One prose paragraph, claim order preserved, each sentence carrying
    its own layer marker (bold) and inline citation.

    Plain Markdown only (no raw HTML) -- safe to pass straight to
    `st.markdown()` without `unsafe_allow_html`.
    """
    sentences = [_sentence(c, bold_opener=True) for c in answer.claims]
    return " ".join(s for s in sentences if s)


def render_plain(answer: LayeredAnswer) -> str:
    """Same composition as `render_markdown`, without Markdown emphasis --
    for terminal/CLI output (`generate.py`'s `main()`)."""
    sentences = [_sentence(c, bold_opener=False) for c in answer.claims]
    return " ".join(s for s in sentences if s)
