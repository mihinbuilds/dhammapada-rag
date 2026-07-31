"""Parse Anandajoti Bhikkhu's interlinear Pali-English Dhammapada (2nd ed., Nov 2017)
into a per-verse phrase/word-level gloss layer.

This is the closest available public resource to the pada-gloss layer that
DhammapadaRAG.txt's Phase 1 item 4 calls for, and that the main narrative
source (sources/Dhammapada-Attakatha.pdf) explicitly omits (see
docs/datasheet.md). Being honest about what it is: it's a line-by-line
interlinear translation with inline scholarly notes on specific word/phrase
choices, textual variants, and parallel readings -- not a traditional
Pali commentarial pada-vibhanga. It's still real phrase-level glossing for
every one of the 423 verses, which is strictly more than the narrative
source alone provides (0 verses at that granularity).

HTML structure (see sources/external/anandajoti_interlinear/*.htm), per verse:

    <div class="verseN">
      <p><b>Pali line 1</b><br>English line 1 [inline <span class="TT"> notes]</p>
      <p><b>Pali line 2</b><br>English line 2</p>
      <p><b>Pali line 3 [maybe inline notes]</b><span class="number">[N]</span><br>
         English line 3 [inline notes]</p>
    </div>

Lines accumulate until a <span class="number">[N]</span> marker closes a verse
-- that marker, not the div boundary (one div can hold many verses, and a div
can also span page-internal content), is what's reliable.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PAGES = [
    "01-Pairs", "02-Heedfulness", "03-Mind", "04-Flowers", "05-Fools", "06-Wise",
    "07-Arahats", "08-Thousands", "09-Wickedness", "10-Stick", "11-Old-Age",
    "12-Self", "13-World", "14-Buddha", "15-Happiness", "16-Love", "17-Anger",
    "18-Stains", "19-Dhamma", "20-Path", "21-Miscellaneous", "22-Underworld",
    "23-Elephant", "24-Craving", "25-Monastics", "26-Brahmins",
]

NUMBER_RE = re.compile(r"\[(\d+)\]")
WS_RE = re.compile(r"\s+")


def clean(text: str) -> str:
    return WS_RE.sub(" ", text).strip()


def extract_notes(p: Tag) -> list[str]:
    notes = []
    for tt in p.find_all("span", class_="TT"):
        inner = tt.find("span")
        note_text = clean(inner.get_text()) if inner else clean(tt.get_text())
        if note_text:
            notes.append(note_text)
        tt.decompose()
    return notes


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    verse_divs = soup.find_all("div", class_=lambda c: bool(c) and c.startswith("verse"))

    verses: list[dict] = []
    pali_lines: list[str] = []
    english_lines: list[str] = []
    notes: list[str] = []

    for div in verse_divs:
        for p in div.find_all("p", recursive=True):
            b_tag = p.find("b")
            if b_tag is None:
                continue

            notes.extend(extract_notes(p))

            verse_number = None
            number_span = p.find("span", class_="number")
            if number_span is not None:
                m = NUMBER_RE.search(number_span.get_text())
                if m:
                    verse_number = int(m.group(1))
                number_span.decompose()

            pali_text = clean(b_tag.get_text())
            full_text = clean(p.get_text())
            english_text = full_text[len(pali_text) :].strip() if full_text.startswith(pali_text) else clean(
                full_text.replace(pali_text, "", 1)
            )

            pali_lines.append(pali_text)
            if english_text:
                english_lines.append(english_text)

            if verse_number is not None:
                verses.append(
                    {
                        "verse": verse_number,
                        "pali": " ".join(pali_lines),
                        "english": " ".join(english_lines),
                        "notes": notes,
                    }
                )
                pali_lines, english_lines, notes = [], [], []

    return verses


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    src_dir = root / "sources" / "external" / "anandajoti_interlinear"
    out_path = root / "data" / "processed" / "interlinear_gloss.jsonl"

    all_verses: dict[int, dict] = {}
    for page in PAGES:
        html = (src_dir / f"{page}.htm").read_text(encoding="utf-8")
        for v in parse_page(html):
            if v["verse"] in all_verses:
                print(f"WARNING: verse {v['verse']} parsed twice (page {page}); keeping first")
                continue
            all_verses[v["verse"]] = v

    missing = sorted(set(range(1, 424)) - set(all_verses))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for v in range(1, 424):
            if v in all_verses:
                f.write(json.dumps(all_verses[v], ensure_ascii=False) + "\n")

    print(f"Parsed {len(all_verses)}/423 verses from {len(PAGES)} pages.")
    print(f"Missing: {missing}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
