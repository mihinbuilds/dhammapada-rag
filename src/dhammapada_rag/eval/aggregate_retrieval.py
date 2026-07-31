"""Aggregate data/eval/retrieval_results.jsonl into per-query-type metrics and
ablation deltas. DhammapadaRAG.txt Phase 5: "broken out per query type.
Aggregate numbers hide the interesting result."

--------------------------------------------------------------------------
FIXES over the previous revision:

1. SUBTYPE BREAKDOWN. build_gold_set now emits a `subtype` alongside `type`
   (see data/eval/build_gold_set_PATCH.py). The cross_recension stratum was
   three unrelated question kinds under one label; reporting only the type
   average made a labelling problem look like a retrieval weakness.

2. BOOTSTRAP CIs ON ABLATION DELTAS. A delta of +0.03 on n=30 is not
   distinguishable from zero, and reporting it to three decimals invites
   over-reading. Deltas are now paired-bootstrapped by question.

3. AN EXPLICIT NOTE ON verse_only. For narrative questions its collapse is
   near-mechanical: their gold is reachable only through story chunks, which
   the condition deletes. The load-bearing cell is doctrinal, whose gold is
   verse-anchored and stays reachable. The printout says so, so the headline
   number cannot be quoted without its caveat.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONDITIONS = ["baseline", "verse_only", "dense_only", "no_rerank", "flat"]
METRICS = ["recall@1", "recall@3", "recall@5", "recall@10", "ndcg@10", "mrr"]
SEED = 20260731
BOOTSTRAP_N = 2000


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def aggregate(rows: list[dict]) -> dict:
    return {cond: {m: round(mean([r[cond][m] for r in rows]), 4) for m in METRICS} for cond in CONDITIONS}


def delta_ci(rows: list[dict], cond: str, metric: str, n: int = BOOTSTRAP_N) -> tuple[float, float]:
    """Paired bootstrap over questions for (baseline - variant) on one metric.

    Paired because both conditions are evaluated on the same question, so the
    per-question difference is the unit to resample -- an unpaired interval
    would be needlessly wide.
    """
    if not rows:
        return (0.0, 0.0)
    diffs = [r["baseline"][metric] - r[cond][metric] for r in rows]
    rng = random.Random(SEED)
    means = []
    for _ in range(n):
        sample = [rng.choice(diffs) for _ in diffs]
        means.append(sum(sample) / len(sample))
    means.sort()
    return (round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4))


def main():
    rows = [json.loads(l) for l in (ROOT / "data" / "eval" / "retrieval_results.jsonl").read_text(encoding="utf-8").splitlines()]
    has_subtype = all("subtype" in r for r in rows)

    report = {"n_questions": len(rows), "overall": aggregate(rows), "by_type": {}, "by_subtype": {}}
    for qtype in sorted({r["type"] for r in rows}):
        subset = [r for r in rows if r["type"] == qtype]
        report["by_type"][qtype] = {"n": len(subset), **aggregate(subset)}
    if has_subtype:
        for st in sorted({r["subtype"] for r in rows}):
            subset = [r for r in rows if r["subtype"] == st]
            report["by_subtype"][st] = {"n": len(subset), **aggregate(subset)}

    print(f"n = {report['n_questions']}\n")
    print("=== OVERALL ===")
    for cond in CONDITIONS:
        m = report["overall"][cond]
        print(
            f"  {cond:12s}  R@1={m['recall@1']:.3f}  R@3={m['recall@3']:.3f}  "
            f"R@5={m['recall@5']:.3f}  R@10={m['recall@10']:.3f}  "
            f"nDCG@10={m['ndcg@10']:.3f}  MRR={m['mrr']:.3f}"
        )

    print("\n=== BY QUERY TYPE (baseline condition) ===")
    for qtype, d in report["by_type"].items():
        m = d["baseline"]
        print(
            f"  {qtype:16s} n={d['n']:3d}  R@1={m['recall@1']:.3f}  R@5={m['recall@5']:.3f}  "
            f"R@10={m['recall@10']:.3f}  nDCG@10={m['ndcg@10']:.3f}  MRR={m['mrr']:.3f}"
        )

    if has_subtype:
        print("\n=== BY SUBTYPE (baseline condition) ===")
        for st, d in report["by_subtype"].items():
            m = d["baseline"]
            print(f"  {st:24s} n={d['n']:3d}  nDCG@10={m['ndcg@10']:.3f}  MRR={m['mrr']:.3f}")

    print("\n=== ABLATION DELTAS, baseline - variant, nDCG@10 [95% CI] ===")
    deltas = {}
    for cond in ["verse_only", "dense_only", "no_rerank", "flat"]:
        d = round(report["overall"]["baseline"]["ndcg@10"] - report["overall"][cond]["ndcg@10"], 4)
        lo, hi = delta_ci(rows, cond, "ndcg@10")
        sig = "" if lo <= 0 <= hi else "  *"
        deltas[cond] = {"delta": d, "ci": [lo, hi]}
        print(f"  baseline - {cond:12s}  {d:+.3f}  [{lo:+.3f}, {hi:+.3f}]{sig}")
    print("  (* = interval excludes zero; unmarked deltas are not distinguishable from no effect)")

    print("\n=== verse_only ablation, per type (the architectural claim) ===")
    for qtype, d in report["by_type"].items():
        b, v = d["baseline"]["ndcg@10"], d["verse_only"]["ndcg@10"]
        print(f"  {qtype:16s} n={d['n']:3d}  baseline={b:.3f} -> verse_only={v:.3f}  (delta {b - v:+.3f})")
    print(
        "  READ WITH CARE: for narrative questions this collapse is near-mechanical --\n"
        "  their gold is reachable only via story chunks, which the condition removes.\n"
        "  The informative cell is DOCTRINAL: its gold is verse-anchored and remains\n"
        "  reachable without commentary chunks, so any drop there is real evidence that\n"
        "  commentary retrieval improves verse-anchored answers. Report that one."
    )

    report["ablation_deltas_ndcg10"] = deltas
    out_path = ROOT / "data" / "eval" / "retrieval_metrics.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
