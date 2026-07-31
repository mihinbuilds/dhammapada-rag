"""Generate answers for a stratified sample of the gold set, to be judged
against docs/eval_rubric.md's layer-attribution-accuracy and anachronistic-
conflation-rate criteria.

Sample size (5 questions/type = 20, not the full 114 retrievable questions):
a documented cost tradeoff, not a silent shortcut. Two costs compound that
don't apply to the retrieval metrics: an LLM call per question, and a human
judgment per generated claim (docs/eval_rubric.md "Annotator status"), which
does not scale the way an automated metric does. 20 questions x ~2-4 claims is
a reviewable batch for one annotator in one sitting; 114 would not be.

This script only generates and saves raw output; judging happens separately in
data/eval/generation_judgments.py so the judgments are auditable as their own
artifact, the same pattern as ingest/corrections.py.

--------------------------------------------------------------------------
FIXES over the previous revision:
1. warnings are serialized with warnings_to_dicts(). audit() now returns
   dataclasses; json.dumps() on them raises TypeError, so this script would
   have crashed on the first warning.
2. layer_counts is recorded per question. The single most important thing to
   know about this run is whether the model produced any commentary claims at
   all -- an all-'verse' answer passes every structural check while failing
   the project's premise. That has to be in the raw file, not inferred later.
3. prompt_tokens / num_ctx are recorded. Any generation metric collected
   before generate.py set num_ctx explicitly measured a truncated context
   where the commentary had been silently dropped; recording the budget makes
   the two regimes distinguishable in the artifact itself.
4. corpus_group_ids is passed so the audit can separate invented group_ids
   from real-but-not-retrieved ones.
5. Sampling is deterministic and its non-randomness is stated: items[::step]
   takes evenly spaced questions in file order, which is reproducible but is
   NOT a random sample. Report it as a systematic sample.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.generate.generate import Generator, warnings_to_dicts  # noqa: E402
from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

SEED = 20260731


def stratified_sample(gold: list[dict], per_type: int = 5) -> list[dict]:
    """Evenly spaced systematic sample within each query type.

    Deterministic and reproducible, but not random: describe it as a
    systematic sample in the write-up, not a random one.
    """
    by_type: dict[str, list[dict]] = {}
    for q in gold:
        if not q["gold_group_ids"]:  # skip non-chunk-retrievable colophon facts
            continue
        by_type.setdefault(q["type"], []).append(q)

    sample = []
    for qtype, items in sorted(by_type.items()):
        step = max(1, len(items) // per_type)
        sample.extend(items[::step][:per_type])
    return sample


def main() -> None:
    gold = [json.loads(l) for l in (ROOT / "data" / "eval" / "gold_set.jsonl").read_text(encoding="utf-8").splitlines()]
    sample = stratified_sample(gold, per_type=5)
    print(
        f"Sampled {len(sample)} questions (systematic, not random): "
        + ", ".join(f"{t}={sum(1 for q in sample if q['type'] == t)}" for t in sorted({q["type"] for q in sample}))
    )

    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    corpus_group_ids = set(stories_by_id)
    generator = Generator(seed=SEED)

    out_path = ROOT / "data" / "eval" / "generation_raw.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_no_commentary = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for i, q in enumerate(sample):
            bundles = query(
                q["question"], index=index, reranker=reranker, top_k=3, root=ROOT,
                verses_by_number=verses_by_number, stories_by_id=stories_by_id,
            )
            gen = generator.generate(q["question"], bundles, corpus_group_ids=corpus_group_ids)
            claims = gen["answer"].claims
            layer_counts = {
                lyr: sum(1 for c in claims if c.layer == lyr)
                for lyr in ("verse", "commentary", "synthesis")
            }
            if layer_counts["commentary"] == 0:
                n_no_commentary += 1

            row = {
                "question_id": q["question_id"],
                "type": q["type"],
                "question": q["question"],
                "gold_group_ids": q["gold_group_ids"],
                "gold_verse_numbers": q["gold_verse_numbers"],
                "retrieved_group_ids": [s["group_id"] for b in bundles for s in b["stories"]],
                "claims": [c.model_dump() for c in claims],
                "layer_counts": layer_counts,
                "structural_warnings": warnings_to_dicts(gen["warnings"]),
                "model": gen["model"],
                "latency_s": gen["latency_s"],
                "prompt_tokens": gen["prompt_tokens"],
                "num_ctx": gen["num_ctx"],
                # gold source text inlined so judging needs no corpus lookup
                "gold_context": [
                    {
                        "group_ids": [s["group_id"] for s in b["stories"]],
                        "verse_numbers": b["verse_numbers"],
                        "verse_text": [
                            {"verse": v["verse"], "pali": v["pali_mahasangiti"], "english": v["english_sujato"]}
                            for v in b["verses"]
                        ],
                        "commentary_text": [
                            {
                                "group_id": s["group_id"],
                                "title_en": s["title_en"],
                                "synopsis": s["synopsis"],
                                "nidana": s["nidana"],
                                "vatthu": s["vatthu"],
                                "desanavasane": s["desanavasane"],
                            }
                            for s in b["stories"]
                        ],
                    }
                    for b in bundles
                ],
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()

            n_err = sum(1 for w in gen["warnings"] if w.severity == "error")
            print(
                f"  [{i+1}/{len(sample)}] {q['question_id']} ({q['type']}): "
                f"{len(claims)} claims {layer_counts}, {n_err} provenance errors, "
                f"~{gen['prompt_tokens']}/{gen['num_ctx']} tok"
            )

    print(f"\nWrote {out_path}")
    if n_no_commentary:
        print(
            f"!! {n_no_commentary}/{len(sample)} answers contain ZERO commentary claims.\n"
            f"   Verify the retrieved groups carry vatthu text and that prompt_tokens is\n"
            f"   well under num_ctx. Structural metrics on such a run are not meaningful."
        )


if __name__ == "__main__":
    main()
