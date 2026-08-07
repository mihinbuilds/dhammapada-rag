"""Stage 2 normalizer (dhammapada_fixes/corpus_rebuild_design.md):
Anandajoti Bhikkhu's 2017 interlinear Pali-English gloss, owned solely by
that source per docs/corpus_source_ownership.md's Stage 1 table.

Writes data/normalized/aj_interlinear.jsonl, one row per verse:
    {"verse": int, "pali": str, "english": str, "notes": [str, ...],
     "source_ref": str}

Reuses parse_interlinear.py's parse_page() for the actual HTML parsing
(the verse-boundary/note-extraction logic already exists and is correct;
duplicating it here would risk the two drifting apart, exactly what this
rebuild exists to prevent) and adds what that script didn't track: which
of the 26 per-vagga HTML pages each verse came from, as source_ref -- the
HTML has no finer-grained per-verse anchor to point to (checked directly:
no `id` attributes, and the one `class="verseN"` div per page isn't keyed
to a Dhammapada verse number), so the page filename is the real available
precision, not an arbitrarily coarsened one.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest.parse_interlinear import PAGES, parse_page  # noqa: E402
from dhammapada_rag.vaggas import vagga_for_verse  # noqa: E402

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f]")

# Found comparing this normalizer's output against normalize_sc_pali.py's
# (both should describe the same verse's own words -- classify_pali_pair()
# in audit_corpus.py flagged 2 residual "boundary" cases after Stage 2's
# other fix, Dhp 51 and Dhp 327, in BOTH the pali and english fields).
# parse_interlinear.py's own docstring claims "the parser keeps the first
# occurrence in document order, which is always the verse's own canonical
# position" -- that claim is false for these two. Traced directly: Dhp 51's
# canonical home is 04-Flowers.htm (vagga 4), clean there -- but PAGES
# processes 01-Pairs.htm (vagga 1) first, and 01-Pairs.htm's OWN closing
# colophon ("<p class="Heading5"><b>Yamakavaggo Paṭhamo</b><br>The Chapter
# about the Pairs, the First</p>") is immediately followed by a "Related
# Verse(s) from the Dhammapada" cross-reference citing Dhp 51 for
# comparison -- none of these three `<p>` tags closes with a `[N]` marker,
# so all their text (the Pali-tagged heading, the bilingual chapter-name
# line's English too, and the citation heading) gets prepended to Dhp 51's
# citation right there, in BOTH languages. THAT contaminated citation, not
# the clean vagga-4 original, is what "keep the first occurrence" actually
# kept. Dhp 327 is the same pattern: canonical home 23-Elephant.htm, but
# 02-Heedfulness.htm (processed 2nd) cites it first, prefixed with vagga
# 2's own closing colophon in both languages.
#
# The general, principled fix -- not a per-string regex, since the leaked
# English text is a different chapter name each time and can't be pattern-
# matched generically -- is to make parse_interlinear.py's own stated
# invariant actually hold: prefer the occurrence whose PAGE is the verse's
# own canonical vagga (via dhammapada_rag.vaggas.vagga_for_verse(), the
# same ground truth ingest/validate.py already checks story vagga claims
# against) over any earlier-processed off-vagga citation, regardless of
# document order. This fixes both languages at once, from the actual root
# cause, rather than guessing at which strings happen to leak.
#
# Fixed HERE, in this normalizer's own transform, not in parse_interlinear.py
# itself: same scope discipline as normalize_aj_stories.py's control-
# character strip -- clean this source's own boundary defect at the Stage 2
# layer rather than editing the already-shipped upstream parser that
# data/processed/interlinear_gloss.jsonl (the live pipeline) still depends
# on unchanged. Porting this fix into parse_interlinear.py itself is a
# legitimate follow-up, not done here.


def normalize() -> list[dict]:
    root = Path(__file__).resolve().parents[3]
    src_dir = root / "sources" / "external" / "anandajoti_interlinear"

    by_verse: dict[int, dict] = {}
    from_own_vagga: dict[int, bool] = {}
    for page in PAGES:
        page_vagga = int(page[:2])
        html = (src_dir / f"{page}.htm").read_text(encoding="utf-8")
        for v in parse_page(html):
            verse = v["verse"]
            is_own_vagga = vagga_for_verse(verse).number == page_vagga
            if verse in by_verse and not (is_own_vagga and not from_own_vagga[verse]):
                continue  # already have an occurrence at least as good as this one
            by_verse[verse] = {
                "verse": verse,
                "pali": v["pali"],
                "english": v["english"],
                "notes": v["notes"],
                "source_ref": f"{page}.htm",
            }
            from_own_vagga[verse] = is_own_vagga

    missing = sorted(set(range(1, 424)) - set(by_verse))
    if missing:
        raise ValueError(f"{len(missing)} verse(s) not found in any interlinear page: {missing}")

    return [by_verse[v] for v in range(1, 424)]


def validate(rows: list[dict]) -> None:
    if len(rows) != 423:
        raise ValueError(f"Expected 423 rows, got {len(rows)}")

    errors = []
    for r in rows:
        for field in ("pali", "english"):
            if not r[field]:
                errors.append(f"Dhp {r['verse']}: empty {field}")
                continue
            cc = _CONTROL_CHAR_RE.findall(r[field])
            if cc:
                errors.append(f"Dhp {r['verse']}: control character(s) in {field}: {sorted(set(cc))!r}")
            if unicodedata.normalize("NFC", r[field]) != r[field]:
                errors.append(f"Dhp {r['verse']}: {field} not NFC-normalized")
        if not r["source_ref"]:
            errors.append(f"Dhp {r['verse']}: empty source_ref")
        # notes is legitimately empty for many verses -- not a required field

    if errors:
        raise ValueError(
            f"{len(errors)} row(s) failed aj_interlinear's own contract:\n"
            + "\n".join(f"  {e}" for e in errors)
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "normalized" / "aj_interlinear.jsonl"

    rows = normalize()
    validate(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {out_path} ({len(rows)} rows, validated)")


if __name__ == "__main__":
    main()
