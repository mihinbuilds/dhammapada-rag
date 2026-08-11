"""Tests for index/chunks.py's _strip_closing_verse_quote.

Found via a research-validation cross-layer retrieval failure (Q16/Q26,
dhammapada_research_validation_results.md): short single-verse stories quote
their own featured Dhp verse verbatim in their closing lines ("...he
pronounced the following verse: <Pali>. <English>"), so their nominally
commentary-only chunk out-competes the true verse-layer chunk on any query
naming words from that verse. The strip must be precise: the same "pronounced
the following verse(s)" phrasing also introduces verses recited mid-narrative
that are not the story's own -- those must survive untouched.

Run: pytest tests/test_chunks_verse_strip.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dhammapada_rag.index.chunks import _strip_closing_verse_quote  # noqa: E402


def test_strips_genuine_closing_quote_of_own_verse():
    text = (
        "And joining the connection, he taught the Dhamma, pronouncing the "
        "following verse:\n\n     401. Vari pokkharapatte va, aragge-r-iva sasapo,\n"
        "     yo na lippati kamesu, tam-aham brumi brahmanam.\n"
        "     Like water on the lotus leaf,\n     like a mustard seed on needle,\n"
        "     he who is unsmeared by desires,\n     that one I say is a Brahmin."
    )
    out = _strip_closing_verse_quote(text, dhp_verses=[401])
    assert out == "And joining the connection, he taught the Dhamma,"
    assert "sasapo" not in out


def test_preserves_mid_narrative_quote_of_a_different_verse():
    # Kisā Gotamī's story (dhp_verses=[114]) also narrates the Buddha later
    # teaching her Dhp 287 -- a real event in the narrative, not this story's
    # own closing citation, and must not be stripped.
    text = (
        "And instructing her in the Dhamma, he pronounced the following verse: "
        "Dhp 287. That person whose mind is attached, besotted by cattle and "
        "children, is snatched away by death just as a sleeping village by a "
        "flood. At the conclusion of the verse, Kisa Gotami was established in "
        "the fruition of Stream-entry, and many others reached the fruition of "
        "Stream-entry and so on."
    )
    out = _strip_closing_verse_quote(text, dhp_verses=[114])
    assert out == text


def test_preserves_story_of_the_past_after_a_single_verse_quote():
    # A "Story of the Past" flashback narrative that continues for many more
    # words after quoting the story's own verse must not be truncated --
    # only the ratio check (words per quoted verse) should catch this.
    text = (
        "   98. Whatever ground the Arahats live on, that ground is delightful.\n"
        "At the end of the teaching many reached the fruition of Stream-entry. "
        + ("Bhikkhus, in a former life this happened, and that happened. " * 40)
    )
    out = _strip_closing_verse_quote(text, dhp_verses=[98])
    assert out == text  # no "pronounced the following verse" trigger at all -> untouched


def test_preserves_incomplete_multi_verse_quote():
    # dhp_verses names two verses but only the first is actually quoted here
    # -- the suffix check must refuse to strip an incomplete match.
    text = (
        "he pronounced the following verses:\n"
        "     294. Destroying mother and father, the Brahmin proceeds untroubled."
    )
    out = _strip_closing_verse_quote(text, dhp_verses=[294, 295])
    assert out == text


def test_strips_multi_verse_closing_quote():
    text = (
        "So he taught the Dhamma, pronouncing the following verses:\n"
        "   87. Having abandoned the dark state, the wise should develop the bright.\n"
        "   88. One should take delight in that place, having given up sense pleasures."
    )
    out = _strip_closing_verse_quote(text, dhp_verses=[87, 88])
    assert out == "So he taught the Dhamma,"


def test_no_trigger_phrase_returns_text_unchanged():
    text = "A perfectly ordinary narrative paragraph with no verse citation at all."
    assert _strip_closing_verse_quote(text, dhp_verses=[1]) == text
