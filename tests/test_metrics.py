from collections import Counter
import math

import pytest

from writing_eval.metrics import (
    mean_sentence_length,
    repeated_opening_corpus_rate,
    repeated_opening_rate,
    sentence_length_variance,
    tell_rate,
    tell_rates_by_severity,
    token_1gram_l2,
    tokenize,
    top_overrepresented,
)
from writing_eval.metrics_distribution import (
    token_1gram_l2_from_counts,
    top_overrepresented_from_counts,
)
from writing_eval.schema import Finding


def finding(severity: str) -> Finding:
    return Finding("rule", severity, "message", "match", 0, 1)


def test_tell_rate_exact_and_filtered() -> None:
    findings = [finding("warning"), finding("error"), finding("warning")]
    assert tell_rate(findings, 6) == 500.0
    assert tell_rate(findings, 6, severity="warning") == pytest.approx(1000 / 3)
    assert tell_rate(findings, 6, severity="info") == 0.0


def test_tell_rates_by_severity_uses_one_normalized_denominator() -> None:
    findings = [finding("info"), finding("warn"), finding("warn")]
    assert tell_rates_by_severity(findings, 4) == {
        "info": pytest.approx(250.0),
        "warn": pytest.approx(500.0),
    }


def test_tokenize_keeps_ascii_and_curly_contractions_together() -> None:
    tokens = tokenize("We'll revise; we’ll ship.")
    assert tokens == [
        "we'll",
        "revise",
        "we’ll",
        "ship",
    ]
    assert "ll" not in tokens


def test_token_1gram_l2_exact_small_corpus() -> None:
    result = token_1gram_l2("a a b", ["a c"])
    assert result == pytest.approx(math.sqrt(14) / 6)


def test_sentence_length_metrics_exact() -> None:
    text = "One two. Three four five six!"
    assert mean_sentence_length(text) == 3.0
    assert sentence_length_variance(text) == 1.0


def test_repeated_openings_use_adjacent_sentence_pairs() -> None:
    assert repeated_opening_rate("We go. We stay. They leave.") == 0.5
    assert repeated_opening_rate("We go. They stay. We leave.") == 0.0


def test_repeated_opening_corpus_rate_ignores_document_boundaries_and_order() -> None:
    documents = ["We go.", "We stay. They leave."]
    assert repeated_opening_corpus_rate(documents) == 0.0
    assert repeated_opening_corpus_rate(list(reversed(documents))) == 0.0


def test_overrepresented_terms_are_ranked_by_rate_then_token() -> None:
    result = top_overrepresented("beta beta alpha alpha", ["alpha gamma"], n=3)
    assert result == [("beta", 0.5)]


def test_empty_inputs_are_safe() -> None:
    assert tell_rate([], 0) == 0.0
    assert token_1gram_l2("", ["reference"]) is None
    assert token_1gram_l2("output", []) is None
    assert top_overrepresented("", ["reference"]) == []
    assert mean_sentence_length("") == 0.0
    assert sentence_length_variance("") == 0.0
    assert repeated_opening_rate("") == 0.0
    assert repeated_opening_rate("Only one sentence.") == 0.0


def test_repeated_opening_corpus_rate_handles_numbered_list_markers() -> None:
    text = "1. Use short subjects. 2. Use active verbs. 3. Use one idea per line."
    assert repeated_opening_corpus_rate([text]) == 1.0
    assert repeated_opening_rate(text) == 1.0


def test_inline_numbered_list_matches_plain_prose_lengths() -> None:
    # Sentences: [3, 3, 5] tokens. Mean 11/3; pvariance 8/9. Digit markers
    # such as the mid-line "2." are dropped, so both forms agree exactly.
    listed = "1. Use short subjects. 2. Use active verbs. 3. Use one idea per line."
    plain = "Use short subjects. Use active verbs. Use one idea per line."
    assert mean_sentence_length(listed) == 11 / 3
    assert mean_sentence_length(listed) == mean_sentence_length(plain)
    assert sentence_length_variance(listed) == 8 / 9
    assert sentence_length_variance(listed) == sentence_length_variance(plain)
    assert repeated_opening_corpus_rate([listed]) == 1.0


