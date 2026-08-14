"""Shared constants and score helpers for profile assessments."""

from __future__ import annotations

import math
from typing import Any

SECTION_DEFINITIONS = (
    ("clarity_directness", "Clarity and directness"),
    ("readability", "Readability"),
    ("rhythm_structure", "Rhythm and structure"),
    ("vocabulary_style", "Vocabulary and style"),
)
SECTION_ORDER = {
    section_id: index
    for index, (section_id, _label) in enumerate(SECTION_DEFINITIONS)
}
SECTION_MAXIMUM = 25
ASSESSMENT_MAXIMUM = len(SECTION_DEFINITIONS) * SECTION_MAXIMUM
CLARITY_RULES = frozenset(
    {
        "negative_parallelism", "metadiscourse_openers", "vague_authority",
        "passive_voice", "hedging", "throat_clearing", "superficial_analysis",
        "negative_listing",
    }
)
SEVERITY_DEDUCTION = {"warn": 2, "info": 0}
SEVERITY_PRIORITY = {"warn": "medium", "info": "low"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PROFILE_METRIC_DETAILS = {
    "mean_sentence_length": ("Average sentence length", "words_per_sentence"),
    "sentence_length_variance": ("Sentence-length variance", "variance"),
    "repeated_opening_rate": ("Repeated openings", "proportion"),
    "flesch_reading_ease": ("Reading ease", "score"),
    "flesch_kincaid_grade": ("Estimated reading level", "grade"),
    "mtld": ("Vocabulary diversity", "mtld"),
}


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def scaled_deduction(
    gap: float | None, tolerance: float, cap: float, maximum: float
) -> float:
    if tolerance >= cap:
        raise ValueError("tolerance must be less than cap")
    if gap is None or gap <= tolerance:
        return 0.0
    bounded = min(gap, cap)
    return maximum * (bounded - tolerance) / (cap - tolerance)


def relative_gap(current: Any, target: Any) -> float | None:
    if current is None or target is None:
        return None
    return abs(float(current) - float(target)) / max(abs(float(target)), 1.0)


def absolute_gap(current: Any, target: Any) -> float | None:
    if current is None or target is None:
        return None
    return abs(float(current) - float(target))


def direction(delta: Any) -> str:
    if delta is None:
        return "unavailable"
    numeric = float(delta)
    if numeric < 0:
        return "increase"
    if numeric > 0:
        return "decrease"
    return "maintain"


def comparison_direction(metric_id: str, current: Any, target: Any) -> str:
    absolute = absolute_gap(current, target)
    relative = relative_gap(current, target)
    within_tolerance = {
        "mean_sentence_length": relative is not None and relative <= 0.15,
        "sentence_length_variance": relative is not None and relative <= 0.25,
        "repeated_opening_rate": absolute is not None and absolute <= 0.03,
        "flesch_reading_ease": absolute is not None and absolute <= 5.0,
        "flesch_kincaid_grade": absolute is not None and absolute <= 1.0,
        "mtld": True,
    }[metric_id]
    if within_tolerance:
        return "maintain" if metric_id != "mtld" else "informational"
    if current is None or target is None:
        return "unavailable"
    return direction(float(current) - float(target))


def metric_comparison(metric: dict[str, Any]) -> dict[str, Any]:
    metric_id = str(metric["metric"])
    label, unit = PROFILE_METRIC_DETAILS[metric_id]
    return {
        "metric": metric_id,
        "label": label,
        "current": metric.get("draft"),
        "target": metric.get("profile"),
        "delta": metric.get("delta"),
        "direction": comparison_direction(
            metric_id, metric.get("draft"), metric.get("profile")
        ),
        "unit": unit,
    }


def profile_priority(deduction: int) -> str:
    if deduction >= 6:
        return "high"
    if deduction >= 3:
        return "medium"
    return "low"


def _first_location(issue: dict[str, Any]) -> tuple[float, float]:
    locations = issue.get("locations", [])
    if not locations:
        return math.inf, math.inf
    first = min(
        locations,
        key=lambda item: (item.get("line", math.inf), item.get("column", math.inf)),
    )
    return first.get("line", math.inf), first.get("column", math.inf)


def issue_sort_key(issue: dict[str, Any]) -> tuple[Any, ...]:
    line, column = _first_location(issue)
    return (
        PRIORITY_ORDER[issue["priority"]],
        SECTION_ORDER[issue["section"]],
        issue["id"],
        line,
        column,
    )


def profile_issue(
    *, issue_id: str, section: str, requested_deduction: int, summary: str,
    comparisons: list[dict[str, Any]], instruction: str,
    success_criteria: list[str], locations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "kind": "improvement",
        "section": section,
        "priority": profile_priority(requested_deduction),
        "deduction": 0,
        "summary": summary,
        "comparisons": comparisons,
        "instruction": instruction,
        "success_criteria": success_criteria,
        "locations": locations or [],
        "_requested_deduction": requested_deduction,
        "_profile_issue": True,
    }
