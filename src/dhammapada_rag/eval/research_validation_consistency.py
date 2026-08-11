"""Section H of dhammapada_research_validation.md: consistency checks, a
different shape of experiment from the A-G grid (research_validation.py) --
repeated/varied calls to the SAME condition rather than one call per
condition. Kept as its own script because Q34 specifically needs the real
production system (Generator.generate(), LayeredAnswer, layer tags), not
this project's plain-text ablation harness -- see research_validation.py's
module docstring, point 1, for why the two are deliberately different code
paths rather than one script forcing both into the same shape.

Run: python -m dhammapada_rag.eval.research_validation_consistency
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.eval.research_validation import ask_ollama, ctx_full, SEED  # noqa: E402
from dhammapada_rag.generate.generate import Generator  # noqa: E402
from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

Q7_TEXT = "What did the Buddha ask Kisā Gotamī to bring, and why could she not bring it?"
Q6_TEXT = "To whom was Dhp 1 spoken, and what happened to him?"


def main() -> None:
    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    corpus_group_ids = set(stories_by_id)

    results: dict = {}

    # ---- Q33: same question, same seed, three times, condition=full ----
    bundles = query(Q7_TEXT, index=index, reranker=reranker, top_k=3, root=ROOT,
                     verses_by_number=verses_by_number, stories_by_id=stories_by_id)
    context = ctx_full(bundles)
    runs = [ask_ollama(Q7_TEXT, context, seed=SEED) for _ in range(3)]
    answers = [r["answer"] for r in runs]
    results["Q33"] = {
        "question": Q7_TEXT, "condition": "full", "seed": SEED,
        "answers": answers,
        "all_identical": len(set(answers)) == 1,
    }
    print(f"Q33: all_identical={results['Q33']['all_identical']}", file=sys.stderr)

    # ---- Q34: shared-claim layer-tag consistency, real production system ----
    generator = Generator(seed=SEED)
    q34_questions = ["who was Kisā Gotamī?", "tell me about the woman who lost her child"]
    q34_runs = []
    for q in q34_questions:
        b = query(q, index=index, reranker=reranker, top_k=3, root=ROOT,
                   verses_by_number=verses_by_number, stories_by_id=stories_by_id)
        gen = generator.generate(q, b, corpus_group_ids=corpus_group_ids)
        q34_runs.append({
            "question": q,
            "retrieved_group_ids": [s["group_id"] for bundle in b for s in bundle["stories"]],
            "claims": [c.model_dump() for c in gen["answer"].claims],
        })
    results["Q34"] = {"runs": q34_runs}
    print(f"Q34: {len(q34_runs[0]['claims'])} claims / {len(q34_runs[1]['claims'])} claims", file=sys.stderr)

    # ---- Q35: same question, top_k in (1, 3, 5), condition=full ----
    q35_runs = []
    for top_k in (1, 3, 5):
        b = query(Q6_TEXT, index=index, reranker=reranker, top_k=top_k, root=ROOT,
                   verses_by_number=verses_by_number, stories_by_id=stories_by_id)
        ctx = ctx_full(b)
        gen = ask_ollama(Q6_TEXT, ctx, seed=SEED)
        q35_runs.append({
            "top_k": top_k,
            "retrieved_group_ids": [s["group_id"] for bundle in b for s in bundle["stories"]],
            "answer": gen["answer"],
        })
        print(f"Q35: top_k={top_k} -> {len(gen['answer'])} chars", file=sys.stderr)
    results["Q35"] = {"question": Q6_TEXT, "condition": "full", "runs": q35_runs}

    out_path = ROOT / "data" / "eval" / "research_validation_consistency.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
