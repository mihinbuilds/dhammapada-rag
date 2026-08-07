"""Stage 5 (dhammapada_fixes/corpus_rebuild_design.md): validation gates.

Runs against Stage 3/4's own artifacts -- data/normalized/verses_joined.json
(Stage 4's provenance-tagged join, via join_verses.join()) and
data/normalized/alignment_table.json (Stage 3, via build_alignment_table.
build()) -- not data/processed/, which Stage 0's audit_corpus.py already
covers as read-only diagnostics on the pre-rebuild corpus. Title/body
coherence (gate 7) is the one exception: it's a property of stories.jsonl's
narrative prose, which the rebuild track doesn't re-derive (aj_stories.jsonl
carries only title/verses/sections, not vatthu/synopsis), so it runs against
data/processed/stories.jsonl directly, same source Stage 0 used.

Per the design doc: "Fail the build on 1-4. Warn and record on 5-7." Gates
1-4 raise GateFailure; run_gates() catches nothing -- main() decides what a
failure means (nonzero exit), this module just tells the truth.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.ingest.audit_corpus import (  # noqa: E402
    check_title_body_coherence,
    classify_pali_pair,
)
from dhammapada_rag.ingest.build_alignment_table import build as build_alignment_table  # noqa: E402
from dhammapada_rag.ingest.join_verses import _SOURCE_NAMES, join  # noqa: E402
from dhammapada_rag.vaggas import VAGGAS, vagga_for_verse  # noqa: E402

HARD_GATES = (1, 2, 3, 4)
WARN_GATES = (5, 6, 7)


class GateFailure(Exception):
    """Raised by main() when a hard gate (1-4) fails. Not raised by the gate
    functions themselves -- each returns a report dict with `passed: bool`
    so run_gates() can collect all seven results before anything decides to
    stop the build."""


# --------------------------------------------------------------------------
# Gate 1 -- structure
# --------------------------------------------------------------------------

def gate_1_structure(records: list[dict]) -> dict:
    """423 verses, 26 vaggas, boundaries matching vaggas.py, no gaps.

    join() always emits exactly one record per verse 1-423 by construction
    (it iterates `range(1, 424)`), so the part actually worth checking here
    is that each record's own `vagga` block agrees with vaggas.py's ground
    truth -- a drift there would mean join_verses.py computed it wrong, not
    that the corpus itself has a gap."""
    verses = sorted(r["verse"] for r in records)
    missing = sorted(set(range(1, 424)) - set(verses))
    duplicates = sorted({v for v in verses if verses.count(v) > 1})

    vagga_mismatches = []
    for r in records:
        expected = vagga_for_verse(r["verse"])
        if r["vagga"]["number"] != expected.number or r["vagga"]["pali"] != expected.name_pali:
            vagga_mismatches.append({
                "verse": r["verse"],
                "recorded": r["vagga"],
                "expected": {"number": expected.number, "pali": expected.name_pali},
            })

    passed = not missing and not duplicates and not vagga_mismatches and len(VAGGAS) == 26
    return {
        "passed": passed,
        "n_verses": len(verses),
        "n_vaggas": len(VAGGAS),
        "missing_verses": missing,
        "duplicate_verses": duplicates,
        "vagga_mismatches": vagga_mismatches,
    }


# --------------------------------------------------------------------------
# Gate 2 -- field ownership
# --------------------------------------------------------------------------

def gate_2_field_ownership(records: list[dict]) -> dict:
    """Every populated field's `source` matches docs/corpus_source_ownership
    .md's table, reused here as join_verses._SOURCE_NAMES so there is one
    mapping, not two that can drift. No exceptions, no fallbacks -- the
    entire point of the rebuild (design doc, opening paragraph)."""
    violations = []
    for r in records:
        for field, entry in r["text"].items():
            expected = _SOURCE_NAMES.get(field)
            if expected is None:
                violations.append({
                    "verse": r["verse"], "field": field,
                    "problem": "field not in the ownership table at all",
                })
            elif entry["source"] != expected:
                violations.append({
                    "verse": r["verse"], "field": field,
                    "problem": f"source={entry['source']!r}, expected {expected!r}",
                })
    return {"passed": not violations, "n_checked": len(records) * 4, "violations": violations}


# --------------------------------------------------------------------------
# Gate 3 -- encoding
# --------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f]")

# Widened from the design doc's own draft set per docs/corpus_audit.md check
# 3's finding: curly quotes and an em dash in pali_mahasangiti are genuine
# source typography marking reported speech (Dhp 17: "Papam me katan"ti),
# not OCR residue -- the design doc's own assumption doesn't hold for this
# corpus, so a hard gate using the narrower set would fail 22 correct verses.
_PALI_CHARSET_RE = re.compile(r"[^a-zāīūṁṃṅñṭḍṇḷ\s.,;'\-‘’“”—]", re.IGNORECASE)


def gate_3_encoding(records: list[dict]) -> dict:
    non_nfc = []
    control_chars = []
    charset_violations = []
    for r in records:
        for field, entry in r["text"].items():
            value = entry["value"]
            if unicodedata.normalize("NFC", value) != value:
                non_nfc.append({"verse": r["verse"], "field": field})
            found = sorted(set(_CONTROL_CHAR_RE.findall(value)))
            if found:
                control_chars.append({
                    "verse": r["verse"], "field": field,
                    "codepoints": [f"U+{ord(c):04X}" for c in found],
                })
            # Restricted to pali_mahasangiti, matching Stage 0's own scope
            # (audit_corpus.check_pali_charset): interlinear_pali is a
            # different edition with legitimate notational conventions of
            # its own (breve vowels marking metrically short vowels, its
            # own punctuation) that this IAST-focused set was never meant
            # to police -- checked here empirically before narrowing: an
            # earlier version of this gate that also checked
            # interlinear_pali flagged 65 verses, all breve vowels/
            # punctuation, zero genuine damage.
            if field == "pali_mahasangiti":
                offenders = sorted(set(_PALI_CHARSET_RE.findall(value)))
                if offenders:
                    charset_violations.append({
                        "verse": r["verse"], "field": field,
                        "offending_characters": offenders,
                        "codepoints": [f"U+{ord(c):04X}" for c in offenders],
                    })
    passed = not non_nfc and not control_chars and not charset_violations
    return {
        "passed": passed,
        "non_nfc": non_nfc,
        "control_characters": control_chars,
        "pali_charset_violations": charset_violations,
    }


# --------------------------------------------------------------------------
# Gate 4 -- alignment closure
# --------------------------------------------------------------------------

def gate_4_alignment_closure() -> dict:
    """Union of dhp_verses over the alignment table (Stage 3) must equal
    1..423 exactly. Duplicates are listed, not failed -- the design doc's
    own instruction: "some are legitimate (Dhp 416 has two stories)."""
    _, report = build_alignment_table()
    return {
        "passed": report["closure_ok"],
        "n_verses_covered": report["n_verses_covered"],
        "missing_verses": report["missing_verses"],
        "duplicated_verses": report["duplicated_verses"],
    }


