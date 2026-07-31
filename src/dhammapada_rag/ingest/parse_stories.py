"""Segment the pdftotext -layout dump of the Dhammapada-Atthakatha into per-story records.

Source structure (see data/raw/PROVENANCE.md), per story:

    <vagga>.<story> <English title, may wrap a line>
                    <Pali title, usually ending in -vatthu>

    Dhp <verse>[-<verse>]
    CST4: <alternate Burmese-edition title>       [optional]
    Burlingame: <original 1921 title>              [optional]
    Compare: <parallel references>                 [optional]
    <unlabeled synopsis paragraph>
    Cast: <names>                                  [optional]
    Keywords: <comma list>
    ****                                           (2-5 stars rating)

    <body: nidana pericope, narrative vatthu (may embed "Story of the Past"
     sub-narratives), the Pali verse, its English translation, and the
     desanavasane "fruits of the teaching" close>

Running per-page headers/footers ("N. The Chapter about X, Vagga - <page>")
and inline PTS/Burlingame pagination crumbs ("[28.146]", "{1.3}") are noise
from the PDF and are stripped. Footnotes (numbered, indented, prefixed BG:
Burlingame's own notes or AJ: Anandajoti Bhikkhu's) are pulled out into a
separate list per story.

This is a best-effort regex segmentation, per DhammapadaRAG.txt Phase 1 item 4
("Regex on the tattha ... ti marker gets you most of the way; hand-correct the
rest and log your correction rate"). It does NOT attempt pada-gloss
(word-commentary) segmentation: this source explicitly omits that layer (see
the translator's introduction — Burlingame omitted it and Anandajoti Bhikkhu
followed suit, intending a separate future translation of it). Coverage of the
nidana/desanavasane/pali_verse/english_verse heuristics is reported by
`report()` below so the miss rate is visible rather than silently swallowed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest.corrections import CORRECTIONS, apply_corrections  # noqa: E402
from dhammapada_rag.models import Footnote, Story  # noqa: E402

HEADER_RE = re.compile(r"^\s*(\d+)\.(\d+)\s+(\S.*)$")
DHP_RE = re.compile(r"^Dhp\s+(\d+)(?:\s*[-–—]\s*(\d+))?\.?\s*$")
FOOTER_RE = re.compile(r"^\s*\d+\.\s+.+ - \d+\s*$")
STARS_RE = re.compile(r"^\*{2,5}$")
CST4_RE = re.compile(r"^CST4:\s*(.*)$")
BURLINGAME_RE = re.compile(r"^Burlingame:\s*(.*)$")
COMPARE_RE = re.compile(r"^Compare:\s*(.*)$")
CAST_RE = re.compile(r"^Cast:\s*(.*)$")
KEYWORDS_RE = re.compile(r"^Keywords:\s*(.*)$")
BRACKET_RE = re.compile(r"\{\d+\.\d+\}|\[\d+(?:\.\d+)?\]")
FOOTNOTE_MARKER_RE = re.compile(r"^\s*(\d{1,3})\s*$")
FOOTNOTE_BODY_RE = re.compile(r"^\s+(AJ|BG):\s*(.*)$")

PALI_CHARS = set("āīūṁṅñṭḍṇḷṛśṣĀĪŪṀṄÑṬḌṆḶṚŚṢ")
NIDANA_RE = re.compile(r".*?\bwith reference to\b.*?\.\s*", re.IGNORECASE | re.DOTALL)
DESANAVASANE_RE = re.compile(
    r"(At the (?:end|conclusion) of[^.]*\.)(?:(?!At the (?:end|conclusion) of).)*$",
    re.IGNORECASE | re.DOTALL,
)


def strip_noise_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if not FOOTER_RE.match(ln)]


def find_dhp_verses(text: str) -> tuple[list[int], str | None]:
    m = DHP_RE.match(text.strip())
    if not m:
        return [], "dhp_line_unparsed"
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    return list(range(start, end + 1)), None


def collect_title_block(lines: list[str], dhp_idx: int, max_back: int = 8) -> list[tuple[int, str]]:
    collected: list[tuple[int, str]] = []
    j = dhp_idx - 1
    floor = max(0, dhp_idx - max_back)
    while j >= floor:
        line = lines[j]
        if line.strip() == "":
            if collected:
                break
            j -= 1
            continue
        collected.append((j, line))
        if HEADER_RE.match(line):
            break
        j -= 1
    collected.reverse()
    return collected


LABEL_PATTERNS = {
    "cst4_title": CST4_RE,
    "burlingame_title": BURLINGAME_RE,
    "compare": COMPARE_RE,
    "cast": CAST_RE,
    "keywords": KEYWORDS_RE,
}


def parse_metadata(lines: list[str], start: int, end: int) -> tuple[dict, int, list[str]]:
    """Parse the metadata block starting right after the Dhp line.

    Labeled fields (CST4:/Burlingame:/Compare:/Cast:/Keywords:) are captured
    from their own line only -- in practice they don't wrap. Every other
    non-blank line in the block is the unlabeled synopsis paragraph, which may
    span several lines and isn't required to be contiguous with its label.

    Returns (fields, stars_line_index_or_-1, parse_flags).
    """
    fields: dict[str, str] = {}
    synopsis_parts: list[str] = []
    stars_idx = -1
    flags: list[str] = []

    i = start
    while i < end:
        line = lines[i]
        stripped = line.strip()
        if stripped == "":
            i += 1
            continue
        if STARS_RE.match(stripped):
            stars_idx = i
            break
        matched_label = False
        for name, pattern in LABEL_PATTERNS.items():
            m = pattern.match(stripped)
            if m:
                value = m.group(1).strip()
                # comma-list fields (Cast/Keywords) sometimes wrap to the next
                # physical line in the PDF; a trailing comma is the tell
                j = i + 1
                while value.endswith(",") and j < end and lines[j].strip():
                    cont = lines[j].strip()
                    if any(p.match(cont) for p in LABEL_PATTERNS.values()) or STARS_RE.match(cont):
                        break
                    value = (value + " " + cont).strip()
                    j += 1
                fields[name] = value
                i = j
                matched_label = True
                break
        if not matched_label:
            synopsis_parts.append(stripped)
            i += 1

    if synopsis_parts:
        fields["synopsis"] = " ".join(synopsis_parts)

    if stars_idx == -1:
        flags.append("no_stars_line_found")

    return fields, stars_idx, flags


def extract_footnotes(body_lines: list[str]) -> tuple[list[Footnote], list[str]]:
    footnotes: list[Footnote] = []
    kept: list[str] = []
    i = 0
    n = len(body_lines)
    while i < n:
        m = FOOTNOTE_MARKER_RE.match(body_lines[i])
        if m and i + 1 < n and FOOTNOTE_BODY_RE.match(body_lines[i + 1]):
            marker = m.group(1)
            fb = FOOTNOTE_BODY_RE.match(body_lines[i + 1])
            source = fb.group(1)
            text_parts = [fb.group(2).strip()]
            j = i + 2
            while j < n and body_lines[j].strip() != "" and not HEADER_RE.match(body_lines[j]):
                # continuation lines of a wrapped footnote are indented and don't
                # start a new footnote marker or a new field
                if FOOTNOTE_MARKER_RE.match(body_lines[j]) and j + 1 < n and FOOTNOTE_BODY_RE.match(body_lines[j + 1]):
                    break
                text_parts.append(body_lines[j].strip())
                j += 1
            footnotes.append(Footnote(marker=marker, source=source, text=" ".join(text_parts).strip()))
            i = j
            continue
        kept.append(body_lines[i])
        i += 1
    return footnotes, kept


def clean_body_text(lines: list[str]) -> str:
    text = "\n".join(lines)
    text = BRACKET_RE.sub("", text)
    # collapse runs of blank lines and trailing spaces
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_pali_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or FOOTNOTE_BODY_RE.match(line):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) < 8:
        return False
    pali_count = sum(1 for c in letters if c in PALI_CHARS)
    return (pali_count / len(letters)) > 0.10


NUMBERED_PALI_LINE_RE = re.compile(r"^\s*(\d{1,3})\.\s+(\S.*)$")

# Pali romanization can be nearly all plain-ASCII (diacritic-density checks
# miss lines like "manasā ce pasannena bhāsati vā karoti vā,"), but it never
# produces these exact short English function words as whole tokens -- their
# presence is what actually separates a wrapped Pali line from the English
# translation line directly below it, since the two blocks are often typeset
# with no blank line between them.
ENGLISH_STOPWORDS = {
    "the", "and", "of", "is", "with", "through", "like", "one", "not", "by", "at",
    "for", "who", "he", "she", "it", "that", "this", "his", "her", "their", "was",
    "were", "are", "to", "in", "on", "as", "if", "but", "so", "from", "which",
    "when", "where", "how", "what", "why", "then", "than", "or", "an", "a", "i",
    "we", "you", "they", "them", "its", "our", "your", "no", "all", "has", "have",
    "do", "does", "did", "will", "would", "can", "could", "may", "might",
}
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def is_indented(line: str, min_indent: int = 3) -> bool:
    return line.strip() != "" and (len(line) - len(line.lstrip(" "))) >= min_indent


def is_pali_text(line: str) -> bool:
    words = WORD_RE.findall(line.lower())
    if not words:
        return False
    return not any(w in ENGLISH_STOPWORDS for w in words)


def extract_verse_blocks(
    cleaned_body: str, dhp_verses: list[int]
) -> tuple[str | None, str | None, int | None, list[str]]:
    """Find this story's full Pali verse quotation, if the source reprints it.

    The source only reprints the full numbered Pali text of a verse at (in
    practice) one of the stories that explains it -- companion verses in a
    multi-verse group story are often represented only by a short teaser
    quote, not a full re-quotation. So a miss here can be a genuine source
    gap, not a parser failure; `report()` surfaces the rate.
    """
    lines = cleaned_body.split("\n")
    flags: list[str] = []
    pali_start = None
    matched_verse_number = None
    for idx, line in enumerate(lines):
        m = NUMBERED_PALI_LINE_RE.match(line)
        if m and int(m.group(1)) in dhp_verses and looks_like_pali_line(m.group(2)):
            pali_start = idx
            matched_verse_number = int(m.group(1))
            break
    if pali_start is None:
        flags.append("pali_verse_not_in_source")
        return None, None, None, flags

    # Verse-quote blocks are typeset indented (block-quoted); narrative prose
    # resumes flush-left. That's the reliable boundary signal here -- a blank
    # line does NOT reliably separate the English verse from the following
    # desanavasane sentence in this source (they're often typeset back to
    # back with no blank line), but the indentation always drops back to zero.
    pali_end = pali_start
    while (
        pali_end + 1 < len(lines)
        and is_indented(lines[pali_end + 1])
        and not NUMBERED_PALI_LINE_RE.match(lines[pali_end + 1])
        and is_pali_text(lines[pali_end + 1])
    ):
        pali_end += 1
    first = NUMBERED_PALI_LINE_RE.match(lines[pali_start]).group(2)
    pali_verse = " ".join([first] + [l.strip() for l in lines[pali_start + 1 : pali_end + 1]])

    eng_lines: list[str] = []
    j = pali_end + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    while j < len(lines) and is_indented(lines[j]) and not is_pali_text(lines[j]):
        eng_lines.append(lines[j].strip())
        j += 1

    english_verse = " ".join(eng_lines) if eng_lines else None
    if english_verse is None:
        flags.append("english_verse_not_detected")

    return pali_verse, english_verse, matched_verse_number, flags


def extract_nidana_desanavasane(cleaned_body: str) -> tuple[str | None, str | None, str, list[str]]:
    flags: list[str] = []
    nidana = None
    m = NIDANA_RE.match(cleaned_body)
    if m and m.end() < 600:
        nidana = m.group(0).strip()
    else:
        flags.append("nidana_not_detected")

    desanavasane = None
    m2 = DESANAVASANE_RE.search(cleaned_body)
    if m2:
        desanavasane = cleaned_body[m2.start() :].strip()
        vatthu = cleaned_body[: m2.start()].strip()
    else:
        flags.append("desanavasane_not_detected")
        vatthu = cleaned_body

    if nidana and vatthu.startswith(nidana):
        vatthu = vatthu[len(nidana) :].strip()

    return nidana, desanavasane, vatthu, flags


def parse_stories(raw_text: str) -> list[Story]:
    lines = strip_noise_lines(raw_text.split("\n"))

    dhp_indices = [i for i, ln in enumerate(lines) if DHP_RE.match(ln.strip())]

    headers = []  # (dhp_idx, header_start_idx, vagga, story, title_en, title_pali)
    for dhp_idx in dhp_indices:
        block = collect_title_block(lines, dhp_idx)
        if not block:
            continue
        header_idx, header_line = block[0]
        hm = HEADER_RE.match(header_line)
        if not hm:
            continue
        vagga_num = int(hm.group(1))
        story_num = int(hm.group(2))
        title_first = hm.group(3).strip()
        if len(block) >= 2:
            title_pali = block[-1][1].strip()
            middle = [ln.strip() for _, ln in block[1:-1]]
            title_en = " ".join([title_first] + middle).strip()
        else:
            title_pali = None
            title_en = title_first
        headers.append((dhp_idx, header_idx, vagga_num, story_num, title_en, title_pali))

    stories: list[Story] = []
    for k, (dhp_idx, header_idx, vagga_num, story_num, title_en, title_pali) in enumerate(headers):
        chunk_end = headers[k + 1][1] if k + 1 < len(headers) else len(lines)

        dhp_verses, dhp_flag = find_dhp_verses(lines[dhp_idx])
        fields, stars_idx, meta_flags = parse_metadata(lines, dhp_idx + 1, chunk_end)

        body_start = stars_idx + 1 if stars_idx != -1 else dhp_idx + 1
        body_lines_raw = lines[body_start:chunk_end]
        footnotes, body_lines = extract_footnotes(body_lines_raw)
        body_raw = clean_body_text(body_lines)

        pali_verse, english_verse, pali_verse_number, verse_flags = extract_verse_blocks(body_raw, dhp_verses)
        nidana, desanavasane, vatthu, seg_flags = extract_nidana_desanavasane(body_raw)

        rating = None
        stars_line = lines[stars_idx].strip() if stars_idx != -1 else ""
        if stars_line:
            rating = len(stars_line)

        flags = meta_flags + verse_flags + seg_flags
        if dhp_flag:
            flags.append(dhp_flag)

        keywords_raw = fields.get("keywords", "")
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

        story = Story(
            group_id=f"{vagga_num}.{story_num}",
            vagga_number=vagga_num,
            story_number=story_num,
            dhp_verses=dhp_verses,
            title_en=title_en,
            title_pali=title_pali,
            cst4_title=fields.get("cst4_title"),
            burlingame_title=fields.get("burlingame_title"),
            compare=fields.get("compare"),
            synopsis=fields.get("synopsis"),
            cast=fields.get("cast"),
            keywords=keywords,
            rating=rating,
            pali_verse=pali_verse,
            english_verse=english_verse,
            pali_verse_number=pali_verse_number,
            nidana=nidana,
            vatthu=vatthu,
            desanavasane=desanavasane,
            footnotes=footnotes,
            body_raw=body_raw,
            parse_flags=flags,
        )
        stories.append(story)

    return stories


def report(stories: list[Story]) -> dict:
    n = len(stories)
    flag_counts: dict[str, int] = {}
    for s in stories:
        for f in s.parse_flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    return {
        "n_stories": n,
        "n_dhp_verses_total": sum(len(s.dhp_verses) for s in stories),
        "flag_counts": flag_counts,
        "flag_rates": {k: round(v / n, 4) for k, v in flag_counts.items()} if n else {},
    }


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    raw_path = root / "data" / "raw" / "dhammapada-attakatha.txt"
    out_path = root / "data" / "processed" / "stories.jsonl"
    report_path = root / "data" / "processed" / "parse_report.json"

    raw_text = raw_path.read_text(encoding="utf-8")
    stories = parse_stories(raw_text)
    story_dicts = [s.to_dict() for s in stories]

    applied = apply_corrections(story_dicts)
    if len(applied) != len(CORRECTIONS):
        missed = set(CORRECTIONS) - set(applied)
        print(f"WARNING: {len(missed)} corrections in corrections.py no longer match parser output: {missed}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for s in story_dicts:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    rep = report(stories)
    rep["hand_corrections_applied"] = applied
    rep["n_hand_corrections_applied"] = len(applied)
    report_path.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Parsed {rep['n_stories']} stories, {rep['n_dhp_verses_total']} verse references.")
    print(f"Applied {len(applied)} hand-corrections (see corrections.py): {applied}")
    print(f"Wrote {out_path}")
    print(f"Wrote {report_path}")
    print(json.dumps(rep["flag_rates"], indent=2))


if __name__ == "__main__":
    main()
