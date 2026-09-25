"""Regression tests for parse_stories.py's text cleaning.

Each case is a minimal reproduction of a defect found in data/processed/
stories.jsonl, shaped like the pdftotext -layout source it came from.
"""

from dhammapada_rag.ingest.parse_stories import (
    classify_verse_line,
    clean_body_text,
    cut_at_structural_boundary,
    extract_footnotes,
    extract_nidana_desanavasane,
    extract_verse_blocks,
    join_wrapped,
    reflow,
    strip_footnote_markers,
)


def test_page_break_inside_verse_keeps_whole_english_translation():
    # Dhp 388 (story 26.6): a page break fell between the verse's second and
    # third English lines, and the blank lines it left stopped extraction
    # after two of four lines.
    body = [
        "So saying, he pronounced the following verse:",
        "   388. Bāhitapāpo ti brāhmaṇo,",
        "   samacariyā samaṇo ti vuccati,",
        "   pabbājayam-attano malaṁ",
        "   tasmā pabbajito ti vuccati.",
        "   Warding wickedness one’s called a Brahmin,",
        "   an austere one is called an ascetic,",
        "",
        "",
        "   because of driving forth all stain from oneself",
        "   one is said to be one who has gone forth.",
        "At the end of the teaching that Brahmin was established in the fruition of Stream-entry.",
    ]
    _, english, number, flags = extract_verse_blocks(clean_body_text(body), [388])
    assert number == 388
    assert english.endswith("one is said to be one who has gone forth.")
    assert flags == []


def test_english_line_without_old_stopwords_is_not_read_as_pali():
    # Dhp 225 (story 17.5): "Those sages without violence," was glued onto
    # the Pali verse.
    assert classify_verse_line("Those sages without violence,") == "english"


def test_pali_so_is_not_read_as_english():
    # Dhp 162 (story 12.6): the Pali "so" alone made this line "English".
    assert classify_verse_line("karoti so tathattānaṁ yathā naṁ icchatī diso.") == "pali"


def test_footnote_markers_stripped_but_numbers_kept():
    text = "the Wheel of the Dhamma,5 at a cost of 80,000 coins; see SN 7.2.3 and ox’s foot.4"
    assert strip_footnote_markers(text, {"4", "5", "000", "3"}) == (
        "the Wheel of the Dhamma, at a cost of 80,000 coins; see SN 7.2.3 and ox’s foot."
    )


def test_footnote_marker_not_in_story_footnotes_is_left_alone():
    assert strip_footnote_markers("Birth Story63 as follows", {"64"}) == "Birth Story63 as follows"


def test_unlabeled_footnote_is_extracted():
    # footnote 230 (story 10.4) has no AJ:/BG: prefix
    lines = [
        "the dispensation of this long-lived Buddha,230 as year by year",
        "",
        "230",
        "   Burlingame translated this as: And in the dispensation of the Buddha Dīghāyu,",
        "inserting an unknown Buddha into the framework.",
    ]
    footnotes, kept = extract_footnotes(lines)
    assert [(f.marker, f.source) for f in footnotes] == [("230", "unlabeled")]
    assert footnotes[0].text.endswith("into the framework.")
    assert kept == lines[:2]


def test_crumb_removal_leaves_no_double_space():
    out = clean_body_text(["erected by the wealthy merchant [28.147] Anāthapiṇḍika"])
    assert out == "erected by the wealthy merchant Anāthapiṇḍika"


def test_vagga_title_page_is_cut_from_preceding_story():
    lines = [
        "arose to many people from the teaching.",
        "            2. The Chapter about Heedfulness,",
        "                    Appamādavagga",
    ]
    story, preface = cut_at_structural_boundary(lines)
    assert story == lines[:1]
    assert preface == []


def test_colophon_is_cut_from_last_story():
    lines = ["declared himself a lay disciple.", "                Conclusion, Nigamanakathā412", "To this extent,"]
    assert cut_at_structural_boundary(lines) == (lines[:1], [])


def test_nidana_found_when_phrase_wraps():
    body = (
        "“A monastic who delights in heedfulness,” this Dhamma\n"
        "teaching was given by the Teacher while he was in residence at Jetavana with\n"
        "reference to a certain bhikkhu.\n"
        "It seems that this bhikkhu obtained from the Teacher a subject of meditation."
    )
    nidana, _, vatthu, flags = extract_nidana_desanavasane(body)
    assert nidana.endswith("a certain bhikkhu.")
    assert vatthu.startswith("It seems")
    assert "nidana_not_detected" not in flags


def test_desanavasane_not_split_mid_sentence():
    # 7.9: "he was reborn at the end of his life in Avīci" is narrative
    body = (
        "Because he committed this act, he was reborn at the end of his life in Avīci.\n"
        "At the end of the teaching many reached the fruition of Stream-entry."
    )
    _, desanavasane, vatthu, _ = extract_nidana_desanavasane(body)
    assert vatthu.endswith("in Avīci.")
    assert desanavasane.startswith("At the end of the teaching")


def test_reflow_joins_wrapped_prose_and_keeps_verse_lines():
    text = "\n".join([
        "At this time the Teacher, having set in motion the glorious Wheel of the",
        "Dhamma, took up his residence at Jetavana. He built night-",
        "quarters there.",
        "So saying, he pronounced the following verse:",
        "   Mind precedes thoughts, mind is their chief,",
        "   their quality is made by mind,",
    ])
    assert reflow(text) == (
        "At this time the Teacher, having set in motion the glorious Wheel of the "
        "Dhamma, took up his residence at Jetavana. He built night-quarters there.\n\n"
        "So saying, he pronounced the following verse:\n\n"
        "Mind precedes thoughts, mind is their chief,\n"
        "their quality is made by mind,"
    )


def test_reflow_keeps_sentence_joined_across_shifted_page_margin():
    # 1.8: pdftotext indented the next page by 5 spaces mid-sentence
    text = "\n".join([
        "older brother said: “Very well, divide the field into two parts. Do not touch my",
        "     portion, but do whatever you like in your own portion of the field.” – “Very",
        "     well,” said Culla Kāḷa.",
    ])
    assert "\n" not in reflow(text)


def test_join_wrapped_keeps_compound_hyphen():
    assert join_wrapped(["a monastery with night-", "quarters and day-quarters"]) == (
        "a monastery with night-quarters and day-quarters"
    )
