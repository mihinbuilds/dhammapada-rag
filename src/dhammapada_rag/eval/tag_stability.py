"""Round 4, Task G: measure layer-tag stability.

The same underlying fact, asked about in different words, should get the
same layer tag every time -- "the verse says X" shouldn't flip to "the
commentary says X" just because the question was phrased differently. No
other metric in this project (or, per the brief, any published layer-
tagged RAG system) measures this, because measuring it requires an
architecture that tags layers at all.

Method: for each of 15 verses drawn from the gold set, ask 3 differently-
worded questions that should each surface that verse-group (VERSE_QUESTIONS
below; phrasing 1 is the verse's actual gold_set.jsonl question, phrasings
2-3 are hand-written alternate angles on the same verse content, following
the same "grounded in the verse's own content" principle
docs/eval_rubric.md's construction method uses for gold questions). Collect
all claims from the resulting 3 answers per verse. Two claims count as "the
same claim" if either one's content words are >=80% contained in the
other's (generate/schemas.py's own `_containment`, reused here rather than
reimplemented, since it is exactly the "is this claim mostly the same
wording as that one" measure Task F already validated) -- checked in both
directions and unioned, since a paraphrase across two differently-phrased
questions is not reliably shorter in one particular direction. Grouping is
scoped per verse: claims from different verses are never compared, since an
accidental match on generic phrasing ("the Buddha taught this at Jetavana")
across unrelated stories would be a false positive, not tag instability.

    tag_stability = (groups where every member shares one layer tag)
                    / (groups with >1 member)

Groups with exactly one member (the claim appeared in only one of the 3
phrasings) are excluded from the denominator -- there is nothing to be
stable or unstable about a fact only one question surfaced.

Reported overall and per layer (a group's layer bucket is its majority
tag), since instability concentrated in one layer is a more specific,
more actionable finding than a single blended rate.

This is a small, self-contained script, run once and its output written to
data/eval/tag_stability_results.json; docs/evaluation.md gets a subsection
built from that file, not from re-deriving these numbers by hand.

Run: python -m dhammapada_rag.eval.tag_stability
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.generate.generate import Generator, warnings_to_dicts  # noqa: E402
from dhammapada_rag.generate.schemas import _containment  # noqa: E402
from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

SEED = 20260801
CONTAINMENT_THRESHOLD = 0.8
# Round 7, Task T: "alignment" is a fourth layer -- see generate/schemas.py.
LAYERS = ("verse", "commentary", "alignment", "synthesis")

# 15 verses from data/eval/gold_set.jsonl (one per distinct verse, taken in
# file order -- all happen to be 'doctrinal', the type gold_set.jsonl lists
# first; not adjusted for type balance, since this metric is about tag
# stability per verse, not query-type coverage). Phrasing 1 is that verse's
# actual gold question (guaranteed to surface the verse group, by the same
# construction-from-known-answer method eval_rubric.md describes). Phrasings
# 2 and 3 are hand-written from the verse's own content (data/processed/
# verses.jsonl english_sujato), asking about the same teaching from a
# different angle -- the same principle Task F's two anger questions used.
VERSE_QUESTIONS: dict[int, list[str]] = {
    11: [
        "What does the Dhammapada say happens to those who mistake the inessential for the essential, and the essential for inessential?",
        "What does the Dhammapada say about people who can't tell what really matters from what doesn't?",
        "Why do wrong thoughts arise, according to the Dhammapada's teaching on essence and inessence?",
    ],
    23: [
        "According to the Dhammapada, what do those who meditate regularly and vigorously attain?",
        "What does the Dhammapada say those who meditate diligently and consistently will realize?",
        "According to the Dhammapada, what is the reward of staunch, regular meditation practice?",
    ],
    39: [
        "What does the Dhammapada say about a person whose mind does not fester and who has given up notions of right and wrong?",
        "What does the Dhammapada say about someone whose heart is undamaged and free from fear?",
        "According to the Dhammapada, what quality of mind makes a person fearless?",
    ],
    45: [
        "What comparison does the Dhammapada draw between a spiritual trainee and an expert selecting flowers?",
        "How does the Dhammapada compare a spiritual trainee to a flower-picker?",
        "What does the Dhammapada say a trainee does with the well-taught truth?",
    ],
    62: [
        "What does the Dhammapada say is wrong with a fool's thought 'sons are mine, wealth is mine'?",
        "Why does the Dhammapada call it foolish to think 'sons are mine, wealth is mine'?",
        "What does the Dhammapada say about attachment to family and possessions?",
    ],
    89: [
        "What does the Dhammapada say happens to those whose minds are rightly developed in the awakening factors and who let go of attachment?",
        "What does the Dhammapada say about those who let go of attachment and develop the awakening factors?",
        "According to the Dhammapada, what happens to those whose defilements have ended?",
    ],
    98: [
        "According to the Dhammapada, what makes a place delightful regardless of whether it is a village or wilderness?",
        "Why does the Dhammapada say a place becomes delightful?",
        "What does the Dhammapada say about village versus wilderness as a dwelling place?",
    ],
    103: [
        "According to the Dhammapada, who is the supreme conqueror?",
        "Who does the Dhammapada consider the greatest conqueror -- someone who wins battles, or someone else?",
        "What does the Dhammapada say about conquering oneself versus conquering others in war?",
    ],
    121: [
        "What warning does the Dhammapada give about thinking lightly of small evil deeds?",
        "What simile does the Dhammapada use for how a fool accumulates wickedness?",
        "Why does the Dhammapada warn against thinking a small evil deed doesn't matter?",
    ],
    130: [
        "What ethical principle does the Dhammapada draw from the observation that all beings tremble at violence and love life?",
        "What does the Dhammapada say about treating others as you would treat yourself?",
        "Why does the Dhammapada say one should not kill or incite others to kill?",
    ],
    154: [
        "What does the famous 'house-builder' verse in the Dhammapada say has been found and demolished?",
        "What does the famous house-builder verse in the Dhammapada mean?",
        "According to the Dhammapada, what happens to craving when the mind reaches the end of construction?",
    ],
    160: [
        "According to the Dhammapada, who is the lord of a person, and how is that lordship gained?",
        "What does the Dhammapada mean by being one's own lord?",
        "Why does the Dhammapada say a well-tamed self is a rare lord to gain?",
    ],
    167: [
        "What four things does the Dhammapada advise against resorting to or perpetuating?",
        "What four pieces of advice does the Dhammapada give about negligence and wrong views?",
        "According to the Dhammapada, what should one not resort to or perpetuate?",
    ],
    181: [
        "According to the Dhammapada, why are the Buddhas envied even by the gods?",
        "Why are the Buddhas envied even by the gods, according to the Dhammapada?",
        "What does the Dhammapada say about those who love the peace of renunciation?",
    ],
    203: [
        "What does the Dhammapada identify as the worst illness and the worst suffering?",
        "What does the Dhammapada identify as the worst illness a person can have?",
        "According to the Dhammapada, what is the ultimate happiness once suffering is understood?",
    ],
}


def _mutual_containment(a: str, b: str) -> float:
    """Max of both directions -- a paraphrase across two independently
    generated answers is not reliably shorter in one particular direction,
    unlike Task F's claim-vs-verse check where the verse is always the
    fixed reference text."""
    return max(_containment(a, b), _containment(b, a))


def group_claims(claims: list[dict]) -> list[list[dict]]:
    """Union-find over claims (each a dict with at least 'text', 'layer'),
    connecting any pair whose mutual containment clears the threshold."""
    n = len(claims)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if _mutual_containment(claims[i]["text"], claims[j]["text"]) >= CONTAINMENT_THRESHOLD:
                union(i, j)

    groups: dict[int, list[dict]] = {}
    for i, c in enumerate(claims):
        groups.setdefault(find(i), []).append(c)
    return list(groups.values())


def main() -> None:
    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    corpus_group_ids = set(stories_by_id)
    generator = Generator(seed=SEED)

    per_verse_records = []
    n_verses = len(VERSE_QUESTIONS)
    for vi, (verse_number, questions) in enumerate(sorted(VERSE_QUESTIONS.items())):
        claims_for_verse: list[dict] = []
        for qi, question in enumerate(questions):
            bundles = query(
                question, index=index, reranker=reranker, top_k=3, root=ROOT,
                verses_by_number=verses_by_number, stories_by_id=stories_by_id,
            )
            gen = generator.generate(question, bundles, corpus_group_ids=corpus_group_ids)
            for c in gen["answer"].claims:
                claims_for_verse.append({
                    "text": c.text,
                    "layer": c.layer,
                    "question_index": qi,
                    "question": question,
                    "verse_number": verse_number,
                })
            print(
                f"  [{vi+1}/{n_verses} verse {verse_number}, phrasing {qi+1}/3] "
                f"{len(gen['answer'].claims)} claims, "
                f"{sum(1 for w in gen['warnings'] if w.severity == 'error')} provenance errors"
            )
        groups = group_claims(claims_for_verse)
        per_verse_records.append({"verse_number": verse_number, "claims": claims_for_verse, "groups": groups})

    # ---------------------------------------------------------- aggregation
    all_groups = [g for rec in per_verse_records for g in rec["groups"]]
    multi = [g for g in all_groups if len(g) > 1]

    def is_stable(g: list[dict]) -> bool:
        return len({c["layer"] for c in g}) == 1

    def majority_layer(g: list[dict]) -> str:
        counts = {lyr: sum(1 for c in g if c["layer"] == lyr) for lyr in LAYERS}
        return max(counts, key=counts.get)

    overall_stability = sum(1 for g in multi if is_stable(g)) / len(multi) if multi else None

    per_layer = {}
    for lyr in LAYERS:
        bucket = [g for g in multi if majority_layer(g) == lyr]
        per_layer[lyr] = {
            "n_groups": len(bucket),
            "stability": (sum(1 for g in bucket if is_stable(g)) / len(bucket)) if bucket else None,
        }

    unstable_examples = [
        {
            "verse_number": g[0]["verse_number"],
            "layers": sorted({c["layer"] for c in g}),
            "claims": [{"text": c["text"], "layer": c["layer"], "question": c["question"]} for c in g],
        }
        for g in multi if not is_stable(g)
    ]

    print(f"\n=== Tag stability ===")
    print(f"n verses = {n_verses}, n questions = {n_verses * 3}, n claims = {sum(len(r['claims']) for r in per_verse_records)}")
    print(f"n groups = {len(all_groups)}, n multi-member groups = {len(multi)}")
    print(f"overall tag_stability = {overall_stability}")
    print("\nper layer (bucketed by group's majority tag):")
    for lyr in LAYERS:
        pl = per_layer[lyr]
        print(f"  {lyr:12s} n_groups={pl['n_groups']:3d}  stability={pl['stability']}")

    if unstable_examples:
        print(f"\n{len(unstable_examples)} unstable group(s):")
        for ex in unstable_examples:
            print(f"  Dhp {ex['verse_number']} -- layers seen: {ex['layers']}")
            for c in ex["claims"]:
                print(f"    [{c['layer']}] ({c['question'][:60]}...) {c['text'][:100]}")

    report = {
        "n_verses": n_verses,
        "n_questions": n_verses * 3,
        "n_claims": sum(len(r["claims"]) for r in per_verse_records),
        "n_groups": len(all_groups),
        "n_multi_member_groups": len(multi),
        "containment_threshold": CONTAINMENT_THRESHOLD,
        "overall_tag_stability": overall_stability,
        "per_layer": per_layer,
        "unstable_examples": unstable_examples,
    }
    out_path = ROOT / "data" / "eval" / "tag_stability_results.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
