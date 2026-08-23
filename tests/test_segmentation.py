from writing_eval.segmentation import segment, sentence_opener, tokenize


def texts_of(text: str) -> list[list[str]]:
    return [[text[start:end] for start, end in group] for group in segment(text)]


def test_empty_and_whitespace_only_yield_no_groups() -> None:
    assert segment("") == []
    assert segment("   \n\n\t") == []


def test_basic_two_sentences_map_to_original_offsets() -> None:
    text = "One two. Three four five six!"
    assert segment(text) == [[(0, 8), (9, 29)]]
    assert texts_of(text) == [["One two.", "Three four five six!"]]


def test_heading_line_yields_no_spans_and_closes_group() -> None:
    text = "Alpha done.\n## Heading here\nBeta done."
    assert texts_of(text) == [["Alpha done."], ["Beta done."]]


def test_blank_line_closes_group() -> None:
    text = "Cat sat.\n\nDog ran."
    assert texts_of(text) == [["Cat sat."], ["Dog ran."]]


def test_list_marker_prefix_is_excluded_from_span() -> None:
    text = "1. Do this thing."
    assert segment(text) == [[(3, 17)]]
    assert texts_of(text) == [["Do this thing."]]


def test_bullet_marker_prefix_is_excluded_from_span() -> None:
    assert texts_of("- Ship the fix.") == [["Ship the fix."]]


def test_decimal_dot_is_not_a_terminator() -> None:
    text = "Latency dropped 3.5 percent."
    assert texts_of(text) == [["Latency dropped 3.5 percent."]]


def test_maximal_terminator_run_is_one_boundary() -> None:
    assert texts_of("Wait!!! Go.") == [["Wait!!!", "Go."]]


def test_spans_without_a_letter_led_token_are_dropped() -> None:
    assert texts_of("... Real text here.") == [["Real text here."]]
    assert texts_of("123 456.") == []
    assert texts_of("2026 was a busy year.") == [["2026 was a busy year."]]


def test_inline_numbered_list_digit_markers_are_dropped() -> None:
    text = "1. Use short subjects. 2. Use active verbs. 3. Use one idea per line."
    assert texts_of(text) == [
        ["Use short subjects.", "Use active verbs.", "Use one idea per line."]
    ]


def test_multi_paragraph_offsets_are_absolute() -> None:
    text = "Intro line.\n\n## Heading\n\n1. First item.\n2. Second item."
    groups = segment(text)
    assert groups[0][0] == (0, 11)
    assert text[groups[1][0][0] : groups[1][0][1]] == "First item."
    assert texts_of(text) == [["Intro line."], ["First item.", "Second item."]]


def test_sentence_opener_returns_letter_led_word_offset() -> None:
    text = "Hello world."
    assert sentence_opener(text, 0, len(text)) == (0, 5)
    assert text[0:5] == "Hello"


def test_sentence_opener_keeps_apostrophes_and_hyphens() -> None:
    for text, expected in (
        ("We\u2019ll ship.", "We\u2019ll"),
        ("We'll ship.", "We'll"),
        ("Well-known things matter.", "Well-known"),
    ):
        opener = sentence_opener(text, 0, len(text))
        assert opener is not None
        assert text[opener[0] : opener[1]] == expected


def test_sentence_opener_is_none_when_no_letter_led_word() -> None:
    text = "123 456."
    assert tokenize(text) == ["123", "456"]
    assert sentence_opener(text, 0, len(text)) is None
