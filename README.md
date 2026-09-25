# Dhammapada RAG

A retrieval-augmented generation system over the Dhammapada that keeps three
layers distinct instead of flattening them: the **verse** (Pāli + translation),
Buddhaghosa's **commentary** (aṭṭhakathā), and the **narrative story** (vatthu)
behind each verse — retrieving on the tightest matching unit but always
returning the full verse-group, with every generated claim tagged to the layer
it came from.

See `DhammapadaRAG.txt` for the full project plan (5 phases: corpus
construction, indexing, retrieval architecture, generation, evaluation).

## Quick start

The processed corpus (`data/processed/`) and the chunk list
(`data/index/chunks.jsonl`) are checked in, so you only need to build the
embeddings once, then start the API and the web app.

```
# 1. Python environment (Python 3.11+)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Build the search index (first run downloads BGE-M3, ~2.3GB; ~4 min on Apple Silicon)
python src/dhammapada_rag/index/embed.py

# 3. Optional, for generated answers: Ollama with the model pulled
ollama pull qwen2.5:7b-instruct
ollama serve                       # skip if the Ollama app is already running

# 4. Terminal 1 -- the API (http://127.0.0.1:8000, docs at /docs)
uvicorn dhammapada_rag.api.main:app --app-dir src --host 127.0.0.1 --port 8000

# 5. Terminal 2 -- the web app (http://localhost:3000; needs Node.js 20.9+)
cd web && npm install && npm run dev
```

Without Ollama, everything except generated answers still works: search,
corpus browsing, and the evaluation dashboard. The Ask page falls back to
retrieval-only results. To try it from the command line instead:

```
python src/dhammapada_rag/index/assemble.py "the woman whose child died"
python src/dhammapada_rag/generate/generate.py "why did the Buddha teach Kisa Gotami about mustard seeds?"
```

Run the tests with `python -m pytest -q`.

## Status

**Phase 1 (corpus construction)** complete: 305 narrative stories covering
all 423 verses / 26 vaggas (hard validation passes), plus a fully-covering
423/423 verse layer (Pali + two English translations + interlinear gloss).
See `docs/datasheet.md` and `docs/licensing.md`.

