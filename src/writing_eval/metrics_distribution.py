"""Distribution and finding-rate metrics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping
import math
from typing import Any

from .segmentation import tokenize


def tell_rate(
    findings: Iterable[Any], word_count: int, severity: str | None = None
) -> float:
    """Return findings per 1,000 words, optionally filtered by severity."""

    if word_count <= 0:
        return 0.0
    count = 0
    for finding in findings:
        finding_severity = (
            finding.get("severity")
            if isinstance(finding, dict)
            else getattr(finding, "severity", None)
        )
        if severity is None or finding_severity == severity:
            count += 1
    return count * 1000.0 / word_count


def tell_rates_by_severity(
    findings: Iterable[Any], word_count: int
) -> dict[str, float]:
    """Return normalized tell rates for each severity in ``findings``."""

    finding_list = list(findings)
    severities = {
        (
            finding.get("severity")
            if isinstance(finding, dict)
            else getattr(finding, "severity", None)
        )
        for finding in finding_list
    }
    normalized = {
        str(severity): tell_rate(finding_list, word_count, severity=severity)
        for severity in severities
        if severity is not None
    }
    return dict(sorted(normalized.items()))


def normalized_from_counts(
    counts: Mapping[str, int], exclude: Collection[str] | None = None
) -> dict[str, float]:
    """Return a token-to-rate distribution from integer unigram counts.

    ``exclude`` drops tokens before the normalization denominator is
    calculated, so remaining rates are relative to the kept tokens only.
    """

    if exclude is not None:
        counts = {
            token: count for token, count in counts.items() if token not in exclude
        }
    total = sum(counts.values())
    if not counts or total <= 0:
        return {}
    return {token: count / total for token, count in counts.items()}


def _reference_tokens(reference_corpus: Iterable[str]) -> list[str]:
    tokens: list[str] = []
    for text in reference_corpus:
        tokens.extend(tokenize(text))
    return tokens


def token_1gram_l2_from_counts(
    output_counts: Mapping[str, int], reference_counts: Mapping[str, int]
) -> float | None:
    """Return L2 distance between normalized output and reference unigrams."""

    if not output_counts or not reference_counts:
        return None
    output_distribution = normalized_from_counts(output_counts)
    reference_distribution = normalized_from_counts(reference_counts)
    # Sum over a fixed, sorted vocabulary order: the cached path builds its
    # distribution from a JSON-loaded dict and the live path from a Counter,
    # so raw-set iteration order (and thus float summation order) can
    # differ between the two, which would break byte-identical output.
    vocabulary = sorted(output_distribution.keys() | reference_distribution.keys())
    squared_distance = sum(
        (output_distribution.get(token, 0.0) - reference_distribution.get(token, 0.0))
        ** 2
        for token in vocabulary
    )
    return math.sqrt(squared_distance)


def top_overrepresented_from_counts(
    output_counts: Mapping[str, int],
    reference_counts: Mapping[str, int],
    n: int = 10,
    exclude: Collection[str] | None = None,
) -> list[tuple[str, float]]:
    """Return tokens with the largest positive output-reference rate."""

    if n <= 0:
        return []
    if not output_counts or not reference_counts:
        return []
    output_distribution = normalized_from_counts(output_counts, exclude=exclude)
    reference_distribution = normalized_from_counts(reference_counts, exclude=exclude)
    differences = [
        (token, output_rate - reference_distribution.get(token, 0.0))
        for token, output_rate in output_distribution.items()
        if output_rate - reference_distribution.get(token, 0.0) > 0.0
    ]
    differences.sort(key=lambda item: (-item[1], item[0]))
    return differences[:n]


def token_1gram_l2(
    output_text: str, reference_corpus: Iterable[str]
) -> float | None:
    """Return L2 distance between normalized output and reference unigrams."""

    output_tokens = tokenize(output_text)
    reference_tokens = _reference_tokens(reference_corpus)
    if not output_tokens or not reference_tokens:
        return None
    return token_1gram_l2_from_counts(Counter(output_tokens), Counter(reference_tokens))


def top_overrepresented(
    output_text: str, reference_corpus: Iterable[str], n: int = 10
) -> list[tuple[str, float]]:
    """Return tokens with the largest positive output-reference rate."""

    if n <= 0:
        return []
    output_tokens = tokenize(output_text)
    reference_tokens = _reference_tokens(reference_corpus)
    if not output_tokens or not reference_tokens:
        return []
    return top_overrepresented_from_counts(
        Counter(output_tokens), Counter(reference_tokens), n=n
    )
