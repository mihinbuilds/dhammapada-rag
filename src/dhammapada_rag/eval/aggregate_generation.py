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
    faithful: bool             claim's content accurately represents (does
                                not invert or misstate) the source text it is
                                grounded in -- a different axis from layer
                                attribution, see generation_judgments.py's
                                "Source fidelity (Task E)" note and
                                docs/eval_rubric.md
If your existing judgment objects lack `gold_layer`, add it -- the confusion
matrix cannot be built without it, and it is the single most informative
number this eval produces.

4. SOURCE FIDELITY RATE ADDED (Task E). Structural provenance checks
   (generate/schemas.py's audit()) and layer-attribution accuracy both only
   ask "is this claim shaped/cited correctly" -- neither can catch a claim
   that cites a real source, is correctly tagged, and still inverts what
   that source says (see docs/eval_rubric.md's worked example: a claim that
   Kisā Gotamī found no mustard seed "because no household had ever seen a
   death," the exact inverse of story 8.13). `faithful` is a distinct,
   per-claim judgment for exactly this failure mode; reported separately
   below rather than folded into layer accuracy, since a claim can be
   tag_correct and unfaithful at the same time.

5. CONTEXT UTILIZATION AND LAYER-COUNT DISTRIBUTION ADDED (Round 7, Task V).
   Every metric above asks whether a produced claim is correctly shaped,
   tagged, and faithful -- none of them ask whether the answer used what
   retrieval gave it. A system that retrieves three verse-groups, cites one,
   and says nothing about the other two is not doing multi-layer synthesis,
   and every existing metric is blind to it: the one claim it does produce
   can be perfectly tagged, cited, and faithful. `utilization` = (groups
   cited + groups explicitly dismissed in a synthesis claim) / groups
   retrieved, computed per question from fields already in
   generation_raw.jsonl (retrieved_group_ids, claims, gold_context) --
   dismissal is detected by a retrieved-but-uncited group's id or story
   title appearing in some synthesis claim's text, a heuristic substring
   check, not semantic verification that the dismissal was reasoned. Layer-
   count distribution (how many answers use 1/2/3/4 distinct layers) is
   reported alongside it: an architecture built on layer separation should
   be able to show what fraction of its answers actually separate layers,
   not just that any one claim, in isolation, is tagged correctly.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "eval"))
sys.path.insert(0, str(ROOT / "src"))

from generation_judgments import JUDGMENTS  # noqa: E402
from dhammapada_rag.generate.schemas import _pali_orthographic, normalize_group_id  # noqa: E402

# Round 7, Task T: "alignment" is a fourth layer (facts about the corpus's
# own editorial structure -- which story explains which verse group -- as
# distinct from both the verse's own words and Buddhaghosa's gloss), so the
# confusion matrix below is 4x4, not 3x3. Every loop in this file already
# iterates LAYERS rather than hardcoding three names, so this one-line
# change is sufficient to widen the matrix, marginals, and per-class table.
LAYERS = ("verse", "commentary", "alignment", "synthesis")

# Round 8, Task AC seed: reproducible bootstrap, same rationale as
# model_sweep.py's own resampling (Round 5, Task N correction) -- an
# arbitrary but fixed value, not tuned.
_BOOTSTRAP_SEED = 20260813
_BOOTSTRAP_RESAMPLES = 2000


