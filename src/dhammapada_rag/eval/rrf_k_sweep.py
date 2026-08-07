"""Round 8, Task AB: is RRF's k=60 (and rank-based fusion itself) the right
choice, or does it systematically penalize candidates only one retrieval arm
finds?

THE MECHANISM (stated in the brief, verified here empirically rather than
just asserted). RRF scores an item as sum(1/(k + rank)) over the ranked
lists it appears in. An item at rank 8 in one list and absent from the other
two scores 1/(60+8) = 1/68 ~= 0.0147. An item at rank 30 in all three lists
scores 3/(60+30) = 3/90 ~= 0.0333 -- more than double, despite being a much
weaker signal in any single list. At k=60 the penalty for simply being
ABSENT from a list dominates within-list rank quality. This is not "the
lexical arm dominates" (Round 5's hypothesis, corrected by Round 7's arm
diagnosis finding that dense also fails on "what does the Dhammapada say
about life?"); it is that k=60 makes single-arm discoveries -- found
confidently by exactly one arm, missed by the other two -- score WORSE than
mediocre-everywhere candidates.

WHAT THIS SCRIPT DOES. Sweeps rrf_k in {10, 20, 40, 60} over the full
114-question gold set (baseline condition: hybrid dense+sparse+colbert,
reranked, deduped to bundles -- exactly what the production system runs,
just varying k), and separately runs one score-based fusion pass (min-max
normalize each arm's raw score, then sum -- see EvalRunner._score_fuse_rank)
as a comparison. Reports nDCG@10 overall and per query type for each
condition.

WHAT THIS SCRIPT DOES NOT DO. It does not adopt a new k or a new fusion
method. Per the brief: state what was selected and on what evidence, and
name explicitly that any k chosen here was selected ON the eval set it is
then reported against -- a held-out check is required before this could
support a headline claim, and this script does not perform one.

Run: python src/dhammapada_rag/eval/rrf_k_sweep.py
Expect ~15-20 min per condition (114 questions x 1 rerank call each) x 5
conditions (4 k values + 1 score-fusion pass) -- budget over an hour.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.eval.retrieval_eval import (  # noqa: E402
    EvalRunner,
    dedupe_to_bundles,
    ndcg_at_10,
    rank_of_hit,
)

K_VALUES = (10, 20, 40, 60)


def _minmax_norm(values: dict[int, float]) -> dict[int, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-12:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def score_fuse_rank(
    runner: EvalRunner, q_dense: np.ndarray, q_sparse: dict, q_colbert: np.ndarray,
    top_n: int = 100, colbert_candidates: int = 50,
) -> list[int]:
    """Score-based fusion: min-max normalize each arm's raw score over the
    candidate set, then sum. Unlike RRF, this preserves HOW CONFIDENT an arm
    was, not just its rank -- a candidate one arm scores decisively is not
    penalized purely for being unranked by the other two, which is exactly
    the pattern this module's docstring names as RRF's k=60 failure mode.
    """
    dense_scores_all = runner.dense @ q_dense
    dense_rank = [int(i) for i in np.argsort(-dense_scores_all)[:top_n]]

    sparse_scored = [(int(i), runner.model.compute_lexical_matching_score(q_sparse, runner.sparse[i]))
                      for i in range(len(runner.sparse))]
    sparse_scored.sort(key=lambda x: -x[1])
    sparse_rank = [i for i, _ in sparse_scored[:top_n]]
    sparse_score_by_idx = dict(sparse_scored)

    colbert_candidate_idx = sorted(set(dense_rank[:colbert_candidates]) | set(sparse_rank[:colbert_candidates]))
    colbert_score_by_idx = {
        i: float(runner.model.colbert_score(q_colbert, runner.colbert[i])) for i in colbert_candidate_idx
    }

    candidates = sorted(set(dense_rank) | set(sparse_rank) | set(colbert_candidate_idx))
    dense_n = _minmax_norm({i: float(dense_scores_all[i]) for i in candidates})
    sparse_n = _minmax_norm({i: sparse_score_by_idx.get(i, 0.0) for i in candidates})
    # colbert is only scored for its candidate subset -- normalized over
    # that subset alone (an unscored candidate contributes 0, the same
    # treatment an item absent from one of RRF's ranked lists gets).
    colbert_n = _minmax_norm(colbert_score_by_idx)

    fused = {i: dense_n.get(i, 0.0) + sparse_n.get(i, 0.0) + colbert_n.get(i, 0.0) for i in candidates}
    return [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])]


def run_condition(runner: EvalRunner, gold: list[dict], label: str, *, rrf_k: int | None, use_score_fusion: bool) -> list[dict]:
    rows = []
    t0 = time.time()
    for i, q in enumerate(gold):
        query_text = q["question"]
        qenc = runner.model.encode([query_text], return_dense=True, return_sparse=True, return_colbert_vecs=True)
        q_dense = np.asarray(qenc["dense_vecs"][0], dtype=np.float32)
        q_sparse = qenc["lexical_weights"][0]
        q_colbert = np.asarray(qenc["colbert_vecs"][0], dtype=np.float32)

        if use_score_fusion:
            ranked = score_fuse_rank(runner, q_dense, q_sparse, q_colbert)
        else:
            ranked = runner._hybrid_rrf_rank(q_dense, q_sparse, q_colbert, mask=None, rrf_k=rrf_k)

        reranked = runner._rerank(query_text, ranked)
        bundles = dedupe_to_bundles(reranked, runner.chunk_story_ids, runner.chunk_bundle_keys)
        rank = rank_of_hit(bundles, q["gold_group_ids"])
        rows.append({"question_id": q["question_id"], "type": q["type"], "ndcg@10": ndcg_at_10(rank), "rank": rank})

        if (i + 1) % 30 == 0:
            elapsed = time.time() - t0
            print(f"    [{label}] {i+1}/{len(gold)} ({elapsed:.0f}s, ~{elapsed/(i+1):.1f}s/query)", file=sys.stderr)
    return rows


def summarize(rows: list[dict]) -> dict:
    overall = sum(r["ndcg@10"] for r in rows) / len(rows)
    by_type: dict[str, float] = {}
    for t in sorted({r["type"] for r in rows}):
        sub = [r for r in rows if r["type"] == t]
        by_type[t] = sum(r["ndcg@10"] for r in sub) / len(sub)
    return {"overall": round(overall, 4), "by_type": {t: round(v, 4) for t, v in by_type.items()}, "n": len(rows)}


def main() -> None:
    gold = [json.loads(l) for l in (ROOT / "data" / "eval" / "gold_set.jsonl").read_text(encoding="utf-8").splitlines()]
    retrievable = [q for q in gold if q["gold_group_ids"]]
    print(f"Sweeping rrf_k {K_VALUES} + score-fusion over {len(retrievable)} gold questions "
          f"(baseline condition: hybrid, reranked, deduped -- same as the production system).")

    runner = EvalRunner(ROOT / "data" / "index", ROOT)

    results = {}
    for k in K_VALUES:
        print(f"\n=== rrf_k={k} ===", file=sys.stderr)
        rows = run_condition(runner, retrievable, f"k={k}", rrf_k=k, use_score_fusion=False)
        results[f"rrf_k={k}"] = summarize(rows)

    print("\n=== score_fusion (min-max normalize + sum) ===", file=sys.stderr)
    rows = run_condition(runner, retrievable, "score_fusion", rrf_k=None, use_score_fusion=True)
    results["score_fusion"] = summarize(rows)

    print("\n=== Table: nDCG@10 by condition and query type ===")
    types = sorted({t for cond in results.values() for t in cond["by_type"]})
    header = f"{'condition':16s} " + " ".join(f"{t:>16s}" for t in types) + f" {'overall':>10s}"
    print(header)
    for cond, data in results.items():
        row = f"{cond:16s} " + " ".join(f"{data['by_type'].get(t, float('nan')):>16.4f}" for t in types) + f" {data['overall']:>10.4f}"
        print(row)

    best_k = max(K_VALUES, key=lambda k: results[f"rrf_k={k}"]["overall"])
    print(
        f"\nBest overall nDCG@10 among swept k values: rrf_k={best_k} "
        f"({results[f'rrf_k={best_k}']['overall']:.4f}). This value was SELECTED ON THE EVAL SET "
        f"it is reported against -- it is evidence about the shape of the k-sensitivity, not a "
        f"validated production default. A held-out check (a disjoint question sample, or k-fold "
        f"over this one) is required before promoting it, per the brief's own instruction not to "
        f"silently adopt a tuned k."
    )
    if results["score_fusion"]["overall"] > results[f"rrf_k={best_k}"]["overall"]:
        print(
            f"Score-based fusion ({results['score_fusion']['overall']:.4f}) beats every swept RRF k -- "
            f"consistent with the brief's mechanism argument (rank-based fusion discards score "
            f"magnitude, which is what makes it blind to 'found confidently by one arm')."
        )
    else:
        print(
            f"Score-based fusion ({results['score_fusion']['overall']:.4f}) does NOT beat the best "
            f"swept RRF k on this eval set -- the arithmetic argument for why RRF *should* penalize "
            f"single-arm discoveries still holds, but does not automatically mean score fusion wins "
            f"in practice on this corpus; report both numbers, not just the mechanism."
        )

    out_path = ROOT / "data" / "eval" / "rrf_k_sweep_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
