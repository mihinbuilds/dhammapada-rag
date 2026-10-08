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

from dhammapada_rag.generate.schemas import Claim, LayeredAnswer, VerseClaim, normalize_group_id

# Reported-speech openers, not fragments spliced into a shared sentence --
# claims are written as complete standalone statements (schema: "One claim,
# in the model's own words"), so "The verse states: <claim>" is grammatical
# regardless of how the model phrased the claim itself.
#
# Round 7, Task T: "alignment" keeps the same colon-joined mechanism as the
# other three layers ("The alignment table records: <claim>") rather than a
# one-off "records that <claim>" construction, for consistency with
# _sentence()'s single shared join logic below -- introducing a second
# grammar path for one layer would be the kind of special case this module's
# uniform-openers design exists to avoid.
_OPENERS = {
    "verse": "The verse states",
    "commentary": "The commentary relates",
    "alignment": "The alignment table records",
    "synthesis": "By way of synthesis",
}


def _citation(c: Claim) -> str:
    # Synthesis claims should carry no citation (schemas.audit() flags one
    # that does, SYNTHESIS_WITH_CITATION) -- callers skip this for synthesis
    # claims rather than relying on both fields being None here.
    #
    # Round 3, Task A: normalize group_id before display and drop it entirely
    # if it doesn't resolve, rather than printing the model's raw string. The
    # observed failure was group_id="Dhp 20.11" -- normalize_group_id()
    # reduces that to "20.11" (correctly demoted to a MALFORMED_GROUP_ID
    # warning, not an error, since it resolves), but interpolating c.group_id
    # directly here rendered the literal typo as "[Dhp 287, DhpA Dhp 20.11]".
    # A group_id that does NOT resolve at all (UNPARSEABLE_GROUP_ID, already
    # an audit error) must not be printed either: showing a citation the
    # audit already rejected is worse than showing none, since the reader has
    # no way to tell it's broken -- that belongs in the warning panel.
    #
    # Round 7, Task T: AlignmentClaim carries verse_numbers (plural, the
    # group's full range) instead of a single verse_number -- getattr()
    # rather than c.verse_number directly, since accessing that attribute on
    # an AlignmentClaim would raise AttributeError (it doesn't have the
    # field at all, same discriminated-union design as SynthesisClaim's
    # missing group_id/verse_number).
    parts = []
    verse_numbers = getattr(c, "verse_numbers", None)
    if verse_numbers:
        parts.append(f"Dhp {', '.join(str(n) for n in verse_numbers)}")
    elif getattr(c, "verse_number", None) is not None:
        parts.append(f"Dhp {c.verse_number}")
    gid = normalize_group_id(getattr(c, "group_id", None))
    if gid is not None:
        parts.append(f"DhpA {gid}")
    return f" [{', '.join(parts)}]" if parts else ""


def _pali_line(c: Claim) -> str:
    """Indented line beneath a verse claim quoting the Pali it rests on.

    Round 4, Task J: the verse layer never showed its own language even
    though the corpus carries Pali for every verse and the
    prompt shows it -- schemas.py's `pali_support` field (audited against
    the source in `audit()`) is the model's copy of the pada it relied on;
    this is where it finally reaches the reader. "  \\n" is CommonMark's hard
    line break, so this stays on its own line without unsafe_allow_html and
    without starting a new paragraph the way a blank line would -- the quote
    stays visually attached to the claim it supports.
    """
    if isinstance(c, VerseClaim) and c.pali_support:
        return f"  \n    Pali: {c.pali_support}"
    return ""


def _sentence(c: Claim, *, bold_opener: bool, show_opener: bool) -> str:
    text = c.text.strip()
    if not text:
        return ""
    citation = "" if c.layer == "synthesis" else _citation(c)
    pali = _pali_line(c)
    opener = _OPENERS.get(c.layer) if show_opener else None
    if opener is None:
        return f"{text}{citation}{pali}"
    label = f"**{opener}**" if bold_opener else opener
    return f"{label}: {text}{citation}{pali}"


def _paragraphs(answer: LayeredAnswer, *, bold_opener: bool) -> list[str]:
    """Group claims into one paragraph per run of same-layer claims.

    Round 3, Task B: the previous version put an opener on every claim
    ("The verse states... The verse states...") and joined every sentence
    with a single space, so consecutive same-layer claims read as one
    run-on paragraph with a repeated lead-in. A lead-in now marks the
    *transition* between layers -- only the first claim in a same-layer run
    gets one -- and each run is its own paragraph.

    Round 7: that single-space join broke down as soon as a verse claim in
    the middle of a run carried a `pali_support` quote. `_sentence()` already
    ends such a claim with a hard line break before its own "Pali: ..." line
    (`_pali_line()`), but a plain " " join put the *next* claim's text
    straight after that Pali quote on the same line, with no break -- so a
    multi-verse run rendered as "Pali: <quote N> <text N+1> ... Pali: <quote
    N+1> <text N+2>", each Pali quote visually glued to the wrong claim.
    Joining with a hard break too keeps every claim (and its own Pali line,
    if any) on its own row while still reading as one grouped paragraph, no
    blank line, between layer runs.
    """
    HARD_BREAK = "  \n"
    paragraphs: list[str] = []
    prev_layer: str | None = None
    current: list[str] = []
    for c in answer.claims:
        if not c.text.strip():
            continue
        show_opener = c.layer != prev_layer
        if show_opener and current:
            paragraphs.append(HARD_BREAK.join(current))
            current = []
        sentence = _sentence(c, bold_opener=bold_opener, show_opener=show_opener)
        if sentence:
            current.append(sentence)
        prev_layer = c.layer
    if current:
        paragraphs.append(HARD_BREAK.join(current))
    return paragraphs


def render_markdown(answer: LayeredAnswer) -> str:
    """Prose grouped into one paragraph per run of same-layer claims, claim
    order preserved, each paragraph opening with its layer marker (bold) and
    every sentence carrying its own inline citation.

    Plain Markdown only (no raw HTML) -- safe to pass straight to
    `st.markdown()` without `unsafe_allow_html`.
    """
    return "\n\n".join(_paragraphs(answer, bold_opener=True))


def render_plain(answer: LayeredAnswer) -> str:
    """Same composition as `render_markdown`, without Markdown emphasis --
    for terminal/CLI output (`generate.py`'s `main()`)."""
    return "\n\n".join(_paragraphs(answer, bold_opener=False))