def _bootstrap_ci_by_question(rows: list[dict], value_key: str, question_key: str = "question_id") -> tuple[float, float, float]:
    """Bootstrap 95% CI for the mean of `value_key` (a bool/0-1 field),
    resampled BY QUESTION rather than by claim.

    Claims within a question are not independent (they share retrieval,
    generation call, and often correctness), so resampling individual
    claims would understate the true uncertainty -- the same reasoning
    model_sweep.py's own bootstrap already applies (Round 5, Task N).
    Returns (point_estimate, ci_lo, ci_hi) over ALL rows given (point
    estimate is the plain mean, not the bootstrap mean, per standard
    practice); rows with no claims contribute nothing to any resample.
    """
    by_question: dict[str, list[bool]] = {}
    for r in rows:
        by_question.setdefault(r[question_key], []).append(r[value_key])
    all_values = [v for vs in by_question.values() for v in vs]
    point = sum(all_values) / len(all_values) if all_values else 0.0

    question_ids = list(by_question)
    rng = random.Random(_BOOTSTRAP_SEED)
    resample_rates = []
    for _ in range(_BOOTSTRAP_RESAMPLES):
        sampled_qids = [rng.choice(question_ids) for _ in question_ids]
        values = [v for qid in sampled_qids for v in by_question[qid]]
        if values:
            resample_rates.append(sum(values) / len(values))
    resample_rates.sort()
    if not resample_rates:
        return point, point, point
    lo = resample_rates[int(0.025 * len(resample_rates))]
    hi = resample_rates[min(int(0.975 * len(resample_rates)), len(resample_rates) - 1)]
    return point, lo, hi


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
            faithful = getattr(j, "faithful", None)
            if faithful is None:
                raise AttributeError(
                    f"Judgment {key} has no `faithful`. Add it to every judgment: "
                    f"structural provenance checks and layer-attribution accuracy cannot "
                    f"detect a claim that cites a real source, is correctly tagged, and "
                    f"still inverts or misstates what that source says (see "
                    f"docs/eval_rubric.md's source-fidelity worked example)."
                )
            claims.append({
                "question_id": r["question_id"],
                "type": r["type"],
                "predicted": c["layer"],
                "gold": gold_layer,
                "tag_correct": j.tag_correct,
                "is_conflation": j.is_conflation,
                "faithful": faithful,
            })

    n = len(claims)

    # ---------------------------------------------------------------- warnings
    n_err = sum(1 for r in raw for w in r["structural_warnings"] if w["severity"] == "error")
    n_fmt = sum(1 for r in raw for w in r["structural_warnings"] if w["severity"] == "warning")

    print(f"n questions = {len(raw)}, n claims = {n}")
    print(f"Provenance errors: {n_err}/{n} claims   Format warnings: {n_fmt}/{n} claims")

    # ------------------------------------- context utilization (Round 8, Task Z)
    # Round 7 inferred utilization from claim citations and synthesis-claim
    # prose after the fact -- a heuristic that measured 0/27 questions as
    # fully accounted for, because it could only recognize a dismissal
    # shaped like prose naming the group. source_disposition (required,
    # decoder-constrained to exactly the retrieved group_ids -- see
    # generate/schemas.py) makes this a direct read of a structured field
    # instead: utilization is 1.0 for every schema-valid answer by
    # construction (every group gets an entry), so the informative numbers
    # here are the disposition marginal and the not_relevant/gold cross-tab,
    # not the utilization figure itself.
    has_disposition = any(r.get("source_disposition") for r in raw)
    disp_counts = {"used": 0, "partially_relevant": 0, "not_relevant": 0}
    n_disp_total = 0
    gold_dismissed: list[tuple[str, str]] = []   # model said not_relevant on a gold group -- generation failure
    noise_dismissed: list[tuple[str, str]] = []  # model said not_relevant on a non-gold group -- retrieval noise, correctly caught
    n_fully_covered = 0
    n_dispute = 0
    print("\n=== Source disposition (Round 8, Task Z) ===")
    if not has_disposition:
        print("  no question in this run carries source_disposition -- predates Task Z, nothing to report")
    else:
        for r in raw:
            disp = r.get("source_disposition") or {}
            retrieved = set(r["retrieved_group_ids"])
            gold = set(r.get("gold_group_ids") or [])
            if retrieved and retrieved <= set(disp):
                n_fully_covered += 1
            for gid, d in disp.items():
                if gid not in retrieved:
                    continue  # UNKNOWN_DISPOSITION_GROUP territory, not a real coverage entry
                disp_counts[d] = disp_counts.get(d, 0) + 1
                n_disp_total += 1
                if d == "not_relevant":
                    (gold_dismissed if gid in gold else noise_dismissed).append((r["question_id"], gid))

        n_dispute = sum(
            1 for r in raw for w in r["structural_warnings"] if w["code"] == "DISPOSITION_CONTRADICTS_CLAIMS"
        )
        print(f"  {n_fully_covered}/{len(raw)} questions carry a disposition for every retrieved group")
        if n_disp_total:
            for d in ("used", "partially_relevant", "not_relevant"):
                print(f"  {d:20s}: {disp_counts[d]}/{n_disp_total} = {disp_counts[d]/n_disp_total:.3f}")
        print(f"  disposition/claims disagreement (DISPOSITION_CONTRADICTS_CLAIMS): {n_dispute}/{n_disp_total if n_disp_total else 1}")
        print(
            f"  'not_relevant' on a GOLD group (generation dismissed the correct source): "
            f"{len(gold_dismissed)}"
        )
        if gold_dismissed:
            print(f"    {gold_dismissed}")
        print(
            f"  'not_relevant' on a non-gold group (retrieval noise, correctly caught by generation): "
            f"{len(noise_dismissed)}"
        )
        if disp_counts["not_relevant"] and (len(gold_dismissed) / disp_counts["not_relevant"]) > 0.2:
            print(
                "  !! A meaningful share of 'not_relevant' dispositions land on gold groups -- this points\n"
                "     at generation misjudging relevance, not just retrieval noise. Read the two counts\n"
                "     above separately; do not average them into one 'not_relevant rate'."
            )

    # ------------------------------------------------- layer-count distribution
    # How many answers actually use 1 / 2 / 3 / 4 distinct layers -- an
    # architecture built on layer separation should be able to show what
    # fraction of its answers actually separate layers, not just that any one
    # claim is individually tagged correctly.
    layer_dist = {1: 0, 2: 0, 3: 0, 4: 0}
    claims_per_answer = []
    for r in raw:
        lc = r["layer_counts"]
        n_layers_used = sum(1 for lyr in LAYERS if lc.get(lyr, 0) > 0)
        if n_layers_used:
            layer_dist[n_layers_used] = layer_dist.get(n_layers_used, 0) + 1
        claims_per_answer.append(len(r["claims"]))

    print("\n=== Layer-count distribution (Task V) ===")
    for k in sorted(layer_dist):
        print(f"  answers using {k} layer(s): {layer_dist[k]}/{len(raw)}")
    print(f"  mean claims/answer: {sum(claims_per_answer)/len(claims_per_answer):.2f}  (min={min(claims_per_answer)}, max={max(claims_per_answer)})")
    # Round 8: a minimum-claims/minimum-layers schema constraint was
    # considered and explicitly rejected -- it produces padding (the model
    # elaborates to hit a count rather than engaging more sources), and
    # layer count is a descriptive fact about the question asked, not a
    # target (see this file's docstring point 5 and docs/generation.md's
    # Round 8 "On 0/27 four-layer answers" discussion: most questions do
    # not warrant four layers, and 0/27 four-layer answers is not itself a
    # shortfall). Read this figure alongside context utilization/source
    # disposition above, not as a number to chase upward on its own.
    if layer_dist.get(1, 0) / len(raw) > 0.5:
        print(
            "  !! Most answers use only one layer. Read this alongside the source-disposition\n"
            "     numbers above -- if not_relevant dispositions are landing on gold groups, that\n"
            "     is a retrieval problem; if utilization is high but layer count is still low,\n"
            "     single-layer answers may simply be correct for the questions asked. Do not add\n"
            "     a minimum-claims constraint on the strength of this number alone."
        )

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

    # ---------------------------------------------------------- source fidelity
    n_unfaithful = sum(1 for c in claims if not c["faithful"])
    fidelity_rate = (n - n_unfaithful) / n
    print("\n=== Source fidelity (Task E) ===")
    print(f"  faithful: {n - n_unfaithful}/{n} = {fidelity_rate:.3f}   unfaithful: {n_unfaithful}/{n}")
    print(
        "  A claim can be tag_correct (right layer) and structurally valid (real, present "
        "group_id) and still be unfaithful -- it cites a real source but inverts or "
        "misstates what that source says. Neither generate/schemas.py's audit() nor the "
        "layer-attribution numbers above can catch this; see docs/eval_rubric.md."
    )
    if n_unfaithful:
        bad = [(c["question_id"], c["type"]) for c in claims if not c["faithful"]]
        print(f"  unfaithful claims: {bad}")

    # ------------------------------- source fidelity, scoped + CI (Task AC)
    # Synthesis claims have no source to be faithful TO -- by definition
    # they are the model's own inference, not grounded in a specific
    # retrieved passage (schemas.py's LAYER_DESCRIPTIONS). Folding them into
    # the fidelity rate above dilutes it with claims the metric doesn't
    # apply to; scoped here to verse+commentary+alignment only, the three
    # layers whose claims cite a group_id/verse_number(s) that can be
    # checked against. Bootstrap CI resampled by question (see
    # _bootstrap_ci_by_question), not by claim -- claims within a question
    # share retrieval and generation context and are not independent draws.
    sourced_claims = [c for c in claims if c["predicted"] != "synthesis"]
    fid_point, fid_lo, fid_hi = _bootstrap_ci_by_question(
        [{"question_id": c["question_id"], "faithful": c["faithful"]} for c in sourced_claims], "faithful"
    )
    print("\n=== Source fidelity, verse+commentary+alignment only, bootstrap 95% CI (Task AC) ===")
    print(f"  n={len(sourced_claims)} (excludes {n - len(sourced_claims)} synthesis claims)")
    print(f"  fidelity rate: {fid_point:.3f}  95% CI [{fid_lo:.3f}, {fid_hi:.3f}]  (resampled by question, n={_BOOTSTRAP_RESAMPLES})")

    # ---------------------------------------------- Pali quote fidelity (Task P)
    # Three tiers, not one rate: PALI_QUOTE_NOT_IN_SOURCE (error) and
    # PALI_QUOTE_ORTHOGRAPHIC_VARIANT (warning) are cross-referenced by
    # claim_index against every VerseClaim that actually carries a
    # pali_support quote; a claim with neither warning code is an exact
    # copy. See generate/schemas.py's Round 6, Task P comment for why the
    # variant tier -- not the exact-copy rate alone -- is where the finding
    # about edition variance vs. fabrication lives.
    pali_tiers = []
    for r in raw:
        warn_by_idx = {
            w["claim_index"]: w["code"]
            for w in r["structural_warnings"]
            if w["code"] in ("PALI_QUOTE_NOT_IN_SOURCE", "PALI_QUOTE_ORTHOGRAPHIC_VARIANT")
        }
        for i, c in enumerate(r["claims"]):
            if not c.get("pali_support"):
                continue
            code = warn_by_idx.get(i)
            if code == "PALI_QUOTE_NOT_IN_SOURCE":
                pali_tiers.append("fabrication")
            elif code == "PALI_QUOTE_ORTHOGRAPHIC_VARIANT":
                pali_tiers.append("variant")
            else:
                pali_tiers.append("exact")

    n_pali = len(pali_tiers)
    pali_report = None
    print("\n=== Pali quote fidelity (Round 6, Task P) ===")
    if n_pali:
        n_exact = pali_tiers.count("exact")
        n_variant = pali_tiers.count("variant")
        n_fab = pali_tiers.count("fabrication")
        print(f"  n verse claims with pali_support: {n_pali}")
        print(f"  exact-copy rate:  {n_exact}/{n_pali} = {n_exact/n_pali:.3f}   <- did the model copy its own printed source")
        print(f"  variant rate:     {n_variant}/{n_pali} = {n_variant/n_pali:.3f}   <- knows the text, quoted a different edition")
        print(f"  fabrication rate: {n_fab}/{n_pali} = {n_fab/n_pali:.3f}   <- matches no available Pali field at all")
        pali_report = {
            "n_pali_claims": n_pali,
            "exact_copy_rate": round(n_exact / n_pali, 4),
            "variant_rate": round(n_variant / n_pali, 4),
            "fabrication_rate": round(n_fab / n_pali, 4),
        }
    else:
        print("  no VerseClaim in this run carries pali_support -- nothing to report")

    # ---------------------------------------------- Pali quote coverage (Task AF)
    # A fourth rate alongside the three tiers above: exact/variant/fabrication
    # all ask "are the quoted words real," never "how much of the verse did
    # the model actually quote." A half-quoted verse passes the substring
    # check cleanly (a truncation is a valid substring) and reads as a full
    # exact match in the tiers above -- this is what that number hides.
    # Measured against the verse's own canonical pali_mahasangiti (not
    # whichever field schemas.py's audit() happened to match against, which
    # this script doesn't have -- generation_raw.jsonl carries claims, not
    # bundles) on the orthographically folded forms, same fold audit() uses,
    # so hyphenation/niggahita/case differences don't register as missing
    # text. Fabricated quotes (tier "fabrication") are excluded -- there is
    # no verse text they actually quote to measure coverage of.
    verses_path = ROOT / "data" / "processed" / "verses.jsonl"
    verse_pali = {
        v["verse"]: v.get("pali_mahasangiti")
        for v in (json.loads(l) for l in verses_path.read_text(encoding="utf-8").splitlines())
    }
    quote_coverages = []
    for r in raw:
        warn_by_idx = {
            w["claim_index"]: w["code"]
            for w in r["structural_warnings"]
            if w["code"] in ("PALI_QUOTE_NOT_IN_SOURCE",)
        }
        for i, c in enumerate(r["claims"]):
            if not c.get("pali_support") or i in warn_by_idx:
                continue
            source = verse_pali.get(c.get("verse_number"))
            if not source:
                continue
            coverage = len(_pali_orthographic(c["pali_support"])) / len(_pali_orthographic(source))
            quote_coverages.append(min(coverage, 1.0))

    if quote_coverages:
        mean_coverage = sum(quote_coverages) / len(quote_coverages)
        print(f"  quote coverage rate: {mean_coverage:.3f}  (n={len(quote_coverages)})   <- mean fraction of the cited verse actually quoted")
        if pali_report is not None:
            pali_report["quote_coverage_rate"] = round(mean_coverage, 4)
            pali_report["n_quote_coverage"] = len(quote_coverages)

    # ---------------------------------------------------------------- by type
    print("\n=== By query type ===")
    for qtype in sorted({c["type"] for c in claims}):
        sub = [c for c in claims if c["type"] == qtype]
        acc = sum(1 for c in sub if c["tag_correct"]) / len(sub)
        faith = sum(1 for c in sub if c["faithful"]) / len(sub)
        pm = {l: sum(1 for c in sub if c["predicted"] == l) for l in LAYERS}
        print(f"  {qtype:16s} n={len(sub):3d}  acc={acc:.3f}  faithful={faith:.3f}  predicted={pm}")

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
        "source_fidelity_rate": round(fidelity_rate, 4),
        "unfaithful_claims": n_unfaithful,
        "source_fidelity_scoped": {
            "n": len(sourced_claims),
            "rate": round(fid_point, 4),
            "ci_95": [round(fid_lo, 4), round(fid_hi, 4)],
            "note": "verse+commentary+alignment only; excludes synthesis; bootstrap CI resampled by question",
        },
        "pali_fidelity": pali_report,
        "source_disposition": {
            "has_data": has_disposition,
            "n_fully_covered": n_fully_covered,
            "n_questions": len(raw),
            "counts": disp_counts,
            "n_total": n_disp_total,
            "disposition_contradicts_claims": n_dispute,
            "not_relevant_on_gold": gold_dismissed,
            "not_relevant_on_noise": len(noise_dismissed),
        },
        "layer_count_distribution": layer_dist,
        "claims_per_answer": {
            "mean": round(sum(claims_per_answer) / len(claims_per_answer), 4) if claims_per_answer else None,
            "min": min(claims_per_answer) if claims_per_answer else None,
            "max": max(claims_per_answer) if claims_per_answer else None,
        },
    }
    out_path = ROOT / "data" / "eval" / "generation_metrics.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
