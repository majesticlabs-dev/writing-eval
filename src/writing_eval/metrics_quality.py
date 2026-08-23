"""General text-quality metrics."""

from __future__ import annotations

from collections.abc import Sequence
import math
from numbers import Real

from .segmentation import segment, tokenize

_SYLLABLE_VOWELS = frozenset("aeiouy")


def _count_syllables(word: str) -> int:
    """Return a heuristic syllable count for one word."""

    word = word.lower()
    count = int(bool(word and word[0] in _SYLLABLE_VOWELS))
    for index in range(1, len(word)):
        if word[index] in _SYLLABLE_VOWELS and word[index - 1] not in _SYLLABLE_VOWELS:
            count += 1
    if word.endswith("e"):
        count -= 1
    if word.endswith("le") and len(word) > 2 and word[-3] not in _SYLLABLE_VOWELS:
        count += 1
    if len(word) > 2 and word.endswith("es"):
        stem = word[:-2]
        consonant_les = (
            len(word) > 3 and word.endswith("les") and word[-4] not in _SYLLABLE_VOWELS
        )
        if not consonant_les and not stem.endswith(("s", "z", "x", "ch", "sh")):
            count -= 1
    if len(word) > 2 and word.endswith("ed"):
        stem = word[:-2]
        if not stem.endswith(("t", "d")):
            count -= 1
    return max(count, 1)


def _readability_counts(text: str) -> tuple[int, int, int] | None:
    tokens: list[str] = []
    sentences = 0
    for group in segment(text):
        sentences += len(group)
        for start, end in group:
            tokens.extend(tokenize(text[start:end]))
    if not tokens or sentences == 0:
        return None
    return len(tokens), sentences, sum(_count_syllables(token) for token in tokens)


def readability_scores(text: str) -> tuple[float | None, float | None]:
    """Return reading ease and grade from one tokenize and segment pass."""

    counts = _readability_counts(text)
    if counts is None:
        return None, None
    words, sentences, syllables = counts
    ease = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
    return ease, grade


def flesch_reading_ease(text: str) -> float | None:
    """Return the Flesch reading ease score for ``text``."""

    return readability_scores(text)[0]


def flesch_kincaid_grade(text: str) -> float | None:
    """Return the Flesch-Kincaid grade level for ``text``."""

    return readability_scores(text)[1]


def _as_tokens(text_or_tokens: str | Sequence[str]) -> list[str]:
    if isinstance(text_or_tokens, str):
        return tokenize(text_or_tokens)
    return [str(token).lower() for token in text_or_tokens]


def _mtld_factor_sum(tokens: Sequence[str], threshold: float) -> float:
    factor_sum = 0.0
    types: set[str] = set()
    segment_len = 0
    ttr = 1.0
    last_index = len(tokens) - 1
    for index, token in enumerate(tokens):
        types.add(token)
        segment_len += 1
        ttr = len(types) / segment_len
        if ttr < threshold:
            factor_sum += 1.0
            types = set()
            segment_len = 0
            ttr = 1.0
        elif index == last_index:
            factor_sum += 1.0
    return factor_sum


def mtld(text_or_tokens: str | Sequence[str], threshold: float = 0.72) -> float | None:
    """Return the Measure of Textual Lexical Diversity."""

    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, Real)
        or not math.isfinite(threshold)
        or not 0.0 < threshold < 1.0
    ):
        raise ValueError("threshold must be a finite real number between 0 and 1")
    tokens = _as_tokens(text_or_tokens)
    if len(tokens) < 10:
        return None
    forward = _mtld_factor_sum(tokens, threshold)
    backward = _mtld_factor_sum(list(reversed(tokens)), threshold)
    if forward <= 0.0 or backward <= 0.0:
        return None
    total = len(tokens)
    return (total / forward + total / backward) / 2.0


def paragraph_stats(text: str) -> dict[str, float] | None:
    """Return markdown-aware paragraph statistics for ``text``."""

    groups = list(segment(text))
    if not groups:
        return None
    sentence_counts = [len(group) for group in groups]
    paragraph_count = len(groups)
    single_sentence = sum(1 for count in sentence_counts if count == 1)
    return {
        "paragraph_count": float(paragraph_count),
        "mean_paragraph_sentence_count": sum(sentence_counts) / paragraph_count,
        "single_sentence_paragraph_rate": single_sentence / paragraph_count,
    }
