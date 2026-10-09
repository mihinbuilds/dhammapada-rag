"""Round 18 judgments for the four runs in this directory: the Round 17
configuration plus a corrective retry when audit() detects an editor's note
under another tag (NOTE_TEXT_AS_OTHER_LAYER). Only answers the retry changed
have new claims; everything else reuses its verdict.

Same annotator (Claude Opus 5.5), procedure and rules as Rounds 14-17. Two
of the relabelled note claims keep the phrase "the commentary explains" in
their prose while carrying the right tag: the tag is judged, and the
content is accurate to the note, so both count as correct and faithful.
"""

from __future__ import annotations

from generation_judgments import Verdict  # noqa: E402 -- data/eval is on sys.path (prompt_sensitivity.py)

V = Verdict
B, C = "r18_b_markdown", "r18_c_typography"

JUDGMENTS = {
    (B, "q043", 2): V(True, "note", False, True,
        "The note's gloss (apadaṁ: none of the states, padāni, of craving), now tagged 'note' after the retry; its prose still says 'the commentary explains'."),
    (B, "q043", 3): V(True, "commentary", False, True,
        "Māra's daughters tempting the Buddha, who was beyond craving -- matches nidana and synopsis."),
    (C, "q013", 1): V(True, "note", False, True,
        "The four knots from the Dhp 90 note, now tagged 'note' after the retry."),
    (C, "q031", 1): V(True, "note", False, True,
        "The Dhp 1 note's 'ethical statement' reading, now tagged 'note'; prose still says 'the commentary'."),
    (C, "q031", 2): V(True, "commentary", False, False,
        "Has Cakkhupāla obtaining a son through a vow to a tree (it was his father who did) and the Buddha teaching the verse to him; it was given with reference to him."),
}
