# Repository status report

Audit date: 2026-09-23. Branch `fix/commentary-pipeline` at `2a20bfd`, plus uncommitted working tree.
Read-only: the only file this audit wrote is this one. Every number below comes from a command run during the audit. Where a claim could not be checked, it says **unverified**.

| § | Area | Verdict | One line |
|---|---|---|---|
| 1 | Repository | **incomplete** | The September cleaning pass, the rebuilt index, the web frontend and a test file are all uncommitted (52 tracked files modified/deleted, 3 untracked paths). The source PDF is in history. |
| 2 | Corpus | **current** (open items) | 305 stories, 423/423 verses, no gaps. 23.1's nidāna says Jetavana. The 42% divergence is still not broken down by type. 416 and 380 both match their sources. |
| 3 | Index | **current** (one timestamp inversion) | 5,909 chunks. `story_alignment` and `story_titles` are present. `chunks.jsonl` is 9 min *newer* than the embeddings, but the IDs match 1:1 and the sparse-token check found no drift. |
| 4 | Code | **current** | 189 passed, 0 failed, 0 skipped. All 9 listed features are present. |
| 5 | Evaluation artifacts | **stale** | Every result file (Aug 6–10) predates the Sep 22 corpus and index. No published number describes the index currently shipped. |
| 6 | Frontend & API | **incomplete** | Streamlit is gone from the tree and `pyproject.toml`. Gradio was never found. The Next.js `web/` app is untracked, and its evaluation page shows the stale numbers with no caveat. |
| 7 | Documentation | **stale** | `evaluation.md` has an earlier set of numbers than `data/eval/`. `indexing.md` says 5,667 chunks. Two docs still describe the removed `ui/app.py`. |
| 8 | Open items | **incomplete** | 8 of the listed items are still outstanding (see §8). |

---

## 1 · Repository

```
$ git log --oneline -15
2a20bfd chunks.py: strip narrative's own closing verse-quote from vatthu/desanavasane
d1f289d Research validation: 32-question x 6-condition ablation grid, production_full column
93ab945 ui/app.py: terminal query logging, Streamlit width-param compat
cb2ca1f Rounds 3-8: corpus rebuild, generation fixes, alignment layer, structural disposition, RRF diagnosis
0595613 Round 2 tasks A, B, C: prose rendering, citation-leak fix, verse-alignment index
b9f94fc Phase 6: UI contrast/warning-object fixes, post-fix evaluation.md, README/indexing.md wording
3b5e9d1 Phase 5: re-run evaluation on the fixed pipeline (bugs 8, 9, 10, 13)
11b9db5 Phase 4: split cross_recension into alignment + cross_recension + corpus_anomaly (bug 14)
4b9b423 Phase 3: fix generation -- num_ctx truncation, then a second gap it exposed (bugs 1, 11, 12)
3b9713e Phase 2: rebuild index with narrative windowing + story titles (bugs 2, 3)
239b3e9 Phase 1: fix provenance audit false positives (bugs 4, 5, 6, 7)
d61d083 Phase 0: archive pre-fix eval outputs and evaluation.md
4e57cd9 Baseline: pre-fix state of DhammapadaRAG (Phases 1-5 as originally built)

$ git branch -a
* fix/commentary-pipeline
$ git tag
v0-prefix
$ du -sh .git
 23M	.git
$ git count-objects -vH
count: 378
size: 21.06 MiB
in-pack: 0
packs: 0
size-pack: 0 bytes
prune-packable: 0
garbage: 245
size-garbage: 980.00 KiB
```

**The working tree is not clean.** `git status --short` shows 50 files modified (` M`), 2 staged deletions (`D  src/dhammapada_rag/ui/__init__.py`, `ui/app.py`) and 3 untracked paths (`dhammapada_fixes/CLAUDE_CODE_BRIEF_ROUND9.md`, `tests/test_parse_stories.py`, `web/`). The full list is in the git status above. There is no `main` branch locally and there are no remotes (`git branch -a` lists only the current branch).

**Real changes vs. line-ending-only changes.** Running `git diff --ignore-cr-at-eol` splits the 50 modified files:

