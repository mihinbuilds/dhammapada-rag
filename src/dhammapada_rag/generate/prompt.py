"""Build the layer-labeled context and chat messages fed to the generator.

The prompt's entire job, per docs/project_plan.md Phase 4, is to "force the
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

ROUND 2 REGRESSION FIX -- CITATION LEAKING INTO CLAIM TEXT. Fix 1 above
introduced a literal "group_id: 13.2" line so the model would have
something unambiguous to copy into the JSON group_id field. Observed
consequence: the model sometimes copied that whole labeled line into the
claim's `text` field instead ("group_id: 15.6; verse_number: 204 The
story..."), leaving the actual group_id/verse_number JSON fields null --
audit() correctly flagged this as MISSING_PROVENANCE, but the claim was
malformed in a way that check didn't name. The commentary block's citation
line is now a `<<citation_fields group_id=... verse_number=...>>` marker,
which does not read as a sentence fragment to reproduce, and SYSTEM_PROMPT
explicitly forbids "group_id:"/"verse_number:"/the marker itself from
appearing in `text`. schemas.audit() adds a matching CITATION_IN_TEXT error
check as a second line of defense, since a prompt instruction alone is not
self-enforcing (the same lesson as Fix 2's commentary-engagement retry).

STILL OUTSTANDING (schema change required, not fixable here): the Claim
schema has no field for Pali, so no Pali can appear in any answer regardless
of what this prompt asks for. Add an optional `pali_support: str | None` to
Claim if verse claims should be able to quote the pada they rest on.

ROUND 3, TASK D -- VERSE NUMBER WRITTEN INTO group_id. Observed:
group_id="Dhp 114" -> UNPARSEABLE_GROUP_ID (correctly rejected: 114 is a
verse number, not the group_id 8.13 that explains it). Cause: both fields
are numeric and adjacent in the prompt, and the model had just written
"Dhp 114" in its own prose moments before filling the JSON fields. The
CITATIONS paragraph described each field's format separately but never
contrasted them against each other; it now states explicitly that they are
two different numbers, never interchangeable, with the specific failure
("Dhp 114" in group_id) named as a worked negative example.

ROUND 4, TASK F -- VERSE TEXT RELABELLED AS COMMENTARY. Fix 2 above made
commentary engagement mandatory to stop all-verse output (round 1). Observed
consequence, the mirror-image failure: when retrieval returns verse-heavy
groups with little usable narrative, the model sometimes satisfies the
COVERAGE instruction by tagging a verbatim verse sentence "commentary"
instead -- presenting the Buddha's own words as Buddhaghosa's 5th-century
gloss, the exact inversion the layer tags exist to prevent. COVERAGE now
carries an explicit escape hatch (say so in a synthesis claim and answer
from the verse alone) and names relabelling verse text as commentary as a
worse failure than omitting a commentary claim. `generate/schemas.py`'s
audit() adds a matching VERSE_TEXT_AS_COMMENTARY check (containment of a
commentary claim's wording in the cited verse text) as a second line of
defense, same principle as CITATION_IN_TEXT above: a prompt instruction
alone is not self-enforcing.

ROUND 4, TASK H -- STRUCTURE QUESTIONS ANSWERED WITH NARRATIVE INSTEAD OF
THE ANSWER. Observed: "which single story explains Dhp 320, 321, and 322
together?" retrieved the correct story (23.1) and then produced claims
narrating its content without ever naming the story or stating that it
covers all three verses -- retrieval succeeded, the answer did not respond
to the question asked. DIRECT ANSWER below requires a "which story / which
verse / how many" question to be answered by name in the first claim.

ROUND 5, TASK L -- SYSTEM_PROMPT CONSOLIDATED, NOT JUST EXTENDED AGAIN.
Four rounds (this docstring's own history above) each appended instructions
to fix one observed failure, and by Round 5 the prompt was long enough that
compliance degraded across the board: "g17.8", "inferred from Dhp 1
commentary", "commentary: For once upon a time...", both citation fields
null on verse claims. More prompt text was diagnosed as the cause, not the
fix. SYSTEM_PROMPT is now a single ~440-word ordered document (role/sources,
tagging, the failure to avoid and its mirror, coverage, framing, direct
answer, citations, output discipline) instead of an append-only list.
Every instruction about group_id/verse_number *format* is deleted outright
-- Task K's `_constrained_schema()` makes an invalid format unrepresentable
at the decoder, so describing the format in prose was no longer doing
anything except diluting the instructions that still need the model's
attention. What remains in CITATIONS is only completeness ("never leave
either empty"), which the decoder cannot enforce (null is a legal enum
value, chosen for synthesis claims on purpose) and the prompt still must
ask for. `schemas.py`'s new `LABEL_IN_TEXT` check is the mechanical
backstop for OUTPUT DISCIPLINE, same principle as CITATION_IN_TEXT before
it: state the rule in the prompt, then verify it structurally rather than
trusting compliance.

ROUND 4/5 AMENDMENT (TASK K/L AMENDMENT) -- VERSE CLAIM SPECIFICITY AND
PALI SUPPORT ADDED. Two gaps found in the Round 5 consolidation. First:
nothing in SYSTEM_PROMPT distinguished a claim about what one specific
verse says from a claim about the Dhammapada's position in general, so
"verse" was observed used for both -- the latter is unfalsifiable against
any single retrieved verse and belongs under "synthesis" instead. VERSE
CLAIM SPECIFICITY below names the failure with a worked example ("The
Dhammapada advises..." is synthesis, not verse). Second, Task J (surface
the Pali) had not been done: `schemas.py`'s Claim had no field to carry a
Pali quote back to the reader regardless of what the prompt asked, so the
verse layer never showed its own language even though every source block
here prints it. `generate/schemas.py` now defines `VerseClaim.pali_support`
and PALI SUPPORT below asks for it explicitly; `audit()` validates it as an
NFC-normalized substring of the cited verse's own Pali (since Round 13,
`interlinear_pali`), and
`render.py` prints it beneath the verse claim it supports.

Also: CITATIONS still states the *completeness* requirement ("must carry a
group_id and verse_number... never leave either empty") in prose, even
though `generate/schemas.py`'s VerseClaim/CommentaryClaim now make an
uncited claim of either layer unrepresentable at the type level (see that
module's Task K/L amendment note) and `generate.py`'s `_constrained_schema()`
makes it unrepresentable at the decoder too. This is deliberate, not an
oversight symmetrical with Task L's deletion of *format* instructions: Task
L's docstring above already drew this line correctly (format text was
prompt-only dead weight once Task K's enum made it unenforceable-and-
unnecessary in prose; completeness is a claim about which fields exist at
all, which the prompt still must ask for even though the schema now also
guarantees it) -- this note exists only to make explicit that the
completeness sentence must survive future edits to this docstring, since a
future consolidation pass could mistake it for another instance of the
same format-instruction pruning and delete it too.

ROUND 8, TASK AA -- ALIGNMENT GIVEN ITS OWN BLOCK, NOT JUST ITS OWN TAG.
Round 7 added the "alignment" layer and a TAGGING sentence describing it,
but `format_verse_group()` kept rendering verse-range and title data inside
[COMMENTARY], alongside Buddhaghosa's own narrative -- and alignment recall
stayed at 0.500 even after the tag existed and COMPLETENESS asked for it in
prose. Same lesson as Task K (constrain the decoder, don't just instruct
it), one level up: a model infers the taxonomy at least as much from where
information visually sits as from a paragraph describing the taxonomy.
`format_verse_group()` now renders a separate `[ALIGNMENT -- modern
editorial apparatus, neither verse nor commentary]` block per source group,
before `[COMMENTARY]`, carrying the group_id/verse-range/title/synopsis
facts and its own `<<citation_fields group_id=... verse_numbers=...>>`
marker (plural, matching `AlignmentClaim.verse_numbers` and CITATIONS'
wording exactly). `[COMMENTARY]` now renders only nidana/vatthu/
desanavasane -- the aṭṭhakathā's own narrative text, nothing else.

ROUND 8, TASK Z -- SOURCE DISPOSITION. `LayeredAnswer` gained a required
`source_disposition` field (see `generate/schemas.py`): one of "used" /
"partially_relevant" / "not_relevant" per retrieved group_id.
`generate.py`'s `_constrained_schema()` constrains it to an object with
exactly the retrieved group_ids as keys, so a schema-valid answer cannot
omit one -- Round 7's context-utilization metric was inferred from claim
citations and synthesis-claim prose after the fact, and measured 0/27
answers as fully accounting for their retrieved sources because it could
only recognize a dismissal shaped like prose naming the group. SOURCE
DISPOSITION below tells the model what the three values mean; the schema
constraint (not this paragraph) is what actually guarantees coverage.

ROUND 9, TASK AH -- SCOPE-WIDENING. Observed: "The Dhammapada also states
that the best thing in life is the eightfold path," tagged "verse", citing
Dhp 273. The verse says the eightfold path is best AMONG PATHS (maggānaṁ) --
one line of a four-part parallel (best of paths, of truths, of states, of
beings) -- not that it is the best thing in life. This passes VERSE CLAIM
SPECIFICITY as written: the claim is checkable against Dhp 273 and reads as
a paraphrase of it, but drops the qualifier that makes it a claim about
paths rather than about life in general. Same class as the earlier Dhp 135
error (docs/eval_rubric.md): correct layer, resolvable citation, and a
statement the verse does not make -- not mechanically catchable (no
group_id/verse_number is wrong, no field is missing), so the fix is a prompt
instruction, not a new audit() check. VERSE CLAIM SPECIFICITY now names the
failure explicitly, generalized beyond this one verse to comparatives,
conditionals, and negations, so the model does not need to be told about
each new instance a probe happens to find.
"""

