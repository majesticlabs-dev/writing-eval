"""Tests for the general text-quality metrics (report-only diagnostics)."""

import pytest

from writing_eval.metrics import (
    flesch_kincaid_grade,
    flesch_reading_ease,
    mtld,
    paragraph_stats,
    tokenize,
)
from writing_eval.metrics_quality import _count_syllables


def test_syllable_heuristic_known_words() -> None:
    # Silent-e drops a syllable ("cake"), the consonant + "le" ending keeps one
    # ("table"), and every word counts at least once.
    assert _count_syllables("the") == 1
    assert _count_syllables("cake") == 1
    assert _count_syllables("apple") == 2
    assert _count_syllables("table") == 2
    assert _count_syllables("syllable") == 3


def test_syllable_heuristic_terminal_suffixes() -> None:
    # Terminal "-es" is silent unless the stem ends in s, z, x, ch, or sh;
    # consonant + "les" keeps its syllable; terminal "-ed" is silent unless
    # the stem ends in t or d.
    assert _count_syllables("makes") == 1
    assert _count_syllables("likes") == 1
    assert _count_syllables("catches") == 2
    assert _count_syllables("boxes") == 2
    assert _count_syllables("tables") == 2
    assert _count_syllables("liked") == 1
    assert _count_syllables("walked") == 1
    assert _count_syllables("wanted") == 2
    assert _count_syllables("needed") == 2


def test_flesch_reading_ease_known_value() -> None:
    # "The quick brown fox." has 4 words, 1 sentence, 4 syllables (1 each).
    # 206.835 - 1.015 * (4 / 1) - 84.6 * (4 / 4) == 118.175.
    assert flesch_reading_ease("The quick brown fox.") == pytest.approx(118.175)


def test_flesch_kincaid_grade_known_value() -> None:
    # 0.39 * (4 / 1) + 11.8 * (4 / 4) - 15.59 == -2.23.
    assert flesch_kincaid_grade("The quick brown fox.") == pytest.approx(-2.23)


def test_flesch_returns_none_for_empty_input() -> None:
    assert flesch_reading_ease("") is None
    assert flesch_kincaid_grade("") is None
    # A heading has word tokens but no sentence span, so readability is undefined.
    assert flesch_reading_ease("## Heading only") is None
    assert flesch_kincaid_grade("## Heading only") is None


def test_mtld_returns_none_below_ten_tokens() -> None:
    assert mtld("one two three") is None
    assert mtld(["word"] * 9) is None
    assert mtld("") is None


def test_mtld_accepts_text_or_tokens_identically() -> None:
    text = "alpha beta gamma delta echo foxtrot golf hotel india juliet"
    assert mtld(text) == mtld(tokenize(text))


def test_mtld_is_higher_for_more_diverse_text() -> None:
    diverse = [
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
        "india",
        "juliet",
    ] * 2
    repetitive = ["cat", "dog"] * 10
    diverse_score = mtld(diverse)
    repetitive_score = mtld(repetitive)
    assert diverse_score is not None
    assert repetitive_score is not None
    assert diverse_score > repetitive_score


def test_paragraph_stats_counts_blank_line_paragraphs() -> None:
    text = "First sentence here. Second sentence here.\n\nThird sentence alone."
    stats = paragraph_stats(text)
    assert stats == {
        "paragraph_count": 2.0,
        "mean_paragraph_sentence_count": 1.5,
        "single_sentence_paragraph_rate": 0.5,
    }


def test_paragraph_stats_excludes_headings() -> None:
    text = "## Title\n\nOne here. Two here.\n\nThree alone."
    stats = paragraph_stats(text)
    assert stats == {
        "paragraph_count": 2.0,
        "mean_paragraph_sentence_count": 1.5,
        "single_sentence_paragraph_rate": 0.5,
    }


def test_paragraph_stats_returns_none_for_empty_input() -> None:
    assert paragraph_stats("") is None
    assert paragraph_stats("   \n\n  ") is None
    assert paragraph_stats("## Only a heading") is None
