"""Model-size sweep ablation: same retrieval, vary the generator size, per
docs/project_plan.md Phase 4 ("run the size sweep as an ablation -- 1B vs 7B vs
14B on the same retrieval -- and report it").

WHAT THIS MEASURES, PRECISELY: structural citation validity -- whether the
generator's provenance fields point at sources it was actually shown, and
whether it emits schema-valid output at all. It does NOT measure answer
quality, correctness of layer tagging, or doctrinal fidelity. Only the 7B run
has human content judging (aggregate_generation.py); calling this sweep's
output "citation reliability" overstates it, and the README should say
"structural citation validity" instead.

Scope decision, made explicit rather than silently: this sweep runs all three
sizes over the full 20-question stratified sample and reports fully automated
metrics for all three. It does NOT re-run the manual layer-attribution /
anachronistic-conflation judging (generation_judgments.py) for the 1.5B and
14B outputs -- that judging is a human-annotator-cost bottleneck
(docs/eval_rubric.md), and tripling it wasn't a good use of the one annotator
available.

Same retrieval across all three sizes: bundles are fetched once per question
and reused for every model, so any difference in output is attributable to
the generator, not to retrieval variance between runs.

--------------------------------------------------------------------------
Corrections applied to the previous revision of this script. The numbers it
produced (85% -> 44% -> 19% "structural warning rate", 1.5B -> 7B -> 14B)
should not be reported; they are affected by all five issues below.

1. WARNING COUNTS WERE SEVERITY-BLIND. `len(warnings)` summed genuine
   fabricated citations together with cosmetic group_id format drift
   ("g13.2" vs stored "13.2"). Since format compliance improves with model
   size independently of hallucination, the observed monotonic trend had an
   obvious confound. Now split via schemas.summarize(): errors are
   provenance failures, warnings are prompt-compliance drift, reported
   separately and never summed.

2. RETRY MASKED FIRST-PASS BEHAVIOUR. max_retries=1 meant reported rates
   were post-correction -- "can this model repair a citation when told it is
   wrong", not "does it cite correctly". Default is now 0. Run both and
   report both; --max-retries is a CLI flag and is recorded in every row so
   the two runs stay distinguishable.

3. FAILURES VANISHED FROM THE DENOMINATOR. Rows with success=False were
   filtered out before computing the rate, so a model that failed schema
   decoding was rewarded for it -- biasing the metric in favour of the
   weakest model while the headline claimed the weakest model was worst.
   The primary metric is now clean_answer_rate = (answers with zero
   provenance errors) / (all attempts, including failures).

4. NO UNCERTAINTY ON n=20. A ratio-of-sums over clustered data (claims
   within a question are not independent) reported to three decimals invites
   over-reading. Bootstrap CIs are now resampled BY QUESTION, and will be
   wide enough to make clear that n=20 supports "large gap between 1.5B and
   14B" but probably not a claim of monotonicity across three points.

5. COLD-START POLLUTED LATENCY. Ollama loads each model on first call, so
   the first generation per model carried a 4.7GB-vs-9GB file read. A
   discarded warm-up call now precedes timing.

Also: results are written incrementally, so an Ollama timeout mid-sweep no
longer loses the whole run.

CAVEAT ON THE SAMPLE: stratified_sample(gold, per_type=5) puts five
cross-recension questions into this 20-question sample. If the corpus has no
Udanavarga / Gandhari / Patna sources, a quarter of this sweep measures
generation behaviour on retrieval that could not have succeeded. Resolve the
cross-recension stratum before treating these aggregates as meaningful; the
per-type table below is printed so the contamination stays visible.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.generate.generate import Generator, GenerationError  # noqa: E402
from dhammapada_rag.generate.schemas import summarize  # noqa: E402
from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402
from dhammapada_rag.eval.generation_metrics import stratified_sample  # noqa: E402

MODELS = ["qwen2.5:1.5b-instruct", "qwen2.5:7b-instruct", "qwen2.5:14b-instruct"]

SEED = 20260731
BOOTSTRAP_N = 2000


def build_generator(model_name: str) -> tuple[Generator, bool]:
    """Construct a Generator with sampling pinned off, if it supports that.

    Returns (generator, deterministic). If Generator does not accept
    temperature/seed, this returns deterministic=False and the caller prints
    a loud warning rather than silently reporting single-sample results from
    a stochastic decoder as if they were stable.
    """
    try:
        return Generator(model=model_name, temperature=0.0, seed=SEED), True
    except TypeError:
        return Generator(model=model_name), False


def bootstrap_ci(rows: list[dict], numer: str, denom: str, n: int = BOOTSTRAP_N) -> tuple[float, float]:
    """95% CI for a ratio-of-sums, resampling BY QUESTION.

    Claims within a question share a retrieval bundle, so they are not
    independent; resampling claims would understate the interval badly.
    """
    if not rows:
        return (0.0, 0.0)
    rng = random.Random(SEED)
    rates = []
    for _ in range(n):
        s = [rng.choice(rows) for _ in rows]
        d = sum(r[denom] for r in s)
        rates.append(sum(r[numer] for r in s) / d if d else 0.0)
    rates.sort()
    return (rates[int(0.025 * n)], rates[int(0.975 * n)])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-retries", type=int, default=0,
        help="0 (default) measures first-pass citation behaviour. 1 measures "
             "post-correction behaviour. Report both; do not conflate them.",
    )
    ap.add_argument("--per-type", type=int, default=5, help="questions per query type")
    ap.add_argument("--out", type=Path, default=None, help="output jsonl path")
    args = ap.parse_args()

    out_path = args.out or (
        ROOT / "data" / "eval" / f"model_sweep_results_retries{args.max_retries}.jsonl"
    )

    gold_path = ROOT / "data" / "eval" / "gold_set.jsonl"
    gold = [json.loads(l) for l in gold_path.read_text(encoding="utf-8").splitlines()]
    sample = stratified_sample(gold, per_type=args.per_type)
    print(
        f"Running {len(MODELS)} models x {len(sample)} questions = "
        f"{len(MODELS) * len(sample)} generations  (max_retries={args.max_retries})"
    )

    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)

    # Fetch retrieval bundles once per question, reused across all models.
    bundles_by_qid = {}
    for q in sample:
        bundles_by_qid[q["question_id"]] = query(
            q["question"], index=index, reranker=reranker, top_k=3, root=ROOT,
            verses_by_number=verses_by_number, stories_by_id=stories_by_id,
        )
    print("Retrieval done, generating per model...")

    results: list[dict] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as fh:
        for model_name in MODELS:
            generator, deterministic = build_generator(model_name)
            if not deterministic:
                print(
                    f"  !! {model_name}: Generator does not accept temperature/seed. "
                    f"Sampling is unpinned, n=1 per question -- run-to-run variance is "
                    f"UNMEASURED. Wire options={{'temperature':0,'seed':...}} through to "
                    f"the Ollama call before reporting these numbers."
                )

            # Discard one generation to absorb Ollama's model load.
            try:
                generator.generate(sample[0]["question"], bundles_by_qid[sample[0]["question_id"]], max_retries=0)
                print(f"  {model_name}: warm-up done")
            except GenerationError:
                print(f"  {model_name}: warm-up call failed (continuing; timings may include load)")

            for q in sample:
                bundles = bundles_by_qid[q["question_id"]]
                row = {
                    "model": model_name,
                    "question_id": q["question_id"],
                    "type": q["type"],
                    "max_retries": args.max_retries,
                    "deterministic": deterministic,
                }
                try:
                    gen = generator.generate(q["question"], bundles, max_retries=args.max_retries)
                    counts = summarize(gen["warnings"])
                    n_claims = len(gen["answer"].claims)
                    row.update({
                        "success": True,
                        "n_claims": n_claims,
                        # Provenance failures: model pointed at something it was not shown.
                        "n_provenance_errors": counts["error"],
                        # Prompt-compliance drift: citation resolved, format deviated.
                        "n_format_warnings": counts["warning"],
                        "n_info": counts["info"],
                        "warning_codes": {k: v for k, v in counts.items()
                                          if k not in ("error", "warning", "info")},
                        "clean": counts["error"] == 0,
                        "latency_s": gen["latency_s"],
                        "attempt": gen["attempt"],
                        # Round 5, Task N: wall-clock latency conflates model size
                        # with prompt length (prompts vary by up to ~2x across
                        # questions in this sample). tokens_per_second is Ollama's
                        # own generation-only rate and is comparable across models
                        # independent of how long any one prompt happened to be.
                        "eval_count": gen["eval_count"],
                        "eval_duration_ns": gen["eval_duration_ns"],
                        "tokens_per_second": gen["tokens_per_second"],
                        "schema_status": gen["schema_status"],
                        # Layer marginals -- a degenerate classifier emitting only
                        # 'verse' produces zero structural warnings while failing the
                        # project's central claim. The audit cannot see this; count it.
                        "layer_counts": {
                            lyr: sum(1 for c in gen["answer"].claims if c.layer == lyr)
                            for lyr in ("verse", "commentary", "alignment", "note", "synthesis")
                        },
                    })
                except GenerationError as e:
                    row.update({
                        "success": False,
                        "error": str(e),
                        "n_claims": 0,
                        "n_provenance_errors": 0,
                        "n_format_warnings": 0,
                        "clean": False,
                        "attempt": args.max_retries + 1,
                    })

                results.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()

                if row["success"]:
                    print(
                        f"  {model_name} / {q['question_id']}: {row['n_claims']} claims, "
                        f"{row['n_provenance_errors']} errors, {row['n_format_warnings']} format, "
                        f"attempt={row['attempt']}, {row['latency_s']:.1f}s"
                    )
                else:
                    print(f"  {model_name} / {q['question_id']}: FAILED: {row['error']}")

    print(f"\nWrote {out_path}")

    # ---------------------------------------------------------------- summary
    print(f"\n=== Summary per model (max_retries={args.max_retries}) ===")
    print(
        f"  {'model':24s} {'clean':>12s}  {'err/claim [95% CI]':>26s}  "
        f"{'fmt/claim':>10s}  {'fail':>6s}  {'retry':>6s}  {'latency':>8s}  {'tok/s':>7s}"
    )
    for model_name in MODELS:
        all_rows = [r for r in results if r["model"] == model_name]
        ok = [r for r in all_rows if r["success"]]
        n_fail = len(all_rows) - len(ok)

        # PRIMARY METRIC: fully clean answers over ALL attempts, failures included.
        # Cannot be gamed by dropping failed generations from the denominator.
        n_clean = sum(1 for r in all_rows if r["clean"])
        clean_rate = n_clean / len(all_rows) if all_rows else 0.0

        if not ok:
            print(f"  {model_name:24s} {n_clean}/{len(all_rows)}  ALL GENERATIONS FAILED")
            continue

        total_claims = sum(r["n_claims"] for r in ok)
        total_err = sum(r["n_provenance_errors"] for r in ok)
        total_fmt = sum(r["n_format_warnings"] for r in ok)
        lo, hi = bootstrap_ci(ok, "n_provenance_errors", "n_claims")
        err_rate = total_err / total_claims if total_claims else 0.0
        fmt_rate = total_fmt / total_claims if total_claims else 0.0
        n_retried = sum(1 for r in ok if r["attempt"] > 1)
        avg_latency = sum(r["latency_s"] for r in ok) / len(ok)
        tps_values = [r["tokens_per_second"] for r in ok if r.get("tokens_per_second")]
        avg_tps = sum(tps_values) / len(tps_values) if tps_values else None
        tps_str = f"{avg_tps:5.1f}" if avg_tps else "  n/a"

        print(
            f"  {model_name:24s} {n_clean:>4d}/{len(all_rows):<3d} {clean_rate:5.1%}  "
            f"{err_rate:8.3f} [{lo:.3f}, {hi:.3f}]  {fmt_rate:10.3f}  "
            f"{n_fail:>6d}  {n_retried:>6d}  {avg_latency:7.1f}s  {tps_str:>7s}"
        )
    print(
        "  tok/s is Ollama's own generation-only rate (eval_count/eval_duration) --\n"
        "  a fairer cross-model comparison than latency alone, which conflates model\n"
        "  size with per-question prompt length."
    )

    # Layer marginals: the degenerate-classifier check.
    print("\n=== Layer marginals (predicted) ===")
    for model_name in MODELS:
        ok = [r for r in results if r["model"] == model_name and r["success"]]
        if not ok:
            continue
        tot = {lyr: sum(r["layer_counts"][lyr] for r in ok) for lyr in ("verse", "commentary", "alignment", "note", "synthesis")}
        n = sum(tot.values()) or 1
        print(
            f"  {model_name:24s} verse={tot['verse']:>3d} ({tot['verse']/n:4.0%})  "
            f"commentary={tot['commentary']:>3d} ({tot['commentary']/n:4.0%})  "
            f"alignment={tot['alignment']:>3d} ({tot['alignment']/n:4.0%})  "
            f"note={tot['note']:>3d} ({tot['note']/n:4.0%})  "
            f"synthesis={tot['synthesis']:>3d} ({tot['synthesis']/n:4.0%})"
        )
    print(
        "  NOTE: a model emitting ~100% 'verse' is not doing layer attribution at all.\n"
        "  Zero structural warnings is compatible with total failure of the project's\n"
        "  central claim. Read this table before reading the one above."
    )

    # Per-type breakdown, so a stratum with no supporting corpus stays visible.
    print("\n=== Clean-answer rate per query type ===")
    types = sorted({r["type"] for r in results})
    print(f"  {'model':24s} " + "  ".join(f"{t[:14]:>14s}" for t in types))
    for model_name in MODELS:
        cells = []
        for t in types:
            rows_t = [r for r in results if r["model"] == model_name and r["type"] == t]
            c = sum(1 for r in rows_t if r["clean"])
            cells.append(f"{c}/{len(rows_t)}".rjust(14) if rows_t else "-".rjust(14))
        print(f"  {model_name:24s} " + "  ".join(cells))


if __name__ == "__main__":
    main()