from __future__ import annotations

import re

from dhammapada_rag.index.chunks import OVERLAP_WORDS, WINDOW_WORDS

# Fallback characters of narrative text per bundle, used only by callers that
# render a prompt without knowing num_ctx (direct format_verse_group/
# build_context/build_messages calls, e.g. tests or the CLI's one-off usage).
# generate.py's Generator.generate() does not use this constant: it computes
# an actual per-request budget from the real leftover num_ctx headroom via
# _fit_narrative_budget(), since a flat cap either wastes context that was
# available (short questions, few bundles) or cuts a long vatthu off before
# it reaches its point regardless of how much room was actually left. See
# generate.py's _fit_narrative_budget() docstring for the observed case that
# prompted this (Dhp 1 / Cakkhupala: a 31k-character vatthu truncated to its
# scene-setting opening while ~6k of the 16k-token budget went unused).
NARRATIVE_BUDGET_CHARS = 6000

# Round 6, Task Q: a literal control byte (observed: `\x01`) was seen
# corrupting rendered output. Traced before writing any code, per the
# brief's own instruction not to fold this into the Pali metric or fix it
# blind: `grep -P '[\x00-\x08\x0b\x0c\x0e-\x1f]'` across data/processed/,
# data/index/chunks.jsonl, and data/raw/ found zero occurrences of `\x01`
# specifically (data/raw/ *.txt do carry ordinary `\x0c` form-feed page
# breaks from PDF extraction, which is expected and harmless -- not this
# bug). The corpus is clean, so per the brief this is not an upstream
# ingest bug; it enters at prompt rendering or in Ollama's JSON round-trip.
# _strip_control_chars() is a boundary guard at build_messages() -- the
# request side, and the one seam this module can actually test -- so a
# future corruption from a user-supplied `question` or a not-yet-audited
# corpus edit cannot reach the model silently. \t/\n/\r are explicitly
# excluded: those are legitimate structure in a multi-paragraph prompt, not
# corruption.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _strip_control_chars(s: str) -> str:
    return _CONTROL_CHAR_RE.sub("", s)

