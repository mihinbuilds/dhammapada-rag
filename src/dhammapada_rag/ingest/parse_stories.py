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

This is a best-effort regex segmentation, per docs/project_plan.md Phase 1 item 4
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

from dhammapada_rag.ingest.corrections import (  # noqa: E402
    CORRECTIONS,
    TEXT_CORRECTIONS,
    apply_corrections,
    apply_text_corrections,
)
from dhammapada_rag.models import Footnote, Story  # noqa: E402

# The source PDF's font mis-maps its curly-quote glyphs when extracted by
# pdftotext: most single-quote/apostrophe occurrences come out as U+2015
# (HORIZONTAL BAR, opening) / U+2016 (DOUBLE VERTICAL LINE, closing/
# apostrophe) instead of U+2018/U+2019 (e.g. "ox‖s foot", "―Who is
# he?‖"). Confirmed a 1:1 substitution, not a context-dependent one: a
# minority of quote glyphs in the same raw dump (314 U+2019 / 26 U+2018)
# extract correctly, in the identical apostrophe/opening-quote roles as
# their mis-mapped counterparts (e.g. "beings’ deeds", "‘Shine
# forth..."). Applied here, at read time, so data/raw/ stays an untouched
# extraction (per README's "unmodified beyond format conversion") while
# every field derived from this text -- title, synopsis, nidana, vatthu,
# desanavasane, footnotes -- gets the fix for free, rather than patching
# each field separately downstream.
_GLYPH_FIX = str.maketrans({"―": "‘", "‖": "’"})

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
# 11 footnotes carry no AJ:/BG: label (e.g. 99, 230, 404) and were
# previously never extracted, leaving their marker in the prose. The body
# must open with a letter: a wrapped number inside another note's text
# ("...15 / , agreeing with the Udāna") is not a marker.
FOOTNOTE_UNLABELED_BODY_RE = re.compile(r"^\s{2,}([^\W\d_].*)$")

# A vagga's own title page ("<FF>   129" then "2. The Chapter about
# Heedfulness," / "Appamādavagga") sits between the last story of one vagga
# and the first story header of the next, so without a cut it gets glued
# onto the end of the preceding story's body. Running page footers carry
# " - <page>" and are removed by FOOTER_RE before this ever runs.
VAGGA_HEADING_RE = re.compile(r"^\s{4,}\d{1,2}\. The (?:Chapter about|Miscellaneous Chapter)\b")
# The book's closing colophon (chapter story-counts plus the authorship
# ascription) follows story 26.40 with no story header of its own.
COLOPHON_RE = re.compile(r"^\s*Conclusion, Nigamanakathā")
# A lone page number on a page with no running footer (vagga title pages):
# "<FF>                    129". The leading form feed is what separates
# it from a footnote marker line, which is also a lone number.
PAGE_NUMBER_RE = re.compile(r"^\x0c\s*\d{1,4}\s*$")

PALI_CHARS = set("āīūṁṅñṭḍṇḷṛśṣĀĪŪṀṄÑṬḌṆḶṚŚṢ")
# \s+ rather than literal spaces: in 48 stories the phrase wraps across a
# line ("with reference\nto ..."), which the literal form missed entirely.
NIDANA_RE = re.compile(r".*?\bwith\s+reference\s+to\b.*?\.\s*", re.IGNORECASE | re.DOTALL)
# The closing "fruits of the teaching" section opens a sentence with a
# capital "At the end/conclusion of". Case-insensitive matching anywhere
# also caught the phrase mid-sentence -- "he was reborn at the end of his
# life in Avīci" (7.9), "and at the end of the rejoicing" (18.1), "verses,
# at the conclusion of each" (25.7) -- cutting those stories off
# mid-sentence. The last sentence-initial occurrence is used.
DESANAVASANE_START_RE = re.compile(r"(?:^|(?<=\n)|(?<=[.!?”’] ))\s*At the (?:end|conclusion) of")


def strip_noise_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if not FOOTER_RE.match(ln) and not PAGE_NUMBER_RE.match(ln)]


