"""General statistics for profile assessments."""

from __future__ import annotations

from typing import Any

from .assessment_core import PROFILE_METRIC_DETAILS


def _interpret(metric_id: str, current: Any, target: Any) -> str:
    if current is None:
        return "unavailable"
    if target is None:
        return "informational"
    delta = float(current) - float(target)
    if metric_id == "mean_sentence_length":
        if abs(delta) / max(abs(float(target)), 1.0) <= 0.15:
            return "closely aligned"
        return "longer than target" if delta > 0 else "shorter than target"
    if metric_id == "sentence_length_variance":
        if abs(delta) / max(abs(float(target)), 1.0) <= 0.25:
            return "closely aligned"
        return "more varied than target" if delta > 0 else "more uniform than target"
    if metric_id == "repeated_opening_rate":
        if abs(delta) <= 0.03:
            return "closely aligned"
        return "higher than target" if delta > 0 else "lower than target"
    if metric_id == "flesch_reading_ease":
        if abs(delta) <= 5.0:
            return "closely aligned"
        return "easier than target" if delta > 0 else "harder than target"
    if metric_id == "flesch_kincaid_grade":
        if abs(delta) <= 1.0:
            return "closely aligned"
        return "higher than target" if delta > 0 else "lower than target"
    if metric_id == "mtld":
        if delta == 0:
            return "aligned; informational"
        return "higher than target; informational" if delta > 0 else "lower than target; informational"
    if metric_id == "mean_paragraph_sentence_count":
        if abs(delta) / max(abs(float(target)), 1.0) <= 0.15:
            return "closely aligned"
        return "more than target" if delta > 0 else "fewer than target"
    if metric_id == "single_sentence_paragraph_rate":
        if abs(delta) <= 0.05:
            return "closely aligned"
        return "higher than target" if delta > 0 else "lower than target"
    return "informational"


def _statistic(
    metric_id: str, label: str, value: Any, unit: str, target: Any = None
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": unit,
        "target": target,
        "interpretation": _interpret(metric_id, value, target),
    }


def build_statistics(
    metrics: dict[str, Any],
    quality: dict[str, Any],
    gaps: dict[str, dict[str, Any]],
    profile_statistics: dict[str, Any],
) -> list[dict[str, Any]]:
    statistics = [
        _statistic("word_count", "Word count", metrics.get("word_count"), "words")
    ]
    for metric_id in (
        "mean_sentence_length", "sentence_length_variance", "repeated_opening_rate",
        "flesch_reading_ease", "flesch_kincaid_grade", "mtld",
    ):
        gap = gaps.get(metric_id) or {}
        label, unit = PROFILE_METRIC_DETAILS[metric_id]
        statistics.append(
            _statistic(metric_id, label, gap.get("draft"), unit, gap.get("profile"))
        )
    paragraph = quality.get("paragraph_stats")
    target_paragraph = profile_statistics.get("paragraph_stats")
    paragraph_values = paragraph if isinstance(paragraph, dict) else {}
    target_values = target_paragraph if isinstance(target_paragraph, dict) else {}
    statistics.extend(
        [
            _statistic(
                "paragraph_count", "Paragraphs",
                paragraph_values.get("paragraph_count"), "paragraphs",
            ),
            _statistic(
                "mean_paragraph_sentence_count", "Average sentences per paragraph",
                paragraph_values.get("mean_paragraph_sentence_count"),
                "sentences_per_paragraph",
                target_values.get("mean_paragraph_sentence_count"),
            ),
            _statistic(
                "single_sentence_paragraph_rate", "Single-sentence paragraphs",
                paragraph_values.get("single_sentence_paragraph_rate"), "proportion",
                target_values.get("single_sentence_paragraph_rate"),
            ),
        ]
    )
    return statistics