**Corpus text cleaning (September 2026):** a corpus-wide scan of the story
text found PDF-extraction defects that earlier checks never looked for, now
fixed in the parser itself and pinned by `tests/test_parse_stories.py`.
Verse quotations were cut in half at page breaks (~30 stories, e.g. Dhp
388's English translation). Footnote numbers were left in the prose
(`Dhamma,5`, ~500 of them), and 26 footnotes were missing or filed under
the wrong story. Chapter title pages were glued onto the end of 24 stories,
and the book's closing colophon onto the last one. Pali and English lines of
11 verse quotes were mixed up. The "opening setting" and "closing section"
boundaries were missed or placed mid-sentence in 47 stories, and the text
had hard line-wraps and double spaces. Nine source typos were corrected, and
SuttaCentral `<j>` markup was stripped from 12 of Sujato's verses. Every
count, and what was deliberately left alone, is in `docs/datasheet.md`
("Text cleaning pass"). The whole downstream pipeline, chunks, and
embeddings were rebuilt from the cleaned text.

**Phase 2 (indexing)** complete: 5,909 chunks (see `docs/indexing.md`;
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
numbers are kept, not deleted, at `docs/evaluation_pre_fix.md`. The
retrieval and generation outputs in `data/eval/` were re-run on 2026-09-23
against the re-embedded 5,909-chunk index built from the September 2026
cleaned corpus (baseline nDCG@10 0.954; generation layer accuracy 0.854,
source fidelity 0.833, zero fabricated Pali quotes). See the top of
`docs/evaluation.md`. The other files in `data/eval/` (model sweep, RRF
k-sweep, arm diagnosis, research validation, tag stability) have not been
re-run and still describe the pre-cleaning index.

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
   (`sources/external/anandajoti_interlinear/`, CC BY-SA 4.0, via
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
data/normalized/             one cleaned, validated file per source (sc_pali, sc_sujato,
                             aj_interlinear, aj_stories) plus the alignment table and joins
data/processed/
  stories.jsonl                narrative/commentary layer, 305 stories, 408 footnotes
  verses.jsonl                 canonical verse layer, 423/423 verses, all sources joined
  alignment_table.json         verse -> story group_id(s)
  interlinear_gloss.jsonl      parsed interlinear edition, 423/423 verses
  *_report.json                coverage/validation reports per pipeline stage
data/index/
  chunks.jsonl                  5,909 indexable chunks (tracked; small)
  dense.npy, sparse.pkl,        BGE-M3 embeddings (gitignored; rebuild with embed.py)
  colbert.pkl, chunk_ids.json
data/eval/                     gold set, evaluation results and metrics
src/dhammapada_rag/
  vaggas.py, models.py          shared schema
  ingest/                        Phase 1 pipeline (PDF/HTML/JSON -> data/processed/)
    corrections.py                 logged hand-corrections: verse numbers and source typos
  index/                         Phase 2-3 pipeline (chunks -> embeddings -> search -> assembly)
  generate/                      Phase 4: layer-attributed generation (schema, prompt, Ollama call)
  api/                           Phase 3-4 service: FastAPI wrapper over index/ and generate/
  eval/                          Phase 5: retrieval/generation evaluation scripts
tests/                         pytest suite (provenance audit, story-text cleaning)
web/                            Next.js UI against the FastAPI service (see "UI" below)
docs/                          datasheet, licensing table, corpus audit, indexing/generation design notes
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
`ollama pull qwen2.5:7b-instruct` (~4.7GB). The web app needs Node.js 20.9+
(required by Next.js 16).

`pyproject.toml` pins `huggingface-hub<1.0`: `transformers<5` (needed by
`FlagEmbedding`'s reranker) requires `huggingface-hub<1.0`, but a plain `pip
install -e .` can otherwise resolve a newer `huggingface-hub` that breaks the
reranker import outright. If you see `ImportError: huggingface-hub>=0.34.0,
<1.0 is required...`, run `pip install "huggingface-hub<1.0,>=0.34.0"` to fix
it in an existing venv.

## Running the pipeline

You only need this after changing a source file or the parsing code. The
outputs are checked in. Run the steps in this order, since each reads the
previous one's output:

```
# Phase 1: corpus construction
python src/dhammapada_rag/ingest/parse_stories.py        # PDF text -> stories.jsonl (cleaning + corrections)
python -m dhammapada_rag.ingest.validate                  # -> validation_report.json (423 verses, 26 vaggas)
python -m dhammapada_rag.ingest.normalize_sc_pali         # -> data/normalized/sc_pali.jsonl
python -m dhammapada_rag.ingest.normalize_sc_sujato       # -> data/normalized/sc_sujato.jsonl
python -m dhammapada_rag.ingest.normalize_aj_interlinear  # -> data/normalized/aj_interlinear.jsonl
python -m dhammapada_rag.ingest.normalize_aj_stories      # -> data/normalized/aj_stories.jsonl
python -m dhammapada_rag.ingest.build_verses              # merge -> verses.jsonl
python -m dhammapada_rag.ingest.build_alignment_table     # -> alignment_table.json
python -m dhammapada_rag.ingest.join_verses               # -> data/normalized/verses_joined.json
python -m dhammapada_rag.ingest.validation_gates          # 7 gates, all must PASS
python -m dhammapada_rag.ingest.audit_corpus              # -> docs/corpus_audit.md

# Phase 2: indexing (re-run both whenever stories.jsonl or verses.jsonl change)
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
| `/vaggas` | GET | The 26-vagga table (number, names, verse range) |
| `/eval/summary` | GET | Passthrough of `data/eval/retrieval_metrics.json` + `generation_metrics.json` + a summarized model-size sweep, for the web app's Evaluation dashboard |

CORS is open to `http://localhost:3000` by default (the Next.js dev server);
override with a comma-separated `DHAMMAPADA_CORS_ORIGINS` env var for other
origins.

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

A web front end (`web/`) against the FastAPI service above -- four routes:
**Ask** (query + optional layer-attributed generation, animated claim cards,
provenance warnings, expandable sources), **Corpus** (vagga browser +
verse/story lookup), **Evaluation** (retrieval metrics, ablations, generation
metrics, model-size sweep, pulled live from `data/eval/` via `/eval/summary`),
and **Method & notes**. Built with Next.js (App Router) + TypeScript +
Tailwind, with a paper/ink design language, layer color-coding, and dark mode.

```
# Terminal 1 -- API, with the Next dev server's origin allowed via CORS
uvicorn dhammapada_rag.api.main:app --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2 -- web app
cd web
npm install    # first time only
npm run dev
```

Opens at `http://localhost:3000`. `web/.env.local` points it at the API
(`NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`). `/answer`
(the Ask page's "Generate layer-attributed answer" option) requires Ollama
running locally, same as the API section above; with it off, or if
generation fails, the page falls back to showing retrieval-only results.

## Licence and citation

Code (`src/`, `tests/`, `web/`) is MIT; see `LICENSE`. The text data under
`data/` is derived partly from CC BY-SA sources, so it is CC BY-SA 4.0 with
upstream attribution; see `DATA_LICENSE.md` for per-source terms. Ānandajoti
Bhikkhu's written permission to use his texts and release the derived data is
in [`sources/PERMISSION.md`](sources/PERMISSION.md). To cite the project, use
`CITATION.cff`.
