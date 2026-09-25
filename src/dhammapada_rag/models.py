from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Footnote:
    marker: str
    source: str  # "BG" (Burlingame), "AJ" (Anandajoti), or "unlabeled" (no prefix in the source)
    text: str


@dataclass
class Story:
    group_id: str  # "{vagga}.{story}", e.g. "1.1"
    vagga_number: int
    story_number: int
    dhp_verses: list[int]  # one or more Dhp verse numbers this story explains
    title_en: str
    title_pali: str | None = None
    cst4_title: str | None = None
    burlingame_title: str | None = None
    compare: str | None = None
    synopsis: str | None = None
    cast: str | None = None
    keywords: list[str] = field(default_factory=list)
    rating: int | None = None  # 2-5 stars, per AJ's rating system
    verse_teaser: str | None = None  # quoted opening words at head of story
    pali_verse: str | None = None
    english_verse: str | None = None
    pali_verse_number: int | None = None  # which of dhp_verses pali_verse/english_verse is
    nidana: str | None = None  # opening "where/with reference to whom" pericope
    vatthu: str = ""  # narrative body (includes embedded past-life substories)
    desanavasane: str | None = None  # "at the end of the teaching, X attained Y"
    footnotes: list[Footnote] = field(default_factory=list)
    body_raw: str = ""  # full raw body text before nidana/desanavasane extraction
    parse_flags: list[str] = field(default_factory=list)  # anomalies logged during parsing

    def to_dict(self) -> dict:
        d = {
            "group_id": self.group_id,
            "vagga_number": self.vagga_number,
            "story_number": self.story_number,
            "dhp_verses": self.dhp_verses,
            "title_en": self.title_en,
            "title_pali": self.title_pali,
            "cst4_title": self.cst4_title,
            "burlingame_title": self.burlingame_title,
            "compare": self.compare,
            "synopsis": self.synopsis,
            "cast": self.cast,
            "keywords": self.keywords,
            "rating": self.rating,
            "verse_teaser": self.verse_teaser,
            "pali_verse": self.pali_verse,
            "english_verse": self.english_verse,
            "pali_verse_number": self.pali_verse_number,
            "nidana": self.nidana,
            "vatthu": self.vatthu,
            "desanavasane": self.desanavasane,
            "footnotes": [f.__dict__ for f in self.footnotes],
            "body_raw": self.body_raw,
            "parse_flags": self.parse_flags,
        }
        return d
