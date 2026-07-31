"""Retrieval + generation service: formalizes the Phase 2-4 pipeline (hybrid
RRF search -> cross-encoder rerank -> parent-group assembly -> layer-attributed
generation) as an HTTP API.

`/query` is retrieval only: sourced text with provenance (chunk_id, group_id,
verse numbers), nothing synthesized. `/answer` adds generation on top, with
every claim tagged verse/commentary/synthesis and cited back to a group_id.

--------------------------------------------------------------------------
FIXES over the previous revision:
1. warnings are now serialized via generate.warnings_to_dicts(); audit()
   returns dataclasses, which the old `warnings=result["warnings"]` would
   have failed to validate against list[str].
2. corpus_group_ids is passed to the generator so the audit can distinguish a
   model inventing a group_id that exists nowhere from one citing a real story
   it was not shown -- different failures with different implications.
3. layer_counts and prompt_tokens/num_ctx are returned, so a client can see
   an answer with zero commentary claims (the failure the audit cannot catch)
   and see whether the prompt was near the context limit.
4. ContextOverflowError maps to 413 rather than a generic 502, since it is a
   request-shape problem (top_k too high) the caller can act on.

Run: uvicorn dhammapada_rag.api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.api.schemas import (  # noqa: E402
    AnswerRequest,
    AnswerResponse,
    HealthResponse,
    LayerCounts,
    QueryRequest,
    QueryResponse,
    StoryOut,
    VerseOut,
)
from dhammapada_rag.generate.generate import (  # noqa: E402
    ContextOverflowError,
    GenerationError,
    Generator,
    warnings_to_dicts,
)
from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]

# Populated once at startup (see lifespan): BGE-M3 and the reranker are
# ~600M/570M-param models; reloading per request would make every query take
# ~10s+ instead of ~1-2s.
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["index"] = ChunkIndex(ROOT / "data" / "index")
    state["reranker"] = CrossEncoderReranker()
    state["verses_by_number"], state["stories_by_id"] = load_verses_and_stories(ROOT)
    state["corpus_group_ids"] = set(state["stories_by_id"])
    state["generator"] = Generator()
    yield
    state.clear()


app = FastAPI(
    title="Dhammapada RAG -- Retrieval Service",
    description=(
        "Hybrid RRF search (BGE-M3 dense+sparse+ColBERT) + bge-reranker-v2-m3 "
        "cross-encoder + parent-group assembly over the Dhammapada verse/"
        "commentary corpus. See DhammapadaRAG.txt Phases 2-3."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    index: ChunkIndex = state["index"]
    return HealthResponse(
        status="ok",
        n_chunks=len(index.chunk_ids),
        n_verses=len(state["verses_by_number"]),
        n_stories=len(state["stories_by_id"]),
    )


def _retrieve(text: str, top_k: int, candidates: int) -> list[dict]:
    return query(
        text,
        index=state["index"],
        reranker=state["reranker"],
        top_k=top_k,
        candidates=candidates,
        root=ROOT,
        verses_by_number=state["verses_by_number"],
        stories_by_id=state["stories_by_id"],
    )


@app.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest) -> QueryResponse:
    return QueryResponse(query=req.query, results=_retrieve(req.query, req.top_k, req.candidates))


@app.post("/answer", response_model=AnswerResponse)
def run_answer(req: AnswerRequest) -> AnswerResponse:
    bundles = _retrieve(req.question, req.top_k, req.candidates)
    if not bundles:
        raise HTTPException(status_code=404, detail="No retrieval results for this question.")

    generator = Generator(model=req.model) if req.model else state["generator"]
    try:
        result = generator.generate(
            req.question, bundles, corpus_group_ids=state["corpus_group_ids"]
        )
    except ContextOverflowError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except GenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    claims = result["answer"].claims
    return AnswerResponse(
        question=req.question,
        claims=[c.model_dump() for c in claims],
        warnings=warnings_to_dicts(result["warnings"]),
        layer_counts=LayerCounts(
            verse=sum(1 for c in claims if c.layer == "verse"),
            commentary=sum(1 for c in claims if c.layer == "commentary"),
            synthesis=sum(1 for c in claims if c.layer == "synthesis"),
        ),
        model=result["model"],
        latency_s=result["latency_s"],
        prompt_tokens=result.get("prompt_tokens", 0),
        num_ctx=result.get("num_ctx", 0),
        sources=bundles,
    )


@app.get("/verses/{verse_number}", response_model=VerseOut)
def get_verse(verse_number: int) -> VerseOut:
    v = state["verses_by_number"].get(verse_number)
    if v is None:
        raise HTTPException(status_code=404, detail=f"No verse {verse_number}; valid range is 1-423.")
    return VerseOut(**v)


@app.get("/stories/{group_id}", response_model=StoryOut)
def get_story(group_id: str) -> StoryOut:
    s = state["stories_by_id"].get(group_id)
    if s is None:
        raise HTTPException(
            status_code=404, detail=f"No story '{group_id}'. Expected format '<vagga>.<story>', e.g. '8.13'."
        )
    return StoryOut(**s)
