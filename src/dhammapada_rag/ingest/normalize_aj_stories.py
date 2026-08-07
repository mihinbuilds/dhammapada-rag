"""Stage 2 normalizer (dhammapada_fixes/corpus_rebuild_design.md): story
titles, grouping, and narrative sections, owned solely by Anandajoti
Bhikkhu's 2024 revision PDF per docs/corpus_source_ownership.md's Stage 1
table -- and, per that table's "the PDF stops owning the Pali" consequence,
NOTHING ELSE from this source. `pali_verse`/`english_verse` (the PDF's own
inline verse quotations) are deliberately excluded from this row shape;
Stage 4's join, if it happens, keeps them as a separate narrative-quote
field the way build_verses.py already does, not as this source's
contribution to the verse's canonical text.

Writes data/normalized/aj_stories.jsonl, one row per story:
    {"group_id": str, "title": {"en", "pali", "cst4", "burlingame"},
     "sections": {"nidana", "vatthu", "desanavasane"}, "verses": [int, ...],
     "source_ref": str}

Reads data/processed/stories.jsonl -- already a PDF-only extraction
(parse_stories.py never blends in another source), so this reshapes rather
than re-parses. Re-deriving story-boundary parsing from the raw PDF text a
second time here would risk exactly the two-implementations drift Stage 2
exists to prevent; parse_stories.py's extraction logic is the one place
that should own it.

source_ref limitation, stated rather than papered over: parse_stories.py
does not currently track which PDF page a story came from, so the finest
available pointer back to the source is the group_id itself (which
ingest/parse_stories.py can be grepped for, or the PDF's own table of
contents searched by title). A page-number source_ref would need that
script extended to track it -- not done here, since this script's job is
to normalize what already exists, not extend the upstream parser.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f]")


def _clean(s: str | None) -> str | None:
    """Strip control characters from a text field.

    Stage 0's audit (docs/corpus_audit.md, check 2) already found and
    diagnosed this exact defect: `\\x0c` (PDF page-break form feed) in
    `desanavasane`/`body_raw` on 22 vagga-final stories, upstream in
    data/processed/stories.jsonl's PDF extraction, not introduced here.
    Confirmed narrow and cosmetic there; stripped here at this normalizer's
    own boundary rather than either (a) silently passing it through, which
    validate() below would then correctly reject anyway, or (b) editing
    parse_stories.py / regenerating the live pipeline's stories.jsonl,
    which is a bigger, separately-scoped change this normalizer has no
    business making on its own. Same pattern as Round 6, Task Q's prompt-
    boundary strip: fix at the boundary, then validate nothing survived.
    """
    return _CONTROL_CHAR_RE.sub("", s) if s is not None else None


def normalize() -> list[dict]:
    root = Path(__file__).resolve().parents[3]
    stories_path = root / "data" / "processed" / "stories.jsonl"
    stories = [json.loads(l) for l in stories_path.read_text(encoding="utf-8").splitlines()]

    rows = []
    for s in stories:
        rows.append({
            "group_id": s["group_id"],
            "title": {
                "en": _clean(s.get("title_en")),
                "pali": _clean(s.get("title_pali")),
                "cst4": _clean(s.get("cst4_title")),
                "burlingame": _clean(s.get("burlingame_title")),
            },
            "sections": {
                "nidana": _clean(s.get("nidana")),
                "vatthu": _clean(s.get("vatthu")),
                "desanavasane": _clean(s.get("desanavasane")),
            },
            "verses": s["dhp_verses"],
            "source_ref": f"sources/Dhammapada-Attakatha.pdf, story {s['group_id']}",
        })
    return rows


def _strings_in(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_strings_in(v))
        return out
    return []


def validate(rows: list[dict]) -> None:
    if not (295 <= len(rows) <= 315):  # design doc's own "~305 rows" estimate, with slack
        raise ValueError(f"Expected roughly 305 rows, got {len(rows)} -- check data/processed/stories.jsonl")

    errors = []
    seen_group_ids: set[str] = set()
    for r in rows:
        if not r["group_id"]:
            errors.append("row with empty group_id")
            continue
        if r["group_id"] in seen_group_ids:
            errors.append(f"{r['group_id']}: duplicate group_id in this file")
        seen_group_ids.add(r["group_id"])

        if not r["title"]["en"]:
            errors.append(f"{r['group_id']}: empty title.en (required; other title variants are optional)")
        if not r["sections"]["vatthu"]:
            errors.append(f"{r['group_id']}: empty sections.vatthu (required; nidana/desanavasane are optional)")
        if not r["verses"]:
            errors.append(f"{r['group_id']}: empty verses list")

        for s in _strings_in(r["title"]) + _strings_in(r["sections"]):
            cc = _CONTROL_CHAR_RE.findall(s)
            if cc:
                errors.append(f"{r['group_id']}: control character(s) {sorted(set(cc))!r}")
            if unicodedata.normalize("NFC", s) != s:
                errors.append(f"{r['group_id']}: a field is not NFC-normalized")

    if errors:
        raise ValueError(
            f"{len(errors)} row(s) failed aj_stories's own contract:\n" + "\n".join(f"  {e}" for e in errors[:50])
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "normalized" / "aj_stories.jsonl"

    rows = normalize()
    validate(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {out_path} ({len(rows)} rows, validated)")


if __name__ == "__main__":
    main()
