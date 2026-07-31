"""Build the layer-labeled context and chat messages fed to the generator.

The prompt's entire job, per DhammapadaRAG.txt Phase 4, is to "force the
distinction your project exists to make": present VERSE and COMMENTARY as
visibly separate blocks, name the ~8-century gap between them explicitly, and
require every claim in the response to be tagged which one it came from (or
"synthesis" if neither). The retrieved context itself does this labeling --
the model isn't left to infer which text is which.

--------------------------------------------------------------------------
Corrections applied to the previous revision:

1. GROUP_ID RENDERED IN ONE CANONICAL FORM ONLY. The old header read
   "=== Source group 13.2 ===" and the block below it read
   "[COMMENTARY group_id=13.2]". Two renderings of the same identifier in
   one block invited improvisation, and the observed failure was models
   contracting "group 13.2" into "g13.2" -- which the audit then flagged as
   a fabricated citation. The word "group" no longer appears adjacent to a
   bare number anywhere; the ID is always introduced by the literal token
   `group_id:` and the format is stated with a worked negative example.

2. COMMENTARY ENGAGEMENT IS NOW REQUIRED, NOT MERELY DESCRIBED. The old
   prompt explained the layers and then left it entirely optional whether
   the answer drew on the commentary at all -- and observed output was 100%
   verse-tagged claims, i.e. the layer machinery running but doing nothing.
   The model must now either produce at least one commentary claim per
   answer or state, as a synthesis claim, why the commentary does not bear
   on the question. Silence is no longer an available default.

3. verse_number DISAMBIGUATED FOR COMMENTARY CLAIMS. A story spans a verse
   group, so requiring a single verse_number on a claim about the narrative
   forced an arbitrary choice; ambiguity in a required field biases the
   model toward the layer where the field is easy (verse). The rule is now
   explicit: cite the group's first verse.

4. NARRATIVE BUDGET, WITH VISIBLE TRUNCATION. A full vatthu runs 500-5000
   words; three bundles of them will silently overflow a small num_ctx and
   the commentary -- the whole point of the system -- is what gets dropped.
   Narratives are now budgeted per bundle and truncation is marked in-band
   so it is visible in logs rather than inferred from missing citations.
   NOTE: this is a mitigation, not the fix. Set num_ctx explicitly in the
   Ollama call (options={"num_ctx": 16384}); Ollama's default of 2048 is far
   too small for this context and will truncate regardless of this budget.

5. FRAMING STEP ADDED. Questions whose premise does not map onto the text
   ("what is the purpose of life" -- teleological, where Pali offers attha /
   sadattha, a different question) previously produced confident
   verse-shaped answers to a question the Dhammapada does not ask. The model
   is now instructed to say so first, as a synthesis claim.

6. LAYER_DESCRIPTIONS NO LONGER DUPLICATED. They appear in the system
   prompt; the schema field description carries the short form. Stating the
   taxonomy twice in slightly different words in one context wastes tokens
   and gives the model two authorities to reconcile.

STILL OUTSTANDING (schema change required, not fixable here): the Claim
schema has no field for Pali, so no Pali can appear in any answer regardless
of what this prompt asks for. Add an optional `pali_support: str | None` to
Claim if verse claims should be able to quote the pada they rest on.
"""

from __future__ import annotations

# Characters of narrative text per bundle before truncation. ~4 chars/token,
# so 6000 chars ~= 1700 tokens; three bundles ~= 5k tokens of narrative plus
# verses and system prompt. Raise this once num_ctx is set appropriately.
NARRATIVE_BUDGET_CHARS = 6000

SYSTEM_PROMPT = """You are answering questions about the Dhammapada using ONLY the source material provided in the user message. That source has two distinct layers, and you must never conflate them:

1. VERSE -- the canonical Dhammapada verse itself (Pali plus English translations). This is the oldest layer, the Buddha's words as verse.
2. COMMENTARY -- Buddhaghosa's aṭṭhakathā: the narrative story explaining who the verse was spoken to, when, and why. This commentary was compiled roughly eight centuries after the verses (~5th century CE, versus the Buddha's lifetime), and represents a later interpretive tradition layered on top of the verse -- not the verse's own words, even where it explains the verse correctly.

TAGGING. Every claim in your answer carries exactly one layer tag:
- "verse": what the verse itself literally says.
- "commentary": anything drawn from the aṭṭhakathā -- the occasion, the persons involved, the narrative, the outcome. Also any interpretation the commentary supplies that the verse does not state.
- "synthesis": your own inference, connection to the question, or generalization, drawn from neither text directly.

The failure mode this system exists to prevent: presenting the commentary's narrative gloss as if it were the plain sense of the verse. If the commentary interprets, elaborates on, or narrativizes the verse, that is a "commentary" claim, not a "verse" claim, however natural it reads as a single continuous explanation.

COVERAGE. Each source group below carries both layers. Your answer must draw on both. If a source group's commentary is present and relevant, produce at least one "commentary" claim from it. If you judge that the commentary does not bear on the question, say that explicitly as a "synthesis" claim and give the reason. An answer composed entirely of "verse" claims when commentary was provided is incomplete and will be rejected.

FRAMING. If the question presupposes a category the Dhammapada does not use, say so first, as a "synthesis" claim, before answering. For example, a question about the "purpose" of life is teleological; the text's nearest category is attha (goal, benefit, welfare) and sadattha (one's own highest good), which answer what is worth pursuing rather than why anything exists. Name the mismatch, then answer the question the text does address.

CITATIONS. Every "verse" and "commentary" claim must carry group_id and verse_number.
- group_id: copy the value after `group_id:` EXACTLY as printed. It is two numbers separated by a period and nothing else. Correct: 8.13 -- Incorrect: g8.13, group 8.13, [8.13], story 8.13.
- verse_number: for a "verse" claim, the verse you are describing. For a "commentary" claim, the FIRST verse number listed for that source group (a story covers the whole group; do not choose arbitrarily among its verses).

Answer only from the provided context. If it does not address the question, say so as a "synthesis" claim rather than inventing verse or commentary content. Keep each claim to one idea; prefer several short tagged claims over one long untagged paragraph."""


