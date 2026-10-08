"""Structured output schema enforcing layer attribution, per
docs/project_plan.md Phase 4: "Require structured output where every claim
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
import unicodedata
from dataclasses import dataclass
from typing import Annotated, Iterable, Literal, Union

from pydantic import BaseModel, Field, model_validator

Layer = Literal["verse", "commentary", "synthesis", "alignment"]

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
    # Round 7, Task T: a claim was observed with no home in the original
    # three-layer taxonomy -- "the Story about the Elder Thulla Tissa
    # explains Dhp 4," tagged 'commentary'. The aṭṭhakathā never states which
    # story explains which verse; that fact belongs to the alignment table
    # (data/processed/alignment_table.json), a modern editorial artifact
    # produced by this project, not by either historical source. Forcing it
    # into 'commentary' attributed a claim to Buddhaghosa he never made and
    # silently inflated the commentary layer in every metric this project
    # reports. 'alignment' is neither 3rd-century-BCE verse nor 5th-century
    # commentary; it is a fact about the corpus's own structure.
    "alignment": (
        "A claim about the corpus's editorial structure, not its content -- "
        "which story explains which verse(s), how many verses a group "
        "covers, or whether editions differ on a grouping. Belongs to "
        "neither the verse nor the commentary; it is a fact about the "
        "alignment table, a modern editorial artifact."
    ),
    "synthesis": (
        "The model's own inference, connection to the question, or "
        "generalization -- not directly stated in either the verse or the "
        "commentary text provided."
    ),
}


class _ClaimBase(BaseModel):
    text: str = Field(..., description="One claim, in the model's own words. Keep each claim to one idea.")


# Round 4/5 amendment (Task K/L amendment) -- a flat `Claim` model with
# `group_id: str | None` / `verse_number: int | None` let an uncited verse or
# commentary claim validate successfully; MISSING_PROVENANCE existed only to
# catch it *after* the fact. That is the same class of problem Task K solved
# for citation *format* (a prompt instruction the model could ignore) by
# moving the constraint into the JSON Schema handed to Ollama's grammar-
# constrained decoder. Splitting Claim into a discriminated union does the
# same for citation *presence*: group_id/verse_number are required
# (non-Optional) on VerseClaim/CommentaryClaim, so an uncited claim of either
# layer cannot be constructed at all -- not merely flagged. SynthesisClaim
# has no group_id/verse_number fields whatsoever, so a synthesis claim
# carrying provenance (previously SYNTHESIS_WITH_CITATION) is now equally
# unrepresentable, for the same reason.
class VerseClaim(_ClaimBase):
    # `layer` is required (no Python default) so it is also required in the
    # generated JSON Schema -- discovered live: with a default, pydantic
    # drops the field from the schema's "required" list, and Ollama's
    # grammar-constrained decoder then happily emits claims with no "layer"
    # key at all (observed: 3 of 5 claims from a real qwen2.5:7b-instruct
    # run), which fails discriminated-union validation with
    # union_tag_not_found -- a claim the decoder was perfectly willing to
    # produce but pydantic cannot resolve to any variant. The _default_layer
    # validator below restores the convenience of omitting `layer=` in
    # Python-side construction (tests, etc.) without reopening that hole.
    layer: Literal["verse"] = Field(...)
    group_id: str = Field(..., description="Story group_id this claim is sourced from.")
    verse_number: int = Field(..., description="Dhp verse number (1-423) this claim is sourced from.")
    # Round 4, Task J: the corpus carries Pali for every verse and
    # the prompt shows it, but nothing in the schema could carry it back out
    # -- no Pali reached the reader regardless of what the prompt asked for.
    # Verse-only (not on CommentaryClaim/SynthesisClaim): the claim this field
    # exists to check against is "does this verse say what the claim says",
    # which only applies to a claim about the verse's own words.
    pali_support: str | None = Field(
        None,
        description=(
            "The pada from the provided Pali (interlinear_pali) that this claim rests on, "
            "copied exactly, character for character -- not translated or paraphrased."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _default_layer(cls, data):
        if isinstance(data, dict):
            data.setdefault("layer", "verse")
        return data


class CommentaryClaim(_ClaimBase):
    layer: Literal["commentary"] = Field(...)  # see VerseClaim.layer's comment: required, not defaulted
    group_id: str = Field(..., description="Story group_id this claim is sourced from.")
    verse_number: int = Field(..., description="Dhp verse number (1-423) this claim is sourced from.")

    @model_validator(mode="before")
    @classmethod
    def _default_layer(cls, data):
        if isinstance(data, dict):
            data.setdefault("layer", "commentary")
        return data


class SynthesisClaim(_ClaimBase):
    layer: Literal["synthesis"] = Field(...)  # see VerseClaim.layer's comment: required, not defaulted

    @model_validator(mode="before")
    @classmethod
    def _default_layer(cls, data):
        if isinstance(data, dict):
            data.setdefault("layer", "synthesis")
        return data


# Round 7, Task T: a fourth claim variant for facts about the corpus's own
# editorial structure -- which story explains which verse group, how many
# verses a group covers -- as distinct from VerseClaim (the verse's own
# words) and CommentaryClaim (Buddhaghosa's gloss). `verse_numbers` is
# plural and required to be the group's FULL verse range, not one verse:
# forcing a single verse_number (as VerseClaim/CommentaryClaim do) would
# have reproduced the exact omission Task U exists to fix -- "story 1.3
# explains Dhp 4" losing the fact that story 1.3 explains Dhp 3 AND 4
# together, which is the one thing an alignment claim exists to state.
class AlignmentClaim(_ClaimBase):
    layer: Literal["alignment"] = Field(...)  # see VerseClaim.layer's comment: required, not defaulted
    group_id: str = Field(..., description="Story group_id this claim is sourced from.")
    verse_numbers: list[int] = Field(
        ..., min_length=1,
        description="The FULL set of Dhp verse numbers this group covers -- not a single verse.",
    )

    @model_validator(mode="before")
    @classmethod
    def _default_layer(cls, data):
        if isinstance(data, dict):
            data.setdefault("layer", "alignment")
        return data


Claim = Annotated[
    Union[VerseClaim, CommentaryClaim, AlignmentClaim, SynthesisClaim], Field(discriminator="layer")
]

Disposition = Literal["used", "partially_relevant", "not_relevant"]

# Round 8, Task Z: context utilization (Round 7, Task V) was inferred after
# the fact -- a group counted as "accounted for" only if a claim happened to
# cite it or a synthesis claim happened to name it in prose, a heuristic that
# measured 0/27 questions as fully accounted for because the model never
# once produced a dismissal in the shape that heuristic looked for. Zero is
# not a low rate; it is an instruction (COMPLETENESS) the model does not act
# on when phrased as prose alone -- the same wall citation *format* hit
# before Task K's decoder-level enum constraint, and it takes the same fix:
# make the disposition a required, per-group structured field rather than an
# optional thing to infer from prose. `source_disposition` is required (not
# Optional, no default) so it cannot be omitted at construction time --
# `generate.py`'s `_constrained_schema()` additionally constrains it to an
# object with exactly the retrieved group_ids as keys (`additionalProperties:
# False`, each required), so the decoder cannot omit a group or invent one
# that was never retrieved.


class LayeredAnswer(BaseModel):
    question: str
    claims: list[Claim] = Field(..., min_length=1)
    source_disposition: dict[str, Disposition] = Field(
        ...,
        description=(
            "One entry for EVERY retrieved source group, keyed by group_id. "
            "'used' = at least one claim draws on it. 'partially_relevant' = "
            "it touches the question but no claim was built from it. "
            "'not_relevant' = it does not bear on the question at all. "
            "Every retrieved group must appear as a key."
        ),
    )


# --------------------------------------------------------------------------
# Provenance audit
# --------------------------------------------------------------------------

Severity = Literal["error", "warning", "info"]

Code = Literal[
    "MISSING_PROVENANCE",         # error   -- verse/commentary claim cites nothing
    "UNPARSEABLE_GROUP_ID",       # error   -- cannot be reduced to canonical form
    "UNKNOWN_GROUP_ID",           # error   -- canonical, but no such story in corpus
    "GROUP_NOT_RETRIEVED",        # error   -- real story, but not shown to the model
    "VERSE_GROUP_MISMATCH",       # error   -- fields stitched from two sources
    "VERSE_NOT_RETRIEVED",        # error   -- verse-only citation, verse not in context
    "CITATION_IN_TEXT",           # error   -- prompt's citation marker leaked into claim text
    "LABEL_IN_TEXT",              # error   -- claim text opens with its own layer/field label
    "VERSE_TEXT_AS_COMMENTARY",   # error   -- commentary claim's wording is mostly the verse itself
    "PALI_QUOTE_NOT_IN_SOURCE",   # error   -- pali_support matches no available Pali field, exact or variant
    "PALI_QUOTE_ORTHOGRAPHIC_VARIANT",  # warning -- matches a different edition's orthography of the right verse
    "PALI_QUOTE_TRUNCATED",       # warning -- quote matches but covers less than PALI_COVERAGE_THRESHOLD of the verse
    "MALFORMED_GROUP_ID",         # warning -- resolvable format drift, e.g. "g13.2"
    "SYNTHESIS_WITH_CITATION",    # info    -- synthesis claim carrying provenance
    "NO_COMMENTARY_ENGAGEMENT",   # warning -- commentary was retrieved but the answer never cites it
    "ALIGNMENT_RANGE_INCOMPLETE", # warning -- alignment claim's verse_numbers is not the group's full range
    "DUPLICATE_CLAIM",            # warning -- two claims, same layer+verse_number, near-identical text
    "MISSING_DISPOSITION",        # error   -- a retrieved group has no source_disposition entry
    "UNKNOWN_DISPOSITION_GROUP",  # warning -- source_disposition names a group that was never retrieved
    "DISPOSITION_CONTRADICTS_CLAIMS",  # warning -- 'not_relevant' group cited, or 'used' group cited by nothing
]

_SEVERITY: dict[str, Severity] = {
    "MISSING_PROVENANCE": "error",
    "UNPARSEABLE_GROUP_ID": "error",
    "UNKNOWN_GROUP_ID": "error",
    "GROUP_NOT_RETRIEVED": "error",
    "VERSE_GROUP_MISMATCH": "error",
    "VERSE_NOT_RETRIEVED": "error",
    "CITATION_IN_TEXT": "error",
    "LABEL_IN_TEXT": "error",
    "VERSE_TEXT_AS_COMMENTARY": "error",
    "PALI_QUOTE_NOT_IN_SOURCE": "error",
    "PALI_QUOTE_ORTHOGRAPHIC_VARIANT": "warning",
    "PALI_QUOTE_TRUNCATED": "warning",
    "MALFORMED_GROUP_ID": "warning",
    "SYNTHESIS_WITH_CITATION": "info",
    "NO_COMMENTARY_ENGAGEMENT": "warning",
    "ALIGNMENT_RANGE_INCOMPLETE": "warning",
    "DUPLICATE_CLAIM": "warning",
    "MISSING_DISPOSITION": "error",
    "UNKNOWN_DISPOSITION_GROUP": "warning",
    "DISPOSITION_CONTRADICTS_CLAIMS": "warning",
}

# Round 5, Task L: SYSTEM_PROMPT's OUTPUT DISCIPLINE rule, checked
# mechanically. Distinct from _CITATION_LEAK_MARKERS/CITATION_IN_TEXT below,
# which catches the prompt's own "group_id:"/"verse_number:"/"citation_fields"
# scaffolding leaking in ANYWHERE in the text; this catches the model
# labelling its own claim with its layer or field name as a sentence-opening
# prefix (observed: `"text": "commentary: For once upon a time..."`,
# `"text": "verse: Pubbenivāsaṁ yo vedī..."`) -- a leaked label means the
# prose is unusable as prose even when the `layer` field is correct, since a
# reader (or a copy-paste into another document) would see the raw label.
_LABEL_PREFIXES = ("verse:", "commentary:", "alignment:", "synthesis:", "group_id:", "verse_number:")

# --------------------------------------------------------------------------
# Round 4, Task F: mechanical detection of verse text relabelled as
# commentary
# --------------------------------------------------------------------------
#
# The failure: Dhp 222's English, verbatim canonical verse (the quote that
# stood here was SuttaCentral text, removed 2026-10-08), tagged 'commentary' in one
# run and 'verse' in another for the same sentence, depending on the
# question. Cause traced to prompt.py's COVERAGE requirement (round 1 fix
# for all-verse output): when retrieval returns verse-heavy groups with
# little usable narrative, the model can satisfy "produce at least one
# commentary claim" by relabelling a verse sentence instead of writing a
# genuine commentary claim. Layer attribution accuracy (docs/eval_rubric.md)
# catches this, but only via a human annotator reading every claim against
# the gold verse text -- it does not scale and does not run at generation
# time. This IS mechanically detectable, though: a claim tagged 'commentary'
# whose wording is mostly the retrieved verse's own words is, by
# construction, verse content mislabelled, independent of any human
# judgment. This turns a semantic error into a structural check -- the thing
# audit() was previously unable to do (see its docstring's "Structural
# only -- never semantic" caveat, which this narrows but does not remove:
# it still cannot tell a *paraphrase* of the verse from a genuine
# commentary claim that happens to quote it, only a claim that is mostly
# the verse's own wording verbatim).

# 0.60 is deliberately conservative: commentary legitimately quotes and
# glosses the verse it explains (a nidana often opens with the verse's own
# words), so a moderate overlap is expected and only a dominant one is
# evidence of mislabelling. Set on inspection of actual claims in
# data/eval/generation_raw.jsonl (see that file's flag-rate check), not
# tuned to minimize flags -- report this value in the write-up.
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
    difference rather than by shared wording. Below MIN_CONTENT_WORDS the
    claim is too short to measure reliably (a two-word claim trivially
    "contains" itself in almost anything) and is not scored at all.
    """
    c = _content_words(claim_text)
    if len(c) < MIN_CONTENT_WORDS:
        return 0.0
    s = _content_words(source_text)
    if not s:
        return 0.0
    return len(c & s) / len(c)

