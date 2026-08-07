"""Retrieval metrics (Recall@k, nDCG@10, MRR) per query type, plus the four
required ablations, per DhammapadaRAG.txt Phase 5.

--------------------------------------------------------------------------
CRITICAL FIXES over the previous revision. Any ablation delta reported from
that version should be withdrawn.

1. TWO ABLATIONS WERE CONFOUNDED. The docstring claimed verse_only and
   dense_only ran "WITH rerank"; neither called the reranker, while baseline
   did. So `baseline - verse_only` measured chunk-set removal PLUS loss of
   reranking, and `baseline - dense_only` measured loss of fusion PLUS loss
   of reranking. Neither was a single-factor ablation, so neither delta could
   be attributed. The reranker now runs in every condition that claims it,
   which costs three cross-encoder calls per query instead of one (~3x
   runtime; budget ~20-25 min for 114 questions rather than ~8).

2. GROUP KEYS DID NOT MATCH THE SYSTEM. compute_group_keys() resolved a
   verse-only chunk to story_group_ids[0] and commented that this "matches
   assemble()'s behavior". assemble() does the opposite: it takes ALL of a
   verse's story_group_ids, unions their verses, and query() dedupes on the
   resulting verse tuple. For any verse explained by more than one story the
   eval was scoring a unit the system never returns. Group resolution now
   mirrors assemble() exactly, and a hit is scored when the returned bundle
   contains any gold story -- the same criterion a reader of the UI would
   apply.

3. THE verse_only ABLATION IS NEAR-TAUTOLOGICAL FOR NARRATIVE QUERIES and
   must be reported as such. Narrative gold questions are answered by story
   chunks; verse_only deletes every story chunk; the collapse to ~0 is
   mechanical, not evidence. The informative cell is the DOCTRINAL row: if
   removing commentary chunks also hurts doctrinal questions -- whose gold is
   verse-anchored and therefore still reachable -- that is a real finding
   about commentary retrieval improving verse-anchored answers. The per-type
   table is printed with that read spelled out so the number is not quoted
   out of context.

Five pipeline conditions per query:

  A. baseline    full index, hybrid dense+sparse+colbert RRF, rerank, deduped to groups
  B. verse_only  verse-only chunk subset, hybrid+RRF, rerank, deduped   [ablation: chunk set]
  C. dense_only  full index, dense cosine only (no sparse/colbert/RRF), rerank, deduped   [ablation: fusion]
  D. no_rerank   full index, hybrid+RRF, NO rerank, deduped   [ablation: reranking]
  E. flat        full index, hybrid+RRF, rerank, NOT deduped (raw chunk ranking)   [ablation: parent assembly]

Each differs from baseline in exactly one factor.

nDCG note: every gold question has exactly one gold group by construction
(docs/eval_rubric.md), so IDCG=1 and nDCG@10 reduces to 1/log2(rank+1) for a
hit inside the top 10. That is correct given the construction, not a shortcut.
"""

from __future__ import annotations

import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import rrf_fuse  # noqa: E402
from FlagEmbedding import BGEM3FlagModel  # noqa: E402

RERANK_CANDIDATES = 30