- **Line endings only (content identical):** `data/eval/arm_diagnosis_results.json`, `generation_raw.jsonl`, `research_validation_consistency.json`, `research_validation_production_full.jsonl`, `research_validation_q2_rerun.jsonl`, `research_validation_raw.jsonl`, `retrieval_metrics.json`, `retrieval_results.jsonl`, `rrf_k_sweep_results.json`, `data/normalized/alignment_table.csv`. Several further `data/normalized/*` and `data/processed/*` files show no numstat lines once CR is ignored. There is no `.gitattributes` to stop this from happening.
- **Real content changes (30 files):** the whole September cleaning pass. `stories.jsonl` changes on all 305 lines, `verses.jsonl` on 80, `chunks.jsonl` goes from 5,876 to 5,909 rows. Also `parse_stories.py` (+358/−41), `generate/schemas.py`, `prompt.py`, `generate.py`, `api/main.py` (+96), `corrections.py` (+51), `tests/test_provenance.py` (+130), `README.md`, four docs, `pyproject.toml`, and one eval file (`generation_metrics.json`, see §5).

```
$ git diff --ignore-cr-at-eol --stat | tail -1
 30 files changed, 4084 insertions(+), 2877 deletions(-)
```

**Large binaries in history:**

```
$ git log --all --pretty=format: --name-only --diff-filter=A | grep -Ei '\.(npy|pkl|pdf|pt|bin|safetensors|faiss)$'
sources/Dhammapada-Attakatha.pdf
$ git log --all --format='%h %ad %s' --date=short -- sources/Dhammapada-Attakatha.pdf
4e57cd9 2026-07-31 Baseline: pre-fix state of DhammapadaRAG (Phases 1-5 as originally built)
largest blob: a00835616a… 7414143 sources/Dhammapada-Attakatha.pdf
```

- **The source PDF (7.4 MB) is in history.** It was committed in the baseline commit and is still tracked.
- **`*.npy` and `*.pkl` are not in history.** `dense.npy`, `sparse.pkl`, `colbert.pkl` and `chunk_ids.json` are gitignored and exist only in the working tree. `colbert.pkl` is 3.34 GB on disk.
- **The object store holds 245 "garbage" files.** They are macOS AppleDouble files (`.git/objects/xx/._<sha>`, 980 KiB). They produce a warning on every `git count-objects`. No packfile exists, so all 378 objects are loose.

## 2 · Corpus

```
$ wc -l data/processed/*.jsonl
     423 data/processed/interlinear_gloss.jsonl
     305 data/processed/stories.jsonl
     423 data/processed/verses.jsonl
    1151 total

stories: 305 verses: 423
verse coverage: 423 min 1 max 423
gaps: []
pali_mahasangiti populated: 423
english_sujato populated: 423
interlinear_pali populated: 423
interlinear_english populated: 423
nidana populated: 301
vatthu populated: 305
desanavasane populated: 297
cst4_title populated: 96
synopsis populated: 304
```

`interlinear_gloss.jsonl` was last modified on Jul 30, and every other file in `data/processed/` on Sep 22. Nothing in this audit checked whether that file still matches the current corpus: **unverified**.

**Checks in `docs/corpus_audit.md` (generated Sep 22 18:54, same run as the current `data/processed/`):**

| Check | Result on current corpus | Status |
|---|---|---|
| 1 Title/body coherence | 1 flagged (23.1), described as a hand-checked false positive for the *title* | pass (with caveat) |
| 2 Control characters | 0 | pass |
| 3 Pali character set | 0 | pass |
| 4 Cross-source verse agreement | 246 exact / 0 boundary / **177 distinct (0.4184)** | open (see below) |
| 5 Inline-vs-canonical Pali | 123 exact / 5 boundary / **98 distinct (0.4336)** | open (same issue) |
| 6 Alignment closure | 423/423, 1 duplicate (Dhp 416: 26.33, 26.34) | pass |
| 7 Length outliers | 0 / 0 | pass |
| 8 Quote-glyph mis-mapping | 0 | pass |

