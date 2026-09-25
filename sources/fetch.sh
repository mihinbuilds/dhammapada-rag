#!/usr/bin/env bash
# Fetch Ānandajoti Bhikkhu's two source editions and compare them with the
# pinned snapshot in sources/SHA256SUMS.
#
#   sources/fetch.sh --verify      check the committed files only (no network)
#   sources/fetch.sh [--out DIR]   download into DIR (default: a new temp dir)
#                                  and report which files differ from the pin
#
# Downloads never go into sources/ itself. Ānandajoti updates his files when he
# finds mistakes, so a fresh download can differ from the snapshot the corpus
# and evaluation were built from. Replacing the pinned files is a deliberate
# corpus rebuild, not something this script does. See data/raw/PROVENANCE.md.
#
# The Mahāsaṅgīti and Sujato sources (CC0, SuttaCentral bilara-data) are not
# covered here; their fetch is documented in sources/external/PROVENANCE.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMS="$HERE/SHA256SUMS"

PDF_URL="https://ancient-buddhist-texts.net/English-Texts/Dhamma-Verses-Comm/Dhamma-Verses-Comm.pdf"
INTERLINEAR_BASE="https://ancient-buddhist-texts.net/Texts-and-Translations/Dhammapada"

# Pinned entries, minus comments: "<sha256>  <path relative to sources/>".
pinned() { grep -v '^#' "$SUMS"; }

check_dir() {  # $1 = directory laid out like sources/
    local dir="$1" ok=0 changed=0 missing=0 sum path actual
    while read -r sum path; do
        if [[ ! -f "$dir/$path" ]]; then
            echo "MISSING  $path"; missing=$((missing + 1)); continue
        fi
        actual="$(sha256sum "$dir/$path" | cut -d' ' -f1)"
        if [[ "$actual" == "$sum" ]]; then
            ok=$((ok + 1))
        else
            echo "CHANGED  $path"; changed=$((changed + 1))
        fi
    done < <(pinned)
    echo "$ok match the pin, $changed changed, $missing missing"
    [[ $changed -eq 0 && $missing -eq 0 ]]
}

if [[ "${1:-}" == "--verify" ]]; then
    check_dir "$HERE"
    exit
fi

OUT=""
if [[ "${1:-}" == "--out" ]]; then
    OUT="${2:?--out needs a directory}"
elif [[ -n "${1:-}" ]]; then
    echo "usage: $0 [--verify | --out DIR]" >&2; exit 2
fi
OUT="${OUT:-$(mktemp -d)}"
mkdir -p "$OUT/external/anandajoti_interlinear"
if [[ "$(cd "$OUT" && pwd)" == "$HERE" ]]; then
    echo "refusing to download over the pinned snapshot in $HERE" >&2; exit 2
fi

echo "downloading into $OUT"
curl -fsSL -o "$OUT/Dhammapada-Attakatha.pdf" "$PDF_URL"
while read -r _ path; do
    [[ "$path" == external/anandajoti_interlinear/* ]] || continue
    curl -fsSL -o "$OUT/$path" "$INTERLINEAR_BASE/${path##*/}"
done < <(pinned)

check_dir "$OUT"
