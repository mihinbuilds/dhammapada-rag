"""Compute layer-attribution metrics from data/eval/generation_raw.jsonl +
data/eval/generation_judgments.py, per docs/eval_rubric.md. See that file's
"Annotator status" for what these numbers do and don't represent (single-pass
annotation, no inter-annotator agreement).

--------------------------------------------------------------------------
FIXES over the previous revision:

1. SCALAR ACCURACY REPLACED BY A 3x3 CONFUSION MATRIX. "Layer attribution
   accuracy = 47.6%" is uninterpretable on its own. If the model tags
   essentially every claim 'verse' -- which observed output suggests -- then
   that figure is roughly the base rate of verse-layer claims and the model is
   constant-predicting, not classifying. A confusion matrix plus the predicted
   marginal distribution shows this immediately; a scalar hides it. This
   requires JUDGMENTS to carry the gold layer, not just a boolean (see
   REQUIRED JUDGMENT SHAPE below).

2. STRUCTURAL WARNINGS COUNTED BY SEVERITY. The old
   `sum(len(r["structural_warnings"]))` summed genuine fabricated citations
   together with cosmetic format drift. They are now reported separately.

3. CONFLATION COUNTED IN BOTH DIRECTIONS. Tagging commentary content as
   'verse' presents a 5th-century gloss as the Buddha's words -- the failure
   the project exists to prevent. But tagging verse content as 'commentary'
   is also an attribution error, and became more likely once the prompt began
   requiring commentary engagement (a model can satisfy that instruction by
   mislabelling). Reporting only one direction would make the prompt fix look
   better than it is.

REQUIRED JUDGMENT SHAPE. Each entry in JUDGMENTS must expose:
    tag_correct: bool          predicted layer matches the gold layer
    gold_layer:  str           "verse" | "commentary" | "synthesis"
    is_conflation: bool        commentary content presented as verse
If your existing judgment objects lack `gold_layer`, add it -- the confusion
matrix cannot be built without it, and it is the single most informative
number this eval produces.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "eval"))

from generation_judgments import JUDGMENTS  # noqa: E402

LAYERS = ("verse", "commentary", "synthesis")


def main():
    raw = [json.loads(l) for l in (ROOT / "data" / "eval" / "generation_raw.jsonl").read_text(encoding="utf-8").splitlines()]

    claims = []
    for r in raw:
        for i, c in enumerate(r["claims"]):
            key = (r["question_id"], i)
            if key not in JUDGMENTS:
                raise KeyError(f"No judgment recorded for {key}")
            j = JUDGMENTS[key]
            gold_layer = getattr(j, "gold_layer", None)
            if gold_layer is None:
                raise AttributeError(
                    f"Judgment {key} has no `gold_layer`. Add it to every judgment: the "
                    f"confusion matrix cannot be built from a boolean alone, and the "
                    f"scalar accuracy it replaces is not interpretable."
                )
            claims.append({
                "question_id": r["question_id"],
                "type": r["type"],
                "predicted": c["layer"],
                "gold": gold_layer,
                "tag_correct": j.tag_correct,
                "is_conflation": j.is_conflation,
            })

    n = len(claims)

    # ---------------------------------------------------------------- warnings
    n_err = sum(1 for r in raw for w in r["structural_warnings"] if w["severity"] == "error")
    n_fmt = sum(1 for r in raw for w in r["structural_warnings"] if w["severity"] == "warning")

    print(f"n questions = {len(raw)}, n claims = {n}")
    print(f"Provenance errors: {n_err}/{n} claims   Format warnings: {n_fmt}/{n} claims")

    # ------------------------------------------------------- predicted marginal
    pred_marginal = {l: sum(1 for c in claims if c["predicted"] == l) for l in LAYERS}
    gold_marginal = {l: sum(1 for c in claims if c["gold"] == l) for l in LAYERS}
    print("\n=== Layer marginals ===")
    print(f"  predicted: " + "  ".join(f"{l}={pred_marginal[l]} ({pred_marginal[l]/n:.0%})" for l in LAYERS))
    print(f"  gold:      " + "  ".join(f"{l}={gold_marginal[l]} ({gold_marginal[l]/n:.0%})" for l in LAYERS))

    dominant = max(pred_marginal, key=pred_marginal.get)
    if pred_marginal[dominant] / n > 0.85:
        print(
            f"  !! {pred_marginal[dominant]/n:.0%} of claims predicted '{dominant}'. This is a\n"
            f"     degenerate classifier, not layer attribution. Any accuracy figure below is\n"
            f"     approximately the base rate of that class and should not be reported as\n"
            f"     evidence the system distinguishes layers."
        )

    # -------------------------------------------------------- confusion matrix
    print("\n=== Confusion matrix (rows = gold, cols = predicted) ===")
    print(f"  {'gold \\ pred':16s} " + "  ".join(f"{l:>12s}" for l in LAYERS) + f"  {'total':>8s}")
    matrix = {g: {p: 0 for p in LAYERS} for g in LAYERS}
    for c in claims:
        matrix[c["gold"]][c["predicted"]] += 1
    for g in LAYERS:
        row = matrix[g]
        print(f"  {g:16s} " + "  ".join(f"{row[p]:>12d}" for p in LAYERS) + f"  {sum(row.values()):>8d}")

    print("\n=== Per-class precision / recall ===")
    per_class = {}
    for l in LAYERS:
        tp = matrix[l][l]
        fp = sum(matrix[g][l] for g in LAYERS if g != l)
        fn = sum(matrix[l][p] for p in LAYERS if p != l)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[l] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "support": tp + fn}
        print(f"  {l:12s} P={prec:.3f}  R={rec:.3f}  F1={f1:.3f}  support={tp + fn}")

    macro_f1 = sum(per_class[l]["f1"] for l in LAYERS) / len(LAYERS)
    accuracy = sum(1 for c in claims if c["tag_correct"]) / n
    print(f"\n  macro-F1 = {macro_f1:.3f}   (accuracy = {accuracy:.3f}; prefer macro-F1 --")
    print("  accuracy rewards predicting only the majority class, which is the failure here)")

    # ------------------------------------------------------------- conflation
    n_vc = sum(1 for c in claims if c["predicted"] in ("verse", "commentary"))
    n_confl = sum(1 for c in claims if c["is_conflation"])
    # commentary content presented as verse -- the directional failure that matters
    n_comm_as_verse = matrix["commentary"]["verse"]
    n_verse_as_comm = matrix["verse"]["commentary"]
    print("\n=== Conflation ===")
    print(f"  anachronistic conflation (judged): {n_confl}/{n_vc} = {n_confl/n_vc if n_vc else 0:.3f}")
    print(f"  commentary content tagged 'verse': {n_comm_as_verse}  <- presents a 5th-c. gloss as the Buddha's words")
    print(f"  verse content tagged 'commentary': {n_verse_as_comm}  <- likely prompt-induced over-compliance")

    # ---------------------------------------------------------------- by type
    print("\n=== By query type ===")
    for qtype in sorted({c["type"] for c in claims}):
        sub = [c for c in claims if c["type"] == qtype]
        acc = sum(1 for c in sub if c["tag_correct"]) / len(sub)
        pm = {l: sum(1 for c in sub if c["predicted"] == l) for l in LAYERS}
        print(f"  {qtype:16s} n={len(sub):3d}  acc={acc:.3f}  predicted={pm}")

    report = {
        "n_questions": len(raw),
        "n_claims": n,
        "provenance_errors": n_err,
        "format_warnings": n_fmt,
        "predicted_marginal": pred_marginal,
        "gold_marginal": gold_marginal,
        "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_f1": round(macro_f1, 4),
        "accuracy": round(accuracy, 4),
        "conflation_rate": round(n_confl / n_vc, 4) if n_vc else None,
        "commentary_tagged_verse": n_comm_as_verse,
        "verse_tagged_commentary": n_verse_as_comm,
    }
    out_path = ROOT / "data" / "eval" / "generation_metrics.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
