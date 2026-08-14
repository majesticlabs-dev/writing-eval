"""Style-profile statistics and draft comparisons."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from .metrics import (
    mtld,
    paragraph_stats,
    repeated_opening_corpus_rate,
    repeated_opening_rate,
)
from .metrics_distribution import (
    token_1gram_l2_from_counts,
    top_overrepresented_from_counts,
)
from .metrics_quality import readability_scores
from .metrics_structure import sentence_length_stats
from .segmentation import tokenize

_STOPWORDS = frozenset(
    {
        "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
        "are", "as", "at", "be", "because", "been", "before", "being", "both",
        "but", "by", "can", "could", "did", "do", "does", "down", "each", "for",
        "from", "had", "has", "have", "he", "her", "here", "hers", "him", "his",
        "how", "i", "if", "in", "into", "is", "it", "its", "just", "may", "me",
        "might", "more", "most", "must", "my", "no", "not", "now", "of", "off",
        "on", "once", "only", "or", "our", "ours", "out", "over", "own", "she",
        "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
        "them", "then", "there", "these", "they", "this", "those", "through",
        "to", "too", "up", "us", "very", "was", "we", "were", "what", "when",
        "where", "which", "while", "who", "whom", "why", "will", "with", "would",
        "you", "your", "yours",
    }
)

_STYLE_GAP_METRIC_ORDER = (
    "mean_sentence_length",
    "sentence_length_variance",
    "repeated_opening_rate",
    "flesch_reading_ease",
    "flesch_kincaid_grade",
    "mtld",
)


def _combined_text(texts: Sequence[str]) -> str:
    cleaned = [text.strip().rstrip(".!?") for text in texts if text and text.strip()]
    return ". ".join(cleaned) + ("." if cleaned else "")


def _top_content_tokens(texts: Sequence[str], n: int = 20) -> list[dict]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(token for token in tokenize(text) if token not in _STOPWORDS)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"token": token, "count": count} for token, count in ranked[:n]]


def profile_statistics(texts: Sequence[str]) -> dict:
    combined = _combined_text(texts)
    sentence_mean, sentence_variance = sentence_length_stats(combined)
    reading_ease, reading_grade = readability_scores(combined)
    return {
        "mean_sentence_length": sentence_mean,
        "sentence_length_variance": sentence_variance,
        "repeated_opening_rate": repeated_opening_corpus_rate(texts),
        "flesch_reading_ease": reading_ease,
        "flesch_kincaid_grade": reading_grade,
        "mtld": mtld(combined),
        "paragraph_stats": paragraph_stats("\n\n".join(texts)),
        "top_tokens": _top_content_tokens(texts),
    }


def build_style_gap(
    name: str,
    draft_text: str,
    statistics: dict,
    reference_counts: Mapping[str, int],
) -> dict:
    """Compare a draft against a profile's statistics and reference token counts."""

    sentence_mean, sentence_variance = sentence_length_stats(draft_text)
    reading_ease, reading_grade = readability_scores(draft_text)
    draft_values = {
        "mean_sentence_length": sentence_mean,
        "sentence_length_variance": sentence_variance,
        "repeated_opening_rate": repeated_opening_rate(draft_text),
        "flesch_reading_ease": reading_ease,
        "flesch_kincaid_grade": reading_grade,
        "mtld": mtld(draft_text),
    }
    metrics: list[dict] = []
    for key in _STYLE_GAP_METRIC_ORDER:
        draft_value = draft_values[key]
        profile_value = statistics.get(key)
        delta = (
            None
            if draft_value is None or profile_value is None
            else draft_value - profile_value
        )
        metrics.append(
            {"metric": key, "draft": draft_value, "profile": profile_value, "delta": delta}
        )
    draft_counts = Counter(tokenize(draft_text))
    return {
        "profile": name,
        "metrics": metrics,
        "token_1gram_l2": token_1gram_l2_from_counts(draft_counts, reference_counts),
        "top_overrepresented": [
            {"token": token, "rate_difference": difference}
            for token, difference in top_overrepresented_from_counts(
                draft_counts, reference_counts, n=10, exclude=_STOPWORDS
            )
        ],
    }
