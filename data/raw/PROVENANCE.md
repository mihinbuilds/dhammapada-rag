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

## SuttaCentral material: removed 2026-10-08

### What was used

From the first Phase 1 pass (fetched 2026-07-30) until 2026-10-08 the verse
layer also carried two sources published by SuttaCentral, both taken from the
`published` branch of their `bilara-data` repository:

- the Mahāsaṅgīti Pāli root text of all 423 verses
  (`sources/external/mahasangiti_pali/`), and
- Bhikkhu Sujato's English translation of all 423 verses
  (`sources/external/sujato_en/`).

Both were indexed for retrieval, shown to the model in every generation
prompt, displayed in the web interface and quoted in the evaluation records.

### The ruling

On 2026-10-07 Ānandajoti Bhikkhu, replying to a message telling him the
project was online, pointed out that SuttaCentral's licensing page asks that
its content not be used for AI (see `sources/PERMISSION.md`). The maintainer
had not seen that request. On 2026-10-08 the project asked on SuttaCentral's
forum whether a
retrieval-based question-answering system over these texts fell under their
request that their content not be used for AI:
[Licensing question: retrieval over CC0 texts — does this fall under your AI request?](https://discourse.suttacentral.net/t/licensing-question-retrieval-over-cc0-texts-does-this-fall-under-your-ai-request/45514)

The same day, SuttaCentral's Forum Management Committee answered:

> You cannot use Bhante Sujato's translations in any project which uses AI.

They pointed to SuttaCentral's licensing page, which asks that their content
"not be scraped or used in any way for the creation of datasets for
generative AI", and to Bhante Sujato's 2024 essay *"Let's Make SuttaCentral
100% AI-free Forever."* The thread was then closed.

The material was released under CC0, and this project was under no legal
obligation to remove it. It was removed because SuttaCentral asked, and
because the project had said publicly in that thread that it would act on
their answer either way. Their request covers content, not only the
translation, so the Mahāsaṅgīti Pāli went too.

### What was removed

From the current tree (commit "Remove SuttaCentral material; Ānandajoti's
interlinear carries the verse layer"):

- both source directories, and `data/normalized/sc_pali.jsonl` and
  `sc_sujato.jsonl` built from them;
- the code that only read them (`ingest/normalize_sc_pali.py`,
  `ingest/normalize_sc_sujato.py`, `ingest/_sc_segments.py`,
  `tests/test_normalize.py`);
- the two verse fields in `data/processed/verses.jsonl` and
  `data/normalized/verses_joined.json`, and the two verse chunk types in
  `data/index/chunks.jsonl` (5,909 chunks became 5,486);
- every SuttaCentral string, and every verbatim span of 30 or more characters,
  in the stored evaluation records (`data/eval/generation_raw.jsonl` and its
  two archives, the three `research_validation_*.jsonl` files,
  `tag_stability_results.json`), replaced with the marker
  `[SuttaCentral text removed 2026-10-08]`; their source labels now read
  "SuttaCentral";
- the English shown in the blind annotation sheets, now Ānandajoti's;
- one gold question and one annotator note that reused the translation's
  wording, and the quotations of it in `docs/`;
- the README screenshots, retaken.

Ānandajoti Bhikkhu's 2017 interlinear Pāli and English, already present for
all 423 verses, now carry the verse layer alone. He confirmed again in writing
on 2026-10-08: "you are always welcome to use my work if you need to"
(`sources/PERMISSION.md`). A Pāli
reader on the SuttaCentral forum who has memorised the Dhammapada across
eight English translations recommended Ānandajoti's as among the best at
preserving the Pāli meaning and sequence.

### History purge, and its exception

On 2026-10-08 the repository's history was rewritten with `git filter-repo`.
The source directories, the two normalized files and the four code files
above were removed from every commit (`--invert-paths`). The two earlier
README screenshots, which showed the removed text, were stripped by blob ID
(`--strip-blobs-with-ids`). Every commit hash changed. The pre-purge state
was pushed first, and a full copy of the repository was kept locally (not
published) in case the rewrite went wrong.

**Exception: files whose earlier versions carried the text inside them.**
Path-based removal cannot reach text stored inside a file that is still part
of the project. Earlier versions of these files contain SuttaCentral text,
and their history was not rewritten:

- `data/processed/verses.jsonl` and `data/normalized/verses_joined.json`
  (the two removed fields);
- `data/index/chunks.jsonl` (the two removed chunk types);
- `data/processed/corpus_audit_report.json`, `docs/corpus_audit.md` and
  `docs/status_report.md` (cross-edition comparisons quoting it);
- the evaluation records and annotation sheets listed above, and a few
  quotations in `docs/`.

The current version of every one of them does not contain it. A scan of
the current tree for every SuttaCentral string, and for every 30-character
fragment of one that does not also occur in Ānandajoti's sources, finds
none.

Why the history was documented rather than rewritten: rewriting these files'
contents in every commit would change what each past evaluation result says
it was computed from. The history would then misdescribe itself, which is
the one thing a provenance record must not do. Removing the files from
history entirely would do the same, more bluntly. This was a judgement call,
recorded here so it can be revisited.

One limit the project does not control: GitHub can keep serving a pre-purge
commit by its old hash until its own garbage collection runs, and any clone
or fork made before 2026-10-08 keeps the old history.
