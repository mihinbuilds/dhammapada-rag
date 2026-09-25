"""Cross-encoder second-stage reranking with bge-reranker-v2-m3, per
docs/project_plan.md Phase 2 ("Pair it with bge-reranker-v2-m3 as a cross-encoder
second stage").

Cross-encoders score a (query, passage) pair jointly (no separate embeddings),
which is more accurate than the bi-encoder/lexical signals in search.py but
too expensive to run over the whole corpus -- it only reranks the RRF-fused
shortlist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch
from FlagEmbedding import FlagReranker


def best_device() -> tuple[str, bool]:
    """Return (device, use_fp16).

    Round 6, Task S -- PC migration. This project was developed on Apple
    Silicon, where this function's predecessor (an inline `torch.backends.
    mps.is_available()` check, here and duplicated in embed.py, which
    hardcoded devices=["cpu"] unconditionally) was the whole story: MPS or
    CPU fp32. On a PC with an NVIDIA GPU neither branch matches, and both
    modules silently ran on CPU -- torch.cuda.is_available() was never
    checked anywhere in the codebase. CUDA is checked first since a machine
    is never both.

    fp16 is a win on CUDA and MPS and typically a loss on CPU, where most
    hardware does not accelerate it -- hence the paired return rather than a
    bare device string; every caller needs both values together, not just
    the device name.
    """
    if torch.cuda.is_available():
        return "cuda", True
    if torch.backends.mps.is_available():
        return "mps", True
    return "cpu", False


class CrossEncoderReranker:
    def __init__(self, model: FlagReranker | None = None):
        # CPU fp32 takes ~18s for a 30-candidate shortlist on Apple Silicon
        # with no MPS; MPS/CUDA + fp16 brings that to ~3s. best_device()
        # logs its choice to stderr so a silent CPU fallback on a GPU
        # machine is visible in the terminal rather than inferred from a
        # slow run -- see this module's Task S docstring.
        if model is not None:
            self.model = model
        else:
            device, use_fp16 = best_device()
            print(f"CrossEncoderReranker: using device={device!r} fp16={use_fp16}", file=sys.stderr)
            self.model = FlagReranker(
                "BAAI/bge-reranker-v2-m3", use_fp16=use_fp16, devices=[device], normalize=True
            )

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
