"""Embed the chunk corpus with BGE-M3: dense + sparse (lexical) + multi-vector
(ColBERT) from one multilingual model, per DhammapadaRAG.txt Phase 2 --
diverging from bge-small-en-v1.5 (English-only; Pali would be near-random
noise in that space).

--------------------------------------------------------------------------
FIX -- TRUNCATION IS NOW DETECTED, NOT SILENT. max_length=512 silently
truncated any chunk longer than that. Combined with index/chunks.py emitting
each full vatthu as a single chunk, this meant most of every long narrative
was never embedded and could not be retrieved at any k. Nothing in the
pipeline surfaced it: the index built cleanly, search returned results, and
the missing text was invisible.

chunks.py now windows long fields, so nothing should exceed the limit. This
script verifies that precondition before spending 10-20 minutes encoding, and
refuses to build an index it knows is lossy. If it raises, lower
chunks.WINDOW_WORDS rather than raising max_length -- 512 is BGE-M3's
efficient operating range and the ColBERT vectors grow linearly with length.

Outputs to data/index/:
  dense.npy      float32 (N, 1024), L2-normalized dense embeddings
  sparse.pkl     list[dict[str, float]], token -> lexical weight, len N
  colbert.pkl    list[np.ndarray (seq_len, 1024)], per-token vectors, len N
  chunk_ids.json list[str], chunk_id in row order (index into the above)
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from FlagEmbedding import BGEM3FlagModel
from dhammapada_rag.index.rerank import best_device

MAX_LENGTH = 512

# Chunks are checked against the real tokenizer, but a cheap word-count
# pre-filter names the offenders before the tokenizer is loaded.
WORDS_WARN = 380


def check_lengths(model: BGEM3FlagModel, texts: list[str], chunk_ids: list[str]) -> None:
    """Raise if any chunk would be truncated at MAX_LENGTH.

    Uses the model's own tokenizer rather than a word-count heuristic --
    diacritic-heavy Pali transliteration fragments into far more tokens per
    word than English, which is exactly the case a heuristic would miss.
    """
    tok = model.tokenizer
    offenders = []
    for cid, t in zip(chunk_ids, texts):
        n = len(tok.encode(t, add_special_tokens=True))
        if n > MAX_LENGTH:
            offenders.append((cid, n))

    if offenders:
        offenders.sort(key=lambda x: -x[1])
        preview = "\n".join(f"    {cid}: {n} tokens" for cid, n in offenders[:10])
        raise ValueError(
            f"{len(offenders)} chunk(s) exceed max_length={MAX_LENGTH} and would be "
            f"silently truncated. Longest:\n{preview}\n"
            f"Lower index/chunks.py WINDOW_WORDS and rebuild chunks.jsonl."
        )
    print(f"Length check passed: all {len(texts)} chunks fit within {MAX_LENGTH} tokens.")


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "src"))
    from dhammapada_rag.index.rerank import best_device  # noqa: E402

    chunks_path = root / "data" / "index" / "chunks.jsonl"
    index_dir = root / "data" / "index"

    chunks = [json.loads(l) for l in chunks_path.read_text(encoding="utf-8").splitlines()]
    texts = [c["text"] for c in chunks]
    chunk_ids = [c["chunk_id"] for c in chunks]

    long_by_words = [c["chunk_id"] for c in chunks if len(c["text"].split()) > WORDS_WARN]
    if long_by_words:
        print(f"Note: {len(long_by_words)} chunks exceed {WORDS_WARN} words; verifying against the tokenizer.")

    # Round 6, Task S: this used to hardcode devices=["cpu"] unconditionally
    # -- correct on the Apple Silicon machine this project was developed on
    # only because that machine's MPS backend wasn't wired up here either,
    # not because CPU was ever the intended default. best_device() (index/
    # rerank.py) checks CUDA, then MPS, then falls back to CPU, and is
    # shared with CrossEncoderReranker so both models in the pipeline pick
    # the same hardware the same way. Logged explicitly so a GPU machine
    # silently running this on CPU is visible here rather than inferred
    # from a 10-20 minute embed run instead of the expected few minutes.
    device, use_fp16 = best_device()
    print(f"Embedding {len(texts)} chunks with BAAI/bge-m3 (device={device!r} fp16={use_fp16})...")

    t0 = time.time()
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16, devices=[device])
    print(f"Model loaded in {time.time() - t0:.1f}s")

    check_lengths(model, texts, chunk_ids)

    t0 = time.time()
    output = model.encode(
        texts,
        batch_size=16,
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    print(f"Encoded in {time.time() - t0:.1f}s")

    dense = np.asarray(output["dense_vecs"], dtype=np.float32)
    sparse = output["lexical_weights"]
    colbert = [np.asarray(v, dtype=np.float32) for v in output["colbert_vecs"]]

    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "dense.npy", dense)
    with (index_dir / "sparse.pkl").open("wb") as f:
        pickle.dump(sparse, f)
    with (index_dir / "colbert.pkl").open("wb") as f:
        pickle.dump(colbert, f)
    (index_dir / "chunk_ids.json").write_text(json.dumps(chunk_ids), encoding="utf-8")

    print(f"dense.npy: {dense.shape}")
    print(f"Wrote index files to {index_dir}")


if __name__ == "__main__":
    main()
