"""Research validation set (dhammapada_research_validation.md): "what can
this system do that a simpler one cannot?" Distinct from retrieval_eval.py
(Recall/nDCG/MRR against a gold set) and generation_metrics.py (layer-
attribution accuracy on the production system) -- this asks a different
question: how much does each *architectural component* actually contribute,
question by question, measured as a reviewer would measure it (read the
answer, judge correct/partial/wrong/confabulated), not as an automated metric.

--------------------------------------------------------------------------
DESIGN DECISIONS, STATED RATHER THAN LEFT IMPLICIT.

1. ALL FIVE CONDITIONS PRODUCE PLAIN TEXT, NOT A LayeredAnswer. The
   production system's schema-constrained generation (generate.py) exists to
   enforce layer attribution; that is a different question from "does this
   condition's context let the model answer correctly." Constraining every
   condition to the layered schema would confound content quality with
   schema compliance (a `no_retrieval` call has no group_id to cite at all,
   so it cannot productively use that schema regardless of answer quality).
   One shared plain-text call isolates the variable this exercise is
   actually about. Section H's Q34 (layer-tag consistency) is the one
   exception -- it specifically asks about the *real* system's layer tags,
   so it runs through the actual `Generator.generate()`, not this harness.

2. `verse_only` / `commentary_only` STRIP CONTENT, NOT RETRIEVAL. retrieval_
   eval.py's identically-named ablations restrict which CHUNKS the retriever
   can find (a retrieval-quality question). Here, the same top_k=3 groups
   are retrieved for every content condition (verse_only/commentary_only/
   full) and only the CONTENT SHOWN to the model differs -- isolating "what
   can the model do with this content" from "did retrieval find the right
   group," which retrieval_eval.py already measures separately. Documented
   here so the two same-named ablations in this codebase are not conflated.

3. `flat` BYPASSES assemble() ENTIRELY. Raw reranked chunks, undeduped, each
   chunk's own text dumped verbatim with no cross-referencing -- the
   "retrieve small, return small" condition assemble.py's own docstring
   defines itself against.

4. SECTION E (alignment table) GETS A COMPUTED GLOBAL SUMMARY UNDER `full`,
   NOT PER-QUESTION RETRIEVAL. "Which verse group is the largest?" and
   "are there verses explained by more than one story?" are corpus-wide
   aggregate facts -- no top-3 semantic retrieval surfaces them, because
   they are not about any one verse-group's content. `full` for these
   questions gets a compact group_id -> dhp_verses index computed directly
   from stories.jsonl; every other condition gets the standard per-question
   retrieval (and should be expected to fail or confabulate -- that failure
   is itself the finding Section E exists to produce).

5. NO AUTOMATED SCORING. correct/partial/wrong/confabulated requires reading
   each answer against the source, the same single-annotator judgment this
   project applies throughout (see docs/eval_rubric.md "Annotator status").
   This script only generates; judging happens in a separate pass, written
   directly into the results file (not a JUDGMENTS dict), since this is a
   one-time validation exercise, not a recurring metric.

Run: python -m dhammapada_rag.eval.research_validation
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402
from dhammapada_rag.generate.prompt import NARRATIVE_BUDGET_CHARS, _budget  # noqa: E402
from dhammapada_rag.generate.generate import Generator, GenerationError, warnings_to_dicts  # noqa: E402
from dhammapada_rag.generate.render import render_plain  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b-instruct"
NUM_CTX = 16384
SEED = 20260813

# `full` is the plain-text ablation (methodology note 1): same content as the
# real pipeline, no schema, isolates "does the content let the model answer
# right." `production_full` is the actual shipped system --
# Generator.generate() with schema-constrained citations, run through
# ordinary per-question retrieval (deliberately NOT given Section E's
# computed alignment summary -- that capability does not exist in the
# deployed pipeline, and Section E is where this column earns its keep: it
# shows what the shipped system can and cannot do today, honestly).
CONDITIONS = ("no_retrieval", "verse_only", "commentary_only", "flat", "full", "production_full")

# --------------------------------------------------------------------------
# The 35 questions, transcribed from dhammapada_research_validation.md.
# `section` is the letter (A-H); H is handled separately (main() skips it
# in the grid loop). `note` carries the doc's own "watch for" / analysis
# text, printed alongside the answer in the results file so a reader isn't
# forced to cross-reference the source spec.
# --------------------------------------------------------------------------
QUESTIONS = [
    {"id": "Q1", "section": "A", "text": "How many verses does story 17.8 cover, and which are they?"},
    # Rephrased from "What does Anandajoti's 2024 edition title the story for
    # Dhp 114..." -- that phrasing never retrieved group 8.13 (the actual
    # Kisa Gotami story) in top-3 for any condition, so every condition
    # declined and the row was uninformative. This phrasing retrieves 8.13
    # at rank 1 without naming Kisa Gotami (so it doesn't hand the answer to
    # no_retrieval) and keeps the original Anandajoti-vs-Burlingame intent.
    {"id": "Q2", "section": "A", "text": "What is the title of the commentarial story for Dhp 114 in Anandajoti's edition, and what did Burlingame call the same story?"},
    {"id": "Q3", "section": "A", "text": "What is the nidāna of the story attached to Dhp 221 -- where was it spoken?"},
    {"id": "Q4", "section": "A", "text": "Which stories in your corpus are set at Jetavana?"},
    {"id": "Q5", "section": "A", "text": "How many distinct commentarial stories cover the 423 verses?"},
    {"id": "Q6", "section": "B", "text": "To whom was Dhp 1 spoken, and what happened to him?"},
    {"id": "Q7", "section": "B", "text": "What did the Buddha ask Kisā Gotamī to bring, and why could she not bring it?"},
    {"id": "Q8", "section": "B", "text": "What did Rohinī's questioner learn at the end of the teaching?"},
    {"id": "Q9", "section": "B", "text": "Which story involves a bhikkhu felling a tree and injuring a devatā's child?"},
    {"id": "Q10", "section": "B", "text": "What occasioned the verse about the swerving chariot?"},
    {"id": "Q11", "section": "C", "text": "What is the Pali of Dhp 223?"},
    {"id": "Q12", "section": "C", "text": "Which verses in the Kodhavagga use a chariot image?"},
    {"id": "Q13", "section": "C", "text": "Does Dhp 166 contain the word nibbāna?"},
    {"id": "Q14", "section": "C", "text": "Quote the Pali pāda in Dhp 1 that contains manopubbaṅgamā."},
    {"id": "Q15", "section": "D", "text": "Give me Dhp 114 with its Pali, an English translation, and the story that explains it."},
    {"id": "Q16", "section": "D", "text": "I remember a story about a mustard seed -- what verse does it belong to and what does that verse say?"},
    {"id": "Q17", "section": "D", "text": "Show me everything your corpus holds for Dhp 3."},
    {"id": "Q18", "section": "E", "text": "Is Dhp 4 explained on its own or together with another verse?"},
    {"id": "Q19", "section": "E", "text": "Are Dhp 1 and Dhp 2 explained by the same story?"},
    {"id": "Q20", "section": "E", "text": "Which single story explains Dhp 320, 321, and 322?"},
    {"id": "Q21", "section": "E", "text": "Which verse group in the corpus is the largest?"},
    {"id": "Q22", "section": "E", "text": "Are there verses explained by more than one story?"},
    {"id": "Q23", "section": "E", "text": "Do your sources disagree about any verse grouping? Name one."},
    {"id": "Q24", "section": "F", "text": "Does the Dhammapada say the goal of life is nibbāna?"},
    {"id": "Q25", "section": "F", "text": "Is Dhp 1 about a blind monk?"},
    {"id": "Q26", "section": "F", "text": "Does the mustard seed appear in the verse or in the commentary?"},
    {"id": "Q27", "section": "F", "text": "Dhp 153-154 mentions a house-builder. Does the text say who that is, or is that an interpretation?"},
    {"id": "Q28", "section": "F", "text": "What does the Dhammapada say about anger -- and which of that is the verse and which the commentary?"},
    {"id": "Q29", "section": "G", "text": "Which verse mentions the internet?"},
    {"id": "Q30", "section": "G", "text": "What does Dhp 500 say?"},
    {"id": "Q31", "section": "G", "text": "Summarize the entire Dhammapada in one sentence."},
    {"id": "Q32", "section": "G", "text": "What is the Dhammapada's position on democracy?"},
]

SECTION_DEFEATS = {
    "A": "no_retrieval", "B": "verse_only", "C": "commentary_only", "D": "flat",
    "E": None, "F": None, "G": None,
}

NO_RETRIEVAL_SYSTEM = (
    "Answer the following question about the Dhammapada (a Buddhist text) using your own "
    "knowledge. Do not fabricate specific citations, verse numbers, story names, or details "
    "you are not genuinely confident about -- if you don't know or aren't sure, say so plainly "
    "rather than guessing."
)
CONTEXT_SYSTEM = (
    "Answer the question using ONLY the source material provided below. If the source "
    "material does not address the question, say so explicitly rather than guessing or "
    "filling the gap from outside knowledge."
)


def ask_ollama(question: str, context: str | None, seed: int = SEED) -> dict:
    system = NO_RETRIEVAL_SYSTEM if context is None else CONTEXT_SYSTEM
    user = question if context is None else f"SOURCE MATERIAL:\n\n{context}\n\nQUESTION: {question}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    t0 = time.time()
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL, "messages": messages, "stream": False,
            "options": {"temperature": 0.0, "seed": seed, "num_ctx": NUM_CTX},
        },
        timeout=300,
    )
    resp.raise_for_status()
    latency = time.time() - t0
    text = resp.json()["message"]["content"]
    return {"answer": text, "latency_s": round(latency, 2), "prompt_chars": len(system) + len(user)}


# --------------------------------------------------------------------------
# Context builders. Each takes the retrieved `bundles` (or None for
# no_retrieval / a raw chunk list for flat) and returns the context string
# shown to the model, or None (no context at all).
# --------------------------------------------------------------------------

def ctx_verse_only(bundles: list[dict]) -> str:
    lines = []
    for b in bundles:
        lines.append(f"=== Dhp {', '.join(str(n) for n in b['verse_numbers'])} ===")
        for v in b["verses"]:
            lines.append(f"Dhp {v['verse']} -- Pali (Mahasangiti): {v['pali_mahasangiti']}")
            if v.get("english_sujato"):
                lines.append(f"Dhp {v['verse']} -- English (Sujato): {v['english_sujato']}")
            if v.get("interlinear_english"):
                lines.append(f"Dhp {v['verse']} -- English (Anandajoti): {v['interlinear_english']}")
        lines.append("")
    return "\n".join(lines).strip()


def ctx_commentary_only(bundles: list[dict]) -> str:
    lines = []
    remaining = NARRATIVE_BUDGET_CHARS
    for b in bundles:
        for s in b["stories"]:
            lines.append(f"=== Story {s['group_id']} (covers Dhp {', '.join(str(n) for n in s['dhp_verses'])}) ===")
            lines.append(f"Title: {s['title_en']}")
            for label, key in (("Pali title", "title_pali"), ("CST4 title", "cst4_title"), ("Burlingame's title", "burlingame_title")):
                if s.get(key):
                    lines.append(f"{label}: {s[key]}")
            if s.get("synopsis"):
                lines.append(f"Synopsis: {s['synopsis']}")
            if s.get("nidana"):
                lines.append(f"Opening: {s['nidana']}")
            if s.get("vatthu"):
                body, remaining = _budget(s["vatthu"], remaining)
                lines.append(f"Narrative: {body}")
            if s.get("desanavasane"):
                lines.append(f"Close: {s['desanavasane']}")
            lines.append("")
    return "\n".join(lines).strip()


def ctx_full(bundles: list[dict]) -> str:
    # Union of verse and commentary content -- same substantive information
    # the production prompt shows, minus the layer-tag/citation scaffolding
    # (not needed since this harness asks for plain text, not a LayeredAnswer).
    lines = []
    remaining = NARRATIVE_BUDGET_CHARS
    for b in bundles:
        lines.append(f"=== Dhp {', '.join(str(n) for n in b['verse_numbers'])} ===")
        for v in b["verses"]:
            lines.append(f"Dhp {v['verse']} -- Pali (Mahasangiti): {v['pali_mahasangiti']}")
            if v.get("english_sujato"):
                lines.append(f"Dhp {v['verse']} -- English (Sujato): {v['english_sujato']}")
            if v.get("interlinear_english"):
                lines.append(f"Dhp {v['verse']} -- English (Anandajoti): {v['interlinear_english']}")
        for s in b["stories"]:
            lines.append(f"--- Story {s['group_id']} ---")
            lines.append(f"Title: {s['title_en']}")
            for label, key in (("Pali title", "title_pali"), ("CST4 title", "cst4_title"), ("Burlingame's title", "burlingame_title")):
                if s.get(key):
                    lines.append(f"{label}: {s[key]}")
            if s.get("synopsis"):
                lines.append(f"Synopsis: {s['synopsis']}")
            if s.get("nidana"):
                lines.append(f"Opening: {s['nidana']}")
            if s.get("vatthu"):
                body, remaining = _budget(s["vatthu"], remaining)
                lines.append(f"Narrative: {body}")
            if s.get("desanavasane"):
                lines.append(f"Close: {s['desanavasane']}")
        lines.append("")
    return "\n".join(lines).strip()


def ctx_flat(raw_chunks: list[dict]) -> str:
    lines = []
    for c in raw_chunks:
        lines.append(f"[{c['chunk_type']}] {c['text']}")
        lines.append("")
    return "\n".join(lines).strip()


def build_alignment_summary(stories_by_id: dict[str, dict]) -> str:
    """Global corpus-structure summary for Section E's `full` condition --
    see module docstring point 4. Computed directly from stories.jsonl, not
    retrieved, since these are aggregate facts no single retrieved group
    carries."""
    by_gid = {gid: sorted(s["dhp_verses"]) for gid, s in stories_by_id.items()}
    sizes = sorted(by_gid.items(), key=lambda kv: -len(kv[1]))
    verse_counts = Counter(v for verses in by_gid.values() for v in verses)
    multi = {v: c for v, c in verse_counts.items() if c > 1}
    lines = [
        f"Total stories in corpus: {len(by_gid)}",
        f"Largest verse group: group_id {sizes[0][0]}, covering Dhp {sizes[0][1]} ({len(sizes[0][1])} verses)",
        "Top 5 largest verse groups (group_id: verses):",
    ]
    for gid, verses in sizes[:5]:
        lines.append(f"  {gid}: Dhp {verses} ({len(verses)} verses)")
    if multi:
        lines.append(f"Verse numbers explained by more than one story: {sorted(multi)}")
        for v in sorted(multi):
            covering = [gid for gid, verses in by_gid.items() if v in verses]
            lines.append(f"  Dhp {v} is covered by group_ids: {covering}")
    else:
        lines.append("No verse number is explained by more than one story.")
    lines.append("Full group_id -> Dhp verses index:")
    for gid, verses in sorted(by_gid.items(), key=lambda kv: [int(p) for p in kv[0].split(".")]):
        lines.append(f"  {gid}: {verses}")
    return "\n".join(lines)


def production_full_row(q: dict, bundles: list[dict], generator: Generator, corpus_group_ids: set[str]) -> dict:
    """The real system's answer to `q`: Generator.generate() (schema-
    constrained citations, layer-tagged claims) through ordinary
    per-question retrieval -- no computed alignment summary, even for
    Section E, because that shortcut does not exist in the deployed
    pipeline (see CONDITIONS comment). Mirrors app.py's own
    `generator.generate(...) if bundles else None` guard and the "No
    retrieval results" message it shows when bundles is empty."""
    group_ids = [s["group_id"] for b in bundles for s in b["stories"]]
    base = {
        "question_id": q["id"], "section": q["section"], "condition": "production_full",
        "question": q["text"], "context": None, "retrieved_group_ids": group_ids,
    }
    if not bundles:
        return {**base, "answer": None, "note": "No retrieval results for this question (production UI shows this verbatim; no generation call is made).",
                "latency_s": None, "schema_status": None, "warnings": []}
    try:
        gen_result = generator.generate(q["text"], bundles, corpus_group_ids=corpus_group_ids)
    except GenerationError as e:
        return {**base, "answer": None, "note": f"GenerationError: {e}",
                "latency_s": None, "schema_status": None, "warnings": []}
    return {
        **base,
        "answer": render_plain(gen_result["answer"]),
        "latency_s": gen_result["latency_s"],
        "schema_status": gen_result["schema_status"],
        "warnings": warnings_to_dicts(gen_result["warnings"]),
    }