def load_index_arrays(index_dir: Path):
    chunk_ids = json.loads((index_dir / "chunk_ids.json").read_text(encoding="utf-8"))
    dense = np.load(index_dir / "dense.npy")
    with (index_dir / "sparse.pkl").open("rb") as f:
        sparse = pickle.load(f)
    with (index_dir / "colbert.pkl").open("rb") as f:
        colbert = pickle.load(f)
    chunks = [json.loads(l) for l in (index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(chunk_ids) == dense.shape[0] == len(sparse) == len(colbert) == len(chunks), (
        "index arrays and chunks.jsonl are out of sync -- rerun index/embed.py after "
        "any change to index/chunks.py"
    )
    return chunk_ids, dense, sparse, colbert, chunks


def resolve_story_ids(chunk: dict, verses_by_number: dict[int, dict]) -> list[str]:
    """Mirror index/assemble.py's assemble() exactly.

    A story-linked chunk resolves to its own group_id. A verse-only chunk
    resolves to ALL stories explaining that verse -- not just the first.
    Diverging here means the eval scores a different unit than the system
    returns, which is how the previous revision silently mismeasured every
    multiply-explained verse.
    """
    if chunk.get("group_id"):
        return [chunk["group_id"]]
    v = chunk["dhp_verses"][0]
    return list(verses_by_number[v]["story_group_ids"])


def bundle_key(story_ids: list[str], stories_by_id: dict[str, dict]) -> tuple[int, ...]:
    """The dedup key query() actually uses: the assembled verse tuple."""
    verses = {v for gid in story_ids for v in stories_by_id[gid]["dhp_verses"]}
    return tuple(sorted(verses))


def dedupe_to_bundles(
    ranked_indices: list[int],
    chunk_story_ids: list[list[str]],
    chunk_bundle_keys: list[tuple[int, ...]],
) -> list[list[str]]:
    """Collapse a chunk ranking into the bundle ranking the user would see.

    Returns, per rank position, the list of story ids in that bundle.
    """
    seen: set[tuple[int, ...]] = set()
    out: list[list[str]] = []
    for idx in ranked_indices:
        key = chunk_bundle_keys[idx]
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk_story_ids[idx])
    return out


def rank_of_hit(ranked_bundles: list[list[str]], gold_group_ids: list[str]) -> int | None:
    gold = set(gold_group_ids)
    for rank, story_ids in enumerate(ranked_bundles, start=1):
        if gold & set(story_ids):
            return rank
    return None


def recall_at_k(rank: int | None, k: int) -> float:
    return 1.0 if rank is not None and rank <= k else 0.0


def ndcg_at_10(rank: int | None) -> float:
    if rank is None or rank > 10:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def mrr(rank: int | None) -> float:
    return 1.0 / rank if rank is not None else 0.0


def score(rank: int | None) -> dict:
    return {
        "rank": rank,
        "recall@1": recall_at_k(rank, 1),
        "recall@3": recall_at_k(rank, 3),
        "recall@5": recall_at_k(rank, 5),
        "recall@10": recall_at_k(rank, 10),
        "ndcg@10": ndcg_at_10(rank),
        "mrr": mrr(rank),
    }


class EvalRunner:
    def __init__(self, index_dir: Path, root: Path):
        self.chunk_ids, self.dense, self.sparse, self.colbert, self.chunks = load_index_arrays(index_dir)

        proc = root / "data" / "processed"
        self.verses_by_number = {
            v["verse"]: v for v in (json.loads(l) for l in (proc / "verses.jsonl").read_text(encoding="utf-8").splitlines())
        }
        self.stories_by_id = {
            s["group_id"]: s for s in (json.loads(l) for l in (proc / "stories.jsonl").read_text(encoding="utf-8").splitlines())
        }

        self.chunk_story_ids = [resolve_story_ids(c, self.verses_by_number) for c in self.chunks]
        self.chunk_bundle_keys = [bundle_key(sids, self.stories_by_id) for sids in self.chunk_story_ids]
        self.verse_mask = np.array([c["chunk_type"].startswith("verse_") for c in self.chunks])

        self.model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, devices=["cpu"])
        self.reranker = CrossEncoderReranker()

    # ---------------------------------------------------------------- ranking
    def _dense_rank(self, q_dense: np.ndarray, mask: np.ndarray | None = None, top_n: int = 100) -> list[int]:
        scores = self.dense @ q_dense
        if mask is not None:
            scores = np.where(mask, scores, -np.inf)
        return [int(i) for i in np.argsort(-scores)[:top_n]]

    def _sparse_rank(self, q_sparse: dict, mask: np.ndarray | None = None, top_n: int = 100) -> list[int]:
        idxs = np.where(mask)[0] if mask is not None else np.arange(len(self.sparse))
        scored = [(int(i), self.model.compute_lexical_matching_score(q_sparse, self.sparse[i])) for i in idxs]
        scored.sort(key=lambda x: -x[1])
        return [i for i, _ in scored[:top_n]]

    def _colbert_rank(self, q_colbert: np.ndarray, candidate_idx: list[int]) -> list[int]:
        scored = [(int(i), float(self.model.colbert_score(q_colbert, self.colbert[i]))) for i in candidate_idx]
        scored.sort(key=lambda x: -x[1])
        return [i for i, _ in scored]

    def _hybrid_rrf_rank(self, q_dense, q_sparse, q_colbert, mask=None, rrf_k=60, colbert_candidates=50) -> list[int]:
        dense_rank = self._dense_rank(q_dense, mask)
        sparse_rank = self._sparse_rank(q_sparse, mask)
        candidate_idx = sorted(set(dense_rank[:colbert_candidates]) | set(sparse_rank[:colbert_candidates]))
        colbert_rank = self._colbert_rank(q_colbert, candidate_idx)
        return [idx for idx, _ in rrf_fuse([dense_rank, sparse_rank, colbert_rank], k=rrf_k)]

    def _rerank(self, question: str, ranked: list[int], n: int = RERANK_CANDIDATES) -> list[int]:
        """Cross-encode the top n, keep the untouched tail.

        Preserving the tail matters: recall@10 on a condition whose gold item
        sits at rank 40 should still be 0, not undefined, and truncating here
        would quietly change what the metric measures between conditions.
        """
        head = ranked[:n]
        if not head:
            return ranked
        pairs = [(question, self.chunks[i]["text"]) for i in head]
        scores = self.reranker.model.compute_score(pairs)
        if isinstance(scores, float):
            scores = [scores]
        ordered = [i for i, _ in sorted(zip(head, scores), key=lambda x: -x[1])]
        return ordered + ranked[n:]

    # ---------------------------------------------------------------- per query
    def run_query(self, question: str) -> dict:
        q = self.model.encode([question], return_dense=True, return_sparse=True, return_colbert_vecs=True)
        q_dense = np.asarray(q["dense_vecs"][0], dtype=np.float32)
        q_sparse = q["lexical_weights"][0]
        q_colbert = np.asarray(q["colbert_vecs"][0], dtype=np.float32)

        full_rrf = self._hybrid_rrf_rank(q_dense, q_sparse, q_colbert, mask=None)
        baseline_chunks = self._rerank(question, full_rrf)            # A, E
        verse_only_rrf = self._hybrid_rrf_rank(q_dense, q_sparse, q_colbert, mask=self.verse_mask)
        verse_only_chunks = self._rerank(question, verse_only_rrf)    # B  (reranked: single-factor)
        dense_only_rank = self._dense_rank(q_dense, mask=None, top_n=100)
        dense_only_chunks = self._rerank(question, dense_only_rank)   # C  (reranked: single-factor)

        d = lambda ranked: dedupe_to_bundles(ranked, self.chunk_story_ids, self.chunk_bundle_keys)  # noqa: E731
        return {
            "baseline": d(baseline_chunks),
            "verse_only": d(verse_only_chunks),
            "dense_only": d(dense_only_chunks),
            "no_rerank": d(full_rrf),
            "flat_chunk_order": baseline_chunks,
        }


