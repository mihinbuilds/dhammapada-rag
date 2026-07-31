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

CUSTOM_CSS = """
<style>
.claim-card {
    border-left: 4px solid var(--claim-color);
    background: var(--claim-bg);
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
    color: #64748b;
    margin-top: 0.25rem;
}
.warning-box {
    border-left: 4px solid #dc2626;
    background: #fef2f2;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
    color: #991b1b;
}
.pali-text { font-style: italic; color: #4b5563; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


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

    question = st.text_input("Question", placeholder="e.g. why did the Buddha teach Kisa Gotami about mustard seeds?")
    example_cols = st.columns(3)
    examples = [
        "the woman whose child died",
        "what does the Dhammapada say about anger?",
        "which single story explains Dhp 320, 321, and 322 together?",
    ]
    for col, ex in zip(example_cols, examples):
        if col.button(ex, use_container_width=True):
            question = ex
            st.session_state["_question_override"] = ex
    if "_question_override" in st.session_state:
        question = st.session_state.pop("_question_override")

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
                    result = generator.generate(question, bundles) if bundles else None
                except GenerationError as e:
                    st.error(f"Generation failed: {e}")
                    result = None

            if not bundles:
                st.warning("No retrieval results for this question.")
            else:
                if result:
                    st.subheader("Answer")
                    st.caption(f"Model: {result['model']}  |  Latency: {result['latency_s']:.1f}s")
                    for c in result["answer"].claims:
                        render_claim(c.model_dump())
                    if result["warnings"]:
                        st.markdown("**Provenance audit warnings**")
                        for w in result["warnings"]:
                            st.markdown(f"<div class='warning-box'>{w}</div>", unsafe_allow_html=True)
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
    sweep_rows = load_eval_jsonl("model_sweep_results.jsonl")

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
    st.caption("Cross-recension questions score far worse than the other three types -- an aggregate-hides-the-result finding (see docs/evaluation.md).")

    fig = go.Figure(go.Bar(x=df_type["type"], y=df_type["nDCG@10"], marker_color=["#dc2626" if t == "cross_recension" else "#2563eb" for t in df_type["type"]]))
    fig.update_layout(title="nDCG@10 by query type (baseline)", yaxis_range=[0, 1], height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ablations (overall, delta from baseline)")
    conds = ["verse_only", "dense_only", "no_rerank", "flat"]
    labels = {"verse_only": "Verse-only chunk set", "dense_only": "Dense-only (no RRF)", "no_rerank": "No cross-encoder rerank", "flat": "Flat chunking (no assembly)"}
    deltas = [b["ndcg@10"] - ret["overall"][c]["ndcg@10"] for c in conds]
    fig2 = go.Figure(go.Bar(x=[labels[c] for c in conds], y=deltas, marker_color="#7c3aed"))
    fig2.update_layout(title="nDCG@10 drop when ablating each component", yaxis_title="baseline - variant", height=350)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Verse-only chunking causes by far the largest drop -- the strongest evidence for the project's core architectural claim. Flat-vs-assembled shows ~no difference (a genuine null result, not oversold).")

    st.header("Generation")
    st.caption(f"{gen['n_questions']}-question stratified sample, {gen['n_claims']} claims, manually judged.")
    metric_row([
        ("Layer attribution accuracy", f"{gen['layer_attribution_accuracy']:.3f}"),
        ("Anachronistic conflation rate", f"{gen['anachronistic_conflation_rate']:.3f}"),
        ("Structural warnings", f"{gen['n_structural_warnings']}/{gen['n_claims']}"),
    ])
    gen_rows = [{"type": t, "n_claims": d["n_claims"], "accuracy": d["accuracy"], "conflation_rate": d["conflation_rate"]} for t, d in gen["by_type"].items()]
    st.dataframe(pd.DataFrame(gen_rows).sort_values("conflation_rate", ascending=False), use_container_width=True, hide_index=True)
    st.caption("Cross-recension claims show both the worst accuracy and by far the worst conflation rate -- bad retrieval cascades into overconfident, mistagged generation.")

    if sweep_rows:
        st.header("Model-size sweep")
        st.caption("Same retrieved context reused across all three sizes -- differences are attributable to the generator, not retrieval variance.")
        by_model = {}
        for r in sweep_rows:
            if not r.get("success"):
                continue
            by_model.setdefault(r["model"], []).append(r)
        sweep_summary = []
        for model, rows in by_model.items():
            n = len(rows)
            avg_latency = sum(r["latency_s"] for r in rows) / n
            total_claims = sum(r["n_claims"] for r in rows)
            total_warnings = sum(r["n_structural_warnings"] for r in rows)
            sweep_summary.append({"model": model, "avg_latency_s": round(avg_latency, 1), "structural_warning_rate": round(total_warnings / total_claims, 3)})
        df_sweep = pd.DataFrame(sweep_summary)
        st.dataframe(df_sweep, use_container_width=True, hide_index=True)

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=df_sweep["model"], y=df_sweep["structural_warning_rate"], name="Structural warning rate", marker_color="#dc2626", yaxis="y"))
        fig3.add_trace(go.Scatter(x=df_sweep["model"], y=df_sweep["avg_latency_s"], name="Avg latency (s)", mode="lines+markers", marker_color="#2563eb", yaxis="y2"))
        fig3.update_layout(
            title="Citation reliability vs. latency by model size",
            yaxis=dict(title="Structural warning rate", range=[0, 1]),
            yaxis2=dict(title="Avg latency (s)", overlaying="y", side="right"),
            height=400,
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Citation reliability improves monotonically with model size, at a proportional latency cost -- a real compute-constraint finding, not a modeling failure.")

    st.info("Full discussion and every number's provenance: `docs/evaluation.md`. Methodology and annotator-status caveats: `docs/eval_rubric.md`.")


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
