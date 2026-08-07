"""Stage 2 normalizer (dhammapada_fixes/corpus_rebuild_design.md): the
Mahasangiti Pali root text, owned solely by SuttaCentral bilara-data per
docs/corpus_source_ownership.md's Stage 1 table.

Writes data/normalized/sc_pali.jsonl, one row per verse:
    {"verse": int, "pali": str, "source_ref": [segment_key, ...]}

Reads only sources/external/mahasangiti_pali/ -- no other normalizer's
output. Validates its own contract (row count, no control characters,
character set, no empty required fields) and fails loudly rather than
writing partial rows, per Stage 2's own instruction.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest._sc_segments import load_sc_segments  # noqa: E402

# Round 6's audit_corpus.py (Stage 0) found the design doc's proposed IAST-
# only charset too narrow: 22 verses legitimately carry curly quotation
# marks around reported speech ("Pāpaṁ me katan"ti) and one em dash. Widened
# here per that finding rather than repeating the false-positive.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f]")
_PALI_CHARSET_RE = re.compile(r"[^a-zāīūṁṃṅñṭḍṇḷ\s.,;'\-—“”]", re.IGNORECASE)


def normalize() -> list[dict]:
    root = Path(__file__).resolve().parents[3]
    segments = load_sc_segments(root / "sources" / "external" / "mahasangiti_pali")

    rows = []
    for verse in range(1, 424):
        if verse not in segments:
            raise ValueError(f"Dhp {verse} missing from sources/external/mahasangiti_pali/")
        rows.append({
            "verse": verse,
            "pali": segments[verse]["text"],
            "source_ref": segments[verse]["source_ref"],
        })
    return rows


def validate(rows: list[dict]) -> None:
    """Fail loudly. This is the normalizer's own contract, not a downstream
    join-time check -- per Stage 2, malformed rows should never reach
    data/normalized/ in the first place."""
    if len(rows) != 423:
        raise ValueError(f"Expected 423 rows, got {len(rows)}")

    errors = []
    for r in rows:
        if not r["pali"]:
            errors.append(f"Dhp {r['verse']}: empty pali")
            continue
        if not r["source_ref"]:
            errors.append(f"Dhp {r['verse']}: empty source_ref")
        cc = _CONTROL_CHAR_RE.findall(r["pali"])
        if cc:
            errors.append(f"Dhp {r['verse']}: control character(s) {sorted(set(cc))!r}")
        bad_chars = sorted(set(_PALI_CHARSET_RE.findall(r["pali"])))
        if bad_chars:
            errors.append(f"Dhp {r['verse']}: out-of-charset character(s) {bad_chars!r}")
        if unicodedata.normalize("NFC", r["pali"]) != r["pali"]:
            errors.append(f"Dhp {r['verse']}: not NFC-normalized")

    if errors:
        raise ValueError(
            f"{len(errors)} row(s) failed sc_pali's own contract:\n" + "\n".join(f"  {e}" for e in errors)
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out_path = root / "data" / "normalized" / "sc_pali.jsonl"

    rows = normalize()
    validate(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {out_path} ({len(rows)} rows, validated)")


if __name__ == "__main__":
    main()
