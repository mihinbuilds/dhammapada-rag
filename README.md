# Dhammapada RAG

A retrieval-augmented generation system over the Dhammapada that keeps three
layers distinct instead of flattening them: the **verse** (Pāli + translation),
Buddhaghosa's **commentary** (aṭṭhakathā), and the **narrative story** (vatthu)
behind each verse — retrieving on the tightest matching unit but always
returning the full verse-group, with every generated claim tagged to the layer
it came from.

See `DhammapadaRAG.txt` for the full project plan (5 phases: corpus
construction, indexing, retrieval architecture, generation, evaluation).

## Status

**Phase 1 (corpus construction)** complete: 305 narrative stories covering
all 423 verses / 26 vaggas (hard validation passes), plus a fully-covering
423/423 verse layer (Pali + two English translations + interlinear gloss).
See `docs/datasheet.md` and `docs/licensing.md`.

**Phase 2 (indexing)** complete: 5,667 chunks (see `docs/indexing.md`;
originally 2,769 -- narrative text is now windowed rather than emitted as one
oversized chunk per story, see `docs/evaluation.md`'s headline finding)
embedded with BGE-M3 (dense + sparse + ColBERT multi-vector), fused with
Reciprocal Rank Fusion, reranked with `bge-reranker-v2-m3`. Verified against
the spec's own worked example: querying "the woman whose child died" surfaces
Kisā Gotamī's stories (Dhp 114 and Dhp 287) with full parent-group assembly.

**Phase 3 (retrieval architecture)** formalized as an HTTP service (see
"Running the API" below) -- `POST /query` runs the full search -> rerank ->
assemble pipeline (~3-5s/query on this machine's Apple Silicon GPU via MPS);
`GET /verses/{n}` and `GET /stories/{group_id}` expose direct lookups.

**Phase 4 (generation with enforced layer attribution)** complete: `POST
/answer` adds Qwen2.5-7B-Instruct (via Ollama, JSON-schema-constrained
decoding) on top of retrieval -- every claim tagged `verse`/`commentary`/
`synthesis` and cited back to a `group_id`. See `docs/generation.md` for the
enforcement design and, importantly, the actual failure cases found while
testing it (citation fields present but pointing at the wrong retrieved
source, and a genuine ambiguity in the verse/synthesis boundary) --
documented rather than hidden, per the spec's emphasis on candid failure
reporting.

**Phase 5 (evaluation)** complete: 120-question gold set (`docs/eval_rubric.md`,
`data/eval/gold_set.jsonl`), retrieval metrics broken out per query type plus
all four required ablations, generation metrics (layer attribution accuracy
against a gold layer tag per claim, conflation rate), and a 1.5B/7B/14B
model-size sweep. A later correctness pass (`docs/evaluation.md`) found and
fixed two silent-truncation bugs -- Ollama's default `num_ctx=2048` dropping
the commentary out of the generation prompt, and a 512-token encoder limit
leaving 84% of narrative text unindexed -- neither of which raised an error
anywhere; the system reported 100% schema-valid output throughout, while
quietly answering from a fraction of its own source material. Post-fix
headline findings: cross-recension retrieval, previously this system's
worst-scoring type (nDCG@10 0.54), reached a perfect 1.000 once title
variants were actually indexed; conflation rate dropped from 31.2% to 2.0%;
verse-only retrieval still collapses for narrative and cross-recension
queries (they cannot be answered without commentary/title chunks, which is
architecturally expected) but, contrary to this project's own working
prediction, does *not* drop for doctrinal queries -- a negative result,
reported as one, not smoothed over; and **structural citation validity**
(does a claim cite a group_id/verse_number actually among the retrieved
sources -- a claim about citation *form*, not about whether the claim's
content is true) improves monotonically with model size at a proportional
latency cost, while retrying a failed generation does not reliably help and
can make a small model's clean rate worse. **No inter-annotator agreement
statistic is computed or claimed anywhere** -- see `docs/eval_rubric.md`'s
"Annotator status" for why and what would be needed to add one. Pre-fix
numbers are kept, not deleted, at `docs/evaluation_pre_fix.md`.

## Sources

Four independently-published sources, documented with fetch commands and
license evidence in `data/raw/PROVENANCE.md` and
`sources/external/PROVENANCE.md`:

1. **`sources/Dhammapada-Attakatha.pdf`** — Ānandajoti Bhikkhu's 2024
   revision of Burlingame's *Dhammapada Aṭṭhakathā* translation. The
   narrative/commentary layer: title, synopsis, cast, and the nidāna/vatthu/
   desanāvasāne story text per `data/processed/stories.jsonl`. Also the only
   source for the vagga.story numbering and story-to-verse grouping.
2. **Mahāsaṅgīti Pali** (`sources/external/mahasangiti_pali/`, CC0, via
   SuttaCentral) — canonical Pali text for all 423 verses.
3. **Bhikkhu Sujato's English translation** (`sources/external/sujato_en/`,
   CC0, via SuttaCentral) — a second, independent English translation for
   all 423 verses.
4. **Ānandajoti Bhikkhu's 2017 interlinear edition**
   (`sources/external/anandajoti_interlinear/`, CC BY-SA 3.0, via
   ancient-buddhist-texts.net) — phrase-level Pali/English gloss with
   scholarly notes for all 423 verses; the closest available substitute for
   the pada-gloss layer, which source (1) explicitly omits.

Sources (2)-(4) were added after the first Phase 1 pass, which used only
source (1) and found real gaps: only ~74% of stories reprint the full Pali
verse inline, no pada-gloss layer exists in source (1) at all, and its own
license wasn't stated in-document. See `docs/datasheet.md` and
`docs/licensing.md` for how each was resolved.

## Layout

```
sources/                     source PDF, unmodified
sources/external/            fetched CC0/CC-BY-SA sources (Pali, 2nd translation, gloss)
data/raw/                    text extracted from sources/, unmodified beyond format conversion
data/interim/                intermediate parsing artifacts (gitignored)
data/processed/
  stories.jsonl                narrative/commentary layer, 305 stories
  verses.jsonl                 canonical verse layer, 423/423 verses, all sources joined
  alignment_table.json         verse -> story group_id(s)
  interlinear_gloss.jsonl      parsed interlinear edition, 423/423 verses
  *_report.json                coverage/validation reports per pipeline stage
data/index/
  chunks.jsonl                  5,667 indexable chunks (tracked; small)
  dense.npy, sparse.pkl,        BGE-M3 embeddings (gitignored; rebuild with embed.py)
  colbert.pkl, chunk_ids.json
src/dhammapada_rag/
  vaggas.py, models.py          shared schema
  ingest/                        Phase 1 pipeline (PDF/HTML/JSON -> data/processed/)
  index/                         Phase 2-3 pipeline (chunks -> embeddings -> search -> assembly)
  generate/                      Phase 4: layer-attributed generation (schema, prompt, Ollama call)
  api/                           Phase 3-4 service: FastAPI wrapper over index/ and generate/
docs/                          datasheet, licensing table, indexing/generation design notes
```

## Setup

```
python3 -m venv .venv && source .venv/bin/activate   # macOS/Linux
pip install -e .
```

On Windows, the venv layout differs (`Scripts/` not `bin/`, `.ps1`/`.bat` not a
POSIX script):

```
python -m venv .venv
.venv\Scripts\Activate.ps1    # PowerShell
pip install -e .
```

Requires `poppler` (`pdftotext`) on PATH for PDF extraction. First run of the
indexing pipeline downloads BAAI/bge-m3 (~2.3GB) and BAAI/bge-reranker-v2-m3
(~1.1GB) from HuggingFace. Generation requires
[Ollama](https://ollama.com) running locally with a model pulled:
`ollama pull qwen2.5:7b-instruct` (~4.7GB).

## Running the pipeline

```
# Phase 1: corpus construction
python src/dhammapada_rag/ingest/parse_stories.py      # PDF -> stories.jsonl
python src/dhammapada_rag/ingest/validate.py            # -> validation_report.json
python src/dhammapada_rag/ingest/parse_interlinear.py   # HTML -> interlinear_gloss.jsonl
python src/dhammapada_rag/ingest/build_verses.py        # merge -> verses.jsonl

# Phase 2: indexing
python src/dhammapada_rag/index/chunks.py               # -> data/index/chunks.jsonl
python src/dhammapada_rag/index/embed.py                # BGE-M3 -> dense/sparse/colbert

# Query via CLI (Phase 3: retrieve small, return whole)
python src/dhammapada_rag/index/search.py "<query>"      # hybrid RRF search only
python src/dhammapada_rag/index/rerank.py "<query>"       # + cross-encoder rerank
python src/dhammapada_rag/index/assemble.py "<query>"     # + parent-group assembly (full pipeline)

# Generate a layer-attributed answer via CLI (Phase 4)
python src/dhammapada_rag/generate/generate.py "<question>" [--model qwen2.5:1.5b-instruct]
```

## Running the API

```
uvicorn dhammapada_rag.api.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Models load once at startup (~5-10s); after that each `/query` takes ~3-5s on
Apple Silicon (MPS) or an NVIDIA GPU (CUDA) -- falls back to slower CPU fp32
automatically where neither is available, see `docs/indexing.md`. Device
selection is logged to stderr at startup (`index/rerank.py`'s `best_device()`,
shared by the reranker, the query-time embedder in `index/search.py`, and the
corpus embedder in `index/embed.py`) so a silent CPU fallback on GPU hardware
is visible rather than inferred from a slow run -- see `docs/evaluation.md`'s
Round 6 section for why this matters even on a machine with a capable GPU.

On Windows, set `PYTHONUTF8=1` before running any of the commands on this
page -- the default terminal codepage (cp1252) cannot print Pali diacritics
and will crash on them rather than degrade gracefully.

Interactive docs at `http://127.0.0.1:8000/docs` (auto-generated from
`src/dhammapada_rag/api/schemas.py`).

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness + corpus size sanity check |
| `/query` | POST | `{"query": str, "top_k"?: 1-20, "candidates"?: 5-100}` -> ranked, deduped verse-groups, each with full Pali/translations/story text and the specific chunk that matched |
| `/answer` | POST | `{"question": str, "top_k"?: 1-10, "candidates"?: 5-100, "model"?: str}` -> retrieval + Qwen2.5-7B generation, every claim tagged `verse`/`commentary`/`alignment`/`synthesis` with a citation, plus a `warnings` list from the provenance audit (see `docs/generation.md`) and the `sources` actually used |
| `/verses/{verse_number}` | GET | Direct verse lookup (1-423) |
| `/stories/{group_id}` | GET | Direct story lookup, e.g. `/stories/8.13` |

`/answer` requires Ollama running locally (`ollama serve`) with the model
pulled; ~3-20s per call depending on answer length.

Examples:

```
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "the woman whose child died", "top_k": 3}'

curl -X POST http://127.0.0.1:8000/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "why did the Buddha teach Kisa Gotami about mustard seeds?", "top_k": 2}'
```

## Running the evaluation

```
python data/eval/build_gold_set.py                       # -> data/eval/gold_set.jsonl (120 questions)
python src/dhammapada_rag/eval/retrieval_eval.py          # -> retrieval_results.jsonl (114 retrievable questions, ~4s/query)
python src/dhammapada_rag/eval/aggregate_retrieval.py     # -> retrieval_metrics.json, prints per-type + ablation tables
python src/dhammapada_rag/eval/generation_metrics.py      # -> generation_raw.jsonl (20-question stratified sample)
# review generation_raw.jsonl, then judge each claim in data/eval/generation_judgments.py (see docs/eval_rubric.md)
python src/dhammapada_rag/eval/aggregate_generation.py    # -> generation_metrics.json
python src/dhammapada_rag/eval/model_sweep.py             # -> model_sweep_results.jsonl (1.5B/7B/14B, ~25min total)
```

Full results and discussion: `docs/evaluation.md`. Rubric and annotator-status
caveats (read this before trusting any number): `docs/eval_rubric.md`.

## UI

A Streamlit front end (`src/dhammapada_rag/ui/app.py`) for demoing the
system and presenting Phase 5 results -- three tabs: **Ask a question**
(query + optional layer-attributed generation, color-coded verse/commentary/
synthesis claim badges, provenance warnings, expandable sources with Pali/
translations/story), **Browse corpus** (direct verse or story lookup), and
**Evaluation results** (retrieval metrics, ablations, generation metrics,
model-size sweep, all pulled live from `data/eval/`).

```
./.venv/bin/streamlit run src/dhammapada_rag/ui/app.py   # macOS/Linux
.venv\Scripts\streamlit.exe run src/dhammapada_rag/ui/app.py   # Windows
```

Opens at `http://localhost:8501`. Calls the pipeline directly (no need for
the FastAPI server to be running separately); models load once on first use
and are cached for the session.
