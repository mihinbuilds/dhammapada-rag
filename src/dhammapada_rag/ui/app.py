"""Streamlit UI: a presentable front end for querying the system and for
showing the Phase 5 evaluation results, for paper/research use.

Calls the pipeline directly (not over HTTP) -- ChunkIndex/CrossEncoderReranker/
Generator are loaded once via st.cache_resource, not per interaction.

Run: streamlit run src/dhammapada_rag/ui/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.generate.generate import Generator, GenerationError  # noqa: E402
from dhammapada_rag.index.assemble import assemble, load_verses_and_stories, query  # noqa: E402
from dhammapada_rag.index.rerank import CrossEncoderReranker  # noqa: E402
from dhammapada_rag.index.search import ChunkIndex  # noqa: E402

st.set_page_config(page_title="Dhammapada RAG", page_icon="\U0001f4dc", layout="wide")

LAYER_STYLE = {
    "verse": {"color": "#1d4ed8", "bg": "#eff6ff", "label": "VERSE"},
    "commentary": {"color": "#b45309", "bg": "#fffbeb", "label": "COMMENTARY"},
    "synthesis": {"color": "#15803d", "bg": "#f0fdf4", "label": "SYNTHESIS"},
}

# Phase 6 fix: .claim-card never set its own text `color`, so it inherited
# Streamlit's page-level default -- white in dark theme -- against the pale
# light-mode background colors in LAYER_STYLE (e.g. verse's #eff6ff). White
# text on pale blue is exactly the "near-white on pale blue, unreadable" bug.
# Every colored card below now sets an explicit dark color, independent of
# the viewer's Streamlit theme.
CUSTOM_CSS = """
<style>
.claim-card {
    border-left: 4px solid var(--claim-color);
    background: var(--claim-bg);
    color: #1f2937;
    border-radius: 6px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.6rem;
}
.layer-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    color: white;
    background: var(--claim-color);
    margin-right: 0.5rem;
}
.claim-cite {
    font-size: 0.78rem;
    color: #475569;
    margin-top: 0.25rem;
}
.warning-box {
    border-left: 4px solid var(--warn-color);
    background: var(--warn-bg);
    color: var(--warn-text);
    border-radius: 6px;
    padding: 0.5rem 1rem;
    margin-bottom: 0.4rem;
    font-size: 0.85rem;
}
.warning-code {
    font-weight: 700;
    font-size: 0.7rem;
    letter-spacing: 0.03em;
    margin-right: 0.4rem;
}
.pali-text { font-style: italic; color: #4b5563; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# severity -> (border/badge color, background, text color). Errors (citation
# cannot be trusted) styled distinctly from format warnings (citation
# resolved, just deviated from the requested format) and info -- conflating
# these severities in one undifferentiated red box was the pre-Phase-6 UI's
# own version of the same bug aggregate_generation.py's rewrite fixed for the
# numeric side (severity-blind warning counts).
WARNING_STYLE = {
    "error": {"color": "#dc2626", "bg": "#fef2f2", "text": "#7f1d1d"},
    "warning": {"color": "#d97706", "bg": "#fffbeb", "text": "#78350f"},
    "info": {"color": "#2563eb", "bg": "#eff6ff", "text": "#1e3a5f"},
}


@st.cache_resource(show_spinner="Loading retrieval index (BGE-M3 + reranker)...")
def load_pipeline():
    index = ChunkIndex(ROOT / "data" / "index")
    reranker = CrossEncoderReranker()
    verses_by_number, stories_by_id = load_verses_and_stories(ROOT)
    return index, reranker, verses_by_number, stories_by_id


@st.cache_resource(show_spinner=False)
def load_generator(model: str):
    return Generator(model=model)


@st.cache_data(show_spinner=False)
def load_eval_json(name: str):
    path = ROOT / "data" / "eval" / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_eval_jsonl(name: str):
    path = ROOT / "data" / "eval" / name
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def render_claim(claim: dict):
    style = LAYER_STYLE.get(claim["layer"], {"color": "#6b7280", "bg": "#f9fafb", "label": claim["layer"].upper()})
    cite = ""
    if claim.get("group_id") or claim.get("verse_number"):
        parts = []
        if claim.get("verse_number"):
            parts.append(f"Dhp {claim['verse_number']}")
        if claim.get("group_id"):
            parts.append(f"story {claim['group_id']}")
        cite = " &middot; ".join(parts)
    else:
        cite = "no citation"
    st.markdown(
        f"""<div class="claim-card" style="--claim-color:{style['color']};--claim-bg:{style['bg']}">
        <span class="layer-badge" style="--claim-color:{style['color']}">{style['label']}</span>{claim['text']}
        <div class="claim-cite">{cite}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_warning(w) -> None:
    """Render one AuditWarning (generate/schemas.py), styled by severity.

    `w` is the dataclass object generate.Generator.generate() returns
    (w.severity / w.code / w.message / w.claim_index) -- not a dict. The API
    layer serializes these via warnings_to_dicts() for JSON responses; the UI
    calls the pipeline directly and gets the objects themselves.
    """
    style = WARNING_STYLE.get(w.severity, WARNING_STYLE["warning"])
    st.markdown(
        f"""<div class="warning-box" style="--warn-color:{style['color']};--warn-bg:{style['bg']};--warn-text:{style['text']}">
        <span class="warning-code" style="color:{style['color']}">{w.severity.upper()} / {w.code}</span>
        claim {w.claim_index}: {w.message}
        </div>""",
        unsafe_allow_html=True,
    )


def render_verse_group(bundle: dict, key_prefix: str):
    gids = ", ".join(s["group_id"] for s in bundle["stories"]) or "-"
    title = " / ".join(s["title_en"] for s in bundle["stories"])
    with st.expander(f"Dhp {bundle['verse_numbers']} -- {title}  (story {gids})", expanded=False):
        for v in bundle["verses"]:
            st.markdown(f"**Dhp {v['verse']}** ({v['vagga_name_pali']})")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"<span class='pali-text'>{v['pali_mahasangiti']}</span>", unsafe_allow_html=True)
                st.caption("Pali (Mahasangiti, CC0)")
            with col2:
                st.markdown(v["english_sujato"] or "*(not available)*")
                st.caption("English (Sujato, CC0)")
            if v.get("interlinear_english"):
                st.markdown(f"*{v['interlinear_english']}*")
                st.caption("English (Anandajoti interlinear)")
            st.divider()
        for s in bundle["stories"]:
            st.markdown(f"**Story {s['group_id']}: {s['title_en']}**")
            if s.get("synopsis"):
                st.markdown(s["synopsis"])
            if s.get("vatthu"):
                with st.expander("Full narrative (vatthu)", expanded=False):
                    st.markdown(s["vatthu"])


def page_query():
    st.title("Ask the Dhammapada")
    st.caption(
        "Hybrid retrieval (BGE-M3 dense+sparse+ColBERT, RRF-fused, cross-encoder reranked) "
        "+ layer-attributed generation (Qwen2.5, schema-constrained). Every generated claim "
        "is tagged verse / commentary / synthesis and cited back to its source."
    )

    with st.sidebar:
        st.header("Settings")
        model = st.selectbox("Generator model", ["qwen2.5:7b-instruct", "qwen2.5:1.5b-instruct", "qwen2.5:14b-instruct"], index=0)
        top_k = st.slider("Verse-groups to return", 1, 10, 3)
        candidates = st.slider("Rerank candidates", 5, 60, 30)
        do_generate = st.checkbox("Generate layer-attributed answer", value=True)
        st.caption("Retrieval-only is faster (~3-5s); generation adds an LLM call (~5-40s depending on model size).")

    # Phase 6 fix: the example buttons used to set a local `question` var
    # plus a session_state override that got popped on the SAME rerun --
    # which meant it never survived to the *next* rerun triggered by
    # clicking Search, so clicking an example then Search silently searched
    # for nothing. A callback that writes into the text_input's own
    # session_state key runs before the widget is instantiated, so the
    # value sticks across the click-example, then-click-Search sequence.
    def _set_question(text: str) -> None:
        st.session_state["question_input"] = text

    question = st.text_input("Question", key="question_input", placeholder="e.g. why did the Buddha teach Kisa Gotami about mustard seeds?")
    example_cols = st.columns(3)
    examples = [
        "the woman whose child died",
        "what does the Dhammapada say about anger?",
        "which single story explains Dhp 320, 321, and 322 together?",
    ]
    for col, ex in zip(example_cols, examples):
        col.button(ex, use_container_width=True, on_click=_set_question, args=(ex,))

    if st.button("Search", type="primary") and question:
        index, reranker, verses_by_number, stories_by_id = load_pipeline()

        if do_generate:
            generator = load_generator(model)
            with st.spinner("Retrieving and generating..."):
                bundles = query(
                    question, index=index, reranker=reranker, top_k=top_k, candidates=candidates,
                    root=ROOT, verses_by_number=verses_by_number, stories_by_id=stories_by_id,
                )
                try:
                    result = (
                        generator.generate(question, bundles, corpus_group_ids=set(stories_by_id))
                        if bundles else None
                    )
                except GenerationError as e:
                    st.error(f"Generation failed: {e}")
                    result = None

            if not bundles:
                st.warning("No retrieval results for this question.")
            else:
                if result:
                    st.subheader("Answer")
                    st.caption(
                        f"Model: {result['model']}  |  Latency: {result['latency_s']:.1f}s  |  "
                        f"Prompt: ~{result.get('prompt_tokens', '?')} tok / num_ctx {result.get('num_ctx', '?')}"
                    )
                    for c in result["answer"].claims:
                        render_claim(c.model_dump())
                    if result["warnings"]:
                        errors = [w for w in result["warnings"] if w.severity == "error"]
                        others = [w for w in result["warnings"] if w.severity != "error"]
                        if errors:
                            st.markdown(f"**Provenance errors ({len(errors)})** -- citations that cannot be trusted:")
                            for w in errors:
                                render_warning(w)
                        if others:
                            with st.expander(f"Format warnings and info ({len(others)}) -- resolvable, not hallucinations"):
                                for w in others:
                                    render_warning(w)
                st.subheader(f"Sources ({len(bundles)} verse-groups)")
                for i, b in enumerate(bundles):
                    render_verse_group(b, key_prefix=f"gen-{i}")
        else:
            with st.spinner("Retrieving..."):
                bundles = query(
                    question, index=index, reranker=reranker, top_k=top_k, candidates=candidates,
                    root=ROOT, verses_by_number=verses_by_number, stories_by_id=stories_by_id,
                )
            if not bundles:
                st.warning("No retrieval results for this question.")
            else:
                st.subheader(f"Retrieved verse-groups ({len(bundles)})")
                for i, b in enumerate(bundles):
                    render_verse_group(b, key_prefix=f"ret-{i}")


def page_browse():
    st.title("Browse the corpus")
    index, reranker, verses_by_number, stories_by_id = load_pipeline()

    mode = st.radio("Look up by", ["Verse number", "Story group_id"], horizontal=True)
    if mode == "Verse number":
        n = st.number_input("Dhp verse (1-423)", min_value=1, max_value=423, value=114)
        v = verses_by_number.get(n)
        if v:
            bundle = assemble({"group_id": None, "dhp_verses": [n]}, verses_by_number, stories_by_id)
            render_verse_group(bundle, key_prefix="browse-verse")
    else:
        gid = st.text_input("group_id (e.g. 8.13)", value="8.13")
        s = stories_by_id.get(gid)
        if s:
            bundle = assemble({"group_id": gid, "dhp_verses": s["dhp_verses"]}, verses_by_number, stories_by_id)
            render_verse_group(bundle, key_prefix="browse-story")
        elif gid:
            st.warning(f"No story '{gid}' found.")


def metric_row(labels_values):
    cols = st.columns(len(labels_values))
    for col, (label, value) in zip(cols, labels_values):
        col.metric(label, value)


def page_evaluation():
    st.title("Evaluation results (Phase 5)")
    st.markdown(
        "**Single-annotator (Claude) evaluation pass -- no inter-annotator agreement is computed or claimed.** "
        "See `docs/eval_rubric.md` for the full methodology and this caveat's justification."
    )

    ret = load_eval_json("retrieval_metrics.json")
    gen = load_eval_json("generation_metrics.json")

    if ret is None or gen is None:
        st.warning("Evaluation results not found. Run `src/dhammapada_rag/eval/*.py` first (see README).")
        return

    st.header("Retrieval")
    st.caption(f"{ret['n_questions']} gold questions, single relevant verse-group each (construction-from-known-answer -- see rubric).")

    b = ret["overall"]["baseline"]
    metric_row([("Recall@1", f"{b['recall@1']:.3f}"), ("Recall@10", f"{b['recall@10']:.3f}"), ("nDCG@10", f"{b['ndcg@10']:.3f}"), ("MRR", f"{b['mrr']:.3f}")])

    st.subheader("By query type")
    type_rows = []
    for qtype, d in ret["by_type"].items():
        m = d["baseline"]
        type_rows.append({"type": qtype, "n": d["n"], "Recall@1": m["recall@1"], "Recall@10": m["recall@10"], "nDCG@10": m["ndcg@10"], "MRR": m["mrr"]})
    df_type = pd.DataFrame(type_rows).sort_values("nDCG@10", ascending=False)
    st.dataframe(df_type, use_container_width=True, hide_index=True)
    # Phase 6 note: the Phase 2 chunking fix (title fields now indexed) moved
    # cross_recension to a perfect 1.000 -- it is no longer the worst type,
    # so the old caption naming it as such would now be a stale, incorrect
    # claim. 'alignment' (multiverse groupings) is the worst substantial-n
    # type post-fix; corpus_anomaly's 0.0 is n=2 and not a reliable estimate.
    worst_type = df_type[df_type["n"] >= 5].sort_values("nDCG@10").iloc[0]["type"]
    st.caption(
        f"'{worst_type}' scores worst among types with a meaningful sample size -- an aggregate-hides-the-result "
        "finding (see docs/evaluation.md). corpus_anomaly (n=2) is too small to draw a conclusion from on its own."
    )

    fig = go.Figure(go.Bar(x=df_type["type"], y=df_type["nDCG@10"], marker_color=["#dc2626" if t == worst_type else "#2563eb" for t in df_type["type"]]))
    fig.update_layout(title="nDCG@10 by query type (baseline)", yaxis_range=[0, 1], height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ablations (overall, delta from baseline, bootstrap 95% CI)")
    # Phase 6 fix: ablation_deltas_ndcg10 (paired-by-question bootstrap CIs)
    # is computed by aggregate_retrieval.py already -- recomputing a bare
    # point-delta here would throw away the CI and could silently diverge
    # from the number docs/evaluation.md reports.
    conds = ["verse_only", "dense_only", "no_rerank", "flat"]
    labels = {"verse_only": "Verse-only chunk set", "dense_only": "Dense-only (no RRF)", "no_rerank": "No cross-encoder rerank", "flat": "Flat chunking (no assembly)"}
    ad = ret["ablation_deltas_ndcg10"]
    deltas = [ad[c]["delta"] for c in conds]
    err_lo = [ad[c]["delta"] - ad[c]["ci"][0] for c in conds]
    err_hi = [ad[c]["ci"][1] - ad[c]["delta"] for c in conds]
    fig2 = go.Figure(go.Bar(
        x=[labels[c] for c in conds], y=deltas, marker_color="#7c3aed",
        error_y=dict(type="data", symmetric=False, array=err_hi, arrayminus=err_lo),
    ))
    fig2.update_layout(title="nDCG@10 drop when ablating each component (error bars: 95% CI)", yaxis_title="baseline - variant", height=350)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Verse-only chunking causes by far the largest drop -- the strongest evidence for the project's core "
        "architectural claim. Flat-vs-assembled shows ~no difference (a genuine null result, not oversold). "
        "**Read with care**: this overall number is pulled down by alignment/cross-recension questions that "
        "verse-only retrieval structurally cannot answer (their gold source is the commentary itself) -- the "
        "doctrinal row alone does *not* show the same drop; see `docs/evaluation.md`."
    )

    if ret.get("by_subtype"):
        st.subheader("By subtype")
        st.dataframe(pd.DataFrame([{"subtype": s, **d["baseline"]} for s, d in ret["by_subtype"].items()]), use_container_width=True, hide_index=True)
    else:
        st.caption("Subtype breakdown not available in this run (retrieval_eval.py does not currently propagate `subtype` into its output rows).")

    st.header("Generation")
    st.caption(f"{gen['n_questions']}-question stratified sample, {gen['n_claims']} claims, manually judged against a gold layer tag per claim.")
    metric_row([
        ("Accuracy", f"{gen['accuracy']:.3f}"),
        ("Macro-F1", f"{gen['macro_f1']:.3f}"),
        ("Conflation rate", f"{gen['conflation_rate']:.3f}"),
        ("Provenance errors", f"{gen['provenance_errors']}/{gen['n_claims']}"),
    ])

    st.subheader("Confusion matrix (rows = gold, columns = predicted)")
    cm = gen["confusion_matrix"]
    layers = ["verse", "commentary", "synthesis"]
    df_cm = pd.DataFrame([[cm[g][p] for p in layers] for g in layers], index=[f"gold: {g}" for g in layers], columns=[f"pred: {p}" for p in layers])
    st.dataframe(df_cm, use_container_width=True)
    st.caption(
        f"Conflation (commentary content tagged 'verse', the failure mode this system exists to catch): "
        f"{gen['commentary_tagged_verse']} instances. Reverse direction (verse tagged 'commentary'): "
        f"{gen['verse_tagged_commentary']} instances."
    )

    st.subheader("Per-class precision / recall / F1")
    pc_rows = [{"layer": l, **{k: v for k, v in d.items()}} for l, d in gen["per_class"].items()]
    st.dataframe(pd.DataFrame(pc_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Synthesis has perfect precision but the worst recall by a wide margin -- when the model does tag "
        "something 'synthesis' it's right, but it under-uses the tag, folding synthesis-type reasoning into "
        "verse or commentary claims instead."
    )

    sweep_rows = load_eval_jsonl("model_sweep_results_retries0.jsonl") + load_eval_jsonl("model_sweep_results_retries1.jsonl")
    if sweep_rows:
        st.header("Model-size sweep")
        st.caption(
            "Same retrieved context reused across all three sizes and both retry settings -- differences are "
            "attributable to the generator, not retrieval variance. 'Clean rate' is computed over ALL attempts, "
            "including failures, not just successful ones -- a model that fails outright doesn't get to drop out "
            "of the denominator."
        )
        model_order = ["qwen2.5:1.5b-instruct", "qwen2.5:7b-instruct", "qwen2.5:14b-instruct"]
        by_key = {}
        for r in sweep_rows:
            by_key.setdefault((r["model"], r["max_retries"]), []).append(r)
        sweep_summary = []
        for model in model_order:
            for max_retries in (0, 1):
                rows = by_key.get((model, max_retries))
                if not rows:
                    continue
                n = len(rows)
                n_clean = sum(1 for r in rows if r.get("clean"))
                avg_latency = sum(r["latency_s"] for r in rows) / n
                sweep_summary.append({
                    "model": model,
                    "max_retries": max_retries,
                    "n": n,
                    "clean_rate": round(n_clean / n, 3),
                    "avg_latency_s": round(avg_latency, 1),
                })
        df_sweep = pd.DataFrame(sweep_summary)
        st.dataframe(df_sweep, use_container_width=True, hide_index=True)

        fig3 = go.Figure()
        for mr, color in ((0, "#2563eb"), (1, "#7c3aed")):
            sub = df_sweep[df_sweep["max_retries"] == mr]
            fig3.add_trace(go.Bar(x=sub["model"], y=sub["clean_rate"], name=f"max_retries={mr}", marker_color=color))
        fig3.update_layout(
            title="Structural citation validity vs. model size and retry budget",
            yaxis=dict(title="Clean rate (zero provenance errors, all attempts)", range=[0, 1]),
            barmode="group",
            height=400,
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(
            "Structural citation validity improves sharply with model size (a real compute-constraint finding, "
            "not a modeling failure). Retrying on failure does **not** reliably help -- the 1.5B model's clean "
            "rate gets slightly *worse* with a retry enabled, not better, so retries are not a substitute for "
            "model capacity."
        )

    st.info("Full discussion and every number's provenance, including the pre-fix numbers this pass superseded: `docs/evaluation.md` (pre-fix baseline archived at `docs/evaluation_pre_fix.md`). Methodology and annotator-status caveats: `docs/eval_rubric.md`.")


def main():
    tabs = st.tabs(["Ask a question", "Browse corpus", "Evaluation results"])
    with tabs[0]:
        page_query()
    with tabs[1]:
        page_browse()
    with tabs[2]:
        page_evaluation()


if __name__ == "__main__":
    main()
