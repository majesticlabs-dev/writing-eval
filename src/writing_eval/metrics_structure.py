"""Sentence and paragraph-structure metrics."""

from __future__ import annotations

from collections.abc import Iterable
import statistics

from .segmentation import segment, sentence_opener, tokenize


def _span_token_lengths(text: str) -> list[int]:
    return [
        len(tokenize(text[start:end]))
        for group in segment(text)
        for start, end in group
    ]


def sentence_length_stats(text: str) -> tuple[float, float]:
    """Return mean and population variance of sentence lengths in one pass."""

    lengths = _span_token_lengths(text)
    if not lengths:
        return 0.0, 0.0
    return sum(lengths) / len(lengths), float(statistics.pvariance(lengths))


def mean_sentence_length(text: str) -> float:
    """Return the mean number of word tokens per sentence."""

    return sentence_length_stats(text)[0]


def sentence_length_variance(text: str) -> float:
    """Return population variance of sentence lengths in word tokens."""

    return sentence_length_stats(text)[1]


def _opener_groups(text: str) -> list[list[str]]:
    groups: list[list[str]] = []
    for group in segment(text):
        openers: list[str] = []
        for start, end in group:
            opener = sentence_opener(text, start, end)
            if opener is not None:
                openers.append(text[opener[0] : opener[1]].casefold())
        groups.append(openers)
    return groups


def repeated_opening_rate(text: str) -> float:
    """Return the within-document repeated sentence-opening rate."""

    return repeated_opening_corpus_rate([text])


def repeated_opening_corpus_rate(texts: Iterable[str]) -> float:
    """Return the corpus repeated sentence-opening rate."""

    repeated_pairs = 0
    total_pairs = 0
    for text in texts:
        for openers in _opener_groups(text):
            total_pairs += max(len(openers) - 1, 0)
            repeated_pairs += sum(
                left == right for left, right in zip(openers, openers[1:])
            )
    return repeated_pairs / total_pairs if total_pairs else 0.0