def test_digit_bearing_prose_sentence_still_counts() -> None:
    # Tokens: 2026, was, a, busy, year. The letter-led words keep the span.
    assert mean_sentence_length("2026 was a busy year.") == 5.0


def test_decimal_does_not_split_sentence_length() -> None:
    # "3.5" stays one sentence: tokens latency, dropped, 3, 5, percent.
    assert mean_sentence_length("Latency dropped 3.5 percent.") == 5.0
    assert sentence_length_variance("Latency dropped 3.5 percent.") == 0.0


def test_sentence_length_metrics_flatten_paragraph_groups() -> None:
    text = "One two.\n\n## Head\n\nThree four five six!"
    assert mean_sentence_length(text) == 3.0
    assert sentence_length_variance(text) == 1.0


def test_opener_less_sentence_is_skipped_without_breaking_sequence() -> None:
    assert repeated_opening_corpus_rate(["We ship. 42. We learn."]) == 1.0


def test_heading_breaks_the_opener_sequence() -> None:
    assert repeated_opening_corpus_rate(["We ship.\n## note\nWe learn."]) == 0.0


def test_token_1gram_l2_from_counts_agrees_with_text_wrapper() -> None:
    output_counts = Counter(tokenize("a a b"))
    reference_counts = Counter(tokenize("a c"))
    assert token_1gram_l2_from_counts(output_counts, reference_counts) == token_1gram_l2(
        "a a b", ["a c"]
    )


def test_top_overrepresented_from_counts_agrees_with_text_wrapper() -> None:
    output_counts = Counter(tokenize("beta beta alpha alpha"))
    reference_counts = Counter(tokenize("alpha gamma"))
    assert top_overrepresented_from_counts(
        output_counts, reference_counts, n=3
    ) == top_overrepresented("beta beta alpha alpha", ["alpha gamma"], n=3)


def test_from_counts_functions_are_empty_safe() -> None:
    assert token_1gram_l2_from_counts({}, Counter(tokenize("reference"))) is None
    assert token_1gram_l2_from_counts(Counter(tokenize("output")), {}) is None
    assert top_overrepresented_from_counts({}, Counter(tokenize("reference"))) == []


def test_metrics_are_deterministic_across_repeated_calls() -> None:
    calls = [
        lambda: token_1gram_l2("one two two", ["one three"]),
        lambda: top_overrepresented("one two two", ["one three"]),
        lambda: mean_sentence_length("One two. Three."),
        lambda: sentence_length_variance("One two. Three."),
        lambda: repeated_opening_rate("One starts. One continues. Two ends."),
    ]
    for call in calls:
        assert call() == call()


def test_sentence_length_stats_matches_single_metric_functions() -> None:
    from writing_eval.metrics_structure import (
        mean_sentence_length,
        sentence_length_stats,
        sentence_length_variance,
    )

    text = "One two three. Four five. Six seven eight nine ten."
    mean, variance = sentence_length_stats(text)
    assert mean == mean_sentence_length(text)
    assert variance == sentence_length_variance(text)
    assert sentence_length_stats("") == (0.0, 0.0)


def test_readability_scores_matches_single_metric_functions() -> None:
    from writing_eval.metrics_quality import (
        flesch_kincaid_grade,
        flesch_reading_ease,
        readability_scores,
    )

    text = "The quick brown fox jumps over the lazy dog. It then rests."
    ease, grade = readability_scores(text)
    assert ease == flesch_reading_ease(text)
    assert grade == flesch_kincaid_grade(text)
    assert readability_scores("## Heading only") == (None, None)


def test_excluded_tokens_are_removed_before_normalization() -> None:
    from writing_eval.metrics_distribution import (
        normalized_from_counts,
        top_overrepresented_from_counts,
    )

    output = {"the": 4, "beacon": 2, "signal": 2}
    reference = {"the": 16, "beacon": 1, "signal": 3}
    distribution = normalized_from_counts(output, exclude={"the"})
    assert distribution == {"beacon": 0.5, "signal": 0.5}
    ranked = top_overrepresented_from_counts(
        output, reference, n=5, exclude={"the"}
    )
    assert [token for token, _difference in ranked] == ["beacon"]