`docs/corpus_validation.md` (Stage 5 gates, Sep 22) reports **Build result: PASS** for gates 1–4. Warning-only gate 6 carries the same 246/0/177.

### Story 23.1's nidāna

```
group_id => '23.1'
dhp_verses => [320, 321, 322]
nidana => '“Like an elephant in battle,” this Dhamma teaching was given by the Teacher while he was in residence at Jetavana with reference to himself.'
synopsis => 'Queen Māgandiyā, who had been rejected by the Buddha, bribed the crowd and slaves to abuse him and the bhikkhus when they came to town; …'
vatthu[:…] => 'The story is related in detail in the commentary on the first verses of the Appamādavagga. For it is there said: Unable to do anything to them, Māgandiyā thought to herself: …'
Kosamb in vatthu: 0 in synopsis: False
Jetavana in vatthu: 0 in synopsis: False
```

**The stored nidāna says Jetavana.** The extraction is faithful to the source: `data/raw/dhammapada-attakatha.txt` lines 36526–36527 read "…was given by the Teacher while he was in residence at Jetavana with reference to himself." The vatthu says the episode is told in full under the Appamādavagga (story 2.1). In the same raw text, 2.1's nidāna reads "…in residence at Ghosita monastery near Kosambī". So the corpus places the Māgandiyā-abuse teaching at Jetavana, while the story it quotes is set at Kosambī.

The corpus carries no correction or annotation for this. `corrections.py`, `datasheet.md` and `README.md` contain no 23.1/Jetavana/Kosambī entry. `corpus_audit.md` and `generation.md` discuss 23.1 only in terms of its **title**, never its location.

It is **unverified** whether the error originates in the Pali aṭṭhakathā, in Burlingame, or in the 2024 revision. No CST4 Pali text of the commentary is in the repo to check against.

### The 42% cross-edition Pali divergence

**Still one undifferentiated number.** `audit_corpus.classify_pali_pair()` returns only `"exact"` / `"boundary"` / `"distinct"`. No code in `src/` breaks `distinct` down further: a search for `variance_class|classify_variance|single_token` finds nothing. `corpus_audit.md` §4 explicitly leaves the split into single-token variants, word substitutions and structural differences unresolved ("flagged as Stage 0's own limit, not resolved here"). The 177 remain unclassified.

### Dhp 416 and Dhp 380

```
=== Dhp 416
pali_mahasangiti => 'Yodha taṇhaṁ pahantvāna, anāgāro paribbaje; Taṇhābhavaparikkhīṇaṁ, tamahaṁ brūmi brāhmaṇaṁ. Yodha taṇhaṁ pahantvāna, anāgāro paribbaje; Taṇhābhavaparikkhīṇaṁ, tamahaṁ brūmi brāhmaṇaṁ.'
interlinear_pali => 'Yodha taṇhaṁ pahatvāna, anāgāro paribbaje, taṇhābhavaparikkhīṇaṁ, tam-ahaṁ brūmi brāhmaṇaṁ.'
english_sujato => 'They’ve given up craving, … that’s who I declare a brahmin. They’ve given up craving, … that’s who I declare a brahmin.'

=== Dhp 380
pali_mahasangiti => 'Attā hi attano nātho, ko hi nātho paro siyā; Attā hi attano gati, tasmā saṁyamamattānaṁ; Assaṁ bhadraṁva vāṇijo.'
interlinear_pali => 'Attā hi attano nātho, attā hi attano gati, tasmā saṁyamayattānaṁ assaṁ bhadraṁ va vāṇijo.'
```

- **Dhp 416: still doubled.** Both `pali_mahasangiti` and `english_sujato` are affected. The doubling comes from the source. The SuttaCentral JSON holds the verse twice under two headings (`dhp416:0 "Jaṭilattheravatthu"` … `dhp416:5.0 "Jotikattheravatthu"`, segments 1–4 and 5.1–8), so the corpus reproduces its source rather than an extraction bug.
  - The side effects are real. Check 4 scores 416 as the worst "distinct" case (similarity 0.661).
  - By the formula at `generate/schemas.py:792` (quote length ÷ matched-field length, threshold 0.6), a complete single quotation of 416 would score about 0.5 and be flagged as truncated. This follows from reading the code; it was not executed.