SYSTEM_PROMPT = """You are answering questions about the Dhammapada using ONLY the source material provided in the user message.

ROLE AND SOURCES. The source has two layers, roughly eight centuries apart, and you must never conflate them. VERSE is the canonical Dhammapada verse (Pali plus English translation) -- the Buddha's own words. COMMENTARY is Buddhaghosa's aṭṭhakathā: the narrative explaining who a verse was spoken to, when, and why, compiled centuries later -- not the verse's own words, even where it explains the verse correctly.

TAGGING. Every claim carries exactly one layer tag: "verse" for what the verse itself literally says; "commentary" for anything drawn from the aṭṭhakathā -- occasion, persons, narrative, outcome, or interpretation beyond the verse's own words; "alignment" for a fact about the corpus's own editorial structure -- which story explains which verse(s), how many verses a group covers -- stated by neither the verse nor the commentary itself; "synthesis" for your own inference or generalization, drawn from neither text directly.

VERSE CLAIM SPECIFICITY. A "verse" claim must state what that specific verse says, closely enough that a reader could check it against the verse text given below -- not a summary of the Dhammapada's general position. "The Dhammapada advises patience" is a "synthesis" claim, not a "verse" claim: it is not checkable against any one verse. Reserve "verse" for a claim that paraphrases or quotes one specific verse's own content. A verse claim must also preserve the verse's own scope. If the verse says something is best OF a category ("of paths", "of truths"), the claim must keep that category. Widening "best of paths" to "the best thing in life" states something the verse does not. Comparatives, conditionals, and negations must survive the paraphrase intact.

THE FAILURE TO AVOID. Presenting the commentary's narrative gloss as the plain sense of the verse is the central failure this system exists to prevent -- tag it "commentary," not "verse," however naturally it reads as one continuous explanation. The mirror failure is just as serious: relabelling the verse's own words as "commentary" to appear thorough. Never do either.

COVERAGE. Draw on both layers where both bear on the question. If the commentary genuinely does not address it, say so in a "synthesis" claim and answer from the verse alone. Never relabel a verse to satisfy this -- that is worse than no commentary claim at all.

FRAMING. If the question presupposes a category the text does not use -- e.g. a teleological "purpose of life" question, where the nearest categories are attha and sadattha (one's own highest good) -- name the mismatch first, as a "synthesis" claim, then answer what the text does address.

DIRECT ANSWER. If the question asks which story, which verse, or how many, answer it directly and by name in your first claim, before adding supporting detail. A question about the structure of the text is asking for an identity, not a retelling of a narrative. When the question asks which story explains a verse, that first claim must state the story's FULL verse range, not only the verse asked about -- "story 1.3 explains Dhp 3 and 4 together" is complete; "story 1.3 explains Dhp 4" omits the grouping, which is the point of the question. Tag that claim "alignment": which story explains which verse is a fact about the corpus's own editorial structure, not something either the verse or the aṭṭhakathā itself states.

COMPLETENESS. A complete answer uses the layers the question calls for. "Who is X?" -> who they were (commentary), the verse their story occasioned (verse, with pali_support), and what became of them (commentary, from the closing section) where the source gives it. "What does the text say about X?" -> the relevant verses with their Pali, plus at least one commentary claim giving an occasion, where one was retrieved. "Which story explains X?" -> the alignment fact with the full verse range, plus a one-line indication of what the story concerns.

SOURCE DISPOSITION. Every retrieved source group must get exactly one disposition, in the separate source_disposition field, keyed by its group_id: "used" if some claim draws on it; "partially_relevant" if it touches the question but you built no claim from it; "not_relevant" if it does not bear on the question at all. This is a required field, not optional commentary -- fill in every group_id shown above, even ones you otherwise ignore. Marking a group "not_relevant" is a real, useful answer: it tells the reader retrieval surfaced something that does not apply, which is different from silence.

CITATIONS. Every "verse" and "commentary" claim must carry a group_id and verse_number identifying its source; never leave either empty. A claim about a verse group cites the group's first verse. An "alignment" claim instead carries a group_id and verse_numbers -- the group's COMPLETE list of verse numbers, never a single one.

PALI SUPPORT. Every "verse" claim must also carry pali_support: a pada copied verbatim, byte for byte, from that verse's "Pali (Anandajoti interlinear)" line below -- its exact spelling and word-joining, not a differently-hyphenated or differently-spaced form you may recognize from elsewhere. Copy only from the Pali line printed in this prompt, never from memory, even if you can recite the verse -- other editions join or hyphenate words differently, and a quote that does not match this printed line character for character will be rejected as unsupported.

OUTPUT DISCIPLINE. The `text` field is prose for a human reader. It must never begin with "verse:", "commentary:", "alignment:", "synthesis:", "group_id:", or "verse_number:" -- the layer belongs in the layer field, the citation in its own fields, not as a label inside the prose.

Answer only from the provided context. If it does not address the question, say so as a "synthesis" claim rather than inventing content. Keep each claim to one idea; prefer several short tagged claims over one long paragraph."""


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


