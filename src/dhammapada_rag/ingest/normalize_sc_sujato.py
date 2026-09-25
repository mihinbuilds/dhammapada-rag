"""Stage 2 normalizer (dhammapada_fixes/corpus_rebuild_design.md): Bhikkhu
Sujato's English translation, owned solely by SuttaCentral bilara-data per
docs/corpus_source_ownership.md's Stage 1 table.

Writes data/normalized/sc_sujato.jsonl, one row per verse:
    {"verse": int, "english": str, "source_ref": [segment_key, ...]}

Reads only sources/external/sujato_en/ -- no other normalizer's output.
Shares _sc_segments.load_sc_segments() with normalize_sc_pali.py (parsing
logic only, not a data dependency between the two -- see that module's
docstring for the segmentation bug both sources share and this fixes).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest._sc_segments import load_sc_segments  # noqa: E402

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f]")
# bilara-data inline markup: "<j>" marks where a long line is split for
# verse display ("Here they’re tormented, <j>hereafter they’re tormented").
# It is layout, not text -- 12 of them leaked into english_sujato verbatim.
_MARKUP_RE = re.compile(r"</?[a-z]+>")


def _clean(text: str) -> str:
    text = _MARKUP_RE.sub("", text)
    return re.sub(r" {2,}", " ", text).strip()


def normalize() -> list[dict]:
    root = Path(__file__).resolve().parents[3]
    segments = load_sc_segments(root / "sources" / "external" / "sujato_en")

    rows = []
    for verse in range(1, 424):
        if verse not in segments:
            raise ValueError(f"Dhp {verse} missing from sources/external/sujato_en/")
        rows.append({
            "verse": verse,
            "english": _clean(segments[verse]["text"]),
            "source_ref": segments[verse]["source_ref"],
        })
    return rows


def validate(rows: list[dict]) -> None:
    if len(rows) != 423:
        raise ValueError(f"Expected 423 rows, got {len(rows)}")

    errors = []
    for r in rows:
        if not r["english"]:
            errors.append(f"Dhp {r['verse']}: empty english")
            continue
        if not r["source_ref"]:
            errors.append(f"Dhp {r['verse']}: empty source_ref")
        if _MARKUP_RE.search(r["english"]):
            errors.append(f"Dhp {r['verse']}: markup tag survived cleaning")
        cc = _CONTROL_CHAR_RE.findall(r["english"])
        if cc:
            errors.append(f"Dhp {r['verse']}: control character(s) {sorted(set(cc))!r}")
        if unicodedata.normalize("NFC", r["english"]) != r["english"]:
            errors.append(f"Dhp {r['verse']}: not NFC-normalized")

    if errors:
        raise ValueError(
            f"{len(errors)} row(s) failed sc_sujato's own contract:\n" + "\n".join(f"  {e}" for e in errors)
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "normalized" / "sc_sujato.jsonl"

    rows = normalize()
    validate(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {out_path} ({len(rows)} rows, validated)")


if __name__ == "__main__":
    main()