- **Dhp 380: the interlinear still lacks `ko hi nātho paro siyā`.** This is also true to the source: `sources/external/anandajoti_interlinear/25-Monastics.htm:214` reads "Attā hi attano nātho, attā hi attano gati," with no such pāda. It is an edition difference (Ānandajoti's 4-pāda text vs. Mahāsaṅgīti's 5-pāda text), not a dropped line.

## 3 · Index

```
$ wc -l data/index/chunks.jsonl
    5909 data/index/chunks.jsonl
$ ls -laT data/index/
-rw-rw-rw-@ 1 …      139662 Sep 22 18:56:47 2026 chunk_ids.json
-rw-rw-rw-@ 1 …     4385573 Sep 22 19:06:02 2026 chunks.jsonl
-rw-rw-rw-@ 1 …  3341459410 Sep 22 18:56:47 2026 colbert.pkl
-rw-rw-rw-@ 1 …    24203392 Sep 22 18:56:44 2026 dense.npy
-rw-rw-rw-@ 1 …     7161194 Sep 22 18:56:44 2026 sparse.pkl

Counter({'story_vatthu': 2302, 'verse_pali_ms': 423, 'verse_en_sujato': 423, 'verse_en_interlinear': 423,
         'story_desanavasane': 395, 'story_titles': 305, 'story_alignment': 305, 'story_keywords': 305,
         'story_synopsis': 304, 'story_nidana': 301, 'verse_en_narrative': 226, 'verse_notes': 129, 'story_cast': 68})
windowed chunks: 2362
longest chunk (words): 200
```

- `story_alignment` (305) and `story_titles` (305) are **present**.
- The embedding files exist. `dense.npy` has shape `(5909, 1024)`, and `chunk_ids.json` has 5,909 entries in the same order as `chunks.jsonl` (`same id list & order: True`).
- **The embeddings are *not* newer than `chunks.jsonl`.** `chunks.jsonl` was modified at 19:06:02, and the embeddings at 18:56:44–47, 9 min 15 s *earlier*. The source files are all older than the embeddings (`data/processed/*` at 18:54, `index/chunks.py` at 18:55:38), so the index is not older than the corpus it was built from. What is unexplained is a rewrite of `chunks.jsonl` *after* embedding.
- **Drift check:** I tokenised every current chunk text with the bge-m3 tokenizer and checked that each stored sparse vector's token IDs are a subset of the text's tokens.
  - Result: **0 of 5,909 chunks** carry a sparse token that is absent from the current text. So no text was removed or replaced after embedding.
  - Limit: additions cannot be detected this way, because bge-m3 zeroes low-weight tokens. Exact equality is **unverified**.
  - A re-run of `embed.py` would settle it.
- The committed `chunks.jsonl` at HEAD (5,876 rows) does not match the embeddings on disk. The only consistent index is the uncommitted working-tree one.

## 4 · Code

```
$ python -m pytest -q
........................................................................ [ 38%]
........................................................................ [ 76%]
.............................................                            [100%]
189 passed in 0.53s

$ find src -name '*.py' | xargs wc -l | tail -1
   10026 total
```

There are 189 tests: all pass, 0 skipped, 0 failed. `tests/test_parse_stories.py` is included in that count but is untracked. Modules: `api/` (main, schemas); `eval/` (10 modules); `generate/` (generate, prompt, render, schemas); `index/` (assemble, chunks, embed, rerank, search); `ingest/` (15 modules). There is no `ui/`.