def main() -> None:
    index_dir = ROOT / "data" / "index"
    gold = [json.loads(l) for l in (ROOT / "data" / "eval" / "gold_set.jsonl").read_text(encoding="utf-8").splitlines()]
    retrievable = [q for q in gold if q["gold_group_ids"]]
    print(
        f"Running retrieval eval over {len(retrievable)}/{len(gold)} chunk-retrievable "
        f"gold questions (3 reranker calls/query; expect ~3x the previous runtime)..."
    )

    runner = EvalRunner(index_dir, ROOT)

    per_question = []
    t0 = time.time()
    for i, q in enumerate(retrievable):
        result = runner.run_query(q["question"])
        # subtype was previously dropped here, so aggregate_retrieval.py's
        # by_subtype output was silently always empty -- a known gap noted
        # in docs/evaluation.md but not fixed until round 2 needed a
        # subtype-level before/after comparison for the verse_grouping
        # chunk-type addition (index/chunks.py's story_alignment).
        row = {"question_id": q["question_id"], "type": q["type"], "subtype": q.get("subtype"), "gold_group_ids": q["gold_group_ids"]}
        for cond in ("baseline", "verse_only", "dense_only", "no_rerank"):
            row[cond] = score(rank_of_hit(result[cond], q["gold_group_ids"]))

        gold_set = set(q["gold_group_ids"])
        flat_rank = None
        for r, idx in enumerate(result["flat_chunk_order"], start=1):
            if gold_set & set(runner.chunk_story_ids[idx]):
                flat_rank = r
                break
        row["flat"] = score(flat_rank)

        per_question.append(row)
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            print(f"  {i+1}/{len(retrievable)} ({elapsed:.0f}s elapsed, ~{elapsed/(i+1):.1f}s/query)")

    out_path = ROOT / "data" / "eval" / "retrieval_results.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in per_question:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {out_path}")
    print(
        "\nREADING THE verse_only ABLATION: for narrative-type questions the collapse is\n"
        "near-mechanical (their gold is reachable only via story chunks, which this\n"
        "condition deletes) and is not evidence for the architecture. The load-bearing\n"
        "cell is the doctrinal row, whose gold is verse-anchored and therefore still\n"
        "reachable without commentary chunks. Report that one as the finding."
    )


if __name__ == "__main__":
    main()