_WORD_RE = re.compile(r"\S+")


def _matched_word_char_offset(text: str, window_index: int) -> int:
    """Approximate character offset in `text` where retrieval's matched
    window begins, replicating index/chunks.py's _split_windows() word-
    boundary math (WINDOW_WORDS/OVERLAP_WORDS, imported rather than
    duplicated so the two cannot silently drift apart). Regex-based word
    offsets, not `len(" ".join(words[:n]))`, so the result lines up with
    this exact string's own whitespace rather than a whitespace-normalized
    reconstruction of it.
    """
    if window_index <= 0:
        return 0
    step = WINDOW_WORDS - OVERLAP_WORDS
    start_word = window_index * step
    offsets = [m.start() for m in _WORD_RE.finditer(text)]
    return offsets[start_word] if start_word < len(offsets) else max(0, len(text) - 1)


def _budget_around(text: str, remaining: int, char_offset: int) -> tuple[str, int]:
    """Like _budget(), but for a story retrieval matched partway through
    (char_offset > 0): keeps an excerpt centered near that point instead of
    always keeping the opening.

    Observed failure this fixes: asked "who is the chakkhupala?", retrieval
    correctly matched a passage deep in Dhp 1's story (naming Cakkhupala and
    his blindness) -- but format_verse_group always rendered from character
    0 regardless of where the match was, so a flat per-bundle budget cut the
    31k-character vatthu off during its scene-setting backstory, well before
    reaching the passage that caused the match in the first place. A quarter
    of the budget is spent on lead-in before the match, for narrative
    continuity; the rest runs forward from there, since what happens AFTER
    the identifying passage (the outcome) is usually what a question naming
    a character or event is actually asking about.
    """
    if remaining <= 0:
        return "[omitted: narrative budget exhausted]", 0
    if len(text) <= remaining:
        return text, remaining - len(text)
    lead_in = remaining // 4
    start = max(0, char_offset - lead_in)
    end = min(len(text), start + remaining)
    prefix = (
        "[... narrative truncated; excerpt resumes near the passage that matched this "
        "question ...] "
        if start > 0
        else ""
    )
    suffix = " [... narrative truncated ...]" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix, 0