| Feature | Status | Identifier found |
|---|---|---|
| Four-layer discriminated union | **present** | `generate/schemas.py:222` `Claim = Annotated[Union[VerseClaim, CommentaryClaim, AlignmentClaim, SynthesisClaim], Field(discriminator="layer")]` |
| Citation fields as per-request enums | **present** | `generate/generate.py:139` `_constrained_schema(bundles)`: `group_id` `"enum": gids` (l.189, 201), `verse_number` `"enum": vnums` (l.193, 206) |
| `num_ctx` set explicitly | **present** | `generate.py:95` `DEFAULT_NUM_CTX = 16384`; l.278 `opts = {"temperature": …, "num_ctx": self.num_ctx}`; prompt measured against `num_ctx - COMPLETION_HEADROOM` (l.304) |
| `source_disposition` required | **present** | `schemas.py:250` `source_disposition: dict[str, Disposition] = Field(..., …)`; decoder-side `generate.py:222` `"required": gids, "additionalProperties": False`. Caveat: an *empty* dict passes pydantic and makes the audit skip its disposition checks (`schemas.py:1008`) |
| Three-tier Pali matching | **present** | `schemas.py:458` `_match_pali_quote()` returns `"exact"` / `"variant"` / `None` (fabrication); codes `PALI_QUOTE_NOT_IN_SOURCE` etc. |
| Quote-coverage / truncation check | **present** | `schemas.py:455` `PALI_COVERAGE_THRESHOLD = 0.6`; applied at l.792–796 |
| Narrative windowing | **present** | `index/chunks.py:109–121` `WINDOW_WORDS = 200`, `OVERLAP_WORDS = 40`, `PALI_WINDOW_WORDS = 100`, `PALI_OVERLAP_WORDS = 20`; `_split_windows()` l.265, `_windowed_chunks()` l.289 |
| Device selection incl. CUDA | **present** | `index/rerank.py:20` `best_device()`: `torch.cuda.is_available()` → `("cuda", True)`, then MPS, then `("cpu", False)`; used by `embed.py` |
| Ablations all reranked | **present** | `eval/retrieval_eval.py:232–236`: `baseline`, `verse_only`, `dense_only` all go through `self._rerank(...)`; `no_rerank` is the only unreranked condition, by design |

## 5 · Evaluation artifacts

```
$ ls -laT data/eval/
drwxrwxrwx   archive_pre_fix                            Aug  3 21:52:58 2026
drwxrwxrwx   archive_round1_post_fix                    Aug  3 21:52:58 2026
-rw-rw-rw-   arm_diagnosis_results.json         3067    Aug  6 18:21:44 2026
-rw-rw-rw-   build_gold_set_PATCH.py            8441    Jul 31 01:36:39 2026
-rw-rw-rw-   build_gold_set.py                 28861    Jul 31 02:32:50 2026
-rw-rw-rw-   generation_judgments.py           19906    Aug  6 23:35:45 2026
-rw-rw-rw-   generation_metrics.json            2457    Sep 17 21:31:04 2026
-rw-rw-rw-   generation_raw.jsonl            1037192    Aug  6 23:30:55 2026
-rw-rw-rw-   gold_set.jsonl                    36991    Jul 31 02:33:51 2026
-rw-rw-rw-   model_sweep_results_retries0.jsonl 31092   Jul 31 09:56:32 2026
-rw-rw-rw-   model_sweep_results_retries1.jsonl 30525   Jul 31 11:19:53 2026
-rw-rw-rw-   research_validation_consistency.json 4946  Aug  7 01:15:58 2026
-rw-rw-rw-   research_validation_production_full.jsonl 32213 Aug 7 16:31:07 2026
-rw-rw-rw-   research_validation_q2_rerun.jsonl 28021   Aug  7 16:30:26 2026
-rw-rw-rw-   research_validation_raw.jsonl     984505   Aug  7 01:15:07 2026
-rw-rw-rw-   retrieval_metrics.json            13248    Aug 10 20:37:29 2026
-rw-rw-rw-   retrieval_results.jsonl           82374    Aug 10 20:36:58 2026
-rw-rw-rw-   rrf_k_sweep_results.json           1306    Aug  6 23:26:34 2026
-rw-rw-rw-   tag_stability_results.json         3590    Aug  1 01:31:10 2026

$ git log -1 --format=%cd -- data/index/chunks.jsonl
Mon Aug 10 22:03:48 2026 -0500
$ git log -1 --format=%cd -- data/eval/retrieval_metrics.json
Mon Aug 10 22:03:48 2026 -0500
$ git log -1 --format=%cd -- data/eval/generation_metrics.json
Thu Aug 6 23:41:25 2026 -0500
```

