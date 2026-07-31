# Indexing (Phase 2) design notes

Implements `DhammapadaRAG.txt` Phase 2: "Diverge from the paper on
embeddings... Use BGE-M3... Pair it with bge-reranker-v2-m3 as a cross-encoder
second stage... For fusion, use Reciprocal Rank Fusion."

## Chunk schema: what gets matched on

`src/dhammapada_rag/index/chunks.py` derives **5,667 chunks** from
`verses.jsonl` and `stories.jsonl` -- see that module's docstring for the
full breakdown by type (`verse_pali_ms`, `verse_en_sujato`,
`verse_en_interlinear`, `verse_notes`, `verse_en_narrative`, `story_titles`,
`story_cast`, `story_keywords`, `story_synopsis`, `story_nidana`,
`story_vatthu`, `story_desanavasane`). Originally 2,769: a post-hoc
correctness pass found that `story_vatthu`/`story_synopsis`/
`story_desanavasane` were each emitted as one unwindowed chunk per story
regardless of length, which silently truncated at `embed.py`'s 512-token
encoder limit for any narrative over ~380 words -- 84% of all narrative
text was unreachable by any query as a result. See `docs/evaluation.md`'s
headline finding for the full diagnosis and measured impact.

This is the "tightest possible unit" side of Phase 3's "retrieve small,
return whole": a chunk is never what's returned to the user, only what's
matched on. Every chunk carries `dhp_verses` and (for story-derived chunks)
`group_id` so a hit can be resolved back to its full verse-group at assembly
time (`assemble.py`).

`story_vatthu`, `story_synopsis`, and `story_desanavasane` are now windowed
(`WINDOW_WORDS=200`, `PALI_WINDOW_WORDS=100` for pure-Pali verse text) --
multiple chunks per story where the source text exceeds one window, each
still carrying the parent `group_id` for reassembly. Window sizing is
tokenizer-measured (English-narrative-with-Pali-names runs ~2.13
tokens/word; pure Pali runs ~3.98), not a word-count guess -- see
`chunks.py`'s own comments for the derivation.

## Embedding: BGE-M3, three representations from one model

`embed.py` runs `BAAI/bge-m3` (568M params, multilingual, CPU inference on
this machine -- MPS is available but untested here for numerical
compatibility, CPU was chosen for reliability given the corpus is small
enough that CPU encoding is tractable -- ~157s for the original 2,769-chunk
index; not re-measured for the current 5,667-chunk index, since re-timing
isn't load-bearing for anything this doc claims) and saves, per chunk:

- **Dense**: 1024-dim normalized embedding (`dense.npy`)
- **Sparse/lexical**: token -> weight dict, BGE-M3's learned lexical
  importance weighting, not raw BM25 (`sparse.pkl`)
- **Multi-vector (ColBERT-style)**: one 1024-dim vector per token
  (`colbert.pkl`, ~1GB -- gitignored, rebuild locally)

This is the explicit divergence from the original paper's `bge-small-en-v1.5`
(English-only -- Pali text would embed as near-random noise in that space).
BGE-M3 covers Pali (via its multilingual XLM-RoBERTa backbone) and English in
the same space without needing separate models per language.

## Retrieval: hybrid search with RRF fusion

`search.py`'s `ChunkIndex.search()`:

1. Dense: cosine similarity (dot product; vectors pre-normalized) over all
   5,667 chunks, top `dense_k=100`.
2. Sparse: BGE-M3's own `compute_lexical_matching_score` (token-overlap dot
   product weighted by learned importance) over all chunks, top
   `sparse_k=100`.
3. Multi-vector: ColBERT MaxSim score, computed **only over the union of the
   dense/sparse top candidates** (`colbert_candidates=50` each side) rather
   than the whole corpus -- MaxSim is O(query_tokens x doc_tokens) per pair,
   too expensive to run unconditionally at this stage, but cheap once
   restricted to ~100 candidates.
4. **Reciprocal Rank Fusion** (`rrf_fuse`, `k=60`, the standard constant from
   the original RRF paper -- not fit to this corpus) combines the three rank
   lists: `score(doc) = sum over lists containing doc of 1/(k + rank + 1)`.
   Rank-based, not score-based, which is exactly why RRF needs no
   normalization or hand-tuned per-signal weight -- the stated reason for
   choosing it over the original paper's fixed 70/30 dense/sparse split.

## Reranking: bge-reranker-v2-m3 cross-encoder

`rerank.py` takes the RRF-fused shortlist (default 30 candidates) and scores
each `(query, chunk_text)` pair jointly with `BAAI/bge-reranker-v2-m3`, a
cross-encoder -- more accurate than any bi-encoder/lexical signal since query
and passage attend to each other directly, but too expensive to run over the
full corpus, hence the two-stage design.

**Device note**: unlike the embedding step, the reranker defaults to MPS
(Apple Silicon GPU) with fp16 when available, falling back to CPU fp32
otherwise (`CrossEncoderReranker.__init__`, `torch.backends.mps.is_available()`
check). This matters in practice: CPU fp32 took ~18s to rerank a 30-candidate
shortlist when measured through the running API service; MPS fp16 brought
that to ~3s. fp16 is skipped on the CPU fallback path since most CPUs don't
accelerate it (fp16-on-CPU can be *slower* than fp32). The embedding step
(`embed.py`) stays on CPU regardless -- it only runs once, offline, so its
absolute speed matters far less than the reranker's, which runs on the
request path of every live query.

**Compatibility note**: `FlagEmbedding`'s reranker code calls a
`PreTrainedTokenizerBase.prepare_for_model` method that `transformers>=5`
removed. `pyproject.toml` pins `transformers<5`; the embedding path
(`BGEM3FlagModel`) doesn't hit this and would work with either major version,
but the two libraries share one environment here.

## Parent-group assembly: "return whole"

`assemble.py` resolves a ranked chunk back to its full verse-group:

- If the chunk came from a story (has `group_id`), the group is that story's
  own `dhp_verses` -- e.g. a hit on a story explaining Dhp 3-4 returns both
  verses plus that one story.
- If the chunk is verse-only (e.g. a Pali or Sujato-translation hit with no
  `group_id`), the group is defined by looking up which story/stories
  explain that verse (`verses.jsonl`'s `story_group_ids`), then expanding to
  *those stories'* full `dhp_verses` (handles the rare case where the
  matched verse is part of a multi-verse story group).

`query()` runs the full pipeline (search -> rerank -> assemble), dedupes
results that resolve to the same verse-group (a story's synopsis and its
vatthu can both rank highly and would otherwise produce duplicate groups),
and returns up to `top_k` distinct groups.

## Verified against the spec's own example

`DhammapadaRAG.txt` Phase 3: "A hit on the story index for 'the woman whose
child died' returns Dhp 114 with its Pali, both translations, and Kisāgotamī's
story." Running that exact query returns, among the top 3 distinct
verse-groups: **Dhp 114 / story 8.13** (the mustard-seed parable) with full
Pali + Sujato translation + synopsis, matching the spec's worked example.

It also surfaces something the spec's example didn't anticipate: the corpus
has a *second*, different Kisā Gotamī story (20.11, explaining Dhp 287) that
the reranker ranks *above* 8.13 for this query -- a real instance of the kind
of narrative ambiguity (same person, different verse, different teaching
moment) that later phases' evaluation should account for, not an error to
fix.
