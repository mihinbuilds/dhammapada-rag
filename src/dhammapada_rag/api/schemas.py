"""Pydantic request/response schemas for the retrieval service.

Field sets mirror data/processed/verses.jsonl and stories.jsonl exactly
(see models.py and index/build_verses.py) rather than inventing a parallel
shape -- the API is a thin, typed/validated wrapper over the same records the
ingest/index pipeline already produces, not a new schema to keep in sync.

--------------------------------------------------------------------------
FIX -- AnswerResponse.warnings was `list[str]`. generate/schemas.py's audit()
now returns structured AuditWarning objects carrying a machine-readable code
and severity, so this field would fail validation on every /answer call that
produced a warning. It is now a typed model, which also means an API consumer
can distinguish a genuine provenance failure (severity="error") from cosmetic
format drift (severity="warning") without parsing message strings.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VaggaOut(BaseModel):
    number: int
    name_pali: str
    name_en: str
    first_verse: int
    last_verse: int
    verse_count: int


class EvalSummaryOut(BaseModel):
    """Passthrough wrapper over the eval JSON files
    (data/eval/retrieval_metrics.json, generation_metrics.json) plus a
    summarized model-size sweep. Each metrics file has its own large, evolving
    nested shape (see docs/eval_rubric.md / docs/evaluation.md); typing every
    field here would duplicate that shape and drift from it. `dict[str, Any] |
    None` lets a client render "not available" when a results file hasn't
    been generated yet.

    `retrieval` is gold set v1 (114 questions, one gold verse-group each);
    `retrieval_v2` is gold set v2 (72 harder questions, some with several
    gold groups; retrieval_metrics_v2.json). Both have the same shape. v2
    reports alongside v1 and does not replace it (docs/evaluation.md,
    Round 10).

    `retrieval_written_at` / `retrieval_v2_written_at` /
    `generation_written_at` / `index_built_at` are
    file modification times (ISO 8601, UTC) of the metrics files and of
    data/index/dense.npy. A metrics file older than the index describes an
    index that is no longer the one being served -- the staleness
    docs/status_report.md found by hand; exposing the times lets a client
    flag it mechanically. Modification times, not provenance: a fresh
    checkout resets them.
    """

    retrieval: dict[str, Any] | None = None
    retrieval_v2: dict[str, Any] | None = None
    generation: dict[str, Any] | None = None
    sweep: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_written_at: str | None = None
    retrieval_v2_written_at: str | None = None
    generation_written_at: str | None = None
    index_built_at: str | None = None


class VerseOut(BaseModel):
    verse: int
    vagga_number: int
    vagga_name_pali: str
    vagga_name_en: str
    pali_mahasangiti: str | None
    english_sujato: str | None
    interlinear_pali: str | None
    interlinear_english: str | None
    interlinear_notes: list[str]
    narrative_pali: str | None
    narrative_english: str | None
    narrative_source_group_id: str | None
    story_group_ids: list[str]


class FootnoteOut(BaseModel):
    marker: str
    source: str
    text: str


class StoryOut(BaseModel):
    group_id: str
    vagga_number: int
    story_number: int
    dhp_verses: list[int]
    title_en: str
    title_pali: str | None
    cst4_title: str | None
    burlingame_title: str | None
    compare: str | None
    synopsis: str | None
    cast: str | None
    keywords: list[str]
    rating: int | None
    pali_verse: str | None
    english_verse: str | None
    pali_verse_number: int | None
    nidana: str | None
    vatthu: str
    desanavasane: str | None
    footnotes: list[FootnoteOut]


class MatchedChunkOut(BaseModel):
    chunk_id: str
    chunk_type: str
    text: str
    rerank_score: float


class VerseGroupResult(BaseModel):
    verse_numbers: list[int]
    verses: list[VerseOut]
    stories: list[StoryOut]
    matched_chunk: MatchedChunkOut


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)
    candidates: int = Field(30, ge=5, le=100)


class QueryResponse(BaseModel):
    query: str
    results: list[VerseGroupResult]


class HealthResponse(BaseModel):
    status: str
    n_chunks: int
    n_verses: int
    n_stories: int


class ClaimOut(BaseModel):
    text: str
    layer: str
    # Round 6 (found verifying Task S on this machine, not itself a Round 6
    # task): `str | None` with no default means the KEY must still be
    # present, just nullable. Round 4/5's Task K/L amendment made
    # SynthesisClaim a distinct model with no group_id/verse_number fields
    # at all, so `SynthesisClaim.model_dump()` (main.py's `run_answer`)
    # doesn't even produce the key -- `ClaimOut(**c.model_dump())` then
    # failed pydantic's "Field required" check for every answer containing
    # a synthesis claim, a 500 on `/answer` for a very common case (e.g. any
    # FRAMING claim). `= None` makes the key optional, matching what
    # `str | None` already implied.
    group_id: str | None = None
    verse_number: int | None = None
    # Same gap as above, same fix: VerseClaim.pali_support (Round 4, Task J)
    # was never added here, so an API client got no Pali at all even though
    # render.py and ui/app.py have shown it since Round 4 -- the same "no
    # Pali reaches the reader" failure Task J exists to fix, just for this
    # one consumer of the schema.
    pali_support: str | None = None
    # Round 7, Task T: AlignmentClaim.model_dump() carries verse_numbers
    # (plural, the group's full range), not verse_number -- without this
    # field, pydantic's default extra="ignore" would silently drop it from
    # every /answer response containing an alignment claim, the same class
    # of gap this file's own docstring already documents for group_id/
    # verse_number/pali_support above.
    verse_numbers: list[int] | None = None


class WarningOut(BaseModel):
    """One provenance-audit finding. See generate/schemas.py audit().

    severity="error"   the model cited something it was not shown
    severity="warning" the citation resolved but deviated from the requested
                       format (prompt compliance, not hallucination)
    severity="info"    advisory, e.g. a synthesis claim carrying provenance

    Clients should count errors and warnings separately; summing them is what
    produced a 100% apparent fabrication rate in an earlier revision.
    """

    code: str
    severity: str
    claim_index: int
    message: str


class LayerCounts(BaseModel):
    """Predicted-layer marginals for one answer.

    Surfaced in the response because an answer with zero provenance warnings
    and zero commentary claims is a total failure of the system's premise that
    the audit cannot detect. A client should be able to show this.
    """

    verse: int = 0
    commentary: int = 0
    alignment: int = 0
    synthesis: int = 0


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(3, ge=1, le=10)
    candidates: int = Field(30, ge=5, le=100)
    model: str | None = Field(None, description="Override the default Ollama model, e.g. 'qwen2.5:1.5b-instruct'")


class AnswerResponse(BaseModel):
    question: str
    claims: list[ClaimOut]
    warnings: list[WarningOut] = Field(
        default_factory=list, description="Provenance-audit findings; see generate/schemas.py audit()"
    )
    layer_counts: LayerCounts
    # Round 8, Task Z: one of "used"/"partially_relevant"/"not_relevant" per
    # retrieved group_id, keyed the same way as `sources`. Surfaced because
    # a "not_relevant" disposition is the model telling a client retrieval
    # surfaced something that doesn't apply -- a retrieval-precision signal
    # this project previously discarded entirely (see generate/schemas.py's
    # Disposition/LayeredAnswer docstring note).
    source_disposition: dict[str, str] = Field(default_factory=dict)
    model: str
    latency_s: float
    prompt_tokens: int = Field(0, description="Estimated prompt size; compare against num_ctx")
    num_ctx: int = Field(0, description="Context window the generator was configured with")
    sources: list[VerseGroupResult] = Field(description="The retrieved verse-groups given to the model as context")
