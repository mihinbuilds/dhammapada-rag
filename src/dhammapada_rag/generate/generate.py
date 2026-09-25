"""Generation with enforced layer attribution (docs/project_plan.md Phase 4).

Uses Ollama's structured-output support (`format: <json schema>`, grammar-
constrained decoding, not just prompted JSON) to guarantee every response
parses as `LayeredAnswer` -- the model cannot emit prose outside the
verse/commentary/synthesis claim structure, which is the actual enforcement
mechanism behind "make the output format make [conflation] visible."

--------------------------------------------------------------------------
CRITICAL FIX -- num_ctx. The previous revision passed only
`options={"temperature": ...}` to Ollama. Ollama defaults num_ctx to 2048
tokens. This prompt carries, per retrieved group, Pali plus two English
translations plus a full narrative body (a vatthu runs 500-5000 words),
times top_k groups. At 2048 tokens the commentary was truncated away before
the model ever saw it -- which is the direct cause of the observed output
where 100% of claims came back tagged 'verse' and zero tagged 'commentary'.
The system's entire thesis was being silently deleted by a default.

num_ctx is now set explicitly, the rendered prompt is measured before the
call, and overflow raises rather than silently truncating. Any generation
metric collected before this fix (layer attribution accuracy, anachronistic
conflation rate, the model-size sweep) measured a truncated context and must
be re-run.

Also fixed:
- temperature defaults to 0.0 and `seed` is accepted, so single-sample eval
  runs are reproducible instead of being unmeasured draws from a sampler.
- the retry path previously resent a byte-identical prompt and hoped for a
  different parse. It now appends the validation error so the retry has
  something to correct, and accumulates latency across attempts rather than
  reporting only the last one.
- warnings are AuditWarning dataclasses (see generate/schemas.py); callers
  that serialize to JSON or across HTTP must use `warnings_to_dicts()`.

ROUND 5, TASK K -- CITATIONS CONSTRAINED AT THE DECODER, NOT JUST AUDITED
AFTER THE FACT. Four rounds of prompt instructions about group_id/
verse_number format produced citations like "g17.8", "inferred from Dhp 1
commentary", and both fields left null even on verse claims -- the model
complying unevenly with a prompt that had grown long enough to dilute any
one instruction's weight. `_constrained_schema()` builds `format` per
request from the retrieved `bundles`, restricting `group_id` and
`verse_number` to enums of the values actually in context. Grammar-
constrained decoding cannot emit a token sequence outside the grammar, so
"g17.8" and "Dhp 114" become unrepresentable rather than merely
discouraged -- this moves citation validity from an instruction the model
may ignore to a constraint it cannot violate. `MALFORMED_GROUP_ID`,
`UNPARSEABLE_GROUP_ID`, `UNKNOWN_GROUP_ID`, and `GROUP_NOT_RETRIEVED`
should now be structurally unreachable on the happy path (kept in
schemas.py regardless -- their staying silent is the evidence this works,
and the fallback path below can still trigger them). `VERSE_GROUP_MISMATCH`
is NOT prevented: the two fields are constrained independently, so a valid
group_id can still be paired with a valid-but-wrong verse_number from a
different retrieved group -- the one citation error left for the audit
layer to catch, and worth reporting as such.

If Ollama rejects the constrained schema outright (a grammar-compilation
failure, not a generation failure), `generate()` logs the rejection and
falls back to the static, unconstrained schema for that request rather than
failing it -- but the rejection is recorded in the returned dict
(`schema_status`) and printed, since silently reverting would hide the
whole point of this change from anyone measuring it.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhammapada_rag.generate.prompt import build_messages, estimate_tokens  # noqa: E402
from dhammapada_rag.generate.render import render_plain  # noqa: E402
from dhammapada_rag.generate.schemas import (  # noqa: E402
    AlignmentClaim,
    AuditWarning,
    CommentaryClaim,
    LayeredAnswer,
    VerseClaim,
    audit,
    bundles_have_commentary,
)

DEFAULT_MODEL = "qwen2.5:7b-instruct"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Qwen2.5 supports 32k natively. 16384 comfortably fits three verse-groups
# with full narratives plus the system prompt plus generation headroom, and
# stays within what a 14B model will hold on consumer hardware. Raise if
# top_k > 3; lower only with the prompt's NARRATIVE_BUDGET_CHARS lowered too.
DEFAULT_NUM_CTX = 16384

# Tokens reserved for the model's own output. Ollama's num_ctx covers prompt
# + completion, so the prompt must fit in (num_ctx - this).
COMPLETION_HEADROOM = 1536


def _fit_narrative_budget(question: str, bundles: list[dict], token_budget: int) -> int:
    """Largest per-bundle narrative_budget_chars (prompt.py) whose rendered
    prompt still fits token_budget, found by measuring the actual rendered
    prompt rather than hand-modeling token cost.

    Replaces a flat NARRATIVE_BUDGET_CHARS=6000 applied regardless of
    num_ctx headroom or story length. Observed failure this fixes: asked
    "who is the chakkhupala?", retrieval correctly surfaced Dhp 1 / story
    1.1, but that story's vatthu is 31,178 characters -- the flat 6000-char
    cap cut it off during the scene-setting backstory, before the text ever
    reaches Cakkhupala going blind or attaining Awakening. The model's
    answer was consequently built from the one-sentence synopsis alone,
    reading as thin not because it failed to synthesize but because the
    narrative it would synthesize from was never in its context. The prompt
    at the time used ~10k of a 16k-token num_ctx -- there was room for far
    more of the story. Binary search (not a bigger flat constant) because
    the right amount depends on num_ctx, how many bundles were retrieved,
    and each one's actual vatthu length -- three questions with different
    shapes should not share one guess.
    """
    longest = max((len(s.get("vatthu") or "") for b in bundles for s in b["stories"]), default=0)
    if longest == 0:
        return 0
    # Fits with every story's full text? No search needed.
    if estimate_tokens(build_messages(question, bundles, narrative_budget_chars=longest)) <= token_budget:
        return longest
    lo, hi, best = 0, longest, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if estimate_tokens(build_messages(question, bundles, narrative_budget_chars=mid)) <= token_budget:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _constrained_schema(bundles: list[dict]) -> dict:
    """JSON Schema with citation fields restricted to what is in context.

    Grammar-constrained decoding cannot emit a token sequence outside the
    grammar, so an enum here makes "g17.8", "Dhp 114", and "inferred from
    Dhp 1 commentary" unrepresentable. This moves citation validity from an
    instruction the model may ignore to a constraint it cannot violate.

    Built fresh per request (bundles differ per query), not cached: the
    valid citation set IS the retrieved context, so this schema is
    necessarily query-specific.

    Round 4/5 amendment (Task K/L amendment): Claim is now a discriminated
    union (VerseClaim / CommentaryClaim / SynthesisClaim, see schemas.py),
    so there is no single "Claim" $def to patch -- group_id/verse_number are
    constrained on VerseClaim and CommentaryClaim only (both require them
    non-null already; this narrows the *value*, same as before). SynthesisClaim
    has no such fields and is left untouched.

    Round 7, Task T: AlignmentClaim gets the same group_id enum as
    VerseClaim/CommentaryClaim, plus each element of its verse_numbers list
    constrained to the retrieved vnums (an array of enum'd items, not a
    single enum -- the field is a list by design, see schemas.py's
    AlignmentClaim). This constrains membership only: the decoder cannot
    invent a group_id or a verse number that was never retrieved, but it
    can still emit a *subset* of a group's true range (e.g. [4] instead of
    [3, 4]) since which verses belong together is a fact about the corpus,
    not enumerable from bundles alone here -- that completeness check is
    audit()'s ALIGNMENT_RANGE_INCOMPLETE (Task U), not a decoder constraint.

    Round 8, Task Z: the top-level `source_disposition` field is constrained
    to an object keyed by exactly the retrieved group_ids, each required and
    enum'd to the three Disposition values, additionalProperties=False. See
    this function's body for why that makes coverage decoder-enforced.
    """
    schema = LayeredAnswer.model_json_schema()
    gids = sorted({s["group_id"] for b in bundles for s in b["stories"]})
    vnums = sorted({n for b in bundles for n in b["verse_numbers"]})
    if not gids or not vnums:
        raise ValueError(
            f"Cannot build a constrained schema from bundles with no group_ids/verse_numbers "
            f"(gids={gids!r}, vnums={vnums!r}) -- retrieval returned nothing citable."
        )

    defs = schema.get("$defs", {})
    for name in ("VerseClaim", "CommentaryClaim"):
        props = defs.get(name, {}).get("properties")
        if not props:
            raise ValueError(f"Could not locate {name} properties in generated schema")
        props["group_id"] = {
            "type": "string", "enum": gids,
            "description": "Story group_id from the provided sources.",
        }
        props["verse_number"] = {
            "type": "integer", "enum": vnums,
            "description": "Dhp verse number from the provided sources.",
        }

    alignment_props = defs.get("AlignmentClaim", {}).get("properties")
    if not alignment_props:
        raise ValueError("Could not locate AlignmentClaim properties in generated schema")
    alignment_props["group_id"] = {
        "type": "string", "enum": gids,
        "description": "Story group_id from the provided sources.",
    }
    alignment_props["verse_numbers"] = {
        "type": "array", "minItems": 1,
        "items": {"type": "integer", "enum": vnums},
        "description": "The group's FULL list of Dhp verse numbers from the provided sources.",
    }

    # Round 8, Task Z: source_disposition constrained to an object with
    # EXACTLY the retrieved group_ids as keys -- additionalProperties=False
    # blocks a group that was never retrieved, and every gid listed in
    # "required" blocks omitting one that was. This is what makes context
    # utilization measurable directly from the field rather than inferred
    # from claim citations after the fact (Round 7's heuristic, which
    # measured 0/27 answers as fully accounted for because it could only
    # detect a dismissal shaped like prose naming the group): the decoder
    # cannot produce a schema-valid answer that leaves a group out.
    top_props = schema.get("properties")
    if not top_props:
        raise ValueError("Could not locate top-level LayeredAnswer properties in generated schema")
    top_props["source_disposition"] = {
        "type": "object",
        "properties": {gid: {"type": "string", "enum": ["used", "partially_relevant", "not_relevant"]} for gid in gids},
        "required": gids,
        "additionalProperties": False,
        "description": "One entry for EVERY retrieved group_id -- see the field description.",
    }
    return schema


class GenerationError(RuntimeError):
    pass


class ContextOverflowError(GenerationError):
    """Prompt does not fit in num_ctx.

    Raised rather than letting Ollama truncate. Silent truncation drops the
    commentary and produces an answer that looks fine and is structurally
    valid while missing the layer the system exists to surface -- the worst
    possible failure mode, because nothing downstream can detect it.
    """


def warnings_to_dicts(warnings: list[AuditWarning]) -> list[dict]:
    """JSON-serializable form of audit warnings.

    Use at every boundary that writes JSON or crosses HTTP:
    eval/generation_metrics.py, eval/model_sweep.py, api/main.py.
    """
    return [
        {"code": w.code, "severity": w.severity, "claim_index": w.claim_index, "message": w.message}
        for w in warnings
    ]


class Generator:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ollama_url: str = OLLAMA_URL,
        temperature: float = 0.0,
        seed: int | None = None,
        num_ctx: int = DEFAULT_NUM_CTX,
        timeout: int = 600,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.temperature = temperature
        self.seed = seed
        self.num_ctx = num_ctx
        # 14B on CPU-backed hardware can exceed the old 180s ceiling on long
        # contexts; a timeout there was being recorded as a model failure.
        self.timeout = timeout

    def _options(self) -> dict:
        opts: dict = {"temperature": self.temperature, "num_ctx": self.num_ctx}
        if self.seed is not None:
            opts["seed"] = self.seed
        return opts

    def generate(
        self,
        question: str,
        bundles: list[dict],
        max_retries: int = 2,
        corpus_group_ids: set[str] | None = None,
    ) -> dict:
        """Retrieve-then-generate is the caller's job (bundles come from
        index/assemble.py's query()); this only does the generation step.

        Returns {"answer": LayeredAnswer, "warnings": [AuditWarning],
        "latency_s": float, "model": str, "attempt": int,
        "prompt_tokens": int, "num_ctx": int, "schema_status": str} so
        callers keep retrieval provenance and context-budget evidence
        alongside the claims. schema_status is "constrained" on the happy
        path (Task K) or "static (constrained schema rejected: <error>)" if
        Ollama rejected the per-request grammar and generate() fell back --
        report this rather than treat it as invisible, since a fallback here
        means citation values for this one answer are audited only, not
        made impossible to get wrong.
        """
        budget = self.num_ctx - COMPLETION_HEADROOM
        narrative_budget_chars = _fit_narrative_budget(question, bundles, budget)
        messages = build_messages(question, bundles, narrative_budget_chars=narrative_budget_chars)
        try:
            schema = _constrained_schema(bundles)
            schema_status = "constrained"
        except ValueError as e:
            # Retrieval returned nothing citable (e.g. empty bundles) -- not
            # an Ollama rejection, just nothing to constrain against.
            schema = LayeredAnswer.model_json_schema()
            schema_status = f"static (no citable bundles: {e})"

        prompt_tokens = estimate_tokens(messages)
        if prompt_tokens > budget:
            raise ContextOverflowError(
                f"Prompt is ~{prompt_tokens} tokens but only {budget} fit in "
                f"num_ctx={self.num_ctx} after reserving {COMPLETION_HEADROOM} for the "
                f"completion, even with narrative truncated to {narrative_budget_chars} chars "
                f"per bundle. Ollama would silently truncate, dropping the commentary. "
                f"Raise num_ctx or lower top_k."
            )

        last_error: Exception | None = None
        total_latency = 0.0

        schema_fallback_tried = False
        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                resp = requests.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "format": schema,
                        "stream": False,
                        "options": self._options(),
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                if schema_status == "constrained" and not schema_fallback_tried:
                    # Ollama rejected the per-request constrained schema (a
                    # grammar-compilation failure, distinct from the model
                    # producing bad output) -- fall back to the static
                    # schema for this request rather than failing it
                    # outright. schema_status records the rejection so it is
                    # reported, not silently reverted -- the whole point of
                    # Task K is that this path *shouldn't* be needed.
                    print(
                        f"WARNING: Ollama rejected the constrained citation schema, "
                        f"falling back to the unconstrained schema: {e}",
                        file=sys.stderr,
                    )
                    schema = LayeredAnswer.model_json_schema()
                    schema_status = f"static (constrained schema rejected: {e})"
                    schema_fallback_tried = True
                    continue
                raise GenerationError(
                    f"Ollama request failed (is `ollama serve` running with model "
                    f"{self.model!r} pulled?): {e}"
                ) from e

            total_latency += time.time() - t0
            resp_json = resp.json()
            content = resp_json["message"]["content"]
            # Round 5, Task N: wall-clock latency conflates model size with
            # prompt length (and, before Task L, prompt length varied across
            # rounds as SYSTEM_PROMPT grew). Ollama reports its own
            # generation-only token count and duration (nanoseconds,
            # excluding prompt eval and network/serialization overhead) --
            # eval_count/eval_duration -- from which tokens/sec is a fairer
            # cross-model comparison than latency alone. Only the values
            # from the attempt that actually returns are kept (each retry
            # overwrites these), so a retry's wasted generation doesn't
            # affect the reported rate of the answer actually used.
            eval_count = resp_json.get("eval_count")
            eval_duration_ns = resp_json.get("eval_duration")

            try:
                answer = LayeredAnswer.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                # Give the retry something to correct. Resending an identical
                # prompt at temperature 0 is a no-op; the old code did exactly
                # that, which is why retries almost never recovered.
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "That response did not validate against the required schema:\n"
                            f"{e}\n\nReturn ONLY a JSON object matching the schema. Every "
                            "claim needs text, layer, and (for verse/commentary layers) "
                            "group_id and verse_number. source_disposition must have exactly "
                            "one entry for every retrieved group_id."
                        ),
                    },
                ]
                continue

            # STOP GATE 3 fix: a schema-valid answer that ignores the
            # commentary is not a JSON-validation failure, so the branch
            # above never catches it -- verified reproducible at temperature
            # 0 across multiple questions even with the full commentary
            # present well under num_ctx. The prompt's prose instruction
            # ("must draw on both layers") is not self-enforcing; nothing
            # upstream of this rejected the answer for ignoring it. Retry
            # with an explicit corrective message, same principle as the
            # JSON-validation retry above: a bare resend at temperature 0
            # would just reproduce the identical answer.
            has_commentary = bundles_have_commentary(bundles)
            zero_commentary_claims = not any(c.layer == "commentary" for c in answer.claims)
            if has_commentary and zero_commentary_claims and attempt < max_retries:
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "Your answer contained zero claims tagged 'commentary', but the "
                            "source material above includes a substantial story (vatthu) "
                            "explaining this verse. Revise your answer: add at least one "
                            "claim tagged 'commentary' describing what that story says (who, "
                            "when, why), citing its group_id and verse_number. Only omit a "
                            "commentary claim if you can state, as a 'synthesis' claim, a "
                            "specific reason the story does not bear on the question."
                        ),
                    },
                ]
                continue

            warnings = audit(answer, bundles, corpus_group_ids=corpus_group_ids)
            return {
                "answer": answer,
                "warnings": warnings,
                "latency_s": total_latency,
                "model": self.model,
                "attempt": attempt + 1,
                "prompt_tokens": prompt_tokens,
                "num_ctx": self.num_ctx,
                "schema_status": schema_status,
                "eval_count": eval_count,
                "eval_duration_ns": eval_duration_ns,
                "tokens_per_second": (eval_count / (eval_duration_ns / 1e9))
                    if eval_count and eval_duration_ns else None,
            }

        raise GenerationError(
            f"Model output didn't validate against LayeredAnswer after "
            f"{max_retries + 1} attempts: {last_error}"
        )


def main() -> None:
    import argparse

    from dhammapada_rag.index.assemble import load_verses_and_stories, query  # noqa: E402

    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top_k", type=int, default=3)
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    bundles = query(args.question, top_k=args.top_k, root=root)
    _, stories_by_id = load_verses_and_stories(root)

    gen = Generator(model=args.model, num_ctx=args.num_ctx, seed=args.seed)
    result = gen.generate(args.question, bundles, corpus_group_ids=set(stories_by_id))

    tps = f"{result['tokens_per_second']:.1f} tok/s" if result["tokens_per_second"] else "n/a"
    print(
        f"Model: {result['model']}  Latency: {result['latency_s']:.1f}s ({tps})  "
        f"Attempt: {result['attempt']}  Prompt: ~{result['prompt_tokens']} tok "
        f"/ num_ctx {result['num_ctx']}  Schema: {result['schema_status']}"
    )

    layers = [c.layer for c in result["answer"].claims]
    counts = {l: layers.count(l) for l in ("verse", "commentary", "alignment", "synthesis")}
    print(f"Layers: {counts}")
    if counts["commentary"] == 0:
        print(
            "  !! Zero commentary claims. Check that the retrieved groups actually "
            "carry vatthu text and that the prompt fits num_ctx."
        )

    if result["warnings"]:
        print("WARNINGS:")
        for w in result["warnings"]:
            print(f"  - {w}")
    print()
    print(render_plain(result["answer"]))
    print()
    for c in result["answer"].claims:
        if isinstance(c, (VerseClaim, CommentaryClaim)):
            src = f"[{c.layer} | Dhp {c.verse_number} | {c.group_id}]"
        elif isinstance(c, AlignmentClaim):
            src = f"[{c.layer} | Dhp {c.verse_numbers} | {c.group_id}]"
        else:
            src = f"[{c.layer}]"
        print(f"{src} {c.text}")


if __name__ == "__main__":
    main()
