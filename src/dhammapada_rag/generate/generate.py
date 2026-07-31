"""Generation with enforced layer attribution (DhammapadaRAG.txt Phase 4).

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
    AuditWarning,
    LayeredAnswer,
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
        "prompt_tokens": int, "num_ctx": int} so callers keep retrieval
        provenance and context-budget evidence alongside the claims.
        """
        messages = build_messages(question, bundles)
        schema = LayeredAnswer.model_json_schema()

        prompt_tokens = estimate_tokens(messages)
        budget = self.num_ctx - COMPLETION_HEADROOM
        if prompt_tokens > budget:
            raise ContextOverflowError(
                f"Prompt is ~{prompt_tokens} tokens but only {budget} fit in "
                f"num_ctx={self.num_ctx} after reserving {COMPLETION_HEADROOM} for the "
                f"completion. Ollama would silently truncate, dropping the commentary. "
                f"Raise num_ctx, lower top_k, or lower prompt.NARRATIVE_BUDGET_CHARS."
            )

        last_error: Exception | None = None
        total_latency = 0.0

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
                raise GenerationError(
                    f"Ollama request failed (is `ollama serve` running with model "
                    f"{self.model!r} pulled?): {e}"
                ) from e

            total_latency += time.time() - t0
            content = resp.json()["message"]["content"]

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
                            "group_id and verse_number."
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

    print(
        f"Model: {result['model']}  Latency: {result['latency_s']:.1f}s  "
        f"Attempt: {result['attempt']}  Prompt: ~{result['prompt_tokens']} tok "
        f"/ num_ctx {result['num_ctx']}"
    )

    layers = [c.layer for c in result["answer"].claims]
    counts = {l: layers.count(l) for l in ("verse", "commentary", "synthesis")}
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
        src = f"[{c.layer} | Dhp {c.verse_number} | {c.group_id}]" if (c.verse_number or c.group_id) else f"[{c.layer}]"
        print(f"{src} {c.text}")


if __name__ == "__main__":
    main()