The last change to `chunks.jsonl` and `data/processed/` was the uncommitted working-tree change on **Sep 22** (18:54–19:06). Git's commit dates show only Aug 10, because the cleaning pass is not committed.

| File | Modified | Predates Sep 22 corpus/index? |
|---|---|---|
| `retrieval_results.jsonl` / `retrieval_metrics.json` | Aug 10 | **yes** (also predates commit `2a20bfd` at 22:03 the same day, which changed `chunks.py`) |
| `generation_raw.jsonl` | Aug 6 | **yes** |
| `generation_metrics.json` | Sep 17 | **yes**. The only real change vs. HEAD is two added keys (`quote_coverage_rate`, `n_quote_coverage`). By file dates it was re-aggregated from the Aug 6 `generation_raw.jsonl`, not re-generated |
| `research_validation_*` | Aug 7 | **yes** |
| `arm_diagnosis_results.json`, `rrf_k_sweep_results.json` | Aug 6 | **yes** |
| `model_sweep_results_*`, `tag_stability_results.json` | Jul 31 – Aug 1 | **yes** |

**No published evaluation number describes the index currently shipped.** All retrieval and generation results were computed against an index of at most 5,876 chunks, built from the pre-cleaning corpus. The shipped index has 5,909 chunks built from the Sep 22 corpus. `README.md:121` says as much. Neither `docs/evaluation.md` nor the web evaluation page carries that caveat.

### `generation_metrics.json`

```
n_questions = 27
n_claims = 48
macro_f1 = 0.8236
accuracy = 0.8542
conflation_rate = 0.027
source_fidelity_rate = 0.9167          (no key named "source_fidelity")
unfaithful_claims = 4
source_fidelity_scoped = {"n": 45, "rate": 0.9333, "ci_95": [0.8511, 1.0]}
provenance_errors = 6
source_disposition = {"counts": {"used": 28, "partially_relevant": 11, "not_relevant": 42},
                      "n_total": 81, "not_relevant_on_noise": 42, "not_relevant_on_gold": [],
                      "disposition_contradicts_claims": 0, "n_fully_covered": 27}
pali_fidelity = {"n_pali_claims": 7, "exact_copy_rate": 0.8571, "variant_rate": 0.0,
                 "fabrication_rate": 0.1429, "quote_coverage_rate": 0.85, "n_quote_coverage": 6}
layer_count_distribution = {"1": 11, "2": 14, "3": 2, "4": 0}
```

- `not_relevant_on_noise` / `n_total` = **42 / 81**. All 42 `not_relevant` dispositions fell on noise groups, and none on gold groups.
- `pali_fidelity` as counts: **7 Pali claims → 6 exact, 0 variant, 1 fabrication.** Quote coverage was measured on **6** claims. `quote_coverage_rate` = 0.85 is not a count: 0.85 × 6 is not an integer, so it is presumably a mean coverage ratio (**unverified** without reading the aggregator).
- `layer_count_distribution`: 11 answers use 1 layer, 14 use 2, 2 use 3, and none use 4 (27 total).

### `retrieval_metrics.json` (n = 114 scored questions out of 120 in `gold_set.jsonl`; 6 have empty gold)

| Type | n | baseline nDCG@10 | verse_only nDCG@10 |
|---|---|---|---|
| doctrinal | 30 | 0.9631 | **0.9754** (above baseline) |
| philological | 30 | 0.9631 | 0.9087 |

(Also on philological: `no_rerank` scores **1.0** against baseline 0.9631, so the reranker lowers the score on this type.)

```
ablation_deltas_ndcg10 (baseline − condition):
  verse_only  delta 0.4365  CI [ 0.3471, 0.5301]
  dense_only  delta 0.0015  CI [-0.0076, 0.0101]   spans zero
  no_rerank   delta 0.0163  CI [-0.0117, 0.0447]   spans zero
  flat        delta 0.0029  CI [ 0.0,    0.0076]   lower bound exactly 0
```

## 6 · Frontend and API

