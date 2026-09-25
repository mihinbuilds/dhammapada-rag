"""Construct data/eval/gold_set_v2.jsonl: a harder retrieval split, 72 questions
in six categories of 12, each aimed at a component the v1 set cannot see.

WHY A SECOND SET. docs/status_report.md §8 item 8 and the 2026-09-23 re-run:
on v1 (gold_set.jsonl, 114 retrievable questions) baseline Recall@10 is 0.98,
only 10 questions miss rank 1, and the ablations barely move -- dense_only
changes the rank of 4 questions, flat of 3. v1 was written by looking at the
answer, so each question restates its one gold verse's distinctive content
(mean content-word containment against its gold chunks 0.31-0.61 by type)
and any retriever finds it. v1 is kept unchanged so earlier numbers stay
comparable; v2 is reported alongside it, never merged into it.

THE SIX CATEGORIES, and the component each is meant to stress:

  narrative_deep      A detail from the middle of a long vatthu, absent from
                      the story's title, synopsis, keywords and cast. Only a
                      narrative window can answer it. Stresses narrative
                      windowing and reranking; verse_only should fail
                      (mechanically -- report it as such, as with v1).
  paraphrase          A doctrinal question in a user's own words, sharing as
                      few content words as possible with the gold verse
                      (containment cap 0.25, checked below). Stresses dense
                      vs. sparse: dense_only should hold up, sparse can't.
  pali_ascii          A Pali verse line or Pali story title typed without
                      diacritics. Stresses the lexical/multi-vector arms and
                      diacritic robustness; dense_only is expected to lose
                      ground here if anywhere.
  disambiguation      A recurring character plus a detail that picks out one
                      of several stories about them -- including near-
                      duplicate pairs (Sāriputta vs. Moggallāna asking for
                      requisites, 26.27/26.28; Sāriputta's uncle, nephew and
                      companion, 8.5-8.7). Stresses the reranker and bundle
                      assembly. Uggasena (24.6/26.14) was drafted here and
                      dropped: both groups carry the full narrative, pole
                      scene and "no fear" episode included, and differ only
                      in the closing verse, which chunks.py strips from the
                      narrative. No question can pick one without quoting
                      its verse, so the pair is scored as multi_gold only.
  multi_gold          A theme with 2-4 relevant stories. Scored with
                      gold_recall@10 (fraction of ALL gold groups in the top
                      10), not first-hit recall. Gold sets were checked
                      against the story text by pattern search, not taken
                      from the `keywords` field, which is applied unevenly
                      (e.g. "Anger" tags 4 stories). Gold is the set of
                      stories where the theme is central; a retriever that
                      also returns a story with a passing mention is not
                      penalized by gold_recall@10.
  situation_to_verse  A story's situation described in everyday words,
                      asking what the Buddha said. The answer is the verse,
                      but only the narrative connects the question to it.
                      verse_only is the informative cell here, unlike for
                      narrative_deep: the question is phrased as a teaching
                      question, so a drop is not purely mechanical.

CONSTRUCTION AND ITS LIMITS. Same method as v1 (construction from a known
answer; see docs/eval_rubric.md), same single-annotator caveat, annotator
Claude (Opus 5.5). Two things differ: every question's word overlap with its
gold chunks is computed and capped (see OVERLAP_CAP), so "harder" is a
measured property rather than a claim; and each narrative_deep /
disambiguation detail was pattern-searched across all 305 stories to confirm
it picks out its gold story (see notes). No second annotator yet: see
docs/eval_rubric.md "Annotator status".
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Max fraction of a question's content words found in any single chunk of its
# gold group(s), for the categories whose difficulty IS low lexical overlap.
# The other three are hard for a different reason and are checked (or only
# reported) differently: pali_ascii folds to an exact match by construction --
# the difficulty is the missing diacritics at the tokenizer, which this
# ASCII-folded measure can't see; disambiguation SHOULD overlap its gold
# heavily -- the difficulty is a distractor that overlaps just as much (see
# DISTRACTOR_RATIO); multi_gold questions are short theme queries.
OVERLAP_CAP = {"paraphrase": 0.25, "narrative_deep": 0.5, "situation_to_verse": 0.5}

# A disambiguation question is only hard if its named distractor stories
# share nearly all of its vocabulary with the gold story: at most
# MAX_SEPARATING_WORDS of the question's content words may occur in the gold
# group's text but in no distractor's. A ratio of overlaps was tried first and
# is the wrong test for short questions: "Sāriputta's nephew" vs "Sāriputta's
# uncle" differ by exactly one word -- the intended distinguishing detail --
# which is already 1/6 of the question.
MAX_SEPARATING_WORDS = 2

STOP = set(
    "the a an of and or to in on at for is are was were be by with what does do did dhammapada say says "
    "according which who whom how why that this these those it its as from about into than when where whose "
    "his her their one two not no has have had can could would should story stories verse verses tell told "
    "buddha i me my you your if there any some so get got just then them they he she him".split()
)

# (group_id, question, notes)
NARRATIVE_DEEP = [
    ("1.12", "In a past-life tale, a crow decides it can fish for itself instead of sharing a water-bird's catch, and gets tangled in the weeds. Which story contains it?",
     "Vīraka/Saviṭṭhaka jātaka inside the Devadatta story; names unique to 1.12"),
    ("3.4", "Which monk daydreamed about selling a robe to buy a goat, starting a family, and then losing the baby under a cart wheel?",
     "she-goat daydream; 'she-goat' also in 2.1 and 11.6, but not the robe-to-family sequence"),
    ("3.9", "A woman tells a visiting old friend that she is actually the young man who vanished years ago on the way to bathe. Which story is this?",
     "Soreyya recognition scene; synopsis mentions the change, not the reunion"),
    ("6.7", "In a past-life tale, a woman so attached to money comes back as a small animal living on top of the hoard. Which story?",
     "Birth Story about the Cats inside Kāṇā's mother's story; unique to 6.7"),
    ("10.4", "A ruler brings soldiers to a monk's room after dark, hunting for a female companion people had complained about, and finds nobody. Which story?",
     "Kuṇḍadhāna; 'under the bed' also in 5.10, different context"),
    ("12.1", "In one past-life story a couple are the only survivors when their boat goes down, and they end up stranded, eating whatever the local birds lay. Which story?",
     "past-life story inside Prince Bodhi; synopsis mentions only the carpets and childlessness"),
    ("13.7", "Why did the Buddha keep gazing at a young woman standing at the edge of the crowd with her basket?",
     "weaver's daughter; she was to die that day; 'shuttle' also in 4.10 (Sakka as weaver)"),
    ("21.5", "A golden dish goes missing from the king's palace and turns up in a boy's wagon, with writing carved into it. What story is this from?",
     "Dārusākaṭikaputta; letters cut by the Amanussas; 'golden dish' in 5 stories, but not in a wagon"),
    ("24.7", "A woman betrays her husband in a fight by arming his attacker, and is later deserted by that same man. Which story tells this?",
     "Culla Dhanuggaha past life; 'hilt' also in 8.9"),
    ("2.9", "In which story does a parrot refuse to leave a dead fig tree out of loyalty, and Sakka comes in disguise to test it?",
     "parrot only in 2.9"),
    ("1.9", "Whose wife called after him, with her hair only half combed, asking him to come back soon, which later made him want to leave the monastery?",
     "Nanda; 'half-combed' only in 1.9"),
    ("26.5", "On one evening Ānanda watched the sun going down, the moon coming up, the king in his finery and a monk meditating. What did the Buddha say shone brightest?",
     "Kāḷudāyi scene; detail is in synopsis but not the ranking of lights"),
]

# (verse_number, question, notes)
PARAPHRASE = [
    (14, "Is there an image comparing a trained mind to a building that stays dry in a storm?", "well-thatched house, rain / lust"),
    (17, "Is punishment for cruelty limited to this lifetime?", "evildoer tormented here and hereafter"),
    (36, "My thoughts jump around and are hard to notice. Why should I bother keeping watch over them?", "hard to see, subtle; guard the mind"),
    (52, "Are fine-sounding words worth anything if the speaker actually lives by them?", "flower with colour and scent"),
    (76, "Is a critic worth keeping close?", "one who shows faults = treasure-revealer"),
    (72, "Can knowledge actually be dangerous in the hands of a foolish person?", "learning ruins the fool, splits his head"),
    (123, "What comparison does it use for steering clear of wrongdoing, involving a trader travelling with valuables and few guards?", "merchant on dangerous road"),
    (252, "Why am I blind to my own shortcomings yet quick to judge everybody else?", "others' faults like chaff, own like a cheat's losing throw"),
    (331, "What does it count as good fortune, such as having companions when you are in trouble?", "friends when need arises"),
    (372, "Can you have insight without meditating, or meditation without insight?", "no jhāna without wisdom, no wisdom without jhāna"),
    (407, "Is there an image of pride and hatred falling away like a tiny grain slipping off a sharp point?", "mustard seed off a needle-point"),
    (405, "What is said about someone who never harms any creature, weak or strong, and never gets others to do it?", "laid down the stick"),
]

# (group_id, question, notes)
PALI_ASCII = [
    ("6.5", "What does udakam hi nayanti nettika mean?", "Dhp 80, irrigators lead water"),
    ("15.6", "Explain arogya parama labha, santutthi paramam dhanam.", "Dhp 204"),
    ("20.2", "Where does sabbe sankhara anicca come from and what follows it?", "Dhp 277"),
    ("24.10", "sabbadanam dhammadanam jinati", "Dhp 354, bare Pali query"),
    ("10.1", "sabbe tasanti dandassa sabbe bhayanti maccuno meaning", "Dhp 129"),
    ("17.3", "What is the story behind akkodhena jine kodham?", "Dhp 223"),
    ("12.4", "atta hi attano natho ko hi natho paro siya", "Dhp 160"),
    ("8.3", "Who was yo sahassam sahassena sangame manuse jine spoken about?", "Dhp 103"),
    ("13.6", "Angulimalattheravatthu", "Pali title, ASCII"),
    ("1.2", "Mattakundalivatthu", "Pali title Maṭṭhakuṇḍalivatthu, ASCII"),
    ("10.9", "Santatimahamattavatthu summary", "Pali title, ASCII"),
    ("9.9", "Kokasunakhaluddakavatthu", "Pali title, ASCII"),
]

# (group_id, distractor_group_ids, question, notes)
DISAMBIGUATION = [
    ("8.6", ["8.5", "8.7"], "What did the Buddha teach Sāriputta's nephew about reaching the Brahma world?", "8.5 uncle / 8.6 nephew / 8.7 companion are near-identical"),
    ("8.7", ["8.5", "8.6"], "What did the Buddha teach Sāriputta's friend about the way to the Brahma world?", "the text says 'companion'; see 8.6"),
    ("8.5", ["8.6", "8.7"], "What did the Buddha teach Sāriputta's uncle about reaching the Brahma world?", "see 8.6"),
    ("26.27", ["26.28"], "After a rains retreat with five hundred monks, Sāriputta left asking that the requisites be sent on after him. What verse did the Buddha speak?", "26.27 Sāriputta / 26.28 Moggallāna are the same story"),
    ("26.28", ["26.27"], "After a rains retreat with five hundred monks, Moggallāna left asking that the requisites be sent on after him. What verse did the Buddha speak?", "see 26.27"),
    ("1.7", ["1.12", "12.6"], "Which Devadatta story is about him being given an expensive robe that people felt he didn't deserve?", "Devadatta titled stories 1.7, 1.12, 12.6"),
    ("16.3", ["4.8", "10.5", "11.1"], "What did the Buddha say to Visākhā when she was grieving for a grandchild?", "Visākhā stories 4.8, 10.5, 11.1, 16.3"),
    ("11.1", ["4.8", "10.5", "16.3"], "What happened when the women Visākhā brought to the monastery had been drinking?", "see 16.3"),
    ("4.10", ["2.5", "5.2", "7.2", "13.7"], "Which Mahā Kassapa story involves a weaver offering him food on his almsround?", "Mahā Kassapa stories 2.5, 4.10, 5.2, 7.2; 13.7 is the other weaver story"),
    ("7.2", ["2.5", "4.10", "5.2"], "Why did the Buddha send Mahā Kassapa back to Sāvatthī instead of taking him on tour?", "see 4.10"),
    ("17.4", ["10.7", "26.28"], "Which Moggallāna story has him asking devatās what deeds led to their rebirth?", "Moggallāna stories 10.7, 17.4, 26.28"),
    ("9.4", ["13.11"], "Which Anāthapiṇḍika story involves a spirit living over his gateway who wanted him to stop supporting the monks?", "Anāthapiṇḍika stories 9.4, 13.11"),
]

# (gold_group_ids, question, notes)
MULTI_GOLD = [
    (["4.8", "21.8"], "Which stories tell of a young wife who refuses to pay respect to naked ascetics in her husband's family home?",
     "Visākhā and Cullā Subhaddā; parallel plots"),
    (["9.11", "12.1"], "Which stories involve people in trouble at sea?", "woman cast overboard; shipwreck; 2.3 mentions a ship only as trade"),
    (["24.6", "26.14", "26.35", "26.36"], "Which stories involve acrobats?", "Uggasena x2, the elder formerly an acrobat x2"),
    (["4.11", "8.11", "25.11"], "Which stories are about monks who decided to take their own lives?", "Godhika, Sappadāsa, Vakkali"),
    (["26.27", "26.28"], "Which stories tell of a chief disciple leaving a rains retreat and asking for the requisites to be sent on?", "Sāriputta and Moggallāna versions"),
    (["8.5", "8.6", "8.7"], "Which stories have Sāriputta asking the Buddha to show his relatives or friends the way to the Brahma world?", "uncle, nephew, friend"),
    (["1.7", "1.12", "9.8", "9.9"], "Which stories feature hunters?", "elephant-hunter (1.7), platform hunter (1.12), Kukkuṭamitta, Koka"),
    (["6.8", "18.10", "21.1"], "Which stories take place during a famine?", "pattern search: 18.10 (11 mentions), 6.8 (3), 21.1 (3)"),
    (["4.8", "10.5", "11.1", "16.3"], "What stories are there about the lay supporter Visākhā?", "titled Visākhā stories; others mention her in passing"),
    (["2.5", "4.10", "5.2", "7.2"], "Which stories centre on Mahā Kassapa?", "titled Mahā Kassapa stories"),
    (["14.3", "14.6"], "Which stories feature a nāga king?", "Erakapatta; the nāga king Moggallāna subdues in Aggidatta's story"),
    (["5.12", "5.13", "10.6", "20.6"], "Which stories describe petas, ghosts suffering for what they did in past lives?", "the four peta-titled stories"),
]

# (group_id, question, notes)
SITUATION_TO_VERSE = [
    ("1.13", "A dying girl called her own father 'little brother'. What did the Buddha say about her?", "Sumanā, Anāthapiṇḍika's daughter; Dhp 18"),
    ("4.6", "A woman was upset because a wandering ascetic she fed kept insulting her. What was the Buddha's advice?", "Pāṭhika; Dhp 50"),
    ("11.6", "What did the Buddha tell a king who was mourning his dead queen?", "Mallikā; Dhp 151"),
    ("11.7", "A monk kept chanting sad songs at weddings and happy ones at funerals. What verse did the Buddha give?", "Lāḷudāyi; Dhp 152"),
    ("12.10", "When the Buddha announced he would die soon, one monk went off alone to meditate instead of crowding round him. How did the Buddha react?", "Attadattha; Dhp 166"),
    ("18.11", "A monk constantly nitpicked everyone else's behaviour. What did the Buddha say about people like that?", "Ujjhānasaññī; Dhp 253"),
    ("23.2", "A monk who used to train animals gave a man tips on handling a difficult elephant. Why was he told off?", "Dhp 323"),
    ("23.5", "A young novice's mother talked him out of quitting monastic life. What teaching was he given?", "Sānu; Dhp 326"),
    ("26.7", "Someone punched a senior monk in the back to see if he would get angry. What was taught about that?", "Sāriputta struck; Dhp 389-390"),
    ("26.25", "A monk spoke rudely to everyone out of habit rather than anger. How did the Buddha explain it?", "Pilindavaccha; Dhp 408"),
    ("26.26", "A monk picked up a cloth he thought had been thrown away and handed it back when the owner turned up. Was that stealing?", "Dhp 409"),
    ("26.20", "A female monastic arrived through the sky, paid homage, and left at once while the king of the gods watched. What verse followed?", "Khemā; Dhp 403"),
]


def fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", fold(s)) if w not in STOP and len(w) > 2}


def load():
    verses = {json.loads(l)["verse"]: json.loads(l) for l in (ROOT / "data/processed/verses.jsonl").read_text(encoding="utf-8").splitlines()}
    stories = {json.loads(l)["group_id"]: json.loads(l) for l in (ROOT / "data/processed/stories.jsonl").read_text(encoding="utf-8").splitlines()}
    chunks = [json.loads(l) for l in (ROOT / "data/index/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    return verses, stories, chunks


def chunk_words_by_group(verses, chunks) -> dict[str, list[set[str]]]:
    """Content-word sets of every chunk that resolves to each group, using the
    same resolution rule as retrieval_eval.resolve_story_ids()."""
    out: dict[str, list[set[str]]] = defaultdict(list)
    for c in chunks:
        gids = [c["group_id"]] if c.get("group_id") else list(verses[c["dhp_verses"][0]]["story_group_ids"])
        words = content_words(c["text"])
        for g in gids:
            out[g].append(words)
    return out


def main() -> None:
    verses, stories, chunks = load()
    by_group = chunk_words_by_group(verses, chunks)

    entries: list[dict] = []

    def add(subtype, gold_group_ids, question, notes, distractors=None):
        for g in list(gold_group_ids) + list(distractors or []):
            if g not in stories:
                raise SystemExit(f"unknown group_id {g!r} for {question!r}")
        gold_verses = sorted({v for g in gold_group_ids for v in stories[g]["dhp_verses"]})
        entries.append({
            "type": subtype,
            "subtype": subtype,
            "question": question,
            "gold_group_ids": gold_group_ids,
            "gold_verse_numbers": gold_verses,
            "notes": notes,
            "annotator_1": "Claude (Opus 5.5)",
            **({"distractor_group_ids": distractors} if distractors else {}),
        })

    for g, q, n in NARRATIVE_DEEP:
        add("narrative_deep", [g], q, n)
    for v, q, n in PARAPHRASE:
        gids = list(verses[v]["story_group_ids"])
        if len(gids) != 1:
            raise SystemExit(f"Dhp {v} maps to {gids}; paraphrase questions need a single story")
        add("paraphrase", gids, q, f"Dhp {v}; {n}")
    for g, q, n in PALI_ASCII:
        add("pali_ascii", [g], q, n)
    for g, ds, q, n in DISAMBIGUATION:
        add("disambiguation", [g], q, n, distractors=ds)
    for gs, q, n in MULTI_GOLD:
        add("multi_gold", gs, q, n)
    for g, q, n in SITUATION_TO_VERSE:
        add("situation_to_verse", [g], q, n)

    # Overlap check: the measured difficulty property. Fails the build rather
    # than warning, so a question that restates its answer can't slip in.
    def overlap(qw: set[str], groups: list[str]) -> float:
        return max((len(qw & cw) / len(qw) for g in groups for cw in by_group[g]), default=0.0) if qw else 0.0

    failures = []
    for i, e in enumerate(entries, start=1):
        e["question_id"] = f"h{i:03d}"
        qw = content_words(e["question"])
        gold_ov = overlap(qw, e["gold_group_ids"])
        e["gold_overlap"] = round(gold_ov, 3)
        cap = OVERLAP_CAP.get(e["subtype"])
        if cap is not None and gold_ov > cap:
            failures.append(f"  {e['question_id']} {e['subtype']} gold overlap {gold_ov:.2f} > {cap}: {e['question']}")
        if "distractor_group_ids" in e:
            in_gold = qw & set().union(*(cw for g in e["gold_group_ids"] for cw in by_group[g]))
            in_dist = qw & set().union(*(cw for g in e["distractor_group_ids"] for cw in by_group[g]))
            separating = sorted(in_gold - in_dist)
            e["separating_words"] = separating
            e["distractor_overlap"] = round(overlap(qw, e["distractor_group_ids"]), 3)
            if len(separating) > MAX_SEPARATING_WORDS:
                failures.append(
                    f"  {e['question_id']} {len(separating)} words separate gold from distractors "
                    f"({', '.join(separating)}) -- not actually confusable: {e['question']}"
                )
    if failures:
        print("Questions over the overlap cap:\n" + "\n".join(failures))
        raise SystemExit(1)

    ids = [e["question_id"] for e in entries]
    assert len(ids) == len(set(ids)) == 72, len(ids)
    out = ROOT / "data/eval/gold_set_v2.jsonl"
    out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")

    print(f"Wrote {len(entries)} questions to {out.relative_to(ROOT)}")
    by_sub: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        by_sub[e["subtype"]].append(e["gold_overlap"])
    for st, xs in by_sub.items():
        print(f"  {st:20s} n={len(xs):2d}  mean gold overlap {sum(xs)/len(xs):.2f}  max {max(xs):.2f}")
    dis = [e for e in entries if "distractor_overlap" in e]
    print(f"  disambiguation: mean distractor overlap {sum(e['distractor_overlap'] for e in dis)/len(dis):.2f} "
          f"vs gold {sum(e['gold_overlap'] for e in dis)/len(dis):.2f}")


if __name__ == "__main__":
    sys.exit(main())