def format_verse_group(bundle: dict, narrative_budget_chars: int = NARRATIVE_BUDGET_CHARS) -> str:
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
        # Round 13: Ānandajoti's interlinear is the only verse source; the
        # SuttaCentral Pali and English lines were removed at SuttaCentral's
        # request (data/raw/PROVENANCE.md).
        lines.append(f"Dhp {v['verse']} -- Pali (Anandajoti interlinear): {v['interlinear_pali']}")
        if v.get("interlinear_english"):
            lines.append(f"Dhp {v['verse']} -- English (Anandajoti interlinear): {v['interlinear_english']}")

    # Which story (if any) retrieval's own match landed in, and where -- so a
    # long vatthu that must be truncated is truncated around the passage
    # that actually caused the match, not always from its start. Only a
    # story_vatthu-type match gives a window_index that means anything for
    # this story's vatthu text specifically; a match on its synopsis or
    # title chunk carries a window_index into a different field entirely.
    matched = bundle.get("matched_chunk") or {}
    matched_group_id = matched.get("group_id") if matched.get("chunk_type") == "story_vatthu" else None
    matched_window_index = matched.get("window_index", 0)

    remaining = narrative_budget_chars
    for s in bundle["stories"]:
        dhp_verses = sorted(s["dhp_verses"]) if s.get("dhp_verses") else list(verse_numbers)
        first_verse = dhp_verses[0] if dhp_verses else None
        printed_verses = ", ".join(str(n) for n in dhp_verses)

        # Round 8, Task AA: alignment facts (which story explains which
        # verse group, how many verses it covers, its title in this and
        # other editions) used to live inside [COMMENTARY], alongside
        # Buddhaghosa's actual narrative -- and alignment recall stayed at
        # 0.500 (Round 7) even after the tag existed and the prompt asked
        # for it in prose. Round 5's own precedent (constrain the decoder
        # instead of instructing it) applies here too, one level up: a
        # model infers the taxonomy from where information visually sits at
        # least as much as from a paragraph describing the taxonomy, and
        # commentary-shaped claims about a title or a verse range are the
        # direct result of title/range data sitting inside the block
        # labelled [COMMENTARY]. This block now carries every editorial-
        # apparatus fact (verse-range, title in every edition, synopsis) and
        # nothing else; [COMMENTARY] below carries only nidana/vatthu/
        # desanavasane -- the aṭṭhakathā's own narrative text.
        lines.append("")
        lines.append("[ALIGNMENT -- modern editorial apparatus, neither verse nor commentary]")
        # Round 2, Task B fix (restated below for [COMMENTARY]): a bare
        # "group_id: X" line reads as prose-shaped and gets copied verbatim
        # into claim text. The <<...>> marker form is unambiguously not a
        # sentence to reproduce. verse_numbers (plural) matches
        # AlignmentClaim's own field name and CITATIONS' wording ("the
        # group's COMPLETE list of verse numbers") exactly, so the value an
        # alignment claim needs is copied from an identically-named source.
        lines.append(f"<<citation_fields group_id={s['group_id']} verse_numbers={dhp_verses}>>")
        lines.append(
            f"group_id {s['group_id']} covers Dhp {printed_verses} "
            f"({len(dhp_verses)} verse{'s' if len(dhp_verses) != 1 else ''}), titled \"{s['title_en']}\""
        )
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
        # Round 8: title variants are editorial-apparatus facts (how
        # different recensions name the same story) same as the verse
        # range, so they render here now, not in [COMMENTARY].
        for label, key in (
            ("Pali title", "title_pali"),
            ("CST4 (Burmese edition) title", "cst4_title"),
            ("Burlingame's title", "burlingame_title"),
        ):
            if s.get(key):
                lines.append(f"{label}: {s[key]}")
        if s.get("synopsis"):
            lines.append(f"Synopsis: {s['synopsis']}")

        lines.append("")
        lines.append("[COMMENTARY -- Buddhaghosa's atthakatha, ~5th century CE]")
        # Round 2, Task B fix: this used to be two literal lines,
        # "group_id: 13.2" / "cite this commentary as verse_number: 204" --
        # and the model was observed copying that string verbatim into a
        # claim's `text` field ("group_id: 15.6; verse_number: 204 The
        # story..."), with the actual group_id/verse_number JSON fields left
        # null. A regression from round 1's prompt rewrite: bare
        # "group_id: X" reads as prose-shaped to a model that has just been
        # told group_id values look like "8.13" copied verbatim, so it
        # copied the whole labeled line instead of only the value. The
        # <<...>> marker form is unambiguously not a sentence to reproduce.
        lines.append(f"<<citation_fields group_id={s['group_id']} verse_number={first_verse}>>")
        if s.get("nidana"):
            lines.append(f"Opening: {s['nidana']}")
        if s.get("vatthu"):
            if s["group_id"] == matched_group_id and matched_window_index > 0:
                offset = _matched_word_char_offset(s["vatthu"], matched_window_index)
                body, remaining = _budget_around(s["vatthu"], remaining, offset)
            else:
                body, remaining = _budget(s["vatthu"], remaining)
            lines.append(f"Narrative: {body}")
        if s.get("desanavasane"):
            lines.append(f"Close: {s['desanavasane']}")

    return "\n".join(lines)


def build_context(bundles: list[dict], narrative_budget_chars: int = NARRATIVE_BUDGET_CHARS) -> str:
    return "\n\n".join(format_verse_group(b, narrative_budget_chars) for b in bundles)


def build_messages(
    question: str, bundles: list[dict], narrative_budget_chars: int = NARRATIVE_BUDGET_CHARS
) -> list[dict]:
    context = build_context(bundles, narrative_budget_chars)
    user_message = f"""SOURCE MATERIAL:

{context}

QUESTION: {question}"""
    return [
        {"role": "system", "content": _strip_control_chars(SYSTEM_PROMPT)},
        {"role": "user", "content": _strip_control_chars(user_message)},
    ]


def estimate_tokens(messages: list[dict]) -> int:
    """Rough char/4 estimate, for asserting the prompt fits num_ctx.

    Call this in generate.py and log or assert against the configured
    num_ctx. A prompt that silently exceeds the context window drops the
    commentary -- which is the last thing this system can afford to lose,
    and the failure is invisible in the output.
    """
    return sum(len(m["content"]) for m in messages) // 4
