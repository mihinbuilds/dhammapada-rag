"""Tests for ingest/audit_corpus.py (Stage 0 of
dhammapada_fixes/corpus_rebuild_design.md).

Focused on classify_pali_pair() -- the exact/boundary/distinct split that
turned a misleading ~46% "disagreement rate" (checks 4 and 5's first draft)
into an honest report: most of that number was vagga-boundary text
contamination or partial-quote truncation, not genuine cross-source
disagreement. See docs/corpus_audit.md for the worked findings.

Run: pytest test_corpus_audit.py -v
"""

from __future__ import annotations

from dhammapada_rag.ingest.audit_corpus import (
    check_length_outliers,
    check_pali_charset,
    check_quote_glyphs,
    check_title_body_coherence,
    classify_pali_pair,
    normalize_pali_orthography,
)


def test_classify_exact_after_normalization():
    assert classify_pali_pair(
        "sabbam-atikkameyya", "sabbamatikkameyya"
    ) == "exact"


def test_classify_boundary_when_one_is_a_prefix_of_the_other():
    """The vagga-final-verse pattern: pali_mahasangiti carries a trailing
    colophon interlinear_pali doesn't."""
    assert classify_pali_pair(
        "Yodha taṇhaṁ pahantvāna, anāgāro paribbaje. Jotikattheravatthu.",
        "Yodha taṇhaṁ pahantvāna anāgāro paribbaje",
    ) == "boundary"


def test_classify_boundary_when_one_is_a_suffix_of_the_other():
    """The vagga-initial-verse pattern: interlinear_pali carries a leading
    page-heading fragment pali_mahasangiti doesn't."""
    assert classify_pali_pair(
        "Yamakavaggo Paṭhamo Related Verses from the Dhammapada Yathā pi ruciraṁ pupphaṁ",
        "Yathāpi ruciraṁ pupphaṁ",
    ) == "boundary"


def test_classify_distinct_for_genuine_word_level_variance():
    """Real edition variance -- different verb forms of the same root, not
    a formatting convention. Must not be folded into "boundary" just
    because most of the string overlaps."""
    assert classify_pali_pair(
        "akiccaṁ pana karīyati", "akiccaṁ pana kayirati"
    ) == "distinct"


def test_classify_distinct_when_completely_different():
    assert classify_pali_pair(
        "Kodhaṁ jahe vippajaheyya mānaṁ", "completely unrelated text"
    ) == "distinct"


def test_normalize_pali_orthography_folds_edition_conventions():
    """Hyphenation, niggahita variant, case, and spacing all fold to the
    same normalized form -- the thing classify_pali_pair's "exact" tier
    relies on."""
    forms = [
        "sabbam-atikkameyya",
        "sabbamatikkameyya",
        "SABBAMATIKKAMEYYA",
        "sabbam atikkameyya",
    ]
    normalized = {normalize_pali_orthography(f) for f in forms}
    assert len(normalized) == 1


def test_title_body_coherence_flags_a_story_with_no_matching_proper_noun():
    stories = [{
        "group_id": "99.1",
        "title_en": "The Story about Devadatta",
        "vatthu": "A monk once did something at Savatthi with no names mentioned at all.",
        "synopsis": None,
    }]
    hits = check_title_body_coherence(stories)
    assert len(hits) == 1
    assert hits[0]["group_id"] == "99.1"


def test_title_body_coherence_not_flagged_when_proper_noun_appears():
    stories = [{
        "group_id": "99.1",
        "title_en": "The Story about Devadatta",
        "vatthu": "Devadatta once tried to harm the Buddha.",
        "synopsis": None,
    }]
    assert check_title_body_coherence(stories) == []


def test_title_body_coherence_skips_stories_with_no_extractable_title_tokens():
    """When every title token is a stopword (after filtering), there is
    nothing to check against the body -- the story is skipped, not flagged.
    Note the heuristic is deliberately loose in the other direction: English
    title-case capitalizes ordinary words too ("Certain", "Monk"), not just
    true proper nouns, so those DO count as candidates elsewhere -- this is
    the design doc's own spec ("capitalised tokens... minus stopwords"),
    not a bug, and is exactly why every hit is a candidate for hand review
    rather than an auto-fail (see docs/corpus_audit.md check 1's caveat)."""
    stories = [{
        "group_id": "99.1",
        "title_en": "The Story about the",
        "vatthu": "Something happened, unrelated to anything in the title.",
        "synopsis": None,
    }]
    assert check_title_body_coherence(stories) == []


