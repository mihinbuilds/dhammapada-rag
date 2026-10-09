"""Round 15 judgments for the three prompt-variant runs in this directory.

Same annotator (Claude Opus 5.5), procedure and rules as the Round 14
judgments in data/eval/generation_judgments.py: every claim checked against
the full stored source text, gold_layer decided by where the content comes
from. Keyed (run, question_id, claim_index). A claim identical to one
already judged (same question, layer, citation and text) is not listed: the
prompt_sensitivity module reuses that verdict. One consistency rule worth
stating, since it recurs: answering q019's "astute" with Dhp 259's
"Dhamma-bearer" is judged unfaithful wherever it appears, as in Round 14.
"""

from __future__ import annotations

from generation_judgments import Verdict  # noqa: E402 -- data/eval is on sys.path (prompt_sensitivity.py)

V = Verdict
A, B, C = "a_reorder", "b_markdown", "c_typography"

JUDGMENTS = {
    # q091 alignment (gold 14.6)
    (A, "q091", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (A, "q091", 1): V(True, "commentary", False, True, "Jetavana, Aggidatta; Pasenadi reappointed him chaplain (vatthu)."),
    (B, "q091", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (B, "q091", 1): V(True, "commentary", False, True, "Went forth, taught refuge in mountains/forests/trees; Triple Gem -- matches vatthu."),
    # q093 alignment (gold 6.11)
    (A, "q093", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (A, "q093", 1): V(True, "commentary", False, True, "Fifty bhikkhus, Kosala, Sāvatthī -- matches synopsis."),
    (C, "q093", 1): V(True, "commentary", False, True, "Jetavana, fifty bhikkhus after the Rains in Kosala -- matches."),
    # q095 alignment (gold 22.9)
    (A, "q095", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (B, "q095", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (C, "q095", 1): V(True, "commentary", False, True, "Sectarians' children forbidden the monastery -- matches."),
    # q097 alignment (gold 25.5)
    (A, "q097", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (A, "q097", 1): V(True, "commentary", False, False,
        "'Switched allegiances to Devadatta's faction' -- the source says he disagreed with Devadatta and only stayed for the food."),
    (B, "q097", 0): V(True, "alignment", False, True, "Title and range, correctly tagged."),
    (B, "q097", 1): V(True, "commentary", False, True,
        "Persuaded to share Devadatta's faction's offerings; the closing line restates Dhp 365. Accurate."),
    # q099 alignment (gold 14.5)
    (A, "q099", 1): V(True, "verse", False, True, "Dhp 186-187 verbatim, correctly tagged."),
    (A, "q099", 2): V(True, "verse", False, True, "Dhp 187 verbatim, correctly tagged."),
    (A, "q099", 3): V(False, "alignment", False, True, "Title and range of 14.5 -- an alignment fact, tagged 'commentary'."),
    (A, "q099", 4): V(True, "commentary", False, True, "Inheritance, discontent, abandoned his practice; the Buddha's teaching -- matches."),
    (A, "q099", 5): V(True, "alignment", False, True, "Range of 14.5, correctly tagged."),
    (B, "q099", 1): V(True, "verse", False, True, "Dhp 186 verbatim, correctly tagged."),
    (C, "q099", 3): V(True, "commentary", False, True, "Jetavana, a discontented bhikkhu -- the nidana."),
    # q119 corpus_anomaly (retrieval wrong)
    (A, "q119", 0): V(True, "commentary", False, False, "Names Dhp 85 as the two-story verse and invents a 'second story'."),
    (B, "q119", 0): V(True, "alignment", False, False, "'The verse in question is Dhp 85 and 86' -- false anomaly fact."),
    (B, "q119", 1): V(True, "commentary", False, False, "Invents a 'second story' for 6.10."),
    (C, "q119", 0): V(False, "alignment", False, False, "False two-story claim about Dhp 85-86, tagged 'commentary'."),
    (C, "q119", 1): V(True, "commentary", False, False, "6.10's narrative, framed as a non-existent 'second story'."),
    # q120 corpus_anomaly (retrieval wrong)
    (A, "q120", 0): V(True, "alignment", False, False, "Fabricated header typo for 26.21 (its header reads Dhp 404)."),
    (A, "q120", 1): V(True, "commentary", False, True, "26.21's nidana, accurate."),
    (B, "q120", 0): V(True, "alignment", False, False, "Fabricated '403' header for 26.21."),
    (B, "q120", 1): V(True, "commentary", False, True, "26.21's nidana, accurate."),
    # q111-q115 cross_recension
    (A, "q111", 0): V(True, "commentary", False, True, "CST4 'Sāriputtattheravatthu' -- correct."),
    (C, "q112", 0): V(True, "commentary", False, True, "CST4 'Sāmāvatīvatthu' -- correct."),
    (A, "q113", 0): V(False, "commentary", False, False,
        "Invents a CST4 title ('The Story about Magha Became Sakka'), tagged 'alignment'."),
    (A, "q113", 1): V(True, "commentary", False, True, "Prince Magha, thirty-three companions, reborn as Sakka -- matches synopsis."),
    (B, "q113", 0): V(True, "commentary", False, True, "'The Story about Magha' -- the English half of CST4's 'Maghavatthu'."),
    (A, "q114", 0): V(True, "commentary", False, True, "CST4 'Cittagahapativatthu' with its gloss -- correct."),
    (B, "q114", 0): V(True, "commentary", False, False, "'Citta and Sudhamma' -- not the CST4 title."),
    (A, "q115", 0): V(True, "commentary", False, True, "CST4 'Āyuvaḍḍhanakumāravatthu' -- correct."),
    # q001 doctrinal (gold 1.8)
    (A, "q001", 0): V(True, "verse", False, True, "Dhp 11, accurate -- the right verse this time."),
    (A, "q001", 1): V(True, "verse", False, True, "Dhp 12, accurate."),
    (A, "q001", 2): V(True, "commentary", False, True, "Sāriputta and Moggallāna, Sañjaya, conversion, the verses -- matches synopsis."),
    (B, "q001", 1): V(True, "verse", False, True, "Dhp 11, accurate."),
    (B, "q001", 2): V(True, "commentary", False, False,
        "Veḷuvana is right, but the verses answered Sañjaya's refusal; nothing says the Chief Disciples misunderstood."),
    (C, "q001", 1): V(True, "synthesis", False, False, "Dhp 347's spider-web image linked to Dhp 11's teaching -- false link."),
    (C, "q001", 2): V(True, "commentary", False, True, "Khemā, Veḷuvana, the decaying image, Arahatship -- compressed but accurate."),
    # q007 doctrinal (gold 7.9)
    (A, "q007", 0): V(True, "verse", False, True, "Dhp 98, accurate."),
    (A, "q007", 1): V(False, "verse", False, True, "Restates Dhp 98, tagged 'commentary'."),
    (B, "q007", 0): V(True, "verse", False, True, "Dhp 98 verbatim."),
    (B, "q007", 1): V(False, "verse", False, True, "'This verse is about Arahats' -- the verse's own content, tagged 'commentary'."),
    (C, "q007", 1): V(True, "commentary", False, True, "Jetavana, Khadiravaniya Revata -- the nidana."),
    # q013 doctrinal (gold 13.1 not retrieved)
    (A, "q013", 0): V(True, "synthesis", False, False,
        "Assembles a 'four things' list (violence, grief, knots, consuming fever) from Dhp 225 and 90; neither advises against these as four."),
    (A, "q013", 1): V(True, "verse", False, True, "Dhp 225's Pali line copied whole, correctly tagged."),
    (A, "q013", 2): V(True, "verse", False, True, "Dhp 90's Pali line copied whole, correctly tagged."),
    (A, "q013", 3): V(True, "note", False, True, "The Dhp 90 note, verbatim, correctly tagged."),
    (A, "q013", 4): V(True, "commentary", False, True, "17.5: Añjanavana near Sāketa, the Brahmin parents of 1,500 lives -- matches."),
    (B, "q013", 0): V(False, "note", False, False,
        "The Dhp 90 note's four knots presented as what 'the Dhammapada advises against', as if answering the question; tagged 'commentary'."),
    (C, "q013", 0): V(True, "synthesis", False, False, "'Does not explicitly advise against any specific four things' -- false (Dhp 167)."),
    (C, "q013", 1): V(False, "note", False, True,
        "The Dhp 90 note's knots, accurately, attributed to 'the commentary' and tagged so; the Jīvaka detail is right."),
    # q019 doctrinal (gold 19.2 not retrieved)
    (A, "q019", 0): V(True, "verse", False, False, "Dhp 259 recast as about being 'astute' -- the 258/259 merge."),
    (A, "q019", 1): V(False, "verse", False, False, "Dhp 259's content tagged 'commentary', with the 'astute' substitution."),
    (B, "q019", 0): V(True, "verse", False, False, "Dhp 259 with 'astute' for 'Dhamma-bearer'."),
    (B, "q019", 1): V(True, "commentary", False, False, "Ekudāna's story is about practice over learning, recast as 'astuteness'."),
    (B, "q019", 2): V(True, "synthesis", False, False, "Same 'astute' merge, as synthesis."),
    (C, "q019", 1): V(False, "verse", False, False, "Dhp 259's content tagged 'commentary', with 'astute'."),
    # q025 doctrinal (gold 25.6)
    (A, "q025", 0): V(True, "verse", False, True, "Dhp 367, accurate."),
    (A, "q025", 1): V(True, "commentary", False, True, "First fruits; asked what makes a true bhikkhu -- matches synopsis."),
    (B, "q025", 1): V(True, "commentary", False, True, "First fruits before his meal -- matches synopsis."),
    # q061 narrative (gold 1.11)
    (A, "q061", 0): V(True, "commentary", False, True, "Matches synopsis."),
    (C, "q061", 0): V(True, "commentary", False, True, "Matches synopsis."),
    # q067 narrative (gold 7.4)
    (A, "q067", 1): V(True, "commentary", False, True, "Worn robes, refuse-heaps -- matches vatthu."),
    (B, "q067", 0): V(False, "commentary", True, True, "The robe-making narrative tagged 'verse' with Dhp 93's Pali. Conflation."),
    (B, "q067", 1): V(True, "commentary", False, False,
        "Cites 7.2 and attributes 7.2's walkabout practice to Anuruddha's robe-making -- neighbouring-story merge."),
    (C, "q067", 1): V(True, "commentary", False, True, "Worn robes -- matches."),
    # q073 narrative (gold 13.10)
    (A, "q073", 0): V(True, "commentary", False, True,
        "Unmatched scale, elephants holding parasols, women fanning, golden boats of perfume -- all in the vatthu."),
    (B, "q073", 0): V(True, "commentary", False, False,
        "Makes the six competitive rounds the 'Gifts beyond Compare'; those were the final offerings by Mallikā's plan, which no one could equal."),
    (C, "q073", 0): V(False, "commentary", True, False,
        "Narrative tagged 'verse' with Dhp 177's Pali -- conflation; and 'the king outdoing the citizens in a series' reverses the vatthu."),
    (C, "q073", 1): V(True, "commentary", False, True, "'Once in a lifetime' -- the synopsis's words."),
    # q079 narrative (gold 19.4)
    (A, "q079", 0): V(False, "commentary", True, True, "Vatthu narrative tagged 'verse' with Dhp 260's Pali. Conflation."),
    (A, "q079", 1): V(False, "verse", False, True, "Dhp 260-261's content (not age but the Truths, non-violence) tagged 'commentary'."),
    (B, "q079", 0): V(False, "commentary", True, True, "The synopsis tagged 'verse'. Conflation."),
    (B, "q079", 1): V(True, "commentary", False, True, "The novice reply and the Buddha's answer -- matches."),
    (C, "q079", 0): V(False, "commentary", True, True, "The synopsis tagged 'verse'. Conflation."),
    (C, "q079", 1): V(True, "commentary", False, True, "Matches the vatthu."),
    # q085 narrative (gold 25.11)
    (A, "q085", 0): V(True, "commentary", False, True, "Matches synopsis."),
    (A, "q085", 1): V(True, "commentary", False, True, "'Whoever beholds the Dhamma beholds me' -- matches vatthu."),
    (B, "q085", 1): V(True, "commentary", False, True, "Consistent with the vatthu."),
    (C, "q085", 1): V(False, "commentary", False, True, "'Perceived that his knowledge had ripened' -- vatthu content, tagged 'synthesis'."),
    (C, "q085", 2): V(True, "commentary", False, False, "Says Vakkali was sent to Rājagaha; it was the Buddha who went to Rājagaha."),
    (C, "q085", 3): V(True, "commentary", False, True, "On the verge of suicide -- matches synopsis."),
    (C, "q085", 4): V(True, "commentary", False, True, "The radiant image, Arahatship -- compressed but accurate."),
    # q031 philological (gold 1.1)
    (A, "q031", 0): V(False, "verse", False, True, "The verse's ethical sense, tagged 'synthesis' (same content Round 14 tagged 'verse')."),
    (A, "q031", 1): V(True, "verse", False, True, "Dhp 1's Pali line copied whole."),
    (A, "q031", 2): V(True, "note", False, True, "The Dhp 1 note, verbatim, correctly tagged."),
    (A, "q031", 3): V(True, "commentary", False, False,
        "'Spoken by the Buddha to the Elder Cakkhupāla' -- given with reference to him, after his death; not to him."),
    (B, "q031", 0): V(True, "verse", False, True, "The verse's ethical sense, accurate."),
    (B, "q031", 1): V(False, "synthesis", False, True, "An inference ('one should cultivate a wholesome mind'), tagged 'commentary'."),
    (C, "q031", 0): V(True, "verse", False, False, "Adds 'a pure mind leads to happiness' -- that is Dhp 2."),
    (C, "q031", 1): V(False, "note", False, True,
        "The Dhp 1 note verbatim ('an ethical statement ... many mistranslations'), attributed to 'the commentary'."),
    # q037 philological (gold 7.1)
    (A, "q037", 0): V(False, "note", False, True, "The note's four knots, verbatim, tagged 'commentary'."),
    (A, "q037", 1): V(True, "verse", False, True, "Dhp 90 verbatim."),
    (B, "q037", 0): V(True, "note", False, True, "The note's four knots, correctly tagged 'note'."),
    (B, "q037", 1): V(True, "commentary", False, True, "Mango Grove, Jīvaka's question after Devadatta's rock -- matches."),
    (C, "q037", 1): V(True, "commentary", False, True, "The nidana, verbatim."),
    # q043 philological (gold 14.1) -- the note's padāni gloss, under every tag
    (A, "q043", 0): V(False, "note", False, True, "The note's gloss, tagged 'verse'."),
    (A, "q043", 1): V(False, "note", False, True, "The note's gloss, as 'the commentary explains'."),
    (A, "q043", 2): V(False, "note", False, True, "The note's gloss, tagged 'synthesis'."),
    (B, "q043", 0): V(False, "note", False, True, "The note's gloss, tagged 'commentary'."),
    (B, "q043", 1): V(False, "note", False, True, "The note's gloss, as 'the commentary explains'."),
    (B, "q043", 2): V(False, "note", False, True, "The note's gloss, tagged 'commentary'."),
    (B, "q043", 3): V(False, "note", False, True, "The note's gloss, tagged 'synthesis'."),
    (C, "q043", 0): V(False, "note", False, True, "The note's gloss, tagged 'verse'."),
    (C, "q043", 1): V(False, "note", False, True, "The note verbatim, as 'the commentary explains'."),
    (C, "q043", 2): V(False, "note", False, True, "The note's gloss restated, tagged 'synthesis'."),
    # q049 philological (gold 20.8)
    (A, "q049", 0): V(True, "commentary", False, True, "The forest of lust, hatred and delusion (vatthu; the note quotes the commentary's rāgādikilesavanaṁ)."),
    (B, "q049", 0): V(True, "commentary", False, True, "Lust, hatred and delusion -- matches the vatthu."),
    (C, "q049", 0): V(True, "commentary", False, False, "'Which the Buddha explains ... in the notes' -- the notes are the editor's, not the Buddha's."),
    # q055 philological (gold 26.1)
    (A, "q055", 0): V(True, "note", False, True, "The note: akata is Nibbāna."),
    (A, "q055", 1): V(True, "commentary", False, False,
        "Adds that the Buddha saw the Brahmin's 'lack of understanding of Nibbāna'; the source says only that he urged him to strive for Arahatship."),
    (B, "q055", 0): V(True, "note", False, True, "The note."),
    (B, "q055", 1): V(True, "commentary", False, True, "Matches synopsis."),
    (C, "q055", 0): V(True, "note", False, True, "The note."),
    (C, "q055", 1): V(True, "commentary", False, True, "Matches synopsis."),
}
