"""Construct data/eval/gold_set.jsonl: 120 questions across five types --
doctrinal (30), philological (30), narrative (30), alignment (14),
cross_recension (16) -- per docs/eval_rubric.md.

Bug 14 fix: `type` used to have four values, with a `cross_recension`
stratum that actually mixed three different question kinds (verse-grouping
lookups, genuine CST4 edition-title variance, corpus anomalies) under one
label -- see "Bug 14 diagnosis" at the end of this docstring. Every entry
now also carries a `subtype`: doctrinal/philological/narrative subtypes equal
their type; the other 30 questions split into subtypes verse_grouping (14, now
its own `alignment` type), cst4_title_variant (8), colophon_not_indexed (6),
corpus_anomaly (2), the last three still under `cross_recension`.

Each entry below specifies either a verse number (for doctrinal/philological,
where the question maps to exactly one verse's own story) or an explicit
group_id (for narrative/alignment/cross_recension, where the specific story
matters). Group_id/verse_number resolution against the corpus happens here,
not by hand, to avoid transcription errors; if a verse maps to more than one
story (true only for Dhp 416; see docs/datasheet.md), specifying by verse
number alone would be ambiguous, so those cases use explicit group_id
instead.

Single-annotator construction-from-known-answer method: see
docs/eval_rubric.md "Construction method" and "Annotator status." The six
question constant lists below (DOCTRINAL, PHILOLOGICAL, NARRATIVE,
CROSS_RECENSION_COLOPHON, CROSS_RECENSION_MULTIVERSE, CROSS_RECENSION_CST4,
CROSS_RECENSION_SPECIAL) are hand-written and unchanged by the bug 14 fix --
only how they get resolved and typed below changed.

--------------------------------------------------------------------------
Bug 14 diagnosis. Carried over verbatim from build_gold_set_PATCH.py, which
proposed this fix and was deleted once it had been applied (the file is
still in git history: `git show 4e57cd9:data/eval/build_gold_set_PATCH.py`).
Figures are from before the fix.

The `cross_recension` stratum scores 0.54 against ~0.86 elsewhere, and
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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def load_corpus():
    verses = [json.loads(l) for l in (ROOT / "data" / "processed" / "verses.jsonl").read_text(encoding="utf-8").splitlines()]
    stories = [json.loads(l) for l in (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()]
    verses_by_number = {v["verse"]: v for v in verses}
    stories_by_id = {s["group_id"]: s for s in stories}
    return verses_by_number, stories_by_id


# (verse_number, question, notes) -- resolves to that verse's sole story.
DOCTRINAL = [
    (11, "What does the Dhammapada say happens to those who mistake the inessential for the essential, and the essential for inessential?", "wrong-thought habitat verse"),
    (23, "According to the Dhammapada, what do those who meditate regularly and vigorously attain?", "extinguishment/nibbana as supreme sanctuary"),
    (39, "What does the Dhammapada say about a person whose mind does not fester and who has given up notions of right and wrong?", "nothing to fear verse"),
    (45, "What comparison does the Dhammapada draw between a spiritual trainee and an expert selecting flowers?", "trainee bestirs the earth verse"),
    (62, "What does the Dhammapada say is wrong with a fool's thought 'sons are mine, wealth is mine'?", "even the self is not one's own"),
    (89, "What does the Dhammapada say happens to those whose minds are rightly developed in the awakening factors and who let go of attachment?", "bojjhanga verse"),
    (98, "According to the Dhammapada, what makes a place delightful regardless of whether it is a village or wilderness?", "wherever the perfected ones live"),
    (103, "According to the Dhammapada, who is the supreme conqueror?", "conquering oneself vs a million men in battle"),
    (121, "What warning does the Dhammapada give about thinking lightly of small evil deeds?", "pot filled drop by drop"),
    (130, "What ethical principle does the Dhammapada draw from the observation that all beings tremble at violence and love life?", "treating others like oneself"),
    (154, "What does the famous 'house-builder' verse in the Dhammapada say has been found and demolished?", "craving as house-builder, rafters broken"),
    (160, "According to the Dhammapada, who is the lord of a person, and how is that lordship gained?", "self as one's own lord, well-tamed self"),
    (167, "What four things does the Dhammapada advise against resorting to or perpetuating?", "lowly things, negligence, wrong views, perpetuating the world"),
    (181, "According to the Dhammapada, why are the Buddhas envied even by the gods?", "love of the peace of renunciation"),
    (203, "What does the Dhammapada identify as the worst illness and the worst suffering?", "hunger / conditioned existence"),
    (215, "According to the Dhammapada, what is the source of both sorrow and fear?", "desire as the root"),
    (222, "What simile does the Dhammapada use to describe someone who keeps their anger in check?", "charioteer who checks a lurching chariot"),
    (242, "What does the Dhammapada identify as a woman's stain, a giver's stain, and a stain in general?", "misconduct / stinginess / bad qualities"),
    (258, "According to the Dhammapada, what actually makes someone 'astute,' as opposed to merely talking a lot?", "security, freedom from enmity and fear"),
    (286, "What mistaken assumption does the Dhammapada say a fool makes when planning where to spend each season?", "not realizing the danger of death"),
    (291, "What does the Dhammapada say about those who seek their own happiness by causing others suffering?", "not freed from enmity"),
    (319, "According to the Dhammapada, what leads beings with right view to a good rebirth?", "knowing fault as fault, faultless as faultless"),
    (329, "What does the Dhammapada advise doing if you cannot find a wise, attentive companion to live with?", "wander alone like a tusker elephant"),
    (337, "What image does the Dhammapada use for how craving should be uprooted?", "digging up grass roots, Mara breaking the reed"),
    (367, "According to the Dhammapada, what quality regarding 'name and form' qualifies someone to be called a mendicant?", "no sense of ownership"),
    (423, "According to the closing verse of the Dhammapada, what qualities define a true brahmin with respect to knowledge of past lives?", "final verse of the whole text"),
    (1, "What does the opening verse of the Dhammapada say about the relationship between the mind and suffering?", "mind precedes, wheel follows ox's foot"),
    (5, "According to the Dhammapada, how is hatred brought to an end?", "never by hatred, only by love -- ancient teaching"),
    (183, "What three-part instruction does the Dhammapada summarize as 'the instruction of the Buddhas'?", "ovada-patimokkha verse: avoid evil, do good, purify the mind"),
    (223, "What does the Dhammapada recommend using to defeat anger, villainy, stinginess, and lies?", "kindness, virtue, giving, truth"),
]

# (verse_number, question, notes) -- must have interlinear_notes; philological = term/translation meaning.
PHILOLOGICAL = [
    (1, "In the opening verse of the Dhammapada, what is the ethical (not descriptive/Abhidhammic) reading of 'mind precedes thoughts, mind is their chief'?", "AJ note on avoiding a common mistranslation"),
    (24, "In Dhp 24, what four different grammatical case-ending forms appear in the string of genitives describing the diligent person?", "-vato/-ato/-assa/-ino genitive forms note"),
    (40, "In Dhp 40, what does the simile comparing the body to a jar/pot mean?", "'i.e. is fragile' gloss on the pot simile"),
    (45, "What does the Pali technical term 'sekha' mean in Dhp 45, and what attainment level does it presuppose?", "sekha = one in training, at least Stream-Entry"),
    (60, "In Dhp 60, do the similes of a long night and a long road actually match the point being made about a fool's time in samsara?", "AJ note on the similes not quite matching the statement"),
    (78, "What grammatical irregularity does Dhp 78 show between its first two lines and its second two lines?", "3rd person singular vs 2nd person polite plural shift"),
    (90, "What are the four 'knots' (gantha) referred to in Dhp 90 and its commentary?", "avarice, ill-will, grasping at virtue/practice, dogmatic insistence"),
    (106, "In Dhp 106, what is disputed about the meaning of the word 'samam' in the phrase describing a hundred years of sacrifice?", "some translations take samam as 'year' following the commentary paraphrase; AJ disputes this reading"),
    (141, "Is there a clear thematic reason Dhp 141 is placed in the Chapter about the Stick (Dandavagga)?", "AJ notes no particular reason is apparent"),
    (150, "What is philologically curious about Dhp 150 describing conceit and anger as hidden 'in the body'?", "AJ notes it seems strange to locate mental states in the body"),
    (164, "What botanical fact about the bamboo plant does the Dhammapada draw on for its simile in Dhp 164?", "bamboo flowers only after 60+ years, then dies"),
    (167, "What technical term is glossed as 'the five strands of sense pleasure' in relation to Dhp 167?", "panca kama-guna gloss on 'lokavagga' terminology"),
    (180, "What wordplay between 'apadam' and 'padani' underlies the meaning of Dhp 180?", "the one beyond the 'tracks/states' (padani) of craving is 'trackless' (apadam)"),
    (198, "What does the commentary gloss the phrase 'kilesaturesu' as, in relation to Dhp 198?", "'amongst those who are sick with defilements'"),
    (217, "What does the commentary's phrase 'tisso sikkha ta purayamanan-ti attho' mean in relation to Dhp 217?", "fulfilling the three trainings: virtue, concentration, wisdom"),
    (221, "How does the commentary gloss 'akincana' (having nothing/possessionless) in relation to Dhp 221?", "not developing possessions like passion, per the commentary's gloss"),
    (235, "Who is 'Yama' as referenced in Dhp 235, according to traditional Indian lore drawn on by the Dhammapada?", "god of death whose men escort one to the other world"),
    (257, "What significance does Dhp 257 have as the last occurrence of a particular term in its chapter?", "last mention of 'dhammattha' in the Dhammatthavagga"),
    (283, "What does the commentary gloss the forest simile in Dhp 283 as referring to?", "'ragadikilesavanam' -- the forest of passion and other defilements"),
    (294, "How does the commentary interpret the string of terms (mother, father, two warrior-kings, etc.) in Dhp 294?", "interpreted as craving, conceit, eternalism and annihilationism, sense-sphere delight"),
    (311, "What is 'kusa' grass, referenced in Dhp 311, and how does the commentary there define it?", "sharp-edged perennial grass; commentary gives it a specific technical sense"),
    (324, "What is unusual about Dhp 324 compared to most other Dhammapada verses, philologically/structurally?", "AJ notes it has no moral outside of its attached story"),
    (337, "How does the commentary paraphrase the reference to 'usira' (a fragrant root) in Dhp 337?", "'usirena atthiko' commentary paraphrase"),
    (362, "How does the commentary explain the term for a meditator in Dhp 362?", "one who personally delights in cultivating his own meditation object"),
    (383, "What does 'akata' (not made/unconditioned) refer to in Dhp 383, according to the note?", "Nibbana"),
    (394, "What does the commentary's phrase for defilements in Dhp 394 compare them to?", "'a jungle of defilements'"),
    (44, "In Dhp 44, what translation problem does the AJ note raise about the verb often rendered 'overcome' or 'conquer'?", "word may be unattested with that meaning outside this verse"),
    (273, "What does the phrase 'of bipeds' literally translate in Dhp 273's description of the Buddha?", "lit. 'dvipadanam' -- of two-footed beings"),
    (149, "In Dhp 149, what do the 'discarded' or 'white' objects in the verse's image specifically refer to, per the commentary's positioning of the scene?", "white gourds = bones/skulls, Buddha pointing at corpses"),
    (218, "What does the phrase 'i.e. for Nibbana' clarify about the object of intent described in Dhp 218?", "clarifies what the 'intangible' referred to actually is"),
]

# explicit group_id -- narrative = who/what/why behind a story.
NARRATIVE = [
    ("1.11", "What happened to the lay disciple Dhammika as he lay dying, that led to a Dhammapada teaching?", "celestial chariots competing for him"),
    ("2.2", "How did the rich man's son Kumbhaghosaka end up disguised as a poor laborer, and how was his fortune discovered?", "escaped affliction, later reclaimed inheritance"),
    ("3.1", "Why did the Buddha's attendant Meghiya leave the Buddha alone in a mango grove, and what happened to his mind as a result?", "meditation subject undermined by desire while alone"),
    ("4.12", "What did Sirigutta do to prove that the Niganthas his friend Garahadinna supported did not know the past, present, or future?", "trick involving pits of filth and flowers"),
    ("5.5", "What was discovered about Elder Udayi's knowledge of the teaching when he was questioned by visiting bhikkhus?", "did not know even the fundamentals despite living with the Buddha"),
    ("6.4", "Why did the other bhikkhus fear Elder Maha Kappina was still attached to his former royal life?", "misread his exclamations of delight as nostalgia for kingship"),
    ("7.4", "Why did the Buddha and the bhikkhus gather to help make a robe for Elder Anuruddha?", "his robe was worn out; a devata incited others to help"),
    ("8.3", "What was Kundalakesi's life before she became a bhikkhuni, and how was she converted?", "killed her husband, joined wanderers, debated, converted by Sariputta"),
    ("9.12", "How did Suppabuddha the Sakiyan obstruct the Buddha, and what was the consequence?", "blocked the Buddha's almsround out of arrogance"),
    ("10.2", "Why did the Group of Seventeen bhikkhus threaten the Group of Six?", "fought over and lost their lodgings"),
    ("11.9", "What led the wealthy youth Maha Dhana to end up as a beggar?", "took to drink and squandered his and his wife's money"),
    ("12.2", "What did Elder Upananda the Sakyan do to two other bhikkhus over a blanket?", "swindled them out of it despite teaching well himself"),
    ("13.10", "What made King Pasenadi's 'Gifts beyond Compare' to the Sangha unusual, and how often does such an event occur?", "something that happens only once in a lifetime"),
    ("14.7", "What question did Elder Ananda reflect the Buddha had never directly addressed, prompting him to ask it?", "well-bred elephants/steeds discussed, but not well-bred people"),
    ("15.1", "What conflict between the Sakiyans and Koliyans did the Buddha personally intervene to prevent?", "near-war over water supply"),
    ("16.1", "What was unusual about the family relationship among the three monastics in this story, and what problem did it cause after ordination?", "son, father, and mother all ordained but remained inseparable"),
    ("17.2", "Why did a devata want to kill the bhikkhu who cut down her tree, and what happened instead?", "the felling injured her child; she reconsidered killing him"),
    ("18.4", "What happened when Elder Laludayi, jealous of the Chief Disciples, declared himself a Dhamma teacher?", "could not recite even one verse when asked"),
    ("19.4", "What happened to Elder Lakuntaka Bhaddiya, described as young-looking and a dwarf, as he was leaving his duties one day?", "mistaken treatment by visiting bhikkhus due to his appearance"),
    ("20.9", "Why did the Buddha give Elder Sariputta's young disciple a different meditation subject than the one Sariputta had assigned?", "understood the disciple's actual inclination/background better"),
    ("21.1", "What happened to the Bodhisatta's son after he met some Paccekabuddhas in a past life, and how did his father react to learning of it?", "attained awakening, later died; father's reaction on discovery"),
    ("22.9", "Why did children of sectarian families go to Jetavana against their families' wishes?", "overcome by thirst"),
    ("23.4", "What problem did King Pasenadi suffer from due to overeating, and how did the Buddha help him?", "torpidity and drowsiness from overeating"),
    ("24.12", "What did the Brahmin Ankura do for ten thousand years, and why was his position in the heavens still limited?", "set up fire places and worshipped gods, yet inferior standing explained"),
    ("25.11", "Why did the Buddha send Elder Vakkali away, given Vakkali's devotion to him?", "obsessed with gazing at the Buddha's body, neglecting meditation"),
    ("26.35", "What was the bhikkhu in this story's occupation before ordination, and what did the bhikkhus ask him when a troupe passed through?", "formerly an acrobat; asked if he still craved that life"),
    ("8.12", "What series of losses drove Patacara mad with grief, and how did she recover?", "lost husband, both children, parents, and brother in one day"),
    ("8.13", "Why did the Buddha ask Kisa Gotami to bring mustard seeds from a house that had never seen death?", "to teach her death's universality after her son's death"),
    ("26.39", "What role did the elder Angulimala play in King Pasenadi's ceremony of Gifts beyond Compare, and how did the elephant beside him react?", "rogue elephant standing motionless beside him"),
    ("4.8", "Why was Visakha, a faithful Buddhist supporter, married into a family that supported the Jains, and what tension resulted?", "married to Migara's son despite the family's different faith"),
]

# explicit group_id/fact -- cross_recension = edition/numbering variants.
CROSS_RECENSION_COLOPHON = [
    ("The Chapter about Flowers (Pupphavagga)", "How many stories does this edition record for the Chapter about Flowers, and how does the PTS edition's count differ, per the text's own colophon?", "this ed: 12, PTS: 11"),
    ("The Chapter about Fools (Balavagga)", "How many stories does this edition record for the Chapter about Fools, and how does the PTS edition's count differ, per the colophon?", "this ed: 15, PTS: 14"),
    ("The Miscellaneous Chapter (Pakinnakavagga)", "How many stories does this edition record for the Miscellaneous Chapter, and how does the PTS edition's count differ, per the colophon?", "this ed: 9, PTS: 10"),
    ("The Chapter about Brahmins (Brahmanavagga)", "How many stories does this edition record for the Chapter about Brahmins, and how does the PTS edition's count differ, per the colophon?", "this ed: 40, PTS: 39"),
    ("total story count", "According to the text's own closing colophon, how many stories does this edition total across all 26 chapters, and how does that compare to the PTS edition's count?", "this ed: 305, PTS: 299"),
    ("recitation sections", "How many recitation sections (bhanavara) does the colophon say this edition's commentary comprises, and how does that compare to the PTS count?", "this ed: 72, PTS: 73"),
]

CROSS_RECENSION_MULTIVERSE = [
    ("14.6", "Which single story explains Dhp 188 through 192 together, rather than as separate individually-explained verses?", "Brahmin Aggidatta, 5-verse group"),
    ("24.12", "Which single story explains Dhp 356 through 359 as one connected group of verses?", "Ankura, 4-verse group"),
    ("6.11", "Which single story explains Dhp 87, 88, and 89 together?", "Five Hundred Visiting Bhikkhus"),
    ("19.6", "Which single story explains both Dhp 264 and Dhp 265?", "Hatthaka"),
    ("22.9", "Which single story explains both Dhp 318 and Dhp 319?", "Sectarian Disciples"),
    ("1.6", "Which single story explains both Dhp 7 and Dhp 8, a paired verse in the Chapter about the Pairs?", "Culla Kala and Maha Kala"),
    ("25.5", "Which single story explains both Dhp 365 and Dhp 366?", "A Treacherous Bhikkhu"),
    ("15.8", "Which single story explains Dhp 206, 207, and 208 together?", "Sakka's Attendance"),
    ("14.5", "Which single story explains both Dhp 186 and Dhp 187?", "A Discontented Bhikkhu"),
    ("11.8", "Which single story explains both Dhp 153 and Dhp 154, the well-known 'exalted utterances' verses?", "spoken to/about Elder Ananda"),
    ("24.1", "Which single story explains Dhp 334 through 337 together?", "Kapilamaccha, 4-verse group"),
    ("18.6", "Which single story explains both Dhp 244 and Dhp 245?", "Culla Sari"),
    ("23.1", "Which single story explains Dhp 320, 321, and 322 together?", "Speaking and Rousing Oneself"),
    ("3.5", "Which single story explains both Dhp 38 and Dhp 39?", "Elder Cittahattha"),
]

CROSS_RECENSION_CST4 = [
    ("1.8", "This edition titles a story 'Aggasavakavatthu' (Story of the Chief Disciples); what different title, naming a specific elder, does the CST4 (Burmese) edition use for the same story?", "CST4: Sariputtattheravatthu"),
    ("2.1", "This edition titles a story after King Udena; what different title, naming a queen instead, does the CST4 edition use for the same story?", "CST4: Samavativatthu"),
    ("2.7", "This edition titles a story after Mahali's question; what different title, naming Sakka's past-life identity Magha, does the CST4 edition use?", "CST4: Maghavatthu"),
    ("5.14", "This edition titles a story after Elder Sudhamma; what different title, naming the householder Citta instead, does the CST4 edition use for the same story?", "CST4: Cittagahapativatthu"),
    ("8.8", "This edition titles a story 'Dighayukumaravatthu' (the long-lived boy); what differently-worded title does the CST4 edition give the same story?", "CST4: Ayuvaddhanakumaravatthu, the youth whose lifespan increased"),
    ("10.5", "This edition titles a story after Visakha and other women observing the sabbath; how does the CST4 edition's title for the same story differ in specificity?", "CST4: Uposathikaitthinam Vatthu, about women observing the observance generally"),
    ("14.1", "This edition titles a story after Magandiya; what completely different title, naming Mara's daughters instead, does the CST4 edition use for the same story?", "CST4: Maradhitaravatthu"),
    ("14.2", "This edition titles the Twin Miracle story 'Yamakapatihariyavatthu'; what different title, naming the Buddha's descent from heaven, does the CST4 edition use?", "CST4: Devorohanavatthu, the Descent of the Devas"),
]

CROSS_RECENSION_SPECIAL = [
    ("26.34", "The translator's introduction notes one verse in the Dhammapada has two separate commentarial stories attached to it, against the practice everywhere else in the text. Which verse is it, and what is the second of the two stories?", "Dhp 416; second story is 26.34, The Story about the Elder Jotika"),
    ("26.17", "One story's own header line in this source PDF misstates its Dhp verse number due to an apparent typo; which story is it, and what is the correct verse number established by the verse quoted in its own body text?", "26.17 states 'Dhp 40' but its body quotes verse 400 in full; see corrections.py"),
]


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

    Bug 14 fix: the old resolve_cross_recension_multiverse_cst4() applied one
    undifferentiated "cross_recension" label to three substantively different
    question kinds (verse-grouping lookups, genuine CST4 edition-title
    variance, and corpus anomalies), which is most of why that stratum's
    aggregate score (0.54 against ~0.86 elsewhere) read as a retrieval
    weakness when it was largely a labelling problem -- see
    "Bug 14 diagnosis" in the module docstring for the full account.
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
    # Colophon facts aren't tied to a single retrievable verse-group -- they're
    # about the text's own back-matter, which isn't chunked/indexed (see
    # index/chunks.py). Excluded from gold_group_ids-based retrieval scoring;
    # kept in the gold set as documented, answerable-from-source knowledge
    # questions for the generation-metrics pass instead (docs/evaluation.md
    # notes this explicitly, doesn't silently drop it).
    return [{
        "type": "cross_recension",
        "subtype": "colophon_not_indexed",
        "question": question,
        "gold_group_ids": [],  # not chunk-retrievable; see note above
        "gold_verse_numbers": [],
        "notes": f"[colophon fact, not chunk-indexed] {subject}: {note}",
    } for subject, question, note in entries]


def main():
    verses_by_number, stories_by_id = load_corpus()

    doctrinal = resolve_doctrinal_philological(DOCTRINAL, "doctrinal", verses_by_number, stories_by_id)
    philological = resolve_doctrinal_philological(PHILOLOGICAL, "philological", verses_by_number, stories_by_id)
    narrative = resolve_narrative(NARRATIVE, stories_by_id)

    # Bug 14, part 2: alignment questions become their own TYPE. They test
    # the verse-to-story grouping table (the project's most valuable single
    # artifact -- see docs/datasheet.md), not edition variance, and burying
    # them inside cross_recension hid a real, well-supported result (this
    # stratum) behind a stratum that could not support the claim it was
    # being read to support.
    alignment = resolve_by_group(CROSS_RECENSION_MULTIVERSE, stories_by_id, "alignment", "verse_grouping")

    # cross_recension now keeps only questions actually about edition
    # variance. CST4 title variants are the only retrievable ones of the
    # three sub-kinds, and only now that index/chunks.py emits story_titles
    # (Phase 2) -- previously unanswerable by retrieval by construction.
    cross_recension = (
        resolve_colophon(CROSS_RECENSION_COLOPHON)
        + resolve_by_group(CROSS_RECENSION_CST4, stories_by_id, "cross_recension", "cst4_title_variant")
        + resolve_by_group(CROSS_RECENSION_SPECIAL, stories_by_id, "corpus_anomaly", "corpus_anomaly")
    )

    all_questions = doctrinal + philological + narrative + alignment + cross_recension
    assert len(doctrinal) == 30, len(doctrinal)
    assert len(philological) == 30, len(philological)
    assert len(narrative) == 30, len(narrative)
    assert len(alignment) == 14, len(alignment)
    assert len(cross_recension) == 16, len(cross_recension)
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
