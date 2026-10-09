"""Round 16 judgments for the four runs in this directory: the Round 14
prompt and the three Round 15 wordings, each after the [NOTES] block was
restructured (header naming the author, a <<citation_fields layer=note>>
marker per verse).

Same annotator (Claude Opus 5.5), procedure and rules as Rounds 14 and 15.
Keyed (run, question_id, claim_index); claims identical to one already
judged are not listed (prompt_sensitivity.py reuses the verdict). Two
consistency rules, as before: q019 answers that recast Dhp 259 as being
about "astute" are unfaithful; restating a note's content under another tag
has gold_layer "note".
"""

from __future__ import annotations

from generation_judgments import Verdict  # noqa: E402 -- data/eval is on sys.path (prompt_sensitivity.py)

V = Verdict
BASE, A, B, C = "r16_base", "r16_a_reorder", "r16_b_markdown", "r16_c_typography"

JUDGMENTS = {
    # q093
    (BASE, "q093", 1): V(True, "commentary", False, True,
        "Jetavana, Rains in Kosala; 'five hundred' follows the story's title (the nidana says fifty) -- judged as in Round 12."),
    # q095
    (BASE, "q095", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (BASE, "q095", 1): V(True, "commentary", False, True, "Matches synopsis."),
    (B, "q095", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    # q097
    (BASE, "q097", 1): V(False, "alignment", False, True, "Alignment fact tagged 'synthesis'."),
    (BASE, "q097", 2): V(True, "commentary", False, True, "Veḷuvana; lured by a bhikkhu of Devadatta's faction -- matches."),
    (A, "q097", 1): V(False, "alignment", False, True, "Alignment fact tagged 'commentary'."),
    (B, "q097", 1): V(True, "commentary", False, True, "Matches synopsis."),
    (C, "q097", 1): V(True, "commentary", False, True, "Veḷuvana, persuaded to share offerings, reproved -- matches."),
    # q119 (retrieval wrong)
    (BASE, "q119", 0): V(False, "alignment", False, False, "False two-story claim, tagged 'synthesis'."),
    (BASE, "q119", 1): V(True, "commentary", False, False, "Calls 6.10 'the first story' of a two-story verse that does not exist."),
    (BASE, "q119", 2): V(True, "commentary", False, False, "Presents 3.5 (Dhp 38-39) as the 'second story' of Dhp 85-86."),
    (A, "q119", 0): V(False, "commentary", False, False, "The invented 'second story', tagged 'synthesis'."),
    (A, "q119", 1): V(True, "verse", False, True, "Dhp 85-86's Pali lines copied, accurate."),
    (A, "q119", 2): V(True, "verse", False, True, "Dhp 85-86's English, accurate."),
    (A, "q119", 3): V(True, "commentary", False, False, "6.10's nidana, then the invented 'second story'."),
    (B, "q119", 0): V(False, "alignment", False, False, "'The verse in question is Dhp 85, 86' -- false anomaly, tagged 'verse'."),
    (B, "q119", 1): V(True, "commentary", False, False, "Invented 'second story'."),
    (C, "q119", 0): V(False, "alignment", False, False, "False two-story claim, tagged 'commentary'."),
    (C, "q119", 1): V(True, "commentary", False, False, "Invented 'second of the two stories'."),
    # q120 (retrieval wrong)
    (A, "q120", 1): V(True, "commentary", False, True, "26.21's nidana, accurate."),
    (B, "q120", 0): V(True, "alignment", False, False, "Fabricated '403' header."),
    (B, "q120", 1): V(True, "commentary", False, True, "26.21's nidana, accurate."),
    (C, "q120", 0): V(True, "alignment", False, False, "Fabricated '403' header."),
    # q111-q115
    (BASE, "q111", 0): V(True, "commentary", False, True, "CST4 'Sāriputtattheravatthu' -- correct."),
    (BASE, "q113", 0): V(False, "commentary", False, True, "CST4 'Maghavatthu' given as 'Magha' -- close enough; tagged 'alignment'."),
    (BASE, "q113", 1): V(True, "commentary", False, True, "Magha's past life, reborn as Sakka -- matches."),
    (A, "q113", 0): V(True, "commentary", False, True, "'Magha' for CST4 'Maghavatthu' -- acceptable."),
    (B, "q113", 0): V(False, "commentary", False, True, "'Magha' for CST4 'Maghavatthu', tagged 'alignment'."),
    (B, "q113", 1): V(True, "commentary", False, True, "Prince Magha, good works, reborn as Sakka -- matches."),
    (A, "q114", 0): V(True, "commentary", False, False, "'Citta and Sudhamma' -- not the CST4 title."),
    (A, "q115", 0): V(True, "commentary", False, True, "CST4 'Āyuvaḍḍhanakumāravatthu' -- correct."),
    # q001
    (BASE, "q001", 1): V(True, "commentary", False, True, "24.5's nidana, verbatim."),
    (A, "q001", 1): V(True, "verse", False, True, "Dhp 12, accurate."),
    (A, "q001", 2): V(True, "commentary", False, True, "Matches 1.8's synopsis."),
    (B, "q001", 1): V(True, "commentary", False, True, "24.5's synopsis, verbatim."),
    # q007
    (BASE, "q007", 1): V(False, "verse", False, True, "Dhp 98's content, tagged 'synthesis'."),
    (BASE, "q007", 2): V(True, "commentary", False, True, "The Buddha's visit and the thicket made delightful by spiritual power -- the synopsis."),
    (A, "q007", 1): V(False, "verse", False, True, "Restates Dhp 98 (the Buddha's words leading into it), tagged 'commentary'."),
    (C, "q007", 1): V(True, "commentary", False, True, "Revata, an Arahat of the acacia forest -- matches."),
    # q013 (gold 13.1 not retrieved)
    (BASE, "q013", 0): V(True, "note", False, False,
        "The Dhp 90 note's knots, correctly tagged 'note', but framed as what 'the Dhammapada advises against' in answer to a question about Dhp 167."),
    (BASE, "q013", 1): V(True, "commentary", False, True, "Jīvaka's question after treating the Buddha's foot -- matches 7.1."),
    (A, "q013", 0): V(True, "synthesis", False, False, "Invents a 'four things' list (violence, grief, knots, ownership)."),
    (A, "q013", 1): V(True, "verse", False, True, "Dhp 225, accurate."),
    (A, "q013", 2): V(True, "verse", False, True, "Dhp 90, accurate."),
    (A, "q013", 3): V(True, "verse", False, True, "Dhp 109, accurate."),
    (A, "q013", 4): V(True, "commentary", False, True, "17.5's story, accurate."),
    (C, "q013", 0): V(True, "synthesis", False, False, "'Does not ... in a single verse' -- false (Dhp 167)."),
    (C, "q013", 1): V(False, "note", False, True, "The note's knots attributed to 'the commentary'."),
    # q019 (gold 19.2 not retrieved)
    (BASE, "q019", 2): V(True, "commentary", False, False,
        "Jetavana, Elder Ekudāna, an Arahat -- the nidana; then the 'astuteness' recasting."),
    (B, "q019", 1): V(True, "verse", False, True, "Dhp 102, accurate."),
    (B, "q019", 2): V(True, "commentary", False, True, "Jetavana, Kuṇḍalakesī -- nidana and synopsis."),
    (C, "q019", 0): V(True, "verse", False, True, "Dhp 259 verbatim -- 'Dhamma-bearer', not 'astute'."),
    (C, "q019", 1): V(True, "verse", False, True, "Dhp 103, accurate."),
    (C, "q019", 2): V(True, "commentary", False, True, "Kuṇḍalakesī's story, accurate."),
    # q025
    (BASE, "q025", 1): V(True, "commentary", False, True, "The true bhikkhu's characteristics -- the synopsis."),
    (A, "q025", 1): V(True, "commentary", False, True, "First fruits before eating -- matches."),
    (C, "q025", 1): V(False, "alignment", False, True, "Title-plus-verse fact, tagged 'commentary'."),
    # q067
    (BASE, "q067", 1): V(True, "commentary", False, True, "Kassapa at the foot, Sāriputta in the midst, Ānanda at the head -- verbatim vatthu."),
    (A, "q067", 1): V(True, "commentary", False, True, "The alms-feast suspicion and the reproof -- the synopsis."),
    (B, "q067", 1): V(True, "commentary", False, True, "The suspicion about the feast -- matches."),
    (C, "q067", 1): V(True, "commentary", False, True, "Matches synopsis."),
    # q073
    (BASE, "q073", 0): V(True, "commentary", False, True, "Escalating offerings, pavilion, elephants, parasols -- in the vatthu."),
    (BASE, "q073", 1): V(True, "commentary", False, True, "'Once in a lifetime' -- the synopsis."),
    (A, "q073", 0): V(True, "commentary", False, True, "Pavilion, elephants, parasols; abundance -- consistent with the vatthu."),
    (B, "q073", 0): V(True, "commentary", False, False,
        "'Each time doubling' (the vatthu says a hundredfold and a thousandfold), and makes the rivalry the Gifts beyond Compare."),
    (B, "q073", 1): V(True, "commentary", False, True, "'Once to all the Buddhas ... a woman always manages this' -- verbatim."),
    (C, "q073", 0): V(True, "commentary", False, True, "Queen Mallikā managed them so the king outdid the citizens -- matches."),
    # q079
    (A, "q079", 0): V(True, "commentary", False, False, "Says the bhikkhus recognised him as an elder; they took him for a novice."),
    (A, "q079", 1): V(True, "commentary", False, True, "The novice reply and the Buddha's answer -- matches."),
    (B, "q079", 0): V(True, "commentary", False, True, "The synopsis, correctly tagged this time."),
    (C, "q079", 1): V(True, "commentary", False, True, "Verbatim vatthu."),
    # q085
    (BASE, "q085", 0): V(False, "commentary", True, True,
        "'The Dhammapada verse 381 states that the Buddha sent Vakkali away ...' -- the synopsis presented as the verse. Conflation."),
    (BASE, "q085", 1): V(True, "commentary", False, True, "The shock -- matches the vatthu."),
    (A, "q085", 0): V(True, "commentary", False, True, "Matches synopsis."),
    (A, "q085", 1): V(True, "commentary", False, True, "Consistent with the vatthu."),
    (A, "q085", 2): V(True, "commentary", False, True, "The radiant image and his attainment -- matches."),
    (B, "q085", 0): V(False, "commentary", True, True, "The synopsis tagged 'verse'. Conflation."),
    (B, "q085", 1): V(True, "commentary", False, True, "Consistent with the vatthu."),
    # q031
    (BASE, "q031", 1): V(False, "synthesis", False, True, "An inference ('one should cultivate a wholesome mind'), tagged 'note'."),
    (A, "q031", 2): V(True, "note", False, True, "The Dhp 1 note, verbatim."),
    (A, "q031", 3): V(True, "commentary", False, False,
        "Says the Buddha explained the Elder's pure mind led to a good outcome; he explained the past misdeed that cost the Elder his sight."),
    (B, "q031", 1): V(False, "synthesis", False, True, "An inference, tagged 'note'."),
    (B, "q031", 2): V(True, "commentary", False, False, "'Spoken to the Elder Cakkhupāla' -- given with reference to him, not to him."),
    (C, "q031", 1): V(False, "note", False, True, "The note's 'ethical statement' reading, attributed to 'the commentary'."),
    # q037
    (BASE, "q037", 1): V(True, "commentary", False, True, "Mango Grove, Jīvaka's question after Devadatta's rock -- matches."),
    (A, "q037", 1): V(True, "commentary", False, False, "'The Buddha healing Jīvaka' reverses who healed whom; the rest matches."),
    (B, "q037", 1): V(True, "commentary", False, True, "Matches nidana/synopsis."),
    # q043 -- the note's padāni gloss again
    (BASE, "q043", 0): V(False, "note", False, True, "The note's gloss, tagged 'verse'."),
    (BASE, "q043", 1): V(False, "note", False, True, "The note's gloss, as 'the commentary explains'."),
    (BASE, "q043", 2): V(False, "note", False, True, "The note's gloss restated, tagged 'synthesis'."),
    (A, "q043", 1): V(False, "note", False, True, "The note's gloss, as 'the commentary explains'."),
    (A, "q043", 2): V(True, "synthesis", False, True, "A loose inference about pathlessness, correctly tagged."),
    (B, "q043", 1): V(False, "note", False, True, "The note, nearly verbatim, as 'the commentary explains'."),
    (B, "q043", 2): V(False, "note", False, True, "The note's gloss, tagged 'synthesis'."),
    (C, "q043", 1): V(False, "note", False, True, "The note's gloss, as 'the commentary explains'."),
    # q049
    (BASE, "q049", 0): V(True, "commentary", False, True, "The forest of lust, hatred and delusion as the source of suffering -- matches."),
    (A, "q049", 0): V(True, "commentary", False, True, "Lust, hatred and delusion -- matches."),
    (C, "q049", 0): V(True, "commentary", False, True, "Matches the vatthu."),
    # q055
    (BASE, "q055", 0): V(True, "note", False, True, "The note: akata is Nibbāna."),
    (BASE, "q055", 1): V(True, "commentary", False, True, "Matches synopsis."),
    (A, "q055", 1): V(True, "commentary", False, True, "Matches synopsis, including his urging to strive for Arahatship."),
    (B, "q055", 1): V(True, "commentary", False, True, "Matches synopsis."),
    (C, "q055", 1): V(True, "commentary", False, True, "Matches synopsis."),
}
