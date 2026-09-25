"""Hybrid retrieval over the BGE-M3 index: dense + sparse + ColBERT
multi-vector, fused with Reciprocal Rank Fusion (RRF) instead of hand-tuned
weights, per docs/project_plan.md Phase 2.

RRF is rank-based and tuning-free: for each candidate, sum 1/(k + rank) across
however many ranked lists it appears in (k=60 is the standard default from the
original RRF paper, not fit to this corpus). No score normalization or
per-signal weight to justify.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from FlagEmbedding import BGEM3FlagModel

from dhammapada_rag.index.rerank import best_device


def rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rank_lists:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


class ChunkIndex:
    def __init__(self, index_dir: Path, model: BGEM3FlagModel | None = None):
        self.index_dir = Path(index_dir)
        self.chunk_ids: list[str] = json.loads((self.index_dir / "chunk_ids.json").read_text(encoding="utf-8"))
        self.dense: np.ndarray = np.load(self.index_dir / "dense.npy")
        with (self.index_dir / "sparse.pkl").open("rb") as f:
            self.sparse: list[dict[str, float]] = pickle.load(f)
        with (self.index_dir / "colbert.pkl").open("rb") as f:
            self.colbert: list[np.ndarray] = pickle.load(f)

        chunks = [json.loads(l) for l in (self.index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}
        assert len(self.chunk_ids) == self.dense.shape[0] == len(self.sparse) == len(self.colbert)

        # Round 6, Task S: this ran on hardcoded CPU regardless of what
        # hardware was available -- the query-time encoder, so this is the
        # one of the three BGE-M3/reranker instantiations in the codebase
        # that runs on every single search, not once at index-build time.
        # best_device() is shared with CrossEncoderReranker and embed.py so
        # all three pick the same hardware the same way.
        if model is not None:
            self.model = model
        else:
            device, use_fp16 = best_device()
            print(f"ChunkIndex: using device={device!r} fp16={use_fp16}", file=sys.stderr)
            self.model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16, devices=[device])

    def _score_arms(
        self,
        query: str,
        dense_k: int,
        sparse_k: int,
        colbert_candidates: int,
        use_colbert: bool,
    ) -> dict:
        """Shared encoding + per-arm scoring, factored out of `search()` so
        Round 5's Task M (arm_diagnosis.py) can inspect each retrieval arm's
        own ranking without duplicating the encode/score calls or -- more
        importantly -- without touching `rrf_fuse()` or `search()`'s
        behavior at all. Returns raw index arrays/dicts; `search()` and
        `search_arms()` each turn these into their own public shape."""
        q = self.model.encode(
            [query], return_dense=True, return_sparse=True, return_colbert_vecs=use_colbert
        )
        q_dense = np.asarray(q["dense_vecs"][0], dtype=np.float32)
        q_sparse = q["lexical_weights"][0]

        dense_scores = self.dense @ q_dense
        dense_rank = list(np.argsort(-dense_scores)[:dense_k])

        sparse_scores = np.array(
            [self.model.compute_lexical_matching_score(q_sparse, sw) for sw in self.sparse]
        )
        sparse_rank = list(np.argsort(-sparse_scores)[:sparse_k])

        colbert_rank: list[int] = []
        colbert_scores: dict[int, float] = {}
        if use_colbert:
            q_colbert = np.asarray(q["colbert_vecs"][0], dtype=np.float32)
            candidate_idx = sorted(set(dense_rank[:colbert_candidates]) | set(sparse_rank[:colbert_candidates]))
            colbert_scores = {
                int(i): float(self.model.colbert_score(q_colbert, self.colbert[i])) for i in candidate_idx
            }
            colbert_rank = sorted(colbert_scores, key=lambda i: -colbert_scores[i])

        return {
            "dense_scores": dense_scores, "dense_rank": dense_rank,
            "sparse_scores": sparse_scores, "sparse_rank": sparse_rank,
            "colbert_scores": colbert_scores, "colbert_rank": colbert_rank,
        }

    def search(
        self,
        query: str,
        top_k: int = 10,
        dense_k: int = 100,
        sparse_k: int = 100,
        colbert_candidates: int = 50,
        rrf_k: int = 60,
        use_colbert: bool = True,
    ) -> list[dict]:
        arms = self._score_arms(query, dense_k, sparse_k, colbert_candidates, use_colbert)
        dense_scores, dense_rank = arms["dense_scores"], arms["dense_rank"]
        sparse_scores, sparse_rank = arms["sparse_scores"], arms["sparse_rank"]

        rank_lists = [dense_rank, sparse_rank]
        if use_colbert:
            rank_lists.append(arms["colbert_rank"])

        fused = rrf_fuse(rank_lists, k=rrf_k)[:top_k]

        results = []
        for idx, rrf_score in fused:
            cid = self.chunk_ids[idx]
            chunk = self.chunks_by_id[cid]
            results.append(
                {
                    "chunk_id": cid,
                    "rrf_score": rrf_score,
                    "dense_score": float(dense_scores[idx]),
                    "sparse_score": float(sparse_scores[idx]),
                    **chunk,
                }
            )
        return results

    def search_arms(
        self,
        query: str,
        top_k: int = 10,
        dense_k: int = 100,
        sparse_k: int = 100,
        colbert_candidates: int = 50,
        rrf_k: int = 60,
    ) -> dict[str, list[dict]]:
        """Round 5, Task M: the four retrieval arms side by side --
        dense-only, sparse-only, ColBERT-only, and RRF-fused -- each as its
        own top_k list of {chunk_id, chunk_type, dhp_verses, score}. Existing
        callers should keep using `search()`; this is for diagnosing which
        arm is driving a fusion result, not for production retrieval.
        """
        arms = self._score_arms(query, dense_k, sparse_k, colbert_candidates, use_colbert=True)

        def _rows(rank: list[int], scores) -> list[dict]:
            out = []
            for idx in rank[:top_k]:
                cid = self.chunk_ids[idx]
                chunk = self.chunks_by_id[cid]
                score = scores[idx] if isinstance(scores, dict) else float(scores[idx])
                out.append({
                    "chunk_id": cid, "chunk_type": chunk["chunk_type"],
                    "dhp_verses": chunk["dhp_verses"], "score": score,
                })
            return out

        rank_lists = [arms["dense_rank"], arms["sparse_rank"], arms["colbert_rank"]]
        fused = [idx for idx, _ in rrf_fuse(rank_lists, k=rrf_k)]

        return {
            "dense": _rows(arms["dense_rank"], arms["dense_scores"]),
            "sparse": _rows(arms["sparse_rank"], arms["sparse_scores"]),
            "colbert": _rows(arms["colbert_rank"], arms["colbert_scores"]),
            "fused": _rows(fused, {idx: s for idx, s in rrf_fuse(rank_lists, k=rrf_k)}),
        }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top_k", type=int, default=8)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    index = ChunkIndex(root / "data" / "index")
    results = index.search(args.query, top_k=args.top_k)
    for r in results:
        print(f"{r['rrf_score']:.4f}  {r['chunk_id']:35s}  {r['text'][:100]}")


if __name__ == "__main__":
    main()