```
$ ls web/
AGENTS.md  app  CLAUDE.md  components  eslint.config.mjs  lib  next-env.d.ts  next.config.ts
node_modules  package-lock.json  package.json  postcss.config.mjs  public  README.md  tsconfig.json
$ ls web/app
corpus  evaluation  favicon.ico  globals.css  layout.tsx  method  page.tsx
$ ls src/dhammapada_rag/ui
ui/ removed
$ grep -rn "streamlit\|gradio\|plotly" --include="*.py" --include="*.toml" . --exclude-dir=.venv --exclude-dir=node_modules
(no output)
```

- **Frontends:** one, the Next.js app in `web/` (pages `/`, `/corpus`, `/evaluation`, `/method`). It talks to the API at `NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"` (`web/lib/api.ts:9`). **`web/` is untracked.**
- **Streamlit:** removed from the tree (`ui/` deletions are staged) and from `pyproject.toml` (the uncommitted diff drops `streamlit>=1.35` and `plotly>=5.20`). Neither removal is committed.
- **Gradio:** no reference anywhere outside `.venv`/`node_modules`.
- **API routes in `api/main.py`:**
  - `GET /health` (l.110)
  - `POST /query` (l.134)
  - `POST /answer` (l.139)
  - `GET /verses/{verse_number}` (l.175)
  - `GET /stories/{group_id}` (l.183)
  - `GET /vaggas` (l.193)
  - `GET /eval/summary` (l.258): serves `retrieval_metrics.json` and `generation_metrics.json` as they are.
- `web/app/evaluation/page.tsx` renders those numbers (e.g. l.241 "Macro-F1"). A search for `september|stale|re-run|predate|before the` in that file finds nothing, so **the web UI shows the stale evaluation with no caveat.**

## 7 · Documentation

```
$ ls -la docs/ ; wc -l docs/*.md
corpus_alignment.md          Aug  4    48
corpus_audit.md              Sep 22   201
corpus_normalization.md      Aug  4   129
corpus_source_ownership.md   Aug  4    94
corpus_validation.md         Sep 22    39
datasheet.md                 Sep 22   253
eval_rubric.md               Sep 17   394
evaluation_pre_fix.md        Jul 30   302
evaluation.md                Aug  6  1230
generation.md                Sep 17   807
indexing.md                  Jul 31   133
licensing.md                 Jul 30    40
                                     3670 total
```

| Doc | Status | Evidence |
|---|---|---|
| `corpus_audit.md` | current | Generated Sep 22 18:54 alongside `data/processed/`; the 246/0/177 split matches `corpus_validation.md` |
| `corpus_validation.md` | current | Sep 22, PASS; same numbers |
| `corpus_normalization.md` | current for its table | 246/0/177 matches the current audit; the rest was not checked |
| `datasheet.md` | current | Describes the September 2026 cleaning pass (l.160) |
| `licensing.md` | current | States the open PDF-confirmation item (see §8) |
| `README.md` | current | 5,909 chunks (l.72, l.168); says the eval predates the cleaning pass (l.121) |
| `eval_rubric.md` | current on annotator status | Other content not checked |
| `evaluation_pre_fix.md` | archival | Kept on purpose as the pre-fix record |
| **`evaluation.md`** | **stale** | Carries an **earlier set** than `data/eval/`: baseline nDCG@10 **0.962** vs file 0.9592; R@1 0.921 vs 0.9123; generation Macro-F1 **0.753** / accuracy 0.830 over **53** claims vs file 0.8236 / 0.8542 over **48**. Also describes `ui/app.py` (l.718, l.767), which has since been removed |
| **`indexing.md`** | **stale** | "derives **5,667 chunks**" (l.9, l.61) vs 5,909 shipped |
| `generation.md` | partly stale | Names `ui/app.py` 4 times (l.138, 372, 444, 479), a file that is now deleted; otherwise unverified |
| `corpus_alignment.md`, `corpus_source_ownership.md` | unverified | Aug 4; not checked against the current data |

## 8 · Open items

Verified as still outstanding:

