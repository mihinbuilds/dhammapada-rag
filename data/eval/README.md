# data/eval/

Evaluation inputs and outputs. The method is in `docs/eval_rubric.md` and the
results are written up in `docs/evaluation.md`.

## Why there are `.py` files in a data folder

Three files here are hand-made annotation data written as Python, not
pipeline code, so they live with the data they define:

| File | What it holds |
|---|---|
| `build_gold_set.py` | The hand-written v1 questions (120) and the resolver that writes `gold_set.jsonl`. Its docstring records the bug 14 diagnosis. |
| `build_gold_set_v2.py` | The hand-written v2 questions (72, harder, multi-gold) and the builder that writes `gold_set_v2.jsonl`. |
| `generation_judgments.py` | The per-claim human judgments of `generation_raw.jsonl`. `src/dhammapada_rag/eval/aggregate_generation.py` imports `JUDGMENTS` from it. |

The code that runs and scores the evaluation is in
`src/dhammapada_rag/eval/`.

## Files

| File | Written by | Contents |
|---|---|---|
| `gold_set.jsonl` | `build_gold_set.py` | v1 gold set, 120 questions. Saturated at baseline. |
| `gold_set_v2.jsonl` | `build_gold_set_v2.py` | v2 gold set, 72 questions |
| `retrieval_results.jsonl`, `retrieval_metrics.json` | `eval.retrieval_eval`, `eval.aggregate_retrieval` | v1 retrieval runs and per-type metrics |
| `retrieval_results_v2.jsonl`, `retrieval_metrics_v2.json` | the same, on the v2 gold set | v2 retrieval runs and metrics |
| `generation_raw.jsonl`, `generation_metrics.json` | `eval.generation_metrics`, `eval.aggregate_generation` | generated answers and scored layer tags |
| `model_sweep_results_retries{0,1}.jsonl` | `eval.model_sweep` | model-size sweep, with and without a retry |
| `rrf_k_sweep_results.json` | `eval.rrf_k_sweep` | fusion-constant sweep |
| `arm_diagnosis_results.json` | `eval.arm_diagnosis` | whether one retrieval arm dominates RRF fusion |
| `tag_stability_results.json` | `eval.tag_stability` | layer-tag stability across paraphrases of the same question |
| `research_validation_*.json(l)` | `eval.research_validation`, `eval.research_validation_consistency` | the 32-question research validation grid (see `dhammapada_research_validation_results.md`) |
| `annotation_v2_blank.csv`, `annotation_v2_sample30.csv` | `eval.annotation_sheet` | blind second-annotator sheets (full, and the 30-question sample; see `docs/annotator_brief.md`) |
| `archive_pre_fix/`, `archive_round1_post_fix/` | — | results from before the bug-fix phases and after round 1, kept for the comparisons in `docs/evaluation.md` |

Several result files predate the September index rebuild; `README.md`
("Status") and `docs/evaluation.md` say which.
