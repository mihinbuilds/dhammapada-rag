"""Round 5, Task M: diagnose whether RRF fusion is dominated by one arm.

The observation this exists to explain: "What is the purpose of life
according to the Dhammapada?" retrieved Dhp 423 (the Brahmin Devahita
story -- the Buddha's humoral disorder, a request for hot water) ahead of
Dhp 166 (sadattha, "be intent on your own highest good"), the verse that
actually answers the question. Dhp 423 contains "knows their former
**lives**" and "**birth's** destruction" -- surface-token overlap with
"life", not conceptual relevance. This is the second clean instance of the
pattern (the first: an early run where every retrieved verse contained the
literal word "live" or "life").

This script does NOT change the fusion. It retrieves top-10 four ways --
dense-only, sparse-only, ColBERT-only, RRF-fused -- for a fixed set of
conceptual queries, via index/search.py's search_arms() (added for this
task; `rrf_fuse()` itself is untouched), and reports the rank at which a
chunk covering the query's gold verse first appears under each arm. If
sparse-only reproduces the fused result while dense-only ranks the gold
verse higher, the lexical arm is dominating fusion on conceptual queries --
the fix is a weighted RRF or query-type routing (keep sparse primary for
Pali-term/verse-number lookup, demote it for conceptual queries), decided
AFTER this diagnosis, not before.

Gold verses below are single-verse anchors chosen by reading
data/processed/verses.jsonl for the named concept (not full gold_set.jsonl
verse-groups): this script asks "does *some* chunk about the right verse
appear," not "is this the one correct IR answer" -- a looser bar, adequate
for a diagnostic about which arm surfaces relevant content, not a
replacement for retrieval_eval.py's gold-set metrics.

Run: python src/dhammapada_rag/eval/arm_diagnosis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

ARMS = ("dense", "sparse", "colbert", "fused")
TOP_K = 10

# (query, gold verse number, short label for the concept it's testing)
#
# Round 7, Task X: "what does the Dhammapada say about life?" retrieved Dhp
# 135 (a cowherd-and-cattle simile that merely contains the token "life")
# ahead of the Dhp 110-115 series -- six consecutive verses each structured
# "better to live a single day X... than a hundred years Y," directly and
# repeatedly about how life should be lived. This is the third clean
# instance of the same pattern this diagnosis exists to name (surface-token
# matching beating conceptual relevance), after "purpose of life" -> Dhp 423
# (Task M) and an early run where every retrieved verse merely contained
# "live"/"life". Dhp 110, the first verse of the six-verse series, is the
# gold anchor -- any of the six would do equally well as evidence the
# *series*, not one verse, is what a conceptually relevant retrieval should
# surface.
#
# Round 8, Task AB, checked before building any argument on this query's
# result: is Dhp 110 a DEFENSIBLE single gold verse for "what does the
# Dhammapada say about life?", or is the question genuinely multi-answer?
# Checked directly against verses.jsonl -- Dhp 135 ("old age and death drive
# life from living beings," mortality/impermanence) and Dhp 182 ("hard to
# gain a human birth... the life of mortals is hard," the rarity of human
# life) are BOTH independently defensible answers to this same question,
# addressing different facets of "life" than the 110-115 series (how it
# should be lived). This query is genuinely thematic, not single-answer --
# the diagnosis below (no arm finds Dhp 110, fusion finds it least of all)
# is still real evidence about arm coverage, but should NOT be read as "the
# system failed to find the right answer": Dhp 135, which several arms DO
# find, is arguably a right answer too. Restated here because this query is
# the clearest instance of a caveat this module's docstring already states
# in general -- not a reason to drop the probe.
QUERIES: list[tuple[str, int, str]] = [
    ("What is the purpose of life according to the Dhammapada?", 166, "purpose/sadattha"),
    ("What does the Dhammapada say about life?", 110, "life/110-115 series"),
    ("How to control anger?", 222, "anger"),
    ("What is craving, according to the Dhammapada?", 216, "craving"),
    ("What is heedfulness?", 21, "heedfulness"),
    ("What does the Dhammapada say about wisdom?", 40, "wisdom"),
    ("What does the Dhammapada say about suffering?", 1, "suffering"),
    ("What does the Dhammapada say about meditation?", 110, "meditation"),
    ("What does the Dhammapada say about the mind?", 96, "mind"),
    ("What does the Dhammapada say about restraint?", 361, "restraint"),
    ("What is the ultimate goal of the spiritual path?", 386, "goal/nibbana"),
]


def gold_rank(rows: list[dict], gold_verse: int) -> int | None:
    for rank, row in enumerate(rows, start=1):
        if gold_verse in row["dhp_verses"]:
            return rank
    return None


def main() -> None:
    index = ChunkIndex(ROOT / "data" / "index")

    per_query = []
    print(f"{'query':45s} {'gold':>5s}  " + "  ".join(f"{a:>8s}" for a in ARMS))
    for query, gold_verse, label in QUERIES:
        arms = index.search_arms(query, top_k=TOP_K)
        ranks = {a: gold_rank(arms[a], gold_verse) for a in ARMS}
        per_query.append({"query": query, "gold_verse": gold_verse, "label": label, "ranks": ranks, "arms": arms})

        rank_str = "  ".join(f"{(ranks[a] if ranks[a] is not None else '>' + str(TOP_K)):>8}" for a in ARMS)
        print(f"{query[:45]:45s} {gold_verse:>5d}  {rank_str}")

    print(f"\n(rank of first chunk covering Dhp {{gold}} in each arm's top-{TOP_K}; '>' + N means not found in top-{TOP_K})")

    print("\n=== Full top-10 per arm, per query ===")
    for rec in per_query:
        print(f"\n--- {rec['query']}  (gold Dhp {rec['gold_verse']}, concept: {rec['label']}) ---")
        for arm in ARMS:
            rows = rec["arms"][arm]
            listing = ", ".join(f"Dhp{r['dhp_verses']}/{r['chunk_type']}" for r in rows)
            print(f"  {arm:8s}: {listing}")

    # ---------------------------------------------------------- diagnosis
    n = len(per_query)
    found_in_top_k = {a: sum(1 for rec in per_query if rec["ranks"][a] is not None) for a in ARMS}
    mean_rank = {
        a: (sum(rec["ranks"][a] for rec in per_query if rec["ranks"][a] is not None) / found_in_top_k[a])
        if found_in_top_k[a] else None
        for a in ARMS
    }
    # "sparse dominates fusion" signal: fused's ranking of the gold verse
    # tracks sparse's more closely than dense's, on queries where they
    # disagree (not just "sparse and dense are usually right together").
    sparse_matches_fused = sum(1 for rec in per_query if rec["ranks"]["sparse"] == rec["ranks"]["fused"])
    dense_matches_fused = sum(1 for rec in per_query if rec["ranks"]["dense"] == rec["ranks"]["fused"])

    print("\n=== Summary ===")
    print(f"n queries = {n}")
    for a in ARMS:
        mr = f"{mean_rank[a]:.1f}" if mean_rank[a] is not None else "n/a"
        print(f"  {a:8s}: gold found in top-{TOP_K} for {found_in_top_k[a]}/{n} queries, mean rank {mr}")
    print(f"\nfused rank == sparse rank on {sparse_matches_fused}/{n} queries")
    print(f"fused rank == dense rank on {dense_matches_fused}/{n} queries")
    if sparse_matches_fused > dense_matches_fused and found_in_top_k["dense"] > found_in_top_k["sparse"]:
        print(
            "  !! sparse tracks the fused result more often than dense does, while dense finds\n"
            "     the gold verse in more queries -- consistent with the lexical arm dominating\n"
            "     fusion on these conceptual queries. Consider a weighted RRF (lower the sparse\n"
            "     arm's weight) or query-type routing (sparse primary for Pali-term/verse-number\n"
            "     lookup, demoted for conceptual queries). Do not tune weights without also\n"
            "     re-running retrieval_eval.py's ablations -- sparse is likely still the right\n"
            "     tool for the query types it was added for."
        )

    report = {
        "top_k": TOP_K,
        "queries": [
            {"query": rec["query"], "gold_verse": rec["gold_verse"], "label": rec["label"], "ranks": rec["ranks"]}
            for rec in per_query
        ],
        "found_in_top_k": found_in_top_k,
        "mean_rank": mean_rank,
        "fused_matches_sparse": sparse_matches_fused,
        "fused_matches_dense": dense_matches_fused,
    }
    out_path = ROOT / "data" / "eval" / "arm_diagnosis_results.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
