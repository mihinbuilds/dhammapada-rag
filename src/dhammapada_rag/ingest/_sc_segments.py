"""Shared segment-loading logic for SuttaCentral bilara-data JSON directories
(`sources/external/mahasangiti_pali/`, `sources/external/sujato_en/`).

Not a violation of Stage 2's "separate script per source, none of them reads
another's output" (`dhammapada_fixes/corpus_rebuild_design.md`): that rule is
about *data* independence between normalizers (sc_pali.jsonl must not be
built from sc_sujato.jsonl or vice versa), not about code reuse. Both
SuttaCentral sources share one segmentation scheme and one bug in it; fixing
the bug identically in two hand-duplicated copies is exactly the kind of
silent drift this whole rebuild exists to prevent.

THE BUG, found while writing Stage 2 by reading the raw segment keys
directly (not assumed from Stage 0's already-normalized-output symptom):

1. Vagga-final colophon folded into the last verse's own segment range.
   dhp423 (the Dhammapada's very last verse) carries segments `dhp423:1`
   through `dhp423:57` -- but the verse itself is only 6 lines
   (`dhp423:1`-`dhp423:6`). `dhp423:7` onward is the closing colophon of
   the entire 26-vagga book ("Brāhmaṇavaggo chabbīsatimo" = "the 26th
   chapter, on Brahmins", then a full enumeration of every vagga's story
   count and verse count). This isn't a chunking-time contamination this
   project introduced -- it is how SuttaCentral's own segmentation
   allocates trailing book-level content: onto the last verse's number,
   with no distinct segment-key marker separating "verse" from "colophon."
   Every vagga-final verse (26 of them, one per vagga) carries its own
   vagga-name colophon the same way, at a smaller scale (e.g. dhp20 carries
   "Yamakavaggo paṭhamo." after its own 6 lines).

2. A second story's title header embedded mid-sequence. dhp416 has two
   stories (26.33, 26.34 -- already a known, documented legitimate
   duplicate, see docs/evaluation.md). SuttaCentral's Pali file inserts the
   second story's title as segment `dhp416:5.0` ("Jotikattheravatthu"),
   sitting between `dhp416:4` and `dhp416:6` in the SAME verse's segment
   range. The existing `load_segmented_json_dir()` (build_verses.py)
   excludes only segments literally equal to "0" or starting with "0." --
   it does not exclude "5.0", so this title header was silently
   concatenated into the verse text. (Sujato's English file omits this
   specific segment rather than mistranslating it -- an asymmetry between
   the two sources worth knowing, not itself a bug this loader needs to
   paper over.)

Both are fixed here at the source, not downstream: a normalizer that lets
book back-matter or the wrong story's title into a field labeled "the
verse's own words" isn't normalizing, it's laundering the defect.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SEGMENT_RE = re.compile(r"^dhp(\d+):(.+)$")

# Fix 2: a segment key like "5.0" (not "0" or "0.N") is a secondary story's
# title header inserted mid-sequence, not verse text. This is DISTINCT from
# the existing "0"/"0.*" exclusion (that catches the verse's OWN leading
# nikaya/vagga/title header) -- "N.0" for N > 0 is a second story's header
# appearing partway through an already-started verse.
_MID_SEQUENCE_TITLE_RE = re.compile(r"^\d+\.0$")

# Fix 1: a segment whose ENTIRE text is "<word ending in -vaggo> <ordinal
# word>[.]" is a vagga-name colophon marker -- e.g. "Brāhmaṇavaggo
# chabbīsatimo.", "Yamakavaggo paṭhamo.". "vaggo" (chapter/section) does not
# otherwise appear as a bare two-word sentence inside real verse content;
# every occurrence checked while writing this loader was this exact
# colophon pattern. Once this fires for a verse's segments (sorted in
# ascending order), that segment and every later one are excluded --
# everything past this point is the book's back matter, not the verse.
_VAGGA_COLOPHON_RE = re.compile(r"^\S*vaggo\s+\S+\.?\s*$", re.IGNORECASE)


def _sort_key(line_key: str) -> tuple[int, ...]:
    return tuple(int(p) for p in line_key.split("."))


def load_sc_segments(dir_path: Path) -> dict[int, dict]:
    """Join `dhp<verse>:<line>` segments into one text string per verse.

    Returns {verse: {"text": str, "source_ref": [segment_key, ...]}} --
    source_ref lists exactly the segment keys that contributed to `text`,
    in the order used, so a value can be checked against the raw JSON
    directly rather than trusted blind (the design doc's own stated purpose
    for this field).
    """
    raw: dict[int, dict[str, str]] = {}
    for f in sorted(dir_path.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key, text in data.items():
            m = SEGMENT_RE.match(key)
            if not m:
                continue
            verse = int(m.group(1))
            line_key = m.group(2)
            if line_key == "0" or line_key.startswith("0."):
                continue  # this verse's own nikaya/vagga/title header
            if _MID_SEQUENCE_TITLE_RE.match(line_key):
                continue  # a second story's title header (bug fix 2)
            raw.setdefault(verse, {})[line_key] = text

    out: dict[int, dict] = {}
    for verse, lines in raw.items():
        ordered_keys = sorted(lines, key=_sort_key)
        kept_keys: list[str] = []
        kept_text: list[str] = []
        for k in ordered_keys:
            text = lines[k].strip()
            if _VAGGA_COLOPHON_RE.match(text):
                break  # colophon marker: this and everything after is back matter (bug fix 1)
            kept_keys.append(k)
            kept_text.append(text)
        out[verse] = {
            "text": " ".join(kept_text),
            "source_ref": [f"dhp{verse}:{k}" for k in kept_keys],
        }
    return out
