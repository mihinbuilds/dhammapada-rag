"""The Ānandajoti sources must match the pinned snapshot in sources/SHA256SUMS.

He corrects his files upstream when he finds mistakes, so a fresh download can
differ from the snapshot the corpus and evaluation were built from. Swapping
one in without a rebuild would change the corpus silently. These tests make
that swap fail loudly instead. See data/raw/PROVENANCE.md.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"


def _pinned() -> dict[str, str]:
    lines = (SOURCES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    return {
        path: digest
        for digest, path in (ln.split(maxsplit=1) for ln in lines if ln and not ln.startswith("#"))
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_covers_both_editions():
    pinned = _pinned()
    assert "Dhammapada-Attakatha.pdf" in pinned
    on_disk = {
        f"external/anandajoti_interlinear/{p.name}"
        for p in (SOURCES / "external" / "anandajoti_interlinear").glob("*.htm")
    }
    assert on_disk == {p for p in pinned if p.startswith("external/anandajoti_interlinear/")}


def test_sources_match_pinned_checksums():
    changed = [path for path, digest in _pinned().items() if _sha256(SOURCES / path) != digest]
    assert not changed, f"source files differ from the pinned snapshot: {changed}"


def test_provenance_records_agree_with_manifest():
    """The human-readable records must quote the same checksums as the manifest."""
    pinned = _pinned()
    provenance = (ROOT / "data" / "raw" / "PROVENANCE.md").read_text(encoding="utf-8")
    datasheet = (ROOT / "docs" / "datasheet.md").read_text(encoding="utf-8")
    pdf = pinned["Dhammapada-Attakatha.pdf"]
    assert pdf in provenance and pdf in datasheet
    for path, digest in pinned.items():
        if path.startswith("external/"):
            assert re.search(rf"{digest}\s+{re.escape(Path(path).name)}", provenance), path