def test_title_body_coherence_checks_nidana_not_just_vatthu_synopsis():
    """Regression for 20.5 ("Elder Padhanakammika Tissa"): the narrative
    frame names its subject only in nidana ("with reference to Elder X"),
    and vatthu refers back with pronouns only. Restricting the body check to
    vatthu/synopsis alone produced a false positive on the real corpus."""
    stories = [{
        "group_id": "20.5",
        "title_en": "The Story about the Elder Padhanakammika Tissa",
        "nidana": "This teaching was given with reference to Elder Padhanakammika Tissa.",
        "vatthu": "One of them fell away, but the rest attained Arahatship.",
        "synopsis": None,
    }]
    assert check_title_body_coherence(stories) == []


def test_title_body_coherence_tolerates_english_plural_in_title():
    """Regression for 16.4 ("the Licchavis"): the body uses the same proper
    noun as a singular-form adjective ("the Licchavi princes"), not the
    title's English-pluralized form. A spelling difference, not an absent
    referent."""
    stories = [{
        "group_id": "16.4",
        "title_en": "The Story about the Licchavis",
        "vatthu": "The Teacher saw the Licchavi princes on their way to the garden.",
        "synopsis": None,
    }]
    assert check_title_body_coherence(stories) == []


def test_length_outliers_flags_short_vatthu():
    stories = [{"group_id": "1.1", "vatthu": "Too short.", "nidana": None}]
    out = check_length_outliers(stories)
    assert out["n_short_vatthu"] == 1
    assert out["short_vatthu"][0]["group_id"] == "1.1"


def test_length_outliers_flags_nidana_longer_than_vatthu():
    stories = [{
        "group_id": "1.1",
        "vatthu": "x" * 250,
        "nidana": "y" * 300,
    }]
    out = check_length_outliers(stories)
    assert out["n_nidana_longer_than_vatthu"] == 1
    assert out["n_short_vatthu"] == 0


def test_length_outliers_clean_story_not_flagged():
    stories = [{
        "group_id": "1.1",
        "vatthu": "x" * 300,
        "nidana": "y" * 50,
    }]
    out = check_length_outliers(stories)
    assert out["n_short_vatthu"] == 0
    assert out["n_nidana_longer_than_vatthu"] == 0


def test_pali_charset_allows_reported_speech_punctuation():
    """Regression: the design doc's original allowed set was IAST-only and
    flagged 22 genuinely correct verses for curly quotes/em dash marking
    reported speech inside the verse (e.g. Dhp 17's "Papam me katan"ti).
    That was the gate's own premise not holding, not corpus damage -- the
    set was widened rather than the corpus changed."""
    verses = [{"verse": 17, "pali_mahasangiti": "Pāpaṁ me katan”ti tappati."}]
    assert check_pali_charset(verses) == []
    verses_em_dash = [{"verse": 208, "pali_mahasangiti": "Tasmā hi— Dhīrañca paññañca."}]
    assert check_pali_charset(verses_em_dash) == []


def test_pali_charset_still_flags_genuine_residue():
    verses = [{"verse": 1, "pali_mahasangiti": "Manopubbaṅgamā dhammā 123"}]
    hits = check_pali_charset(verses)
    assert len(hits) == 1
    assert hits[0]["verse"] == 1


def test_quote_glyphs_flags_mis_mapped_apostrophe():
    """The exact observed bug: pdftotext extracted this source's apostrophe
    glyph as U+2016 (DOUBLE VERTICAL LINE) instead of U+2019, e.g. "ox‖s
    foot" for "ox's foot"."""
    stories = [{"group_id": "1.1", "vatthu": "a wheel follows ox‖s foot"}]
    hits = check_quote_glyphs(stories, "stories.jsonl")
    assert len(hits) == 1
    assert hits[0]["record"] == "1.1"
    assert hits[0]["codepoints"] == ["U+2016"]


def test_quote_glyphs_flags_mis_mapped_opening_quote():
    stories = [{"group_id": "1.1", "vatthu": "he said: ―Who is he?‖"}]
    hits = check_quote_glyphs(stories, "stories.jsonl")
    assert len(hits) == 1
    assert hits[0]["codepoints"] == ["U+2015", "U+2016"]


def test_quote_glyphs_does_not_flag_correct_curly_quotes():
    """The corpus's small minority of correctly-extracted quotes (U+2018/
    U+2019) must not trip this check -- only the mis-mapped pair does."""
    stories = [{"group_id": "1.1", "vatthu": "the beings’ deeds and ‘Shine forth’"}]
    assert check_quote_glyphs(stories, "stories.jsonl") == []


def test_quote_glyphs_clean_corpus_not_flagged():
    stories = [{"group_id": "1.1", "vatthu": "a wheel follows the ox's foot"}]
    assert check_quote_glyphs(stories, "stories.jsonl") == []
