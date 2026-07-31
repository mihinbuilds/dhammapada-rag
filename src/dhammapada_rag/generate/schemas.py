"""Structured output schema enforcing layer attribution, per
DhammapadaRAG.txt Phase 4: "Require structured output where every claim
carries a layer tag (verse / commentary / synthesis) and a group_id.
Conflating the two layers is the failure mode; make the output format make
it visible."

Deliberately no free-text "summary" field alongside `claims` -- if the model
could write an untagged summary, that's exactly the escape hatch that would
let a conflated verse/commentary claim slip through untagged. The entire
answer has to be built out of tagged claims; a client renders them into
prose, it doesn't get handed prose to begin with.

Provenance auditing (`audit()`) returns *structured* warnings carrying a
machine-readable `code` and `severity`, not bare strings. This matters for
measurement: a model that types the group_id in the wrong format and a model
that cites a source it was never shown are different failures, and counting
`len(warnings)` conflates them. Earlier revisions of this file compared raw
citation strings against bundle IDs, so a model emitting "g13.2" against a
corpus storing "13.2" produced a 100% apparent fabrication rate -- every
warning a false positive. Canonicalization now happens before comparison, and
format drift is reported separately at WARNING severity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from pydantic import BaseModel, Field

Layer = Literal["verse", "commentary", "synthesis"]

# --------------------------------------------------------------------------
# Canonical group_id form
# --------------------------------------------------------------------------

# Canonical form is bare "<vagga>.<story>", e.g. "13.2", "1.14", "20.11".
# This is the form stored in data/processed/stories.jsonl and the form the
# prompt must render. Anything else is drift.
GROUP_ID_RE = re.compile(r"^(?P<vagga>[1-9]|1\d|2[0-6])\.(?P<story>[1-9]\d{0,2})$")

# Tolerated decorations stripped during normalization. Each of these has been
# observed from at least one model size; extend the list rather than loosening
# GROUP_ID_RE, so that drift stays visible in the warning stream.
_STRIP_PREFIXES = ("story", "group", "grp", "dhp", "g", "#")


def normalize_group_id(raw: str | None) -> str | None:
    """Reduce a model-emitted group_id to canonical '<vagga>.<story>' form.

    Returns None if `raw` cannot be reduced to something matching
    GROUP_ID_RE. Normalization is deliberately narrow: it strips known
    decorations and whitespace, and does nothing else. It will not, for
    example, coerce "13-2" or "13.02" -- those are genuine malformations and
    should surface as such.
    """
    if raw is None:
        return None

    s = raw.strip().lower()
    s = s.strip("[](){}<>\"'`,;:")

    # Strip decorations repeatedly: "story g13.2" needs two passes.
    changed = True
    while changed:
        changed = False
        s = s.strip().lstrip("_-")
        for prefix in _STRIP_PREFIXES:
            if s.startswith(prefix) and len(s) > len(prefix):
                s = s[len(prefix):]
                changed = True
                break

    s = s.strip().strip("[](){}<>\"'`,;:")
    return s if GROUP_ID_RE.match(s) else None


# --------------------------------------------------------------------------
# Claim / answer schema
# --------------------------------------------------------------------------

LAYER_DESCRIPTIONS = {
    "verse": (
        "A claim about what the Dhammapada verse itself literally says (the "
        "oldest layer -- the Buddha's words as verse, or their direct "
        "translation)."
    ),
    "commentary": (
        "A claim sourced from Buddhaghosa's aṭṭhakathā: the narrative story "
        "explaining who the verse was spoken to, when, and why. Compiled "
        "roughly eight centuries after the verses -- a later interpretive "
        "layer, not the verse's own words, even when it explains the verse "
        "correctly."
    ),
    "synthesis": (
        "The model's own inference, connection to the question, or "
        "generalization -- not directly stated in either the verse or the "
        "commentary text provided."
    ),
}


class Claim(BaseModel):
    text: str = Field(..., description="One claim, in the model's own words. Keep each claim to one idea.")
    layer: Layer = Field(..., description=" | ".join(f"{k}: {v}" for k, v in LAYER_DESCRIPTIONS.items()))
    group_id: str | None = Field(
        None,
        description=(
            "Story group_id this claim is sourced from. Copy it EXACTLY as it appears "
            "in the provided sources: two numbers separated by a period, with no "
            "prefix and no letters. Correct: '8.13'. Incorrect: 'g8.13', 'story 8.13', "
            "'[8.13]'. Required for verse/commentary claims."
        ),
    )
    verse_number: int | None = Field(
        None, description="Dhp verse number (1-423) this claim is sourced from. Required for verse/commentary claims."
    )


class LayeredAnswer(BaseModel):
    question: str
    claims: list[Claim] = Field(..., min_length=1)


# --------------------------------------------------------------------------
# Provenance audit
# --------------------------------------------------------------------------

Severity = Literal["error", "warning", "info"]

Code = Literal[
    "MISSING_PROVENANCE",      # error   -- verse/commentary claim cites nothing
    "UNPARSEABLE_GROUP_ID",    # error   -- cannot be reduced to canonical form
    "UNKNOWN_GROUP_ID",        # error   -- canonical, but no such story in corpus
    "GROUP_NOT_RETRIEVED",     # error   -- real story, but not shown to the model
    "VERSE_GROUP_MISMATCH",    # error   -- fields stitched from two sources
    "VERSE_NOT_RETRIEVED",     # error   -- verse-only citation, verse not in context
    "MALFORMED_GROUP_ID",      # warning -- resolvable format drift, e.g. "g13.2"
    "SYNTHESIS_WITH_CITATION", # info    -- synthesis claim carrying provenance
]

_SEVERITY: dict[str, Severity] = {
    "MISSING_PROVENANCE": "error",
    "UNPARSEABLE_GROUP_ID": "error",
    "UNKNOWN_GROUP_ID": "error",
    "GROUP_NOT_RETRIEVED": "error",
    "VERSE_GROUP_MISMATCH": "error",
    "VERSE_NOT_RETRIEVED": "error",
    "MALFORMED_GROUP_ID": "warning",
    "SYNTHESIS_WITH_CITATION": "info",
}


@dataclass(frozen=True)
class AuditWarning:
    """A single provenance finding.

    `severity == "error"` means the citation cannot be trusted: the model
    pointed at something it was not given. `severity == "warning"` means the
    citation resolved correctly but the model deviated from the requested
    format -- a prompt-compliance issue, not a hallucination. Aggregate these
    separately; do not sum them.
    """

    code: Code
    severity: Severity
    claim_index: int
    message: str

    def __str__(self) -> str:  # keeps existing string-oriented callers working
        return f"[{self.severity.upper()}/{self.code}] claim {self.claim_index}: {self.message}"


def _warn(code: Code, i: int, message: str) -> AuditWarning:
    return AuditWarning(code=code, severity=_SEVERITY[code], claim_index=i, message=message)


def audit(
    answer: LayeredAnswer,
    bundles: list[dict] | None = None,
    corpus_group_ids: Iterable[str] | None = None,
) -> list[AuditWarning]:
    """Mechanical provenance check. Structural only -- never semantic.

    Tiers:

    1. Presence: every verse/commentary claim must cite *some* group_id or
       verse_number. Needs neither `bundles` nor `corpus_group_ids`.
    2. Form: the cited group_id must reduce to canonical '<vagga>.<story>'.
       Drift that normalizes cleanly (e.g. "g13.2" -> "13.2") is reported at
       WARNING severity and validation continues against the normalized
       value. Drift that does not normalize is an ERROR.
    3. Validity (needs `bundles`): the normalized group_id must be one
       actually in context, and the cited verse_number must belong to that
       group. Passing `corpus_group_ids` additionally distinguishes a model
       inventing an ID that exists nowhere (UNKNOWN_GROUP_ID) from one citing
       a real story it was not shown (GROUP_NOT_RETRIEVED) -- the latter is
       the more interesting hallucination, since it implies memorization
       rather than confabulation.

    Neither tier verifies a claim's *content* is correctly tagged against
    what the source text actually says -- that is what Phase 5's layer
    attribution accuracy and anachronistic conflation rate measure, against a
    human-rated gold set. This is a structural check, reported as such.

    Returns structured warnings. To count, filter by severity or code:

        errors = [w for w in warnings if w.severity == "error"]
        drift  = [w for w in warnings if w.code == "MALFORMED_GROUP_ID"]
    """
    warnings: list[AuditWarning] = []

    valid_group_ids: set[str] = set()
    verses_by_group: dict[str, set[int]] = {}
    retrieved_verses: set[int] = set()
    if bundles is not None:
        for b in bundles:
            for s in b["stories"]:
                gid = s["group_id"]
                valid_group_ids.add(gid)
                verses = set(s["dhp_verses"])
                verses_by_group.setdefault(gid, set()).update(verses)
                retrieved_verses.update(verses)

    known_ids: set[str] | None = set(corpus_group_ids) if corpus_group_ids is not None else None

    for i, c in enumerate(answer.claims):
        if c.layer == "synthesis":
            if c.group_id is not None or c.verse_number is not None:
                warnings.append(
                    _warn(
                        "SYNTHESIS_WITH_CITATION", i,
                        f"tagged 'synthesis' but carries provenance "
                        f"(group_id={c.group_id!r}, verse_number={c.verse_number!r}); "
                        f"likely mis-tagged verse/commentary content: {c.text!r}",
                    )
                )
            continue

        if c.group_id is None and c.verse_number is None:
            warnings.append(
                _warn("MISSING_PROVENANCE", i,
                      f"layer={c.layer!r} with no group_id/verse_number -- untraceable: {c.text!r}")
            )
            continue

        gid: str | None = None
        if c.group_id is not None:
            gid = normalize_group_id(c.group_id)
            if gid is None:
                warnings.append(
                    _warn("UNPARSEABLE_GROUP_ID", i,
                          f"group_id={c.group_id!r} does not reduce to canonical "
                          f"'<vagga>.<story>' form: {c.text!r}")
                )
            elif gid != c.group_id:
                warnings.append(
                    _warn("MALFORMED_GROUP_ID", i,
                          f"group_id={c.group_id!r} normalized to {gid!r}; the citation resolves "
                          f"but the model deviated from the requested format")
                )

        if bundles is None:
            continue

        # NOTE: these are independent checks, not elif branches. A claim can
        # simultaneously cite an out-of-context group and a mismatched verse,
        # and the stitched-provenance failure is *most* likely exactly when
        # the group_id is also wrong.
        group_ok = gid is not None and gid in valid_group_ids

        if gid is not None and not group_ok:
            if known_ids is not None and gid not in known_ids:
                warnings.append(
                    _warn("UNKNOWN_GROUP_ID", i,
                          f"cites group_id={gid!r}, which does not exist in the corpus -- "
                          f"invented citation: {c.text!r}")
                )
            else:
                warnings.append(
                    _warn("GROUP_NOT_RETRIEVED", i,
                          f"cites group_id={gid!r}, a real story that was not among the retrieved "
                          f"sources {sorted(valid_group_ids)} -- cited from memory, not context: {c.text!r}")
                )

        if c.verse_number is not None:
            if group_ok:
                allowed = verses_by_group.get(gid, set())
                if c.verse_number not in allowed:
                    warnings.append(
                        _warn("VERSE_GROUP_MISMATCH", i,
                              f"cites verse_number={c.verse_number} with group_id={gid!r}, but that "
                              f"story's verses are {sorted(allowed)} -- provenance fields stitched "
                              f"from two different retrieved sources: {c.text!r}")
                    )
            elif gid is None and c.group_id is None:
                # Verse-only citation: validate against the union of retrieved verses.
                if c.verse_number not in retrieved_verses:
                    warnings.append(
                        _warn("VERSE_NOT_RETRIEVED", i,
                              f"cites verse_number={c.verse_number} with no group_id; that verse was "
                              f"not among the retrieved verses {sorted(retrieved_verses)}: {c.text!r}")
                    )

    return warnings


def summarize(warnings: list[AuditWarning]) -> dict[str, int]:
    """Counts by severity and code, for aggregation across an eval run.

    Use `out["error"]` -- not `len(warnings)` -- as the provenance-failure
    count. Reporting the two separately is the point of this module.
    """
    out: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for w in warnings:
        out[w.severity] += 1
        out[w.code] = out.get(w.code, 0) + 1
    return out
