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

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.api.schemas import (  # noqa: E402
    AnswerRequest,
    AnswerResponse,
    EvalSummaryOut,
    HealthResponse,
    LayerCounts,
    QueryRequest,
    QueryResponse,
    StoryOut,
    VaggaOut,
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
from dhammapada_rag.vaggas import VAGGAS  # noqa: E402

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

# The Next.js dev server runs on a different origin (localhost:3000) than
# this API (localhost:8000); browsers block cross-origin fetches without
# this. DHAMMAPADA_CORS_ORIGINS overrides the dev default for deployment
# (comma-separated list of allowed origins).
_cors_origins = [
    o.strip()
    for o in os.environ.get("DHAMMAPADA_CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
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
            alignment=sum(1 for c in claims if c.layer == "alignment"),
            synthesis=sum(1 for c in claims if c.layer == "synthesis"),
        ),
        source_disposition=result["answer"].source_disposition,
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


@app.get("/vaggas", response_model=list[VaggaOut])
def list_vaggas() -> list[VaggaOut]:
    return [
        VaggaOut(
            number=v.number, name_pali=v.name_pali, name_en=v.name_en,
            first_verse=v.first_verse, last_verse=v.last_verse, verse_count=v.verse_count,
        )
        for v in VAGGAS
    ]


def _read_eval_json(name: str) -> dict | None:
    path = ROOT / "data" / "eval" / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")


def _read_eval_jsonl(name: str) -> list[dict]:
    path = ROOT / "data" / "eval" / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _sweep_summary() -> list[dict]:
    """Same aggregation as ui/app.py's _sweep_section: per (model, max_retries)
    pair, n / clean_rate / average latency, over both retry-budget result files."""
    rows = _read_eval_jsonl("model_sweep_results_retries0.jsonl") + _read_eval_jsonl(
        "model_sweep_results_retries1.jsonl"
    )
    order = ["qwen2.5:1.5b-instruct", "qwen2.5:7b-instruct", "qwen2.5:14b-instruct"]
    by_key: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        by_key.setdefault((r["model"], r.get("max_retries", 0)), []).append(r)

    summary = []
    for model in order:
        for mr in (0, 1):
            group = by_key.get((model, mr))
            if not group:
                continue
            lat = [g["latency_s"] for g in group if isinstance(g.get("latency_s"), (int, float))]
            summary.append({
                "model": model,
                "max_retries": mr,
                "n": len(group),
                "clean_rate": sum(1 for g in group if g.get("clean")) / len(group),
                "avg_latency_s": (sum(lat) / len(lat)) if lat else None,
            })
    return summary


@app.get("/eval/summary", response_model=EvalSummaryOut)
def eval_summary() -> EvalSummaryOut:
    return EvalSummaryOut(
        retrieval=_read_eval_json("retrieval_metrics.json"),
        retrieval_v2=_read_eval_json("retrieval_metrics_v2.json"),
        generation=_read_eval_json("generation_metrics.json"),
        sweep=_sweep_summary(),
        retrieval_written_at=_mtime_iso(ROOT / "data" / "eval" / "retrieval_metrics.json"),
        retrieval_v2_written_at=_mtime_iso(ROOT / "data" / "eval" / "retrieval_metrics_v2.json"),
        generation_written_at=_mtime_iso(ROOT / "data" / "eval" / "generation_metrics.json"),
        index_built_at=_mtime_iso(ROOT / "data" / "index" / "dense.npy"),
    )
