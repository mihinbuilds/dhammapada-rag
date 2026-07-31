"""Canonical table of the 26 Dhammapada vaggas (chapters) and their verse ranges.

This is fixed, well-established structure of the Pali canon, independent of any
particular edition's PDF pagination or headers. Used as ground truth to
validate parsed output against, per DhammapadaRAG.txt Phase 1 item 1:
"423 verses, 26 vaggas, no gaps."
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Vagga:
    number: int
    name_pali: str
    name_en: str
    first_verse: int
    last_verse: int

    @property
    def verse_count(self) -> int:
        return self.last_verse - self.first_verse + 1


VAGGAS: list[Vagga] = [
    Vagga(1, "Yamakavagga", "The Chapter about the Pairs", 1, 20),
    Vagga(2, "Appamādavagga", "The Chapter about Heedfulness", 21, 32),
    Vagga(3, "Cittavagga", "The Chapter about the Mind", 33, 43),
    Vagga(4, "Pupphavagga", "The Chapter about Flowers", 44, 59),
    Vagga(5, "Bālavagga", "The Chapter about Fools", 60, 75),
    Vagga(6, "Paṇḍitavagga", "The Chapter about the Wise", 76, 89),
    Vagga(7, "Arahantavagga", "The Chapter about the Arahats", 90, 99),
    Vagga(8, "Sahassavagga", "The Chapter about the Thousands", 100, 115),
    Vagga(9, "Pāpavagga", "The Chapter about Wickedness", 116, 128),
    Vagga(10, "Daṇḍavagga", "The Chapter about the Stick", 129, 145),
    Vagga(11, "Jarāvagga", "The Chapter about Old Age", 146, 156),
    Vagga(12, "Attavagga", "The Chapter about the Self", 157, 166),
    Vagga(13, "Lokavagga", "The Chapter about the World", 167, 178),
    Vagga(14, "Buddhavagga", "The Chapter about the Buddha", 179, 196),
    Vagga(15, "Sukhavagga", "The Chapter about Happiness", 197, 208),
    Vagga(16, "Piyavagga", "The Chapter about Love", 209, 220),
    Vagga(17, "Kodhavagga", "The Chapter about Anger", 221, 234),
    Vagga(18, "Malavagga", "The Chapter about Stains", 235, 255),
    Vagga(19, "Dhammaṭṭhavagga", "The Chapter about One Who Stands by Dhamma", 256, 272),
    Vagga(20, "Maggavagga", "The Chapter about the Path", 273, 289),
    Vagga(21, "Pakiṇṇakavagga", "The Miscellaneous Chapter", 290, 305),
    Vagga(22, "Nirayavagga", "The Chapter about Niraya Hell", 306, 319),
    Vagga(23, "Nāgavagga", "The Chapter about the Elephant", 320, 333),
    Vagga(24, "Taṇhāvagga", "The Chapter about Craving", 334, 359),
    Vagga(25, "Bhikkhuvagga", "The Chapter about Bhikkhus", 360, 382),
    Vagga(26, "Brāhmaṇavagga", "The Chapter about Brahmins", 383, 423),
]

assert len(VAGGAS) == 26
assert VAGGAS[0].first_verse == 1
assert VAGGAS[-1].last_verse == 423
assert sum(v.verse_count for v in VAGGAS) == 423
for _a, _b in zip(VAGGAS, VAGGAS[1:]):
    assert _a.last_verse + 1 == _b.first_verse, (_a, _b)

VAGGA_BY_NUMBER = {v.number: v for v in VAGGAS}


def vagga_for_verse(verse_number: int) -> Vagga:
    for v in VAGGAS:
        if v.first_verse <= verse_number <= v.last_verse:
            return v
    raise ValueError(f"verse {verse_number} out of range 1-423")
