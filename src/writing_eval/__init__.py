"""Public package interface for writing-eval."""

from .metrics import (
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
from .report import build_provenance, build_report, render_markdown
from .schema import ContentAssignment, EvalRecord, Finding

__all__ = [
    "ContentAssignment",
    "EvalRecord",
    "Finding",
    "build_report",
    "build_provenance",
    "mean_sentence_length",
    "render_markdown",
    "repeated_opening_corpus_rate",
    "repeated_opening_rate",
    "sentence_length_variance",
    "tell_rate",
    "tell_rates_by_severity",
    "token_1gram_l2",
    "tokenize",
    "top_overrepresented",
]