1. **Second annotator / IAA statistic: not done.** `eval_rubric.md:10`: "This gold set has exactly one annotator: Claude (Sonnet 5)…" and "no IAA statistic is computed or claimed anywhere". No kappa or Krippendorff code exists in `src/` or `data/eval/`.
2. **Ānandajoti PDF licence: resolved by inference only.** No `PROVENANCE.md` states a licence for the PDF itself: `data/raw/PROVENANCE.md` records its metadata but no licence. `docs/licensing.md` gives CC BY-SA 3.0 "High, by inference" from the site-wide notice, and keeps a "Remaining action item, unchanged: … get written confirmation from Ānandajoti Bhikkhu naming this specific PDF". Meanwhile the PDF is committed to git history (§1). *Resolved 2026-09-25, after this report: written permission from Ānandajoti Bhikkhu, licence CC BY-SA 4.0; see `sources/PERMISSION.md`.*
3. **Story 23.1 nidāna: open.** The stored text says Jetavana, the quoted episode is set at Kosambī, and the corpus has no annotation or correction (§2).
4. **Cross-edition variance: unclassified.** 177/423 are still one "distinct" bucket (§2).
5. **Eval artifacts: not re-run after the cleaning pass.** Every file predates Sep 22 (§5), and `evaluation.md` predates even those (§7).
6. **`LICENSE`, `DATA_LICENSE.md`, `CITATION.cff`, `.gitattributes`: all absent.**
   ```
   $ ls LICENSE* DATA_LICENSE.md CITATION.cff .gitattributes
   no matches found: LICENSE*   /   .gitattributes: No such file or directory
   ```
   (`DATA_LICENSE.md` and `CITATION.cff` are also absent.) The missing `.gitattributes` is why nine eval files show as modified with line-ending-only diffs.
7. **`build_gold_set_PATCH.py`: applied, not removed.** `build_gold_set.py` already contains the patch's split (l.279–301, `alignment` type with `assert len(alignment) == 14`, `corpus_anomaly`). `gold_set.jsonl` has the post-patch types: doctrinal 30, philological 30, narrative 30, alignment 14, cross_recension 14, corpus_anomaly 2. The PATCH file is still present and still tracked. *Resolved 2026-09-25, after this report: PATCH deleted; its diagnosis now sits in `build_gold_set.py`'s docstring ("Bug 14 diagnosis").*
8. **The gold set is saturated.** Baseline Recall@10 is 0.9912 overall and **1.0 on 5 of 6 types**. The exception is corpus_anomaly, with n = 2 and R@10 0.5. Two ablation CIs span zero (dense_only, no_rerank), and flat's lower bound is exactly 0.0. verse_only *beats* baseline on doctrinal (0.9754 vs 0.9631), and no_rerank *beats* baseline on philological (1.0 vs 0.9631). On this question set, only the verse_only ablation (which deletes the story chunks) produces a clearly measurable difference. The set cannot currently tell fusion, reranking or assembly apart from their absence.

Additional items found during the audit:

9. The September cleaning pass, the rebuilt index source, the web app and `tests/test_parse_stories.py` are **uncommitted**. The committed `chunks.jsonl` (5,876) matches no embeddings on disk.
10. `chunks.jsonl` was rewritten 9 min after the embeddings were built. No drift was detected, but exact equality is unverified (§3).
11. The Dhp 416 doubling (faithful to SuttaCentral) will make the coverage check flag a complete single quotation as truncated (inferred from `schemas.py:792`; not executed).
12. `.git/objects` contains 245 AppleDouble `._*` files.

---

## What I would fix first

1. **Commit the working tree (and tag it).** Everything else rests on this: the corpus, the index source, the tests and the frontend exist only as uncommitted changes. No eval re-run could be tied to a reproducible state until they are committed.
2. **Re-embed, then re-run retrieval and generation eval against that commit, and update `evaluation.md` and the web page.** Right now every published number describes an index that is no longer shipped. Re-embedding first also clears the unexplained 9-minute timestamp inversion, so the new numbers have a clean provenance chain.
3. **Make the gold set able to tell components apart (harder questions, and a second annotator).** This comes third because only post-rebuild numbers can confirm the saturation seen in the August run still holds. Once it is confirmed, adding a second annotator is cheaper done together with the question rewrite than twice.
