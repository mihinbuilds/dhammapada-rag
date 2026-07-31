"""PATCH for data/eval/build_gold_set.py -- apply these edits, keep the six
question constant lists exactly as they are.

WHY. The `cross_recension` stratum scores 0.54 against ~0.86 elsewhere, and
that number has been read as a retrieval weakness. Reading the 30 questions
against index/chunks.py shows it is mostly a labelling problem plus one
concrete indexing bug:

  CROSS_RECENSION_COLOPHON (6)   PTS story-count comparisons. Genuinely about
                                 edition variance, but gold_group_ids=[] --
                                 excluded from retrieval scoring by design.
                                 Correctly handled already.

  CROSS_RECENSION_MULTIVERSE (14) "Which single story explains Dhp 320-322?"
                                 This is NOT recension comparison. It tests
                                 the verse-to-story ALIGNMENT TABLE -- which
                                 is the project's most valuable artifact, and
                                 deserves to be its own named query type
                                 rather than being buried inside a stratum it
                                 has nothing to do with. Nearly half the
                                 stratum is mislabelled.

  CROSS_RECENSION_CST4 (8)       Burmese-edition title variants. Genuinely
                                 cross-recension -- and the only sub-group
                                 that is. BUT: cst4_title was never emitted as
                                 a chunk by index/chunks.py, so these eight
                                 questions were unanswerable by retrieval by
                                 construction. The fixed chunks.py adds a
                                 story_titles chunk carrying title_en,
                                 title_pali, cst4_title, burlingame_title and
                                 compare. Re-run the retrieval eval after
                                 rebuilding the index before drawing any
                                 conclusion about this sub-group.

  CROSS_RECENSION_SPECIAL (2)    Dhp 416's two stories, and a verse-number
                                 typo in the source PDF. Corpus anomalies, not
                                 recension comparison.

WHAT TO CLAIM IN THE PAPER. With 8 genuine cross-recension questions and no
Udanavarga / Gandhari / Patna sources in the corpus, this stratum cannot
support a claim about cross-recension retrieval. Either say so plainly, or
ingest SuttaCentral's parallels data and build the stratum properly. What you
CAN claim -- alignment-table lookup as a distinct, well-supported query type
with 14 questions -- is a real contribution and is currently invisible because
it is filed under the wrong name.

--------------------------------------------------------------------------
EDIT 1. Add a `subtype` to every resolver. Replace the three resolver
functions and main() with the versions below; the constant lists are unchanged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def resolve_doctrinal_philological(entries, qtype, verses_by_number, stories_by_id):
    out = []
    for verse_number, question, note in entries:
        v = verses_by_number[verse_number]
        group_ids = v["story_group_ids"]
        assert len(group_ids) == 1, (
            f"Dhp {verse_number} has {len(group_ids)} stories, expected 1 for an "
            f"unambiguous gold label: {group_ids}"
        )
        out.append({
            "type": qtype,
            "subtype": qtype,
            "question": question,
            "gold_group_ids": group_ids,
            "gold_verse_numbers": [verse_number],
            "notes": note,
        })
    return out


def resolve_narrative(entries, stories_by_id):
    out = []
    for group_id, question, note in entries:
        s = stories_by_id[group_id]
        out.append({
            "type": "narrative",
            "subtype": "narrative",
            "question": question,
            "gold_group_ids": [group_id],
            "gold_verse_numbers": s["dhp_verses"],
            "notes": note,
        })
    return out


def resolve_by_group(entries, stories_by_id, qtype: str, subtype: str):
    """Shared resolver for every group_id-keyed list.

    Replaces resolve_cross_recension_multiverse_cst4(), which applied one
    undifferentiated label to three substantively different question kinds.
    """
    out = []
    for group_id, question, note in entries:
        s = stories_by_id[group_id]
        out.append({
            "type": qtype,
            "subtype": subtype,
            "question": question,
            "gold_group_ids": [group_id],
            "gold_verse_numbers": s["dhp_verses"],
            "notes": note,
        })
    return out


def resolve_colophon(entries):
    """Colophon facts live in the text's back matter, which is not chunked.

    Kept in the gold set as documented, answerable-from-source knowledge
    questions for the generation pass, and excluded from retrieval scoring via
    an empty gold_group_ids -- not silently dropped.
    """
    return [{
        "type": "cross_recension",
        "subtype": "colophon_not_indexed",
        "question": question,
        "gold_group_ids": [],
        "gold_verse_numbers": [],
        "notes": f"[colophon fact, not chunk-indexed] {subject}: {note}",
    } for subject, question, note in entries]


def main():
    # Unchanged: load_corpus() and the six question constants above.
    from build_gold_set import (  # type: ignore  # noqa
        CROSS_RECENSION_COLOPHON, CROSS_RECENSION_CST4, CROSS_RECENSION_MULTIVERSE,
        CROSS_RECENSION_SPECIAL, DOCTRINAL, NARRATIVE, PHILOLOGICAL, load_corpus,
    )

    verses_by_number, stories_by_id = load_corpus()

    doctrinal = resolve_doctrinal_philological(DOCTRINAL, "doctrinal", verses_by_number, stories_by_id)
    philological = resolve_doctrinal_philological(PHILOLOGICAL, "philological", verses_by_number, stories_by_id)
    narrative = resolve_narrative(NARRATIVE, stories_by_id)

    # EDIT 2: alignment questions become their own TYPE. They test the
    # verse-to-story grouping table, not edition variance, and they are the
    # stratum most directly probing the project's headline artifact.
    alignment = resolve_by_group(CROSS_RECENSION_MULTIVERSE, stories_by_id, "alignment", "verse_grouping")

    # EDIT 3: cross_recension keeps only questions actually about edition
    # variance. CST4 title variants are the only retrievable ones, and only
    # after index/chunks.py emits story_titles.
    cross_recension = (
        resolve_colophon(CROSS_RECENSION_COLOPHON)
        + resolve_by_group(CROSS_RECENSION_CST4, stories_by_id, "cross_recension", "cst4_title_variant")
        + resolve_by_group(CROSS_RECENSION_SPECIAL, stories_by_id, "corpus_anomaly", "corpus_anomaly")
    )

    all_questions = doctrinal + philological + narrative + alignment + cross_recension
    assert len(all_questions) == 120, len(all_questions)

    for i, q in enumerate(all_questions):
        q["question_id"] = f"q{i+1:03d}"

    out_path = ROOT / "data" / "eval" / "gold_set.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for q in all_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Wrote {out_path}: {len(all_questions)} questions")
    by_type: dict[str, int] = {}
    by_sub: dict[str, int] = {}
    for q in all_questions:
        by_type[q["type"]] = by_type.get(q["type"], 0) + 1
        by_sub[q["subtype"]] = by_sub.get(q["subtype"], 0) + 1
    print("  by type:    " + json.dumps(by_type))
    print("  by subtype: " + json.dumps(by_sub))

    n_retrievable = sum(1 for q in all_questions if q["gold_group_ids"])
    n_xrec = sum(1 for q in all_questions if q["type"] == "cross_recension" and q["gold_group_ids"])
    print(f"  chunk-retrievable: {n_retrievable}/{len(all_questions)}")
    print(
        f"\n  NOTE: only {n_xrec} retrievable cross_recension questions remain, all of them\n"
        f"  CST4 title variants. This stratum cannot support a general claim about\n"
        f"  cross-recension retrieval; the corpus holds no Udanavarga, Gandhari, or\n"
        f"  Patna Dharmapada. Say so, or ingest SuttaCentral's parallels data."
    )


if __name__ == "__main__":
    main()
