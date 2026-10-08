"""Blind second-annotator pass over gold_set_v2, and the agreement statistic.

docs/eval_rubric.md "Annotator status": the gold set has one annotator, so no
agreement statistic exists. This module makes a second pass possible without
the second annotator ever seeing the first one's labels.

  build   Writes a CSV with one row per (question, candidate story). Candidates
          are the gold stories, the named distractors, and the top-TOP_K
          stories of each retrieval condition, shuffled per question so
          position gives nothing away. No column says which is gold. The
          annotator fills `relevant` with 1 or 0.
  kappa   Reads the filled CSV and compares it with annotator 1's labels
          (candidate is in gold_group_ids) -- Cohen's kappa overall and per
          subtype, raw agreement, and every disagreement listed for review.
          Scores whatever rows have a 0/1 `relevant` value and reports how
          many were still blank, rather than refusing a partially-filled
          sheet -- a realistic stopping point, not an error.

What kappa here measures: agreement on "does this story answer this
question", over the stories a retriever actually surfaced. That is the
judgment every retrieval number in docs/evaluation.md rests on. It says
nothing about generation-claim judgments, which are a separate pass.

Usage:
  python -m dhammapada_rag.eval.annotation_sheet build [--per-category N]
  python -m dhammapada_rag.eval.annotation_sheet kappa data/eval/annotation_v2_filled.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOP_K = 3
CONDITIONS = ("baseline", "verse_only", "dense_only", "no_rerank")
SEED = 20260924

INSTRUCTIONS = (
    "Mark relevant=1 if this story -- its narrative or the verse(s) it explains -- answers or directly bears "
    "on the question; 0 otherwise. For questions asking 'which stories', mark every story that fits. "
    "Judge each row on its own; several rows for one question may be 1, or none. Do not open "
    "data/eval/gold_set_v2.jsonl or retrieval_results_v2.jsonl before finishing."
)


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def candidate_pool(question: dict, result_row: dict | None) -> list[str]:
    pool = list(question["gold_group_ids"]) + list(question.get("distractor_group_ids", []))
    if result_row:
        for cond in CONDITIONS:
            for bundle in result_row[cond].get("top10", [])[:TOP_K]:
                pool.extend(bundle)
    seen: set[str] = set()
    out = []
    for g in pool:
        if g not in seen:
            seen.add(g)
            out.append(g)
    rng = random.Random(f"{SEED}:{question['question_id']}")
    rng.shuffle(out)
    return out


def build(per_category: int | None, out_path: Path) -> None:
    gold = _load_jsonl(ROOT / "data/eval/gold_set_v2.jsonl")
    results_path = ROOT / "data/eval/retrieval_results_v2.jsonl"
    results = {r["question_id"]: r for r in _load_jsonl(results_path)} if results_path.exists() else {}
    if not results:
        print(f"note: {results_path.relative_to(ROOT)} not found; pool is gold + distractors only, which leaks the answer")
    stories = {s["group_id"]: s for s in _load_jsonl(ROOT / "data/processed/stories.jsonl")}
    verses = {v["verse"]: v for v in _load_jsonl(ROOT / "data/processed/verses.jsonl")}

    if per_category:
        by_sub: dict[str, list[dict]] = defaultdict(list)
        for q in gold:
            by_sub[q["subtype"]].append(q)
        rng = random.Random(SEED)
        gold = [q for sub in sorted(by_sub) for q in sorted(rng.sample(by_sub[sub], min(per_category, len(by_sub[sub]))), key=lambda q: q["question_id"])]

    n_rows = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["question_id", "question", "candidate_group_id", "title", "synopsis", "verse_english", "relevant", "comment"])
        for q in gold:
            for g in candidate_pool(q, results.get(q["question_id"])):
                s = stories[g]
                verse_text = " / ".join(f"Dhp {v}: {verses[v]['interlinear_english']}" for v in s["dhp_verses"])
                w.writerow([q["question_id"], q["question"], g, s["title_en"], s["synopsis"] or "", verse_text, "", ""])
                n_rows += 1
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path  # --out pointed outside the repo (e.g. a scratch path)
    print(f"Wrote {n_rows} rows for {len(gold)} questions to {shown}")
    print(f"Instructions for the annotator:\n  {INSTRUCTIONS}")


def cohen_kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa(filled: Path, out_path: Path) -> None:
    gold = {q["question_id"]: q for q in _load_jsonl(ROOT / "data/eval/gold_set_v2.jsonl")}
    all_rows = list(csv.DictReader(filled.open(encoding="utf-8")))

    # A blank `relevant` cell means "not yet judged" -- realistic for someone
    # who filled in 200 of 507 rows and stopped -- and is scored on whatever
    # subset is complete rather than refused outright. Anything non-blank
    # that isn't 0/1 (a stray "y", a typo) is still a hard error: it's not
    # incompleteness, it's a formatting mistake that would silently corrupt
    # the count if scored as-is.
    malformed = [r for r in all_rows if r["relevant"].strip() and r["relevant"].strip() not in ("0", "1")]
    if malformed:
        raise SystemExit(
            f"{len(malformed)} rows have a `relevant` value that isn't blank or 0/1 "
            f"(first: {malformed[0]['question_id']} {malformed[0]['candidate_group_id']} = {malformed[0]['relevant']!r})"
        )
    rows = [r for r in all_rows if r["relevant"].strip() in ("0", "1")]
    n_unlabeled = len(all_rows) - len(rows)
    if not rows:
        raise SystemExit("0 rows have a 0/1 `relevant` value -- nothing to score yet")
    if n_unlabeled:
        print(f"note: {n_unlabeled}/{len(all_rows)} rows are still blank; scoring the {len(rows)} that are filled in")

    pairs: dict[str, list[tuple[int, int]]] = defaultdict(list)
    disagreements = []
    for r in rows:
        q = gold[r["question_id"]]
        a1 = int(r["candidate_group_id"] in q["gold_group_ids"])
        a2 = int(r["relevant"])
        pairs["overall"].append((a1, a2))
        pairs[q["subtype"]].append((a1, a2))
        if a1 != a2:
            disagreements.append({"question_id": r["question_id"], "question": q["question"], "candidate": r["candidate_group_id"],
                                  "title": r["title"], "annotator_1": a1, "annotator_2": a2, "comment": r["comment"]})

    report = {
        "n_rows_total": len(all_rows),
        "n_rows_scored": len(rows),
        "n_unlabeled": n_unlabeled,
        "n_questions": len({r["question_id"] for r in rows}),
        "by": {},
    }
    for key, ps in sorted(pairs.items(), key=lambda kv: (kv[0] != "overall", kv[0])):
        a, b = [x for x, _ in ps], [y for _, y in ps]
        report["by"][key] = {
            "n": len(ps),
            "cohen_kappa": round(cohen_kappa(a, b), 3),
            "raw_agreement": round(sum(x == y for x, y in ps) / len(ps), 3),
        }
        print(f"  {key:20s} n={len(ps):4d}  kappa={report['by'][key]['cohen_kappa']:.3f}  agreement={report['by'][key]['raw_agreement']:.3f}")
    report["disagreements"] = disagreements
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path  # --out pointed outside the repo (e.g. a scratch path)
    print(f"{len(disagreements)} disagreements; wrote {shown}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--per-category", type=int, default=None, help="annotate a stratified sample of N questions per subtype")
    b.add_argument("--out", default="data/eval/annotation_v2_blank.csv")
    k = sub.add_parser("kappa")
    k.add_argument("filled")
    k.add_argument("--out", default="data/eval/iaa_v2.json")
    args = ap.parse_args()
    if args.cmd == "build":
        build(args.per_category, ROOT / args.out)
    else:
        kappa(Path(args.filled), ROOT / args.out)


if __name__ == "__main__":
    main()
