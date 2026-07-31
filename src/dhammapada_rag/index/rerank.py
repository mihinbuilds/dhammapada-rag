"""Cross-encoder second-stage reranking with bge-reranker-v2-m3, per
DhammapadaRAG.txt Phase 2 ("Pair it with bge-reranker-v2-m3 as a cross-encoder
second stage").

Cross-encoders score a (query, passage) pair jointly (no separate embeddings),
which is more accurate than the bi-encoder/lexical signals in search.py but
too expensive to run over the whole corpus -- it only reranks the RRF-fused
shortlist.
"""

from __future__ import annotations

from pathlib import Path

import torch
from FlagEmbedding import FlagReranker


class CrossEncoderReranker:
    def __init__(self, model: FlagReranker | None = None):
        # CPU fp32 takes ~18s for a 30-candidate shortlist on this machine;
        # MPS (Apple Silicon GPU) + fp16 brings that to ~3s. Fall back to CPU
        # fp32 wherever MPS isn't available -- fp16 on CPU is typically
        # *slower* than fp32 since most CPUs don't accelerate it.
        if model is not None:
            self.model = model
        elif torch.backends.mps.is_available():
            self.model = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True, devices=["mps"], normalize=True)
        else:
            self.model = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False, devices=["cpu"], normalize=True)

    def rerank(self, query: str, candidates: list[dict], top_k: int | None = None) -> list[dict]:
        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.compute_score(pairs)
        if isinstance(scores, float):
            scores = [scores]
        reranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
        out = []
        for chunk, score in reranked:
            out.append({**chunk, "rerank_score": float(score)})
        return out[:top_k] if top_k else out


def main() -> None:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top_k", type=int, default=8)
    parser.add_argument("--candidates", type=int, default=30)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    index = ChunkIndex(root / "data" / "index")
    candidates = index.search(args.query, top_k=args.candidates)

    reranker = CrossEncoderReranker()
    results = reranker.rerank(args.query, candidates, top_k=args.top_k)
    for r in results:
        print(f"{r['rerank_score']:.4f}  (rrf {r['rrf_score']:.4f})  {r['chunk_id']:35s}  {r['text'][:90]}")


if __name__ == "__main__":
    main()