# --------------------------------------------------------------------------
# Round 6, Task P: three-tier Pali matching (exact / edition variant /
# fabrication)
# --------------------------------------------------------------------------
#
# Round 4's PALI_QUOTE_NOT_IN_SOURCE was a binary substring check against
# the SuttaCentral Pali field alone. Task O's probe (see docs/evaluation.md's Round 6
# section) found that two of three flagged quotes -- "sabbam-atikkameyya"
# for Dhp 221, "tam-ahaṁ"/"bhantaṁ va" for Dhp 222 -- are Ānandajoti's
# sandhi-split, differently-capitalized rendering of the SAME words the
# SuttaCentral edition printed unhyphenated ("sabbamatikkameyya", "Tamahaṁ",
# "bhantaṁva"), and that rendering reaches the model's own context: both
# verses' story narrative fields (verses.jsonl's narrative_pali /
# interlinear_pali) quote the verse in Ānandajoti's orthography in the same
# prompt that also printed the SuttaCentral line SYSTEM_PROMPT's PALI SUPPORT
# rule asks the model to copy from. That makes the binary check wrong in two
# ways at once: it can't tell "quoted a different edition of the right
# verse" (edition variance -- the exact phenomenon this project exists to
# represent) from "invented a quote" (a real fabrication), and the field it
# checked against wasn't the only Pali actually available to the model.
#
# Fix: normalize away the conventions that differ *between editions* but not
# the words, and check the quote against every Pali field actually in
# context, not one field alone.
#
# Round 13: the SuttaCentral Pali field is gone (removed at SuttaCentral's
# request, data/raw/PROVENANCE.md). The candidates are now interlinear_pali
# plus each retrieved story's pali_verse -- still two orthographies, both
# Ānandajoti's (2017 interlinear, 2024 commentary edition), so the tiers
# below still earn their keep.
def _pali_exact(s: str) -> str:
    """NFC only. Catches byte-identical copying, the thing PALI SUPPORT asks for."""
    return unicodedata.normalize("NFC", s)