# --------------------------------------------------------------------------
# Gate 5 -- metrical sanity (warn only)
# --------------------------------------------------------------------------

_PALI_VOWEL_RE = re.compile(r"[aāiīuūeo]", re.IGNORECASE)
# Genuine Dhammapada metres run from 8 (siloka pada) to 11 (tutthubha pada)
# syllables; real variety exists beyond that, so this is deliberately wide
# -- per the design doc, "a pada coming in at 3 or 19 syllables is almost
# always truncation or OCR damage," not a pada at 6 or 13.
_MIN_SYLLABLES, _MAX_SYLLABLES = 4, 18


def gate_5_metrical_sanity(records: list[dict]) -> dict:
    anomalies = []
    n_padas = 0
    for r in records:
        text = r["text"]["pali_mahasangiti"]["value"]
        for pada in re.split(r"[,;]", text):
            pada = pada.strip()
            if not pada:
                continue
            n_padas += 1
            n_syllables = len(_PALI_VOWEL_RE.findall(pada))
            if n_syllables < _MIN_SYLLABLES or n_syllables > _MAX_SYLLABLES:
                anomalies.append({"verse": r["verse"], "pada": pada, "n_syllables": n_syllables})
    return {
        "passed": True,  # warn-only per the design doc; never fails the build
        "n_padas_checked": n_padas,
        "n_anomalies": len(anomalies),
        "anomaly_rate": round(len(anomalies) / n_padas, 4) if n_padas else None,
        "anomalies": anomalies,
    }


