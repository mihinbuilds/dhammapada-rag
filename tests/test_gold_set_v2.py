"""Invariants of data/eval/gold_set_v2.jsonl and the multi-gold aggregation.

The builder (data/eval/build_gold_set_v2.py) enforces these when it runs;
these tests catch a hand-edited or stale jsonl that no longer matches them.
"""

import json
from pathlib import Path

from dhammapada_rag.eval.aggregate_retrieval import METRICS, aggregate, metrics_present

ROOT = Path(__file__).resolve().parents[1]
GOLD_V2 = ROOT / "data" / "eval" / "gold_set_v2.jsonl"
SUBTYPES = {"narrative_deep", "paraphrase", "pali_ascii", "disambiguation", "multi_gold", "situation_to_verse"}


def load_v2():
    return [json.loads(l) for l in GOLD_V2.read_text(encoding="utf-8").splitlines()]


def test_v2_has_twelve_questions_per_category_with_unique_ids():
    rows = load_v2()
    assert len(rows) == 72
    assert len({r["question_id"] for r in rows}) == 72
    for st in SUBTYPES:
        assert sum(r["subtype"] == st for r in rows) == 12, st


def test_v2_gold_groups_exist_in_corpus():
    stories = {
        json.loads(l)["group_id"]
        for l in (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()
    }
    for r in load_v2():
        assert r["gold_group_ids"], r["question_id"]
        assert set(r["gold_group_ids"]) <= stories, r["question_id"]
        assert set(r.get("distractor_group_ids", [])) <= stories, r["question_id"]
        assert not set(r["gold_group_ids"]) & set(r.get("distractor_group_ids", [])), r["question_id"]


def test_v2_overlap_caps_hold():
    caps = {"paraphrase": 0.25, "narrative_deep": 0.5, "situation_to_verse": 0.5}
    for r in load_v2():
        if r["subtype"] in caps:
            assert r["gold_overlap"] <= caps[r["subtype"]], r["question_id"]


def test_v2_only_multi_gold_has_several_gold_groups():
    for r in load_v2():
        if r["subtype"] == "multi_gold":
            assert len(r["gold_group_ids"]) >= 2, r["question_id"]
        else:
            assert len(r["gold_group_ids"]) == 1, r["question_id"]


def test_disambiguation_questions_have_confusable_distractors():
    for r in load_v2():
        if r["subtype"] == "disambiguation":
            assert r["distractor_group_ids"], r["question_id"]
            assert len(r["separating_words"]) <= 2, r["question_id"]


def _row(value: float, with_gold_recall: bool) -> dict:
    cond = {m: value for m in METRICS}
    if with_gold_recall:
        cond["gold_recall@10"] = value
    return {c: dict(cond) for c in ("baseline", "verse_only", "dense_only", "no_rerank", "flat")}


def test_gold_recall_reported_only_when_every_row_has_it():
    # v1 results files predate gold_recall@10; aggregating them must not
    # KeyError or report a mean over a partial column.
    assert "gold_recall@10" not in metrics_present([_row(1.0, False), _row(1.0, True)])
    assert "gold_recall@10" in metrics_present([_row(1.0, True), _row(0.5, True)])
    assert aggregate([_row(1.0, True), _row(0.5, True)])["baseline"]["gold_recall@10"] == 0.75
    assert "gold_recall@10" not in aggregate([_row(1.0, False)])["baseline"]


def test_cohen_kappa_known_values():
    from dhammapada_rag.eval.annotation_sheet import cohen_kappa

    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    # Textbook 2x2: a=20 both yes, b=5, c=10, d=15 both no -> po=0.7, pe=0.5, kappa=0.4
    a = [1] * 20 + [1] * 5 + [0] * 10 + [0] * 15
    b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert abs(cohen_kappa(a, b) - 0.4) < 1e-9


def test_candidate_pool_is_deduplicated_and_contains_gold():
    from dhammapada_rag.eval.annotation_sheet import candidate_pool

    q = {"question_id": "h999", "gold_group_ids": ["1.1"], "distractor_group_ids": ["1.2"]}
    row = {c: {"top10": [["1.1"], ["2.1", "2.2"], ["1.2"], ["3.1"]]} for c in ("baseline", "verse_only", "dense_only", "no_rerank")}
    pool = candidate_pool(q, row)
    assert sorted(pool) == ["1.1", "1.2", "2.1", "2.2"]  # top-3 bundles only; 3.1 is 4th
    assert pool == candidate_pool(q, row)  # deterministic shuffle