def _pali_orthographic(s: str) -> str:
    """Fold the conventions that differ between editions but not the words.

    Editions of the Pali canon differ systematically in how they mark sandhi
    (Ānandajoti hyphenates "sabbam-atikkameyya" where other editions write
    "sabbamatikkameyya"), in niggahita glyph (ṃ vs ṁ -- and ṅ is folded in
    too, since some digitizations use it interchangeably at a syllable-final
    nasal), in capitalisation at pada boundaries ("Tamahaṁ" vs "tamahaṁ"),
    and in punctuation/spacing ("bhantaṁ va" vs "bhantaṁva"). None of these
    change the text; all of them defeat a substring test. Folding them
    separates "quoted a different edition" from "invented a quote" -- a
    distinction that matters more in this project than in most, since
    edition variance is part of the subject matter, not noise to discard.
    """
    s = unicodedata.normalize("NFC", s).lower()
    s = s.replace("ṃ", "ṁ").replace("ṅ", "ṁ")   # ṃ, ṅ -> ṁ
    s = s.replace("-", "").replace("’", "").replace("'", "")
    s = re.sub(r"[.,;:!?\"“”]", "", s)
    return re.sub(r"\s+", "", s)                 # spacing is not lexical here


# Round 9, Task AF: pali_support is validated by substring containment, so a
# half-quoted verse passes clean -- a truncation is a valid substring. A
# partial quote is not fabrication (the words quoted are genuine), but
# presenting half a verse as the verse is a fidelity failure invisible to
# the exact/variant/fabrication tiers above, all three of which only ask
# "did the model quote real words," never "how much of the verse did it
# quote." Coverage is measured on the orthographically folded forms (see
# _pali_orthographic) so that hyphenation/niggahita/case differences between
# the quote and the matched field don't masquerade as missing text.
#
# 0.6 is set so that quoting one of two half-verses (a common and sometimes
# legitimate move when only one half bears on the claim, e.g. citing only
# the pada a question actually asks about) is flagged for review rather
# than silently accepted, while a near-complete quote missing only a
# closing particle is not. Tuned against data/eval/generation_raw.jsonl;
# report this value in the write-up.
PALI_COVERAGE_THRESHOLD = 0.6


