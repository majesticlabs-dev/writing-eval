"""Compatibility facade for deterministic writing metrics."""

from .metrics_distribution import (
    tell_rate,
    tell_rates_by_severity,
    token_1gram_l2,
    top_overrepresented,
)
from .metrics_quality import (
    flesch_kincaid_grade,
    flesch_reading_ease,
    mtld,
    paragraph_stats,
)
from .metrics_structure import (
    mean_sentence_length,
    repeated_opening_corpus_rate,
    repeated_opening_rate,
    sentence_length_variance,
)
from .segmentation import tokenize

__all__ = [
    "flesch_kincaid_grade",
    "flesch_reading_ease",
    "mean_sentence_length",
    "mtld",
    "paragraph_stats",
    "repeated_opening_corpus_rate",
    "repeated_opening_rate",
    "sentence_length_variance",
    "tell_rate",
    "tell_rates_by_severity",
    "token_1gram_l2",
    "tokenize",
    "top_overrepresented",
]
