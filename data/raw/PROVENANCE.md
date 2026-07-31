# Provenance: data/raw/

## dhammapada-attakatha.txt

Extracted from `sources/Dhammapada-Attakatha.pdf` via:

```
pdftotext -layout sources/Dhammapada-Attakatha.pdf data/raw/dhammapada-attakatha.txt
```

- Tool: poppler `pdftotext` 26.07.0
- Extraction date: 2026-07-30
- Source PDF: "The Dhamma Verses Commentary" — E.W. Burlingame / Ānandajoti
  Bhikkhu, August 2024 revision. Title/Author/Subject per PDF metadata:
  Title="Dhamma Verses Commentary", Author="E.W. Burlingame;Anandajoti
  Bhikkhu", Subject="Translation of the Dhammapada Commentary". 1156 pages.
- `-layout` was used (not plain reading order) to preserve indentation, which
  distinguishes body text from indented footnotes and sub-story blocks, and
  keeps page running-headers/footers on their own lines for reliable removal
  during parsing.
- This file is a straight format conversion, not otherwise edited. Any
  correction of extraction artifacts happens downstream in
  `data/interim/`/`data/processed/`, never here.
