"""Round 15: how much do generation metrics move when only the wording of
the system prompt moves?

Generation runs at temperature 0, so the seed does nothing and a repeated
run is (near-)identical -- measured, not assumed: 25/27 answers came back
word-for-word the same (data/eval/prompt_sensitivity/rerun_identical.jsonl).
What does move the answers is the prompt. Round 13 -> 14 changed the system
prompt and every answer changed with it, so a single-run comparison between
two prompts confounds the change being tested with the change in wording.
This script measures that confound directly: the Round 14 prompt and three
meaning-preserving variants of it (rules reordered, Markdown headings,
typography), each run on the same 27 questions and judged the same way.

Judgments are looked up per claim:
  1. an explicit entry in data/eval/prompt_sensitivity/judgments.py, keyed
     (run, question_id, claim_index); else
  2. a claim with the same question, layer, citation and text already judged
     elsewhere (the Round 14 judgments in data/eval/generation_judgments.py,
     or another run's explicit entry) -- the same claim gets the same verdict.

Metric definitions match aggregate_generation.py exactly.

Round 16 adds a second set of four runs, same wordings, after the [NOTES]
block was restructured (data/eval/note_block/); both sets are scored side
by side, so the block's effect is read against the wording spread rather
than against a single run.

Run: python -m dhammapada_rag.eval.prompt_sensitivity [--todo]
  --todo   list every claim that still has no verdict, and stop
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "eval"))  # judgment files import Verdict from generation_judgments


def _load_module(path: Path):
    name = f"judgments_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


# The Round 14 run's own judgments, loaded by path: the canonical
# data/eval/generation_judgments.py has since moved on to a later run.
ROUND14 = _load_module(ROOT / "data" / "eval" / "archive_round14_note_layer" / "generation_judgments.py").JUDGMENTS

LAYERS = ("verse", "commentary", "alignment", "note", "synthesis")
_PS = ROOT / "data" / "eval" / "prompt_sensitivity"
_NB = ROOT / "data" / "eval" / "note_block"
_CF = ROOT / "data" / "eval" / "corpus_facts"
_NR = ROOT / "data" / "eval" / "note_retry"
RUNS = {
    "round14": ROOT / "data" / "eval" / "archive_round14_note_layer" / "generation_raw.jsonl",
    "a_reorder": _PS / "run_a_reorder.jsonl",
    "b_markdown": _PS / "run_b_markdown.jsonl",
    "c_typography": _PS / "run_c_typography.jsonl",
    "r16_base": _NB / "run_base.jsonl",
    "r16_a_reorder": _NB / "run_a_reorder.jsonl",
    "r16_b_markdown": _NB / "run_b_markdown.jsonl",
    "r16_c_typography": _NB / "run_c_typography.jsonl",
    "r17_base": _CF / "run_base.jsonl",
    "r17_a_reorder": _CF / "run_a_reorder.jsonl",
    "r17_b_markdown": _CF / "run_b_markdown.jsonl",
    "r17_c_typography": _CF / "run_c_typography.jsonl",
    "r18_base": _NR / "run_base.jsonl",
    "r18_a_reorder": _NR / "run_a_reorder.jsonl",
    "r18_b_markdown": _NR / "run_b_markdown.jsonl",
    "r18_c_typography": _NR / "run_c_typography.jsonl",
}
SETS = {
    "round15 (note block v1)": ["round14", "a_reorder", "b_markdown", "c_typography"],
    "round16 (note block v2)": ["r16_base", "r16_a_reorder", "r16_b_markdown", "r16_c_typography"],
    "round17 (corpus facts)": ["r17_base", "r17_a_reorder", "r17_b_markdown", "r17_c_typography"],
    "round18 (note retry)": ["r18_base", "r18_a_reorder", "r18_b_markdown", "r18_c_typography"],
}
JUDGMENT_FILES = (_PS / "judgments.py", _NB / "judgments.py", _CF / "judgments.py", _NR / "judgments.py")


def _load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def signature(question_id: str, c: dict) -> tuple:
    return (
        question_id, c["layer"], c.get("group_id"), c.get("verse_number"),
        tuple(c.get("verse_numbers") or ()), " ".join(c["text"].split()),
    )


def _verdicts() -> tuple[dict, dict]:
    explicit = {}
    for path in JUDGMENT_FILES:
        if path.exists():
            explicit.update(_load_module(path).JUDGMENTS)
    by_sig = {}
    for r in _load(RUNS["round14"]):
        for i, c in enumerate(r["claims"]):
            by_sig[signature(r["question_id"], c)] = ROUND14[(r["question_id"], i)]
    for (run, qid, i), v in explicit.items():
        c = {r["question_id"]: r for r in _load(RUNS[run])}[qid]["claims"][i]
        by_sig.setdefault(signature(qid, c), v)
    return explicit, by_sig


def metrics(claims: list[dict]) -> dict:
    n = len(claims)
    matrix = {g: {p: 0 for p in LAYERS} for g in LAYERS}
    for c in claims:
        matrix[c["gold"]][c["predicted"]] += 1
    f1s = {}
    for l in LAYERS:
        tp = matrix[l][l]
        fp = sum(matrix[g][l] for g in LAYERS if g != l)
        fn = sum(matrix[l][p] for p in LAYERS if p != l)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[l] = (2 * prec * rec / (prec + rec) if prec + rec else 0.0, tp + fn, rec)
    n_vc = sum(1 for c in claims if c["predicted"] in ("verse", "commentary"))
    cited = [c for c in claims if c["predicted"] != "synthesis"]
    return {
        "claims": n,
        "accuracy": sum(c["tag_correct"] for c in claims) / n,
        "macro_f1": sum(f for f, _, _ in f1s.values()) / len(LAYERS),
        "conflation_rate": sum(c["is_conflation"] for c in claims) / n_vc if n_vc else 0.0,
        "fidelity": sum(c["faithful"] for c in claims) / n,
        "fidelity_cited": sum(c["faithful"] for c in cited) / len(cited) if cited else 0.0,
        "note_recall": f1s["note"][2] if f1s["note"][1] else None,
    }


def main() -> None:
    explicit, by_sig = _verdicts()
    todo, results = [], {}
    for run, path in RUNS.items():
        if not path.exists():
            print(f"(skipping {run}: {path.name} not found)")
            continue
        claims = []
        for r in _load(path):
            for i, c in enumerate(r["claims"]):
                v = explicit.get((run, r["question_id"], i)) or by_sig.get(signature(r["question_id"], c))
                if v is None:
                    todo.append((run, r["question_id"], i, c))
                    continue
                claims.append({"predicted": c["layer"], "gold": v.gold_layer, "tag_correct": v.tag_correct,
                               "is_conflation": v.is_conflation, "faithful": v.faithful})
        results[run] = claims
    if todo or "--todo" in sys.argv:
        print(f"{len(todo)} claims without a verdict:")
        for run, qid, i, c in todo:
            cite = {k: c.get(k) for k in ("group_id", "verse_number", "verse_numbers") if c.get(k) is not None}
            print(f"  ({run!r}, {qid!r}, {i}): {c['layer']} {cite} :: {c['text']}")
        if todo:
            sys.exit(1)
        return

    per_run = {run: metrics(claims) for run, claims in results.items()}
    keys = ("claims", "accuracy", "macro_f1", "conflation_rate", "fidelity", "fidelity_cited", "note_recall")
    spread_by_set = {}
    for set_name, runs in SETS.items():
        runs = [r for r in runs if r in per_run]
        if not runs:
            continue
        print(f"\n== {set_name}")
        print(f"{'run':18s}" + "".join(f"{k:>16s}" for k in keys))
        for run in runs:
            m = per_run[run]
            print(f"{run:18s}" + "".join(f"{m[k]:>16.3f}" if m[k] is not None else f"{'-':>16s}" for k in keys))
        spread = {}
        for k in keys:
            vals = [per_run[r][k] for r in runs if per_run[r][k] is not None]
            spread[k] = {"mean": statistics.mean(vals), "min": min(vals), "max": max(vals),
                         "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0}
        print(f"{'mean':18s}" + "".join(f"{spread[k]['mean']:>16.3f}" for k in keys))
        print(f"{'min-max':18s}" + "".join(f"{spread[k]['min']:>8.3f}-{spread[k]['max']:<7.3f}" for k in keys))
        spread_by_set[set_name] = spread
    out = _PS / "results.json"
    out.write_text(json.dumps({"per_run": per_run, "spread_by_set": spread_by_set}, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