def _match_pali_quote(quote: str, candidates: list[tuple[str, str]]) -> tuple[str | None, str | None, str | None]:
    """Check `quote` against each (field_name, field_text) candidate.

    Returns (tier, matched_field, matched_text): tier is "exact", "variant",
    or None (fabrication -- matches nothing, at either tier); matched_text is
    the full text of the field the quote matched against (for coverage
    measurement) or None when tier is None. Exact is checked across ALL
    candidates before variant is checked against any of them, so an exact
    match in a later-listed field is never shadowed by an earlier-listed
    field's variant match.
    """
    quote_exact = _pali_exact(quote)
    for field_name, field_text in candidates:
        if field_text and quote_exact in _pali_exact(field_text):
            return "exact", field_name, field_text
    quote_ortho = _pali_orthographic(quote)
    for field_name, field_text in candidates:
        if field_text and quote_ortho in _pali_orthographic(field_text):
            return "variant", field_name, field_text
    return None, None, None


# Round 2, Task B: prompt.py's commentary block renders a
# "<<citation_fields group_id=... verse_number=...>>" marker for the model
# to copy into the JSON fields. Observed failure: the model instead copied a
# citation-shaped string into the claim's `text` field, leaving the actual
# group_id/verse_number fields null -- MISSING_PROVENANCE caught the null
# fields but didn't name that the text itself carries an untraceable,
# copy-pasted citation. Checked against the *current* prompt.py's marker
# syntax plus the pre-round-2 "group_id:"/"verse_number:" label form, so this
# still catches the failure even if a future prompt revision reintroduces
# bare labeled lines.
# Round 8, Task AA: the [ALIGNMENT] block's marker uses "verse_numbers:"
# (plural), which is NOT a substring of "verse_number:" (singular) -- the
# latter's trailing "r:" never matches the former's "rs:" -- so it needs its
# own entry rather than relying on the existing singular-form marker.
#
# Round 9, Task AG: the colon-suffixed forms above missed
# "the story explaining Dhp 194 (group_id 14.8) tells that..." -- a leaked
# field name followed by a space and a parenthesis, not a colon. The field
# name itself is what makes prose unusable (a reader sees raw JSON-schema
# vocabulary either way); the punctuation that happens to follow it is not
# load-bearing. Bare field names, matched anywhere in the text regardless of
# what follows -- "verse_number" as a substring also catches "verse_numbers:",
# making that entry redundant, and "pali_support" is added since that field
# name can leak into prose exactly like the others.
_CITATION_LEAK_MARKERS = ("group_id", "verse_number", "pali_support", "citation_fields")

# A story counts as "substantive commentary" above this length -- short
# enough to exclude near-empty synopses, long enough that a real vatthu or a
# proper synopsis always clears it. Used both by generate.py (to decide
# whether a zero-commentary answer is worth retrying) and by audit() (to
# decide whether it is worth flagging).
MIN_COMMENTARY_WORDS = 40