def cut_at_structural_boundary(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split a story's body at the next vagga title page or the book's
    closing colophon, whichever comes first -- neither is story content.

    Returns (story_lines, vagga_preface_lines). The preface is any prose
    printed on a vagga title page after the heading and before the next
    story's header: only vagga 5 has one, Burlingame's essay on story 5.1's
    structure (originally his footnote, per AJ's footnote 151). The colophon
    yields no preface -- it is dropped whole.
    """
    for i, ln in enumerate(lines):
        if COLOPHON_RE.match(ln):
            return lines[:i], []
        if VAGGA_HEADING_RE.match(ln):
            rest = lines[i + 1:]
            # skip the heading's wrapped continuation up to its Pali name
            # ("Bālavagga"), which closes every vagga heading
            for j, r in enumerate(rest):
                if r.strip().endswith("vagga"):
                    rest = rest[j + 1:]
                    break
            return lines[:i], [r for r in rest if r.strip()]
    return lines, []


def join_wrapped(parts: list[str]) -> str:
    """Join physically wrapped lines into one string.

    A line ending in a hyphen joins the next with no space: every such
    break in this source is a genuine compound ("night-/quarters",
    "rice-/porridge"), never a word split by automatic hyphenation --
    checked across all 92 occurrences in the body text.
    """
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out:
            out = p
        elif out.endswith("-") and len(out) > 1 and out[-2].isalpha():
            out += p
        else:
            out += " " + p
    return out


# A footnote marker is typeset as bare digits glued to the preceding word or
# punctuation ("Wheel of the Dhamma,5", "ox’s foot.4", "Udayana87").
_MARKER_CANDIDATE_RE = re.compile(r"(?<=[^\W\d_]|[.,;:!?’”)\]–—])(\d{1,3})(?=[\s.,;:!?’”)\]]|$)")


def strip_footnote_markers(text: str, markers: set[str], found: set[str] | None = None) -> str:
    """Remove inline footnote markers, but only digits that match an
    extracted footnote -- so ordinary numbers are never touched -- and never
    the tail of a digit-grouped number ("80,000", "7.2.3"), where the
    lookbehind's punctuation is itself preceded by a digit. Markers actually
    removed are added to `found`, when given.
    """
    if not markers or not text:
        return text

    def repl(m: re.Match) -> str:
        start = m.start()
        if start >= 2 and text[start - 1] in ".," and text[start - 2].isdigit():
            return m.group(0)
        if m.group(1) not in markers:
            return m.group(0)
        if found is not None:
            found.add(m.group(1))
        return ""

    return _MARKER_CANDIDATE_RE.sub(repl, text)


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

    Returns (fields, stars_line_index_or_-1, body_start_index, parse_flags).
    """
    fields: dict[str, str] = {}
    synopsis_parts: list[str] = []
    stars_idx = -1
    flags: list[str] = []

    # A story with no rating line (26.40) would otherwise have its whole
    # body -- and, being the last story, the book's colophon -- read as
    # synopsis. Without stars, the block ends at the first blank line after
    # the Keywords line, which is where the body begins in the source.
    if not any(STARS_RE.match(lines[k].strip()) for k in range(start, end)):
        seen_keywords = False
        for k in range(start, end):
            if KEYWORDS_RE.match(lines[k].strip()):
                seen_keywords = True
            elif seen_keywords and lines[k].strip() == "":
                end = k
                break

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
                    value = join_wrapped([value, cont])
                    j += 1
                fields[name] = value
                i = j
                matched_label = True
                break
        if not matched_label:
            synopsis_parts.append(stripped)
            i += 1

    if synopsis_parts:
        fields["synopsis"] = join_wrapped(synopsis_parts)

    if stars_idx == -1:
        flags.append("no_stars_line_found")

    body_start = stars_idx + 1 if stars_idx != -1 else end
    return fields, stars_idx, body_start, flags


def extract_footnotes(body_lines: list[str]) -> tuple[list[Footnote], list[str]]:
    footnotes: list[Footnote] = []
    kept: list[str] = []
    i = 0
    n = len(body_lines)
    def body_at(k: int) -> tuple[str, str] | None:
        if k >= n:
            return None
        fb = FOOTNOTE_BODY_RE.match(body_lines[k])
        if fb:
            return fb.group(1), fb.group(2)
        fu = FOOTNOTE_UNLABELED_BODY_RE.match(body_lines[k])
        if fu:
            return "unlabeled", fu.group(1)
        return None

    while i < n:
        m = FOOTNOTE_MARKER_RE.match(body_lines[i])
        fb = body_at(i + 1) if m and not body_lines[i].startswith("\x0c") else None
        if fb:
            marker = m.group(1)
            source, first = fb
            text_parts = [first.strip()]
            j = i + 2
            while j < n and body_lines[j].strip() != "" and not HEADER_RE.match(body_lines[j]):
                # continuation lines of a wrapped footnote are indented and don't
                # start a new footnote marker or a new field
                if FOOTNOTE_MARKER_RE.match(body_lines[j]) and body_at(j + 1):
                    break
                text_parts.append(body_lines[j].strip())
                j += 1
            footnotes.append(Footnote(marker=marker, source=source, text=join_wrapped(text_parts)))
            i = j
            continue
        kept.append(body_lines[i])
        i += 1
    return footnotes, kept


def clean_body_text(lines: list[str], footnote_markers: set[str] = frozenset()) -> str:
    """Line-structured body: one physical source line per line, indentation
    kept (verse blocks are the indented lines), no blank lines.

    Blank lines in this source's body are never paragraph breaks -- the PDF
    separates paragraphs by line breaks alone -- they are the residue of page
    breaks and extracted footnote blocks, and they fall mid-sentence or
    mid-verse as often as not ("I will / <page> / go forth"). Keeping them
    split verse quotations in two, so extract_verse_blocks() stopped at the
    page break and kept half the English verse (e.g. Dhp 388). Paragraphs
    are rebuilt from line lengths by reflow(), not from these.
    """
    text = "\n".join(lines)
    # U+000C (form feed): the PDF's page-break character, surviving pdftotext
    # extraction on stories that fall at or near a vagga boundary. Not
    # narrative content -- strip before it can propagate into vatthu,
    # desanavasane (a suffix of this same cleaned text), or embeddings.
    text = text.replace("\x0c", "")
    # PTS/Burlingame pagination crumbs, taking one adjacent space with them
    # so "merchant [28.147] Anāthapiṇḍika" doesn't become a double space.
    text = re.sub(r" ?(?:" + BRACKET_RE.pattern + r")", "", text)
    text = strip_footnote_markers(text, set(footnote_markers))
    out = []
    for ln in text.split("\n"):
        ln = ln.rstrip()
        if not ln.strip():
            continue
        indent = ln[: len(ln) - len(ln.lstrip(" "))]
        out.append(indent + re.sub(r" {2,}", " ", ln.lstrip(" ")))
    return "\n".join(out)


# A prose line shorter than this, ending in sentence-final punctuation, ends
# its paragraph. Justified prose lines in this source run 65-89 characters
# (the 60-64 bucket is mostly lines carrying a long unbreakable word).
PARAGRAPH_END_MAX_LEN = 62
_SENTENCE_END_RE = re.compile(r"[.!?:;”’)–]$")


# Indented lines are either verse (short) or block-quoted prose -- "Story of
# the Past" sections and quoted discourses, typeset indented at full width.
# No verse line in this source reaches this length; wrapped prose does.
VERSE_LINE_MAX_LEN = 55


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def reflow(text: str | None) -> str | None:
    """Turn line-structured body text into readable text: wrapped prose lines
    rejoined into paragraphs (blank line between paragraphs), each verse line
    kept on its own line with the typesetting indent removed."""
    if not text:
        return text
    lines = [ln.rstrip() for ln in text.split("\n") if ln.strip()]
    blocks: list[str] = []
    para: list[str] = []
    verse: list[str] = []

    def flush_para() -> None:
        if para:
            blocks.append(join_wrapped(para))
            para.clear()

    def flush_verse() -> None:
        if verse:
            blocks.append("\n".join(verse))
            verse.clear()

    def verse_like(ln: str) -> bool:
        if not is_indented(ln):
            return False
        s = ln.strip()
        # Pali verse lines run long ("24. Uṭṭhānavato satīmato sucikammassa
        # nisammakārino,") but never contain English function words
        return len(s) < VERSE_LINE_MAX_LEN or bool(NUMBERED_PALI_LINE_RE.match(ln)) or is_pali_text(s)

    def opens_prose(i: int) -> bool:
        # a short indented line that runs straight on (no closing
        # punctuation) into a full-width line at the same indent is the
        # first line of an indented paragraph, not a verse line
        ln = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        return (
            not re.search(r"[.,;:!?–—’”]$", ln)
            and _indent(nxt) == _indent(ln)
            and len(nxt.strip()) >= 60
            and not is_pali_text(nxt)
        )

    for i, ln in enumerate(lines):
        s = ln.strip()
        if not para and verse_like(ln) and not opens_prose(i):
            verse.append(s)
            continue
        flush_verse()
        # An indentation switch is only a block-quote boundary when the line
        # before it ends a sentence (checked below, one line ahead):
        # pdftotext sometimes shifts a whole page's margin, so mid-sentence
        # "Do not touch my / <page> /      portion, but..." must stay joined.
        para.append(ln)
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        ends_sentence = bool(_SENTENCE_END_RE.search(s))
        short = len(s) < PARAGRAPH_END_MAX_LEN - _indent(ln)
        if nxt is None or (ends_sentence and (short or verse_like(nxt) or is_indented(nxt) != is_indented(ln))):
            flush_para()
    flush_para()
    flush_verse()
    return "\n\n".join(blocks)


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
    # English verse lines with none of the above ("Those sages without
    # violence,", Dhp 225) otherwise read as Pali
    "those", "these", "without", "into", "should", "be", "been", "whose",
}
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def is_indented(line: str, min_indent: int = 3) -> bool:
    return line.strip() != "" and (len(line) - len(line.lstrip(" "))) >= min_indent


def classify_verse_line(line: str) -> str:
    """"pali", "english", or "unknown" for one line of a verse quotation.

    Weighs English function words against diacritic-bearing tokens rather
    than letting any single stopword decide: "so", "no", "a" are Pali words
    too ("karoti so tathattānaṁ yathā naṁ icchatī diso", Dhp 162, was read
    as English on its "so" alone). A line with neither signal is "unknown"
    and each caller keeps it with the block it is already in.
    """
    words = WORD_RE.findall(line.lower())
    english = sum(w in ENGLISH_STOPWORDS for w in words)
    pali = sum(any(c in PALI_CHARS for c in w) for w in words)
    if english == pali == 0:
        return "unknown"
    return "pali" if pali > english else "english"


def is_pali_text(line: str) -> bool:
    return classify_verse_line(line) == "pali"


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
        and classify_verse_line(lines[pali_end + 1]) != "english"
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

    def trim(t: str) -> str:
        # keep the first line's indent: it marks a verse line for reflow()
        return t.strip("\n").rstrip()

    nidana = None
    m = NIDANA_RE.match(cleaned_body)
    if m and m.end() < 600:
        nidana = trim(m.group(0))
    else:
        flags.append("nidana_not_detected")

    desanavasane = None
    starts = [m.start() for m in DESANAVASANE_START_RE.finditer(cleaned_body)]
    if starts:
        desanavasane = trim(cleaned_body[starts[-1] :])
        vatthu = trim(cleaned_body[: starts[-1]])
    else:
        flags.append("desanavasane_not_detected")
        vatthu = cleaned_body

    if nidana and vatthu.startswith(nidana):
        vatthu = trim(vatthu[len(nidana) :])

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

    # Pass 1: segment each story's lines and pull out the footnotes printed
    # inside its span.
    pre = []
    for k, (dhp_idx, header_idx, vagga_num, story_num, title_en, title_pali) in enumerate(headers):
        chunk_end = headers[k + 1][1] if k + 1 < len(headers) else len(lines)
        fields, stars_idx, body_start, meta_flags = parse_metadata(lines, dhp_idx + 1, chunk_end)
        # footnotes first: a note printed on a vagga title page (after the
        # cut point) still belongs to someone
        footnotes, body_lines_all = extract_footnotes(lines[body_start:chunk_end])
        body_lines, preface = cut_at_structural_boundary(body_lines_all)
        tail = body_lines_all[len(body_lines):]
        if any(COLOPHON_RE.match(ln) for ln in tail):
            # notes on the colophon (412-420: PTS story-count variants)
            # leave with it
            in_tail: set[str] = set()
            strip_footnote_markers("\n".join(tail), {fn.marker for fn in footnotes}, in_tail)
            footnotes = [fn for fn in footnotes if fn.marker not in in_tail]
        pre.append([fields, stars_idx, meta_flags, body_lines, footnotes, preface])

    # A vagga preface annotates the vagga's first story: keep it as that
    # story's footnote under the marker it carries, merged with any note
    # printed for the same marker (AJ's "this was originally a footnote").
    for k in range(len(pre) - 1):
        preface = pre[k][5]
        if not preface:
            continue
        text = join_wrapped([ln.strip() for ln in preface])
        all_markers = {fn.marker for fn in pre[k][4]}
        found: set[str] = set()
        text = strip_footnote_markers(text, all_markers, found)
        notes = [fn for fn in pre[k][4] if fn.marker in found]
        pre[k][4] = [fn for fn in pre[k][4] if fn.marker not in found]
        marker = min(found, key=int) if found else "preface"
        merged = " ".join([text] + [f"[{fn.source}: {fn.text}]" for fn in notes])
        pre[k + 1][4] = [Footnote(marker=marker, source="BG", text=merged)] + pre[k + 1][4]

    # Pass 2: clean. A footnote is printed at the foot of the page its marker
    # is on, and that page can end inside the next story's span (e.g. 1.1's
    # closing "assembled.14" has its note printed under story 1.2's opening
    # lines) -- so markers are resolved against the neighbours' footnotes as
    # well as the story's own. Footnote numbers are unique book-wide, so a
    # neighbour's marker can't collide with one of this story's own.
    found_by_story: list[set[str]] = []
    stories: list[Story] = []
    for k, (dhp_idx, header_idx, vagga_num, story_num, title_en, title_pali) in enumerate(headers):
        fields, stars_idx, meta_flags, body_lines, footnotes, _ = pre[k]
        dhp_verses, dhp_flag = find_dhp_verses(lines[dhp_idx])
        markers = {fn.marker for j in (k - 1, k, k + 1) if 0 <= j < len(pre) for fn in pre[j][4]}
        found: set[str] = set()

        body_raw = clean_body_text(body_lines, markers)
        strip_footnote_markers("\n".join(body_lines), markers, found)

        pali_verse, english_verse, pali_verse_number, verse_flags = extract_verse_blocks(body_raw, dhp_verses)
        nidana, desanavasane, vatthu, seg_flags = extract_nidana_desanavasane(body_raw)
        nidana, vatthu, desanavasane = reflow(nidana), reflow(vatthu), reflow(desanavasane)
        if english_verse:
            english_verse = strip_footnote_markers(english_verse, markers, found)
        for key in ("cst4_title", "burlingame_title", "compare", "synopsis", "cast"):
            if fields.get(key):
                fields[key] = strip_footnote_markers(fields[key], markers, found)
        title_en = strip_footnote_markers(title_en, markers, found)
        title_pali = strip_footnote_markers(title_pali, markers, found) if title_pali else title_pali
        found_by_story.append(found)

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

    # Move each footnote to the story whose text actually carries its marker,
    # when that isn't the story it was printed inside.
    for k, story in enumerate(stories):
        own = {fn.marker for fn in story.footnotes}
        for marker in sorted(found_by_story[k] - own, key=int):
            for j in (k - 1, k + 1):
                if not 0 <= j < len(stories) or marker in found_by_story[j]:
                    continue
                moving = [fn for fn in stories[j].footnotes if fn.marker == marker]
                if moving:
                    stories[j].footnotes = [fn for fn in stories[j].footnotes if fn.marker != marker]
                    story.footnotes = sorted(story.footnotes + moving, key=lambda fn: int(fn.marker))
                    break

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

    raw_text = raw_path.read_text(encoding="utf-8").translate(_GLYPH_FIX)
    stories = parse_stories(raw_text)
    story_dicts = [s.to_dict() for s in stories]

    applied = apply_corrections(story_dicts)
    if len(applied) != len(CORRECTIONS):
        missed = set(CORRECTIONS) - set(applied)
        print(f"WARNING: {len(missed)} corrections in corrections.py no longer match parser output: {missed}")
    typos_fixed = apply_text_corrections(story_dicts)
    if set(typos_fixed) != set(TEXT_CORRECTIONS):
        print(f"WARNING: typo corrections no longer found in parser output: {set(TEXT_CORRECTIONS) - set(typos_fixed)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for s in story_dicts:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    rep = report(stories)
    rep["hand_corrections_applied"] = applied
    rep["n_hand_corrections_applied"] = len(applied)
    rep["typo_corrections_applied"] = typos_fixed
    report_path.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Parsed {rep['n_stories']} stories, {rep['n_dhp_verses_total']} verse references.")
    print(f"Applied {len(applied)} hand-corrections (see corrections.py): {applied}")
    print(f"Wrote {out_path}")
    print(f"Wrote {report_path}")
    print(json.dumps(rep["flag_rates"], indent=2))


if __name__ == "__main__":
    main()