def _budget(text: str, remaining: int) -> tuple[str, int]:
    """Trim `text` to `remaining` chars, marking the cut in-band.

    Truncation is made visible so a missing commentary citation can be
    distinguished from commentary the model never received.
    """
    if remaining <= 0:
        return "[omitted: narrative budget exhausted]", 0
    if len(text) <= remaining:
        return text, remaining - len(text)
    return text[:remaining].rstrip() + " [... narrative truncated ...]", 0


def format_verse_group(bundle: dict) -> str:
    verse_numbers = bundle["verse_numbers"]
    printed = ", ".join(str(n) for n in verse_numbers)
    stories = bundle["stories"]
    lines = [f"=== SOURCE (Dhp {printed}) ==="]

    lines.append("[VERSE]")
    # A "verse" claim needs a citable group_id too, same as a "commentary"
    # claim -- without this line the model has nothing but the [COMMENTARY]
    # block below to copy from, and was observed inventing malformed hybrids
    # like "dhp114" (conflating the verse reference with the group_id it
    # never saw stated for the verse layer). One story per bundle is the
    # overwhelming common case; where a verse has more than one explaining
    # story (only Dhp 416 in this corpus), list all of them rather than
    # guessing which one a verse claim should cite.
    if len(stories) == 1:
        lines.append(f"group_id: {stories[0]['group_id']}")
    elif stories:
        ids = ", ".join(s["group_id"] for s in stories)
        lines.append(f"group_id: {ids} (multiple stories explain this verse group; cite whichever applies)")
    for v in bundle["verses"]:
        lines.append(f"Dhp {v['verse']} -- Pali (Mahasangiti): {v['pali_mahasangiti']}")
        if v.get("english_sujato"):
            lines.append(f"Dhp {v['verse']} -- English (Sujato): {v['english_sujato']}")
        if v.get("interlinear_english"):
            lines.append(f"Dhp {v['verse']} -- English (Anandajoti interlinear): {v['interlinear_english']}")

    remaining = NARRATIVE_BUDGET_CHARS
    for s in bundle["stories"]:
        first_verse = min(s["dhp_verses"]) if s.get("dhp_verses") else (verse_numbers[0] if verse_numbers else None)
        lines.append("")
        lines.append("[COMMENTARY -- Buddhaghosa's atthakatha, ~5th century CE]")
        lines.append(f"group_id: {s['group_id']}")
        lines.append(f"cite this commentary as verse_number: {first_verse}")
        lines.append(f"Story title: {s['title_en']}")
        # Found during Phase 5 generation-metrics judging (post-hoc, not
        # anticipated by the original bug list): index/chunks.py's
        # story_titles chunk (Phase 2 fix) carries title_pali/cst4_title/
        # burlingame_title/compare and made cross-recension title-variant
        # questions retrievable (cross_recension nDCG@10 went to a perfect
        # 1.000). But this function never rendered those fields, only
        # title_en -- so the generator had literally never seen a CST4 title
        # in its context. Every CST4-title generation answer sampled was
        # wrong or fabricated for exactly this reason: not a model failure,
        # a prompt-completeness gap in the same file STOP GATE 3 already
        # fixed once. Mirrors chunks.py's _title_text() field selection.
        for label, key in (
            ("Pali title", "title_pali"),
            ("CST4 (Burmese edition) title", "cst4_title"),
            ("Burlingame's title", "burlingame_title"),
        ):
            if s.get(key):
                lines.append(f"{label}: {s[key]}")
        if s.get("synopsis"):
            lines.append(f"Synopsis: {s['synopsis']}")
        if s.get("nidana"):
            lines.append(f"Opening: {s['nidana']}")
        if s.get("vatthu"):
            body, remaining = _budget(s["vatthu"], remaining)
            lines.append(f"Narrative: {body}")
        if s.get("desanavasane"):
            lines.append(f"Close: {s['desanavasane']}")

    return "\n".join(lines)


def build_context(bundles: list[dict]) -> str:
    return "\n\n".join(format_verse_group(b) for b in bundles)


def build_messages(question: str, bundles: list[dict]) -> list[dict]:
    context = build_context(bundles)
    user_message = f"""SOURCE MATERIAL:

{context}

QUESTION: {question}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def estimate_tokens(messages: list[dict]) -> int:
    """Rough char/4 estimate, for asserting the prompt fits num_ctx.

    Call this in generate.py and log or assert against the configured
    num_ctx. A prompt that silently exceeds the context window drops the
    commentary -- which is the last thing this system can afford to lose,
    and the failure is invisible in the output.
    """
    return sum(len(m["content"]) for m in messages) // 4