def main() -> None:
    print("Loading retrieval pipeline...", file=sys.stderr)
    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    alignment_summary = build_alignment_summary(stories_by_id)
    corpus_group_ids = set(stories_by_id)
    generator = Generator(seed=SEED)

    out_path = ROOT / "data" / "eval" / "research_validation_raw.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_total = len(QUESTIONS) * len(CONDITIONS)
    n_done = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for q in QUESTIONS:
            bundles = query(
                q["text"], index=index, reranker=reranker, top_k=3, root=ROOT,
                verses_by_number=verses_by_number, stories_by_id=stories_by_id,
            )
            raw_hits = index.search(q["text"], top_k=30)
            raw_chunks = reranker.rerank(q["text"], raw_hits)[:5]

            for cond in CONDITIONS:
                if cond == "production_full":
                    row = production_full_row(q, bundles, generator, corpus_group_ids)
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                    n_done += 1
                    print(f"  [{n_done}/{n_total}] {q['id']}/{cond}: {row.get('latency_s')}s", file=sys.stderr)
                    continue

                if cond == "no_retrieval":
                    context = None
                elif cond == "verse_only":
                    context = ctx_verse_only(bundles) if bundles else ""
                elif cond == "commentary_only":
                    context = ctx_commentary_only(bundles) if bundles else ""
                elif cond == "flat":
                    context = ctx_flat(raw_chunks)
                elif cond == "full":
                    if q["section"] == "E":
                        context = alignment_summary
                    else:
                        context = ctx_full(bundles) if bundles else ""
                else:
                    raise ValueError(cond)

                gen = ask_ollama(q["text"], context)
                row = {
                    "question_id": q["id"], "section": q["section"], "condition": cond,
                    "question": q["text"], "context": context,
                    "retrieved_group_ids": [s["group_id"] for b in bundles for s in b["stories"]] if cond != "no_retrieval" else None,
                    **gen,
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                n_done += 1
                print(f"  [{n_done}/{n_total}] {q['id']}/{cond}: {gen['latency_s']}s, {len(gen['answer'])} chars", file=sys.stderr)

    print(f"\nWrote {out_path}", file=sys.stderr)


def run_production_full_only() -> None:
    """Run only the production_full condition for all 32 questions,
    writing to a separate file so the already-judged 5-condition grid in
    research_validation_raw.jsonl (and its committed judgments in the
    results doc) is left untouched. Merge the two files by question_id when
    updating the results table."""
    print("Loading retrieval pipeline...", file=sys.stderr)
    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    corpus_group_ids = set(stories_by_id)
    generator = Generator(seed=SEED)

    out_path = ROOT / "data" / "eval" / "research_validation_production_full.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for i, q in enumerate(QUESTIONS, 1):
            bundles = query(
                q["text"], index=index, reranker=reranker, top_k=3, root=ROOT,
                verses_by_number=verses_by_number, stories_by_id=stories_by_id,
            )
            row = production_full_row(q, bundles, generator, corpus_group_ids)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"  [{i}/{len(QUESTIONS)}] {q['id']}: {row.get('latency_s')}s", file=sys.stderr)
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    if "--production-full-only" in sys.argv:
        run_production_full_only()
    else:
        main()