def bundles_have_commentary(bundles: list[dict], min_words: int = MIN_COMMENTARY_WORDS) -> bool:
    for b in bundles:
        for s in b.get("stories", []):
            text = " ".join(filter(None, (s.get("vatthu"), s.get("synopsis"))))
            if len(text.split()) >= min_words:
                return True
    return False


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

    Round 7, Task T: AlignmentClaim reuses tiers 1-3's group_id validation
    (its own branch, since it carries verse_numbers plural rather than a
    singular verse_number) and adds ALIGNMENT_RANGE_INCOMPLETE (needs
    `bundles`): a group_id that resolves but whose cited verse_numbers is
    not the group's full range -- the structural backstop for Task U's
    prompt instruction to always state the complete verse group. Task W adds
    an answer-level DUPLICATE_CLAIM check: two VerseClaim/CommentaryClaim
    claims sharing a layer and verse_number with >80% text containment,
    flagged (never auto-merged) as evidence of the same underlying claim
    produced twice, e.g. under different orthography.

    Round 8, Task Z (needs `bundles`; skipped if `answer.source_disposition`
    is empty -- see below): `answer.source_disposition` is checked for
    completeness (MISSING_DISPOSITION -- a retrieved group with no entry),
    validity (UNKNOWN_DISPOSITION_GROUP -- an entry naming a group that was
    never retrieved), and self-consistency (DISPOSITION_CONTRADICTS_CLAIMS
    -- 'not_relevant' cited by a claim, or 'used' cited by none). Structural
    only, like everything else in this function: it cannot tell whether a
    'not_relevant' disposition is actually correct, only whether it
    contradicts what the claims themselves did. An empty
    `source_disposition` skips these three checks rather than reporting
    every retrieved group missing -- treated as "this caller didn't
    populate the field" (true of most hand-built test fixtures) rather than
    "the model returned nothing" (which cannot happen via a real
    `Generator.generate()` call: the constrained-schema path requires every
    retrieved group_id as a key).

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
    4. Verse/commentary conflation, narrow and mechanical (needs `bundles`,
       Round 4 Task F): a 'commentary' claim whose wording is mostly the
       cited verse's own words (see VERSE_OVERLAP_THRESHOLD) is verse content
       relabelled, by construction -- VERSE_TEXT_AS_COMMENTARY. This is the
       one piece of layer-attribution *content* checking this function can
       do without a human annotator, and it catches only one direction and
       one degree of the general conflation problem: verse text tagged
       'commentary' (the round-4 failure), and only where the claim is
       mostly the verse's own wording verbatim. It does not attempt the
       original, opposite-direction anachronistic-conflation failure
       (commentary content tagged 'verse', docs/eval_rubric.md), and it
       misses a *paraphrased* verse presented as commentary -- confirmed
       against data/eval/generation_raw.jsonl, where the one known instance
       of verse content tagged 'commentary' (q019, claim 1: a paraphrase,
       not a verbatim quote) does not trip this check. The gold-set human
       judging this narrows, rather than replaces, still catches paraphrase;
       this only catches the near-verbatim case a machine can verify without
       reading for meaning.
    5. Quote coverage (Round 9, Task AF): a pali_support quote matching at
       tier "exact" or "variant" is real words, but says nothing about how
       much of the verse those words are. A quote covering less than
       PALI_COVERAGE_THRESHOLD of the matched field is flagged
       PALI_QUOTE_TRUNCATED (warning) -- a genuine partial quote, not a
       fabrication, but presenting half a verse as the verse is a fidelity
       failure the exact/variant/fabrication tiers alone cannot see.

    Tiers 1-3 verify a claim's citation is well-formed and traceable, not
    that its content is correctly tagged against what the source text
    actually says -- that gap is what Phase 5's full layer attribution
    accuracy and anachronistic conflation rate measure, against a
    human-rated gold set, and tier 4 above narrows without closing it.

    Returns structured warnings. To count, filter by severity or code:

        errors = [w for w in warnings if w.severity == "error"]
        drift  = [w for w in warnings if w.code == "MALFORMED_GROUP_ID"]
    """
    warnings: list[AuditWarning] = []

    valid_group_ids: set[str] = set()
    # Round 8, Task Z: every group_id actually cited by some claim (verse,
    # commentary, or alignment), normalized -- accumulated across the main
    # per-claim loop below and used by the answer-level
    # DISPOSITION_CONTRADICTS_CLAIMS check after it.
    cited_group_ids: set[str] = set()
    verses_by_group: dict[str, set[int]] = {}
    retrieved_verses: set[int] = set()
    verse_text_by_number: dict[int, str] = {}
    all_verse_text: list[str] = []
    # Round 4/6, Task J/P: kept separate from verse_text_by_number above,
    # which joins the verse's Pali + English for the (looser)
    # verse-overlap containment check. pali_support must be checked against
    # Pali fields alone -- a claim's Pali quote "matching" only because it
    # overlaps the English gloss would defeat the point of asking for a
    # primary-source quote. Round 6, Task P widens this from a single field
    # (one edition only) to every Pali field actually reaching the
    # model's context for that verse -- interlinear_pali from the verse
    # record (the only verse-record Pali since Round 13), plus pali_verse from each retrieved story that
    # explains it -- since Task O's probe found the model's own prompt
    # carries more than one edition's orthography of the same verse.
    pali_candidates_by_number: dict[int, list[tuple[str, str]]] = {}
    if bundles is not None:
        for b in bundles:
            for s in b["stories"]:
                gid = s["group_id"]
                valid_group_ids.add(gid)
                verses = set(s["dhp_verses"])
                verses_by_group.setdefault(gid, set()).update(verses)
                retrieved_verses.update(verses)
                if s.get("pali_verse"):
                    # Round 9, Task AE: a story's pali_verse quotes ONE verse
                    # of its (possibly multi-verse) group -- pali_verse_number
                    # says which. Previously this was attached to every verse
                    # in `verses`, so a claim citing e.g. Dhp 274 could be
                    # "validated" against group 20.1's pali_verse, which is
                    # actually Dhp 273's text -- real Pali from the retrieved
                    # group, but the wrong verse within it, passing silently.
                    # Fall back to the group union only when pali_verse_number
                    # is absent (unknown which verse it quotes) so a legitimate
                    # match isn't lost to a parsing gap.
                    pvn = s.get("pali_verse_number")
                    target_verses = {pvn} if pvn is not None else verses
                    for vn in target_verses:
                        pali_candidates_by_number.setdefault(vn, []).append(
                            (f"pali_verse ({gid})", s["pali_verse"])
                        )
            for v in b["verses"]:
                parts = [v.get("interlinear_pali"), v.get("interlinear_english")]
                joined = " ".join(p for p in parts if p)
                verse_text_by_number[v["verse"]] = joined
                all_verse_text.append(joined)
                vn = v["verse"]
                if v.get("interlinear_pali"):
                    pali_candidates_by_number.setdefault(vn, []).append(
                        ("interlinear_pali", v["interlinear_pali"])
                    )
    combined_verse_text = " ".join(all_verse_text)

    known_ids: set[str] | None = set(corpus_group_ids) if corpus_group_ids is not None else None

    for i, c in enumerate(answer.claims):
        # Checked before the per-layer branches below, and independent of
        # them: a claim can carry a leaked marker regardless of layer, and
        # this is checked even when group_id/verse_number are ALSO populated
        # correctly -- a model that writes its citation into prose has
        # produced an untraceable claim (a reader can't tell which part of
        # the text is the model's own statement vs. copied scaffolding)
        # even when the structured fields happen to be right too.
        text_lower = c.text.lower()
        leaked = [m for m in _CITATION_LEAK_MARKERS if m in text_lower]
        if leaked:
            warnings.append(
                _warn("CITATION_IN_TEXT", i,
                      f"claim text contains citation scaffolding ({', '.join(leaked)}) copied "
                      f"from the prompt rather than composed as prose: {c.text!r}")
            )

        # Round 5, Task L: checked independently of CITATION_IN_TEXT above --
        # a claim can open with "commentary: ..." without containing any of
        # _CITATION_LEAK_MARKERS at all, and vice versa (a marker can leak
        # mid-sentence without the text opening with a label).
        text_stripped_lower = c.text.strip().lower()
        label_prefix = next((p for p in _LABEL_PREFIXES if text_stripped_lower.startswith(p)), None)
        if label_prefix:
            warnings.append(
                _warn("LABEL_IN_TEXT", i,
                      f"claim text opens with its own label ({label_prefix!r}) instead of "
                      f"composed prose -- the layer belongs in the layer field, not the text: {c.text!r}")
            )

        # Round 4, Task F: checked here, before the synthesis/missing-
        # provenance branches below can `continue` past it. Found live
        # during tag_stability.py's sweep (Round 4, Task G): a 'commentary'
        # claim that was verbatim Dhp 39's own words AND carried no
        # group_id/verse_number at all -- placing this check after the
        # MISSING_PROVENANCE early-continue meant a claim missing its
        # citation could never be checked for content mislabelling, exactly
        # backwards, since a claim this malformed is if anything the more
        # likely candidate for a content error too. Content mislabelling and
        # citation presence are independent failures on independent fields;
        # neither should gate the other.
        if isinstance(c, CommentaryClaim) and bundles is not None:
            target_text = verse_text_by_number.get(c.verse_number)
            if not target_text:
                target_text = combined_verse_text
            overlap = _containment(c.text, target_text)
            if overlap > VERSE_OVERLAP_THRESHOLD:
                warnings.append(
                    _warn("VERSE_TEXT_AS_COMMENTARY", i,
                          f"tagged 'commentary' but {overlap:.0%} of its content words appear in "
                          f"the retrieved verse text (threshold {VERSE_OVERLAP_THRESHOLD:.0%}) -- "
                          f"this is verse content presented as Buddhaghosa's gloss: {c.text!r}")
                )

        # Round 4/6, Task J/P: pali_support must be a substring -- exact or an
        # edition-orthography variant, never neither -- of some Pali field
        # actually available for the cited verse. A binary match/fabricate
        # check (Round 4) conflated "quoted a different edition of the right
        # verse" with "invented a quote"; see the three-tier matching
        # comment above _pali_exact() for why that distinction matters here
        # specifically. An exact match is silent (the model did what PALI
        # SUPPORT asked); a variant match is a warning naming the field and
        # tier, not an error, since the words are correct even though the
        # requested edition wasn't used; no match at either tier is the
        # error PALI_QUOTE_NOT_IN_SOURCE always was.
        if isinstance(c, VerseClaim) and c.pali_support and bundles is not None:
            candidates = pali_candidates_by_number.get(c.verse_number, [])
            tier, matched_field, matched_text = _match_pali_quote(c.pali_support, candidates)
            if tier == "variant":
                warnings.append(
                    _warn("PALI_QUOTE_ORTHOGRAPHIC_VARIANT", i,
                          f"pali_support={c.pali_support!r} matches {matched_field!r} for Dhp "
                          f"{c.verse_number} only after folding edition orthography (hyphenation/"
                          f"niggahita/case/spacing) -- a different edition's rendering of the same "
                          f"words, not a fabrication: {c.text!r}")
                )
            elif tier is None:
                available = sorted({f for f, _ in candidates}) or ["none available"]
                warnings.append(
                    _warn("PALI_QUOTE_NOT_IN_SOURCE", i,
                          f"pali_support={c.pali_support!r} matches no Pali field available for Dhp "
                          f"{c.verse_number} ({', '.join(available)}), exact or edition-variant -- "
                          f"fabricated primary-source quote: {c.text!r}")
                )

            # Round 9, Task AF: a match at either tier only says the quoted
            # words are real; it says nothing about how much of the verse
            # they cover. Measured on the folded forms so hyphenation
            # differences between the quote and matched_text don't read as
            # missing text.
            if tier is not None and matched_text:
                coverage = len(_pali_orthographic(c.pali_support)) / len(_pali_orthographic(matched_text))
                if coverage < PALI_COVERAGE_THRESHOLD:
                    warnings.append(
                        _warn("PALI_QUOTE_TRUNCATED", i,
                              f"pali_support={c.pali_support!r} covers only {coverage:.0%} of "
                              f"{matched_field!r} for Dhp {c.verse_number} (threshold "
                              f"{PALI_COVERAGE_THRESHOLD:.0%}) -- a genuine but partial quote "
                              f"presented as the verse: {c.text!r}")
                    )

        if isinstance(c, SynthesisClaim):
            # Round 4/5 amendment (Task K/L amendment): SynthesisClaim has no
            # group_id/verse_number fields at all, so "tagged synthesis but
            # carries provenance" is now unrepresentable by construction, not
            # merely unobserved. SYNTHESIS_WITH_CITATION stays in the Code
            # literal (same rationale as Task K's now-unreachable citation-
            # format codes: the absence is the evidence, so the code that
            # would have caught it should stay legible even with no live
            # check left to trigger it) but there is no longer an attribute
            # to inspect here.
            continue

        # Round 7, Task T: AlignmentClaim cites a group_id like verse/
        # commentary claims, but carries verse_numbers (plural) instead of a
        # single verse_number, so it cannot fall through into the
        # VerseClaim/CommentaryClaim branch below (which reads
        # c.verse_number, an attribute AlignmentClaim doesn't have). Handled
        # as its own branch, reusing the same citation-validity codes.
        if isinstance(c, AlignmentClaim):
            gid = normalize_group_id(c.group_id)
            if gid is not None:
                cited_group_ids.add(gid)
            if gid is None:
                warnings.append(
                    _warn("UNPARSEABLE_GROUP_ID", i,
                          f"group_id={c.group_id!r} does not reduce to canonical "
                          f"'vagga.story' form: {c.text!r}")
                )
            elif gid != c.group_id:
                warnings.append(
                    _warn("MALFORMED_GROUP_ID", i,
                          f"group_id={c.group_id!r} normalized to {gid!r}; the citation resolves "
                          f"but the model deviated from the requested format")
                )

            if bundles is not None:
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
                                  f"cites group_id={gid!r}, a real story that was not among the "
                                  f"retrieved sources {sorted(valid_group_ids)} -- cited from memory, "
                                  f"not context: {c.text!r}")
                        )
                elif group_ok:
                    # Task U's own point, checked structurally: an alignment
                    # claim about a group that states less than the group's
                    # full verse range has omitted the one fact this layer
                    # exists to carry ("story 1.3 explains Dhp 4" instead of
                    # "Dhp 3 and 4").
                    full_range = verses_by_group.get(gid, set())
                    claimed = set(c.verse_numbers)
                    if full_range and claimed != full_range:
                        warnings.append(
                            _warn("ALIGNMENT_RANGE_INCOMPLETE", i,
                                  f"cites verse_numbers={sorted(claimed)} for group_id={gid!r}, but "
                                  f"that group's full verse range is {sorted(full_range)} -- an "
                                  f"alignment claim must state the FULL range, not a subset: {c.text!r}")
                        )
            continue

        # c is VerseClaim or CommentaryClaim from here on: group_id and
        # verse_number are required (non-Optional) fields, so MISSING_
        # PROVENANCE -- a verse/commentary claim citing nothing -- is now
        # unrepresentable by construction (Task K/L amendment): pydantic
        # rejects the claim at validation time, before audit() ever sees it.
        # The check below is retained as a defensive assertion (mirrors Task
        # K's treatment of its own now-unreachable codes) in case audit() is
        # ever called against a claim built via model_construct() or another
        # path that bypasses validation.
        if c.group_id is None or c.verse_number is None:  # pragma: no cover - unrepresentable via normal validation
            warnings.append(
                _warn("MISSING_PROVENANCE", i,
                      f"layer={c.layer!r} with no group_id/verse_number -- untraceable: {c.text!r}")
            )
            continue

        gid: str | None = normalize_group_id(c.group_id)
        if gid is not None:
            cited_group_ids.add(gid)
        if gid is None:
            warnings.append(
                _warn("UNPARSEABLE_GROUP_ID", i,
                      f"group_id={c.group_id!r} does not reduce to canonical "
                      f"'vagga.story' form: {c.text!r}")
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

        if group_ok:
            allowed = verses_by_group.get(gid, set())
            if c.verse_number not in allowed:
                warnings.append(
                    _warn("VERSE_GROUP_MISMATCH", i,
                          f"cites verse_number={c.verse_number} with group_id={gid!r}, but that "
                          f"story's verses are {sorted(allowed)} -- provenance fields stitched "
                          f"from two different retrieved sources: {c.text!r}")
                )
        elif gid is None:
            # Group_id didn't resolve at all: validate the verse_number
            # against the union of retrieved verses, same as the old
            # verse-only-citation path (now reached via an unparseable
            # group_id rather than an absent one, since group_id can no
            # longer be absent on a VerseClaim/CommentaryClaim).
            if c.verse_number not in retrieved_verses:
                warnings.append(
                    _warn("VERSE_NOT_RETRIEVED", i,
                          f"cites verse_number={c.verse_number} with an unresolvable group_id; that "
                          f"verse was not among the retrieved verses {sorted(retrieved_verses)}: {c.text!r}")
                )

    # Round 7, Task W: two claims in one answer sharing a layer and a
    # verse_number, with near-identical text, is evidence the model produced
    # the same underlying claim twice -- observed live: two 'verse' claims
    # both citing Dhp 135, wording near-identical but differing by one
    # consonant (pācenti / pājenti). Flagged, not merged: which spelling (if
    # either) is correct is itself the kind of orthographic question this
    # project exists to make visible, not paper over by silently keeping
    # one and discarding the other. Scoped to VerseClaim/CommentaryClaim,
    # the two layer types that carry a singular verse_number -- an
    # AlignmentClaim's verse_numbers is a group range, not a per-claim
    # identity, and duplication there is a different question this check
    # does not attempt.
    numbered = [(idx, c) for idx, c in enumerate(answer.claims) if isinstance(c, (VerseClaim, CommentaryClaim))]
    for pos_a in range(len(numbered)):
        i_a, claim_a = numbered[pos_a]
        for pos_b in range(pos_a + 1, len(numbered)):
            i_b, claim_b = numbered[pos_b]
            if claim_a.layer != claim_b.layer or claim_a.verse_number != claim_b.verse_number:
                continue
            overlap = max(_containment(claim_a.text, claim_b.text), _containment(claim_b.text, claim_a.text))
            if overlap > 0.8:
                warnings.append(
                    _warn("DUPLICATE_CLAIM", i_b,
                          f"claim {i_b} duplicates claim {i_a} ({overlap:.0%} text containment, both "
                          f"layer={claim_a.layer!r} verse_number={claim_a.verse_number}) -- the model "
                          f"produced the same underlying claim twice, possibly under different "
                          f"orthography: {claim_a.text!r} / {claim_b.text!r}")
                )

    # Answer-level check, not tied to one claim (claim_index=-1): commentary
    # was substantively available but the model produced no commentary claim
    # at all. This is the STOP GATE 3 failure mode -- num_ctx being large
    # enough to fit the commentary does not by itself make the model use it.
    # Surfaced as a warning, not an error: the answer may still be schema-
    # valid and its verse claims individually correct, but the system's
    # actual thesis (surface both layers, distinctly) went unmet.
    if bundles is not None and bundles_have_commentary(bundles):
        if not any(c.layer == "commentary" for c in answer.claims):
            warnings.append(
                _warn(
                    "NO_COMMENTARY_ENGAGEMENT", -1,
                    "retrieved sources included substantive commentary/narrative text, but "
                    "the answer contains zero claims tagged 'commentary' -- the verse/"
                    "commentary distinction this system exists to surface was not made",
                )
            )

    # Round 8, Task Z: source_disposition is validated against the retrieved
    # groups and cross-checked against what the claims actually did. This
    # replaces Round 7's heuristic context-utilization inference (a group
    # counted as "accounted for" only if a claim happened to cite it or a
    # synthesis claim happened to name it in prose) with a required,
    # structured field the decoder is constrained to fill in completely --
    # see this module's Disposition/LayeredAnswer docstring note.
    # An empty source_disposition is treated as "not populated by this
    # caller" rather than "every group missing" -- a real Generator.generate()
    # response is always non-empty here (the constrained-schema path requires
    # every retrieved group_id as a key, and bundles is never empty when
    # generate() is called at all; _constrained_schema() raises before that
    # point otherwise), so this only matters for callers -- tests, mainly --
    # constructing a LayeredAnswer directly without exercising this field.
    if bundles is not None and answer.source_disposition:
        disposition = answer.source_disposition
        missing = valid_group_ids - set(disposition)
        for gid in sorted(missing):
            warnings.append(
                _warn("MISSING_DISPOSITION", -1,
                      f"retrieved group_id={gid!r} has no source_disposition entry -- the "
                      f"model did not account for a source it was shown")
            )
        unknown = set(disposition) - valid_group_ids
        for gid in sorted(unknown):
            warnings.append(
                _warn("UNKNOWN_DISPOSITION_GROUP", -1,
                      f"source_disposition names group_id={gid!r}, which was not among the "
                      f"retrieved sources {sorted(valid_group_ids)}")
            )
        for gid, disp in sorted(disposition.items()):
            if gid not in valid_group_ids:
                continue  # already reported as UNKNOWN_DISPOSITION_GROUP above
            cited = gid in cited_group_ids
            if disp == "not_relevant" and cited:
                warnings.append(
                    _warn("DISPOSITION_CONTRADICTS_CLAIMS", -1,
                          f"group_id={gid!r} is marked 'not_relevant' but is cited by a claim -- "
                          f"the stated disposition disagrees with what the answer actually did")
                )
            elif disp == "used" and not cited:
                warnings.append(
                    _warn("DISPOSITION_CONTRADICTS_CLAIMS", -1,
                          f"group_id={gid!r} is marked 'used' but no claim cites it -- the stated "
                          f"disposition disagrees with what the answer actually did")
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
