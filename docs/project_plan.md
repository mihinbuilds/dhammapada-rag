
## Phase 1 — Corpus construction

This is where your actual contribution lives, and it's mostly unglamorous.

1. Ingest Pali (Mahāsaṅgīti, CC0) and two English translations. Validate hard: 423 verses, 26 vaggas, no gaps.
2. Ingest Burlingame's *Buddhist Legends* (public domain), segment into the ~300 stories.
3. **Build the verse↔story alignment table by hand and have it checked.** Dhp 1–2, 3–4, 21–23, 153–154 and dozens of others are grouped, not one-to-one. Record edition-numbering variants explicitly.
4. Segment each story into nidāna / vatthu / pada-gloss / desanāvasāne. Regex on the `tattha ... ti` marker gets you most of the way; hand-correct the rest and log your correction rate — that number belongs in the paper.
5. Write a datasheet (Gebru et al., *Datasheets for Datasets*) and a licensing table covering every source. Release on Zenodo with a DOI.

Budget the most time here. The GitaGPT paper spends three sentences on data preparation and it shows.

## Phase 2 — Indexing 

Diverge from the paper on embeddings. `bge-small-en-v1.5` is English-only; Pali will be near-random noise in that space. Use **BGE-M3**, which produces dense, sparse, and multi-vector representations from one multilingual model — precisely the hybrid you need, without hand-tuned 70/30 weights. Pair it with `bge-reranker-v2-m3` as a cross-encoder second stage.

For fusion, use **Reciprocal Rank Fusion** rather than fixed weights. It's tuning-free, standard, and you avoid having to justify an arbitrary 70/30 split.

## Phase 3 — Retrieval architecture 

The core mechanism is *retrieve small, return whole*: match on the tightest possible unit, then assemble and return the full verse group so the user always sees all three layers regardless of which one matched.The parent-assembly step is your architectural claim. A hit on the story index for "the woman whose child died" returns Dhp 114 with its Pali, both translations, and Kisāgotamī's story — not just the narrative fragment that matched.

## Phase 4 — Generation with enforced layer attribution 

Use a real generator, not a 1B model. Qwen2.5-7B/14B-Instruct or Llama-3.1-8B locally; an API model if compute allows. Then **run the size sweep as an ablation** — 1B vs 7B vs 14B on the same retrieval — and report it. That turns your compute constraint into a finding.

The prompt must force the distinction your project exists to make: the verse says X, Buddhaghosa's commentary explains it as Y, and these are separated by roughly eight centuries. Require structured output where every claim carries a layer tag (`verse` / `commentary` / `synthesis`) and a `group_id`. Conflating the two layers is the failure mode; make the output format make it visible.

## Phase 5 — Evaluation

This is where you beat the paper decisively.

**Gold set**: ~120 questions, stratified across four types — doctrinal, philological (term meaning), narrative, and cross-recension. Two annotators with Pali competence, published rubric, **report Krippendorff's α or Cohen's κ**. Even modest agreement, honestly reported, outranks an unaudited 92.4%.

**Retrieval metrics**: Recall@k, nDCG@10, MRR — broken out *per query type*. Aggregate numbers hide the interesting result, which is almost certainly that narrative queries fail on verse-only retrieval and philological queries fail on narrative retrieval.

**Ablations, generator held constant**:
- verse-only vs. verse + commentary
- flat chunking vs. parent-group assembly
- dense-only vs. hybrid + RRF
- with vs. without cross-encoder rerank

**Two metrics worth proposing as contributions:**

*Layer attribution accuracy* — given a generated answer, does each claim correctly identify whether it derives from the verse, the aṭṭhakathā, or the model's own synthesis? Nobody measures this, and it's the philologically meaningful error.

*Anachronistic conflation rate* — how often does the system present Buddhaghosa's commentarial gloss as the plain sense of the verse? This is the specific harm a naive verse-only RAG can't even commit, and a verse-plus-commentary RAG commits constantly unless designed against it.

Report failure cases explicitly. A paper with a candid failure analysis reads as more credible than one claiming 92.4%.