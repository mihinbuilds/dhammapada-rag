"""Hybrid retrieval over the BGE-M3 index: dense + sparse + ColBERT
multi-vector, fused with Reciprocal Rank Fusion (RRF) instead of hand-tuned
weights, per DhammapadaRAG.txt Phase 2.

RRF is rank-based and tuning-free: for each candidate, sum 1/(k + rank) across
however many ranked lists it appears in (k=60 is the standard default from the
original RRF paper, not fit to this corpus). No score normalization or
per-signal weight to justify.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
from FlagEmbedding import BGEM3FlagModel


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

        self.model = model or BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, devices=["cpu"])

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

        rank_lists = [dense_rank, sparse_rank]

        if use_colbert:
            q_colbert = np.asarray(q["colbert_vecs"][0], dtype=np.float32)
            candidate_idx = sorted(set(dense_rank[:colbert_candidates]) | set(sparse_rank[:colbert_candidates]))
            colbert_scores = {
                int(i): float(self.model.colbert_score(q_colbert, self.colbert[i])) for i in candidate_idx
            }
            colbert_rank = sorted(colbert_scores, key=lambda i: -colbert_scores[i])
            rank_lists.append(colbert_rank)

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
