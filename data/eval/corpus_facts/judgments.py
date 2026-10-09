"""Round 17 judgments for the four runs in this directory: the Round 16
configuration plus corpus facts (index/corpus_facts.py) and the
shared-verse assembly fix. Only the prompts whose sources include one of
the seven stories with a corpus fact changed, so only q091 (one reworded
claim), q119 and q120 have new claims; everything else reuses its verdict.

Same annotator (Claude Opus 5.5), procedure and rules as Rounds 14-16.
"""

from __future__ import annotations

from generation_judgments import Verdict  # noqa: E402 -- data/eval is on sys.path (prompt_sensitivity.py)

V = Verdict
BASE, A, B, C = "r17_base", "r17_a_reorder", "r17_b_markdown", "r17_c_typography"

JUDGMENTS = {
    (BASE, "q091", 0): V(False, "alignment", False, True,
        "Aggidatta's story explains Dhp 188-192 together -- an alignment fact, tagged 'commentary'; Pasenadi detail correct."),

    # q119 -- gold 26.34 now retrieved at rank 1 (bundle with 26.33).
    (BASE, "q119", 0): V(False, "alignment", False, True,
        "Dhp 416 is the two-story verse -- correct, from the corpus note; a structural fact, tagged 'verse'."),
    (BASE, "q119", 1): V(False, "alignment", False, False,
        "Names Jaṭila (26.33) as the second story; the second is Jotika (26.34)."),
    (A, "q119", 0): V(True, "alignment", False, True,
        "Dhp 416, first Jaṭila (26.33), second Jotika (26.34) -- exactly right, correctly tagged."),
    (A, "q119", 1): V(True, "commentary", False, True,
        "Jotika's story, verbatim from 26.34's synopsis."),
    (B, "q119", 0): V(False, "alignment", False, True,
        "Dhp 416 has two stories -- correct; tagged 'commentary'."),
    (B, "q119", 1): V(True, "commentary", False, False,
        "Jaṭila's story summarised accurately, but presented as the second story; it is the first."),

    # q120 -- gold 26.17 now retrieved at rank 1.
    (BASE, "q120", 0): V(True, "alignment", False, True,
        "3.1's header gives Dhp 33 for Dhp 33-34 -- a true corpus fact (one of the six corrections), but not "
        "the typo the question means (26.17's Dhp 40 for 400). Accurate, so faithful; the answer is wrong."),
    (BASE, "q120", 1): V(True, "commentary", False, True,
        "3.1: Meghiya, Cālikā mountain, the mango grove -- matches."),
    (A, "q120", 0): V(True, "alignment", False, True,
        "26.17: header Dhp 40, body Dhp 400 -- exactly right, correctly tagged."),
    (A, "q120", 1): V(True, "commentary", False, True,
        "Sāriputta abused by his mother when offered alms, did not get angry -- matches the synopsis."),
    (B, "q120", 0): V(True, "alignment", False, True, "26.17: Dhp 40 for 400 -- correct."),
    (B, "q120", 1): V(True, "commentary", False, False,
        "'Explains Dhp 400 to the Elder Sāriputta' -- given with reference to him (nidana), not to him."),
    (C, "q120", 0): V(True, "alignment", False, True, "26.17: Dhp 40 for 400 -- correct."),
}