# --------------------------------------------------------------------------
# Gate 6 -- cross-source agreement (warn only, record the rate)
# --------------------------------------------------------------------------

def gate_6_cross_source_agreement(records: list[dict]) -> dict:
    exact = boundary = distinct = 0
    for r in records:
        a = r["text"]["pali_mahasangiti"]["value"]
        b = r["text"]["interlinear_pali"]["value"]
        tier = classify_pali_pair(a, b)
        if tier == "exact":
            exact += 1
        elif tier == "boundary":
            boundary += 1
        else:
            distinct += 1
    n = len(records)
    return {
        "passed": True,  # warn-only; a high distinct rate is a finding, not a build blocker
        "n_verses": n,
        "n_exact": exact,
        "n_boundary_artifact": boundary,
        "n_distinct": distinct,
        "exact_rate": round(exact / n, 4) if n else None,
        "distinct_rate": round(distinct / n, 4) if n else None,
    }


# --------------------------------------------------------------------------
# Gate 7 -- title/body coherence (warn only)
# --------------------------------------------------------------------------

def gate_7_title_body_coherence(stories: list[dict]) -> dict:
    """Reuses audit_corpus.check_title_body_coherence rather than
    reimplementing it -- the design doc calls this "the Stage 0 check, run
    permanently as a gate," not a second, independently-drifting one.
    Runs against data/processed/stories.jsonl (vatthu/synopsis live there,
    not in aj_stories.jsonl -- Stage 2's normalizer deliberately narrowed
    its own scope to title/verses/sections, per docs/corpus_normalization
    .md)."""
    hits = check_title_body_coherence(stories)
    return {
        "passed": True,  # warn-only per the design doc
        "n_flagged": len(hits),
        "flagged": hits,
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run_gates(root: Path) -> dict:
    records = join()
    stories = [
        json.loads(l)
        for l in (root / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    gates = {
        "1_structure": gate_1_structure(records),
        "2_field_ownership": gate_2_field_ownership(records),
        "3_encoding": gate_3_encoding(records),
        "4_alignment_closure": gate_4_alignment_closure(),
        "5_metrical_sanity": gate_5_metrical_sanity(records),
        "6_cross_source_agreement": gate_6_cross_source_agreement(records),
        "7_title_body_coherence": gate_7_title_body_coherence(stories),
    }
    hard_gate_names = ("1_structure", "2_field_ownership", "3_encoding", "4_alignment_closure")
    hard_failures = [name for name in hard_gate_names if not gates[name]["passed"]]
    return {"gates": gates, "hard_failures": hard_failures, "build_ok": not hard_failures}


def render_markdown(report: dict) -> str:
    g = report["gates"]
    lines = [
        "# Corpus validation gates (Stage 5)",
        "",
        "Generated by `dhammapada_rag.ingest.validation_gates`, per "
        "`dhammapada_fixes/corpus_rebuild_design.md`'s Stage 5. Runs against "
        "Stage 3/4's own artifacts (`data/normalized/verses_joined.json`, "
        "`alignment_table.json`), not `data/processed/` -- see "
        "`docs/corpus_audit.md` for the pre-rebuild diagnostic this "
        "supersedes as a permanent, re-runnable check. Gates 1-4 fail the "
        "build; 5-7 warn and record.",
        "",
        f"**Build result: {'PASS' if report['build_ok'] else 'FAIL'}**"
        + (f" -- failing gate(s): {', '.join(report['hard_failures'])}" if report["hard_failures"] else ""),
        "",
    ]

    s = g["1_structure"]
    lines += [
        "## Gate 1 -- Structure",
        "",
        f"{s['n_verses']}/423 verses, {s['n_vaggas']}/26 vaggas. "
        f"Missing: {s['missing_verses']}. Duplicates: {s['duplicate_verses']}. "
        f"Vagga mismatches: {len(s['vagga_mismatches'])}.",
        f"**{'PASS' if s['passed'] else 'FAIL'}**",
        "",
    ]

    o = g["2_field_ownership"]
    lines += [
        "## Gate 2 -- Field ownership",
        "",
        f"{o['n_checked']} (verse, field) pairs checked against "
        "docs/corpus_source_ownership.md's table. Violations: "
        f"{len(o['violations'])}.",
        f"**{'PASS' if o['passed'] else 'FAIL'}**",
        "",
    ]

    e = g["3_encoding"]
    lines += [
        "## Gate 3 -- Encoding",
        "",
        f"Non-NFC values: {len(e['non_nfc'])}. Control characters: "
        f"{len(e['control_characters'])}. Pali charset violations "
        f"(widened per corpus_audit.md check 3 to allow curly quotes/em "
        f"dash as genuine source typography): {len(e['pali_charset_violations'])}.",
        f"**{'PASS' if e['passed'] else 'FAIL'}**",
        "",
    ]

    c = g["4_alignment_closure"]
    lines += [
        "## Gate 4 -- Alignment closure",
        "",
        f"Covered: {c['n_verses_covered']}/423. Missing: {c['missing_verses']}. "
        f"Duplicated (listed, not failed): {c['duplicated_verses']}.",
        f"**{'PASS' if c['passed'] else 'FAIL'}**",
        "",
    ]

    m = g["5_metrical_sanity"]
    lines += [
        "## Gate 5 -- Metrical sanity (warning-only)",
        "",
        f"{m['n_anomalies']}/{m['n_padas_checked']} pada-segments "
        f"(rate {m['anomaly_rate']}) fall outside {_MIN_SYLLABLES}-"
        f"{_MAX_SYLLABLES} syllables. Heuristic flag per the design doc, "
        "not proof of damage -- the Dhammapada has genuine metrical variety.",
    ]
    if m["anomalies"]:
        lines.append("")
        for a in m["anomalies"][:20]:
            lines.append(f"- Dhp {a['verse']} ({a['n_syllables']} syll.): `{a['pada']}`")
        if len(m["anomalies"]) > 20:
            lines.append(f"- ... and {len(m['anomalies']) - 20} more (see the JSON report)")
    lines.append("")

    x = g["6_cross_source_agreement"]
    lines += [
        "## Gate 6 -- Cross-source agreement (warning-only)",
        "",
        f"Of {x['n_verses']} verses: **{x['n_exact']} exact** "
        f"(rate {x['exact_rate']}), {x['n_boundary_artifact']} boundary-"
        f"artifact, **{x['n_distinct']} distinct** (rate {x['distinct_rate']}). "
        "See docs/corpus_normalization.md's \"measured effect\" table for "
        "the pre/post Stage 2 comparison -- the distinct tier is mostly "
        "genuine cross-edition variance, not corpus damage.",
        "",
    ]

    t = g["7_title_body_coherence"]
    lines += [
        "## Gate 7 -- Title/body coherence (warning-only)",
        "",
        f"{t['n_flagged']} stories where no proper noun in `title_en` "
        "appears in `vatthu`/`synopsis`. See docs/corpus_audit.md's check 1 "
        "for the known-false-positive caveat (23.1).",
    ]
    for h in t["flagged"]:
        lines.append(f"- **{h['group_id']}** — \"{h['title_en']}\"")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    report = run_gates(root)

    json_path = root / "data" / "normalized" / "validation_gates_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = root / "docs" / "corpus_validation.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for name, gate in report["gates"].items():
        print(f"  {name}: {'PASS' if gate['passed'] else 'FAIL'}")

    if not report["build_ok"]:
        print(f"\nBUILD FAILED -- hard gate(s) {report['hard_failures']} did not pass.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
