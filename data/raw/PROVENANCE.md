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
- Permission: written permission from Ānandajoti Bhikkhu, 2026-09-25, to use
  the text and release derived data under CC BY-SA 4.0. Recorded verbatim in
  [`sources/PERMISSION.md`](../../sources/PERMISSION.md).
- `-layout` was used (not plain reading order) to preserve indentation, which
  distinguishes body text from indented footnotes and sub-story blocks, and
  keeps page running-headers/footers on their own lines for reliable removal
  during parsing.
- This file is a straight format conversion, not otherwise edited. Any
  correction of extraction artifacts happens downstream in
  `data/interim/`/`data/processed/`, never here.

## Source snapshot (pinned)

The corpus, alignment table, story numbering, titles and narrative text all
derive from the snapshot below. Ānandajoti Bhikkhu updates his files when he
finds mistakes (see [`sources/PERMISSION.md`](../../sources/PERMISSION.md)),
so the files he publishes now may differ from these. A discrepancy between
this corpus and a newer upstream file may be his correction, not a parsing
error here. Upstream corrections made after this snapshot are not
incorporated. Do not replace these files with a fresh download without
rebuilding and re-evaluating the corpus.

### `sources/Dhammapada-Attakatha.pdf`

- Edition: *The Dhamma Verses Commentary*, E.W. Burlingame / Ānandajoti
  Bhikkhu, revised translation, page dated "updated: August, 2024".
- Source URL: `https://ancient-buddhist-texts.net/English-Texts/Dhamma-Verses-Comm/Dhamma-Verses-Comm.pdf`.
  The original download URL was not logged. This URL was identified on
  2026-09-25: the file it serves has exactly this file's size (7,414,143
  bytes), and its `Last-Modified` is 2025-11-21, before the snapshot date. A
  size match is strong evidence but not proof of identity; the file was not
  re-downloaded to compare checksums.
- Snapshot date: **2026-07-30**. The download date was not logged. This is
  the extraction date above, the earliest recorded date the file existed
  locally, and the file is in the baseline commit `4e57cd9` (2026-07-31). The
  file's mtime cannot be used: it is the date of the git checkout.
- SHA-256: `ec4c81dbd31c5b22707353acaa0ab9879031d881aa5cdd4f5da015e46c06bc2c`

### `sources/external/anandajoti_interlinear/` (27 HTML files)

- Edition: *Dhammapada* interlinear Pāli-English edition, Ānandajoti
  Bhikkhu, 2nd edition, November 2017.
- Source URL: `https://ancient-buddhist-texts.net/Texts-and-Translations/Dhammapada/`
  (`/tt/Dhammapada/`, the page cited in the permission, redirects here).
- Snapshot date: **2026-07-30**, the fetch date logged in
  `sources/external/PROVENANCE.md`.
- SHA-256 of each file, byte-for-byte as fetched (`.gitattributes` keeps
  `sources/**` unconverted, so these hold on any checkout):

```
57c6fe0fe084eb0b3fc515254ee1763120e7d4d0b5ebb51ea9342f9025975675  00-Introduction.htm
726cbd04db365e01b5a11ec12d3bb2dd53cbaa33475aeb10ab593769ee35e714  01-Pairs.htm
16ef4a3be62305b3a4f4e8b5c9fc51d06ee6ec9164c8494939bdcc250c40d827  02-Heedfulness.htm
6b7f67e530468ac700eae73684b3bec7132a84270b312da1c1c0b01b3fc8a1ed  03-Mind.htm
2999674096858f8607d42c605fb968f06431cbe2b42f632c0c50544343bc5f8c  04-Flowers.htm
b32e93437c4eae1ccc9917a819da3f3ff345750f060f0744c9d7795376682557  05-Fools.htm
186ff910b1ce9de9f7dce4e9dfd0c13b5972e3057e2de434c0a1c33ff7381164  06-Wise.htm
5804d7ebbd2e2e2babcbcf625da9c0130bf1b2c630e819b2f9d96de138ddd74e  07-Arahats.htm
ac697607bb1ac6214ee6837d0bf66e5ecee8e6f0b05d466555a13a10f66059f6  08-Thousands.htm
3dc0ad6a71fb1a03ad1f5a62427d1adbd4bb87616b0bcc229886def196aa037b  09-Wickedness.htm
3920f1bb5420608a4e5ba468cde7c0111b0bf7b3167624249c8749cfb7bafd67  10-Stick.htm
b83050dd9a8a1e2b32bd3025279b997c290126a8c9d9da22bd0da53951ceb5ce  11-Old-Age.htm
ce4e9d22ea6ffd70ce3d841ca2a8328ad35552a15f1ce9c7805d0607a371f413  12-Self.htm
0b3c92bcb19e2c688e3563fa1c9199b1e87f17439bd14f2b206f193127f2ed1a  13-World.htm
8ca9b062c9d849de3eb5ec972b86e15b84382037636c299ea62fe76a309d44d3  14-Buddha.htm
f824918165da76fd616e967daab04bcf31236c2748d07b27dc3c984e837c7e68  15-Happiness.htm
75c67903008ccedd2564b8b808ce4d1dc74894284d7fb65f84e9a1fbdd0fb404  16-Love.htm
e644ee4c0ca10bbd925ec76e4c59fbebe838de70026638b3a2666de24041ece5  17-Anger.htm
1bf6ed7a99319ebb9f1c362cc4aff2a8c8de6f5ac9d201b31546dafe005cf56a  18-Stains.htm
0a026c50c77e976523748b7a4c55cd48dd990b9e7fdb6ab4353d77a71f862877  19-Dhamma.htm
0ce289bca5d3152af92009e59c59c78e0197f00e41bb466cf99c6047e644b7b0  20-Path.htm
ea791870ad8da519d4ee10c3041cd4ef6a0c41956b9ef2f27c7875a530abd43b  21-Miscellaneous.htm
5659a4f45a0b4e835306971db2a278f36afe3bb5bcabecb70cd2c69f1a368006  22-Underworld.htm
6db59366b062a9731cdfdc0d4931ef5804c9a49010298a66ae622d58f21ad934  23-Elephant.htm
6e9e455b8021d174c85769e6fe6f3584aea914d5b87293750517668ee04cefde  24-Craving.htm
2105297fd7f871e1b88fc2cc48dbeafb5213eb2232809cd45d6e2317f4955e12  25-Monastics.htm
fdd448c2a20f4a10602c53f14701bc736b08e19776cac70463d2c195bf466c37  26-Brahmins.htm
```

### Verifying

`sources/SHA256SUMS` holds the same checksums in machine-readable form.
`sources/fetch.sh --verify` checks the committed files against it.
`sources/fetch.sh` with no arguments downloads both editions into a temporary
directory, never into `sources/`, and reports which files differ from this
snapshot.

Neither source has changed in git since the baseline commit. With
permission granted, shipping the PDF in the repository is allowed but no
longer necessary. It stays for now; `fetch.sh` is the alternative, and it
makes version drift visible instead of silent.
