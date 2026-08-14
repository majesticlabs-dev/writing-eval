"""Build scored profile-relative assessments."""

from __future__ import annotations

from typing import Any

from .assessment_core import (
    ASSESSMENT_MAXIMUM,
    SECTION_DEFINITIONS,
    SECTION_MAXIMUM,
    issue_sort_key,
    profile_priority,
)
from .assessment_profile import gap_map, profile_issues
from .assessment_rules import rule_issues
from .assessment_statistics import build_statistics


def _score_label(total: int) -> str:
    if total >= 90:
        return "High alignment"
    if total >= 75:
        return "Moderate alignment"
    if total >= 60:
        return "Low alignment"
    return "Very low alignment"


def build_assessment(
    text: str,
    findings: list[dict[str, Any]],
    metrics: dict[str, Any],
    quality_metrics: dict[str, Any],
    style_gap: dict[str, Any],
    profile_statistics: dict[str, Any],
    rule_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, profile-relative editorial assessment."""

    gaps = gap_map(style_gap)
    statistics = build_statistics(metrics, quality_metrics, gaps, profile_statistics)
    profile_relative_rules = rule_baseline is not None
    assessment: dict[str, Any] = {
        "schema_version": 2 if profile_relative_rules else 1,
        "rubric_version": (
            "profile-alignment-v2" if profile_relative_rules else "profile-alignment-v1"
        ),
        "basis": "rules_and_target_profile",
        "status": "scored",
        "profile": {"id": style_gap["profile"]},
        "score": {},
        "issues": [],
        "statistics": statistics,
    }
    if rule_baseline is not None:
        assessment["rule_baseline"] = rule_baseline
    if (
        not metrics.get("word_count")
        or quality_metrics.get("flesch_reading_ease") is None
    ):
        assessment["status"] = "unscored"
        assessment["reason"] = "Draft has no scorable prose sentences."
        assessment["score"] = {
            "total": None,
            "maximum": ASSESSMENT_MAXIMUM,
            "label": None,
            "sections": [
                {
                    "id": section_id, "label": label, "score": None,
                    "maximum": SECTION_MAXIMUM, "deduction": None,
                }
                for section_id, label in SECTION_DEFINITIONS
            ],
        }
        return assessment
    issues = rule_issues(findings, rule_baseline)
    issues.extend(profile_issues(text, findings, gaps))
    issues.sort(key=issue_sort_key)
    remaining = {
        section_id: SECTION_MAXIMUM for section_id, _label in SECTION_DEFINITIONS
    }
    for issue in issues:
        section = issue["section"]
        requested = int(issue["_requested_deduction"])
        assigned = min(requested, remaining[section])
        issue["deduction"] = assigned
        remaining[section] -= assigned
        if issue["_profile_issue"]:
            issue["priority"] = profile_priority(assigned)
    issues.sort(key=issue_sort_key)
    for issue in issues:
        issue.pop("_requested_deduction", None)
        issue.pop("_profile_issue", None)
    sections = [
        {
            "id": section_id,
            "label": label,
            "score": remaining[section_id],
            "maximum": SECTION_MAXIMUM,
            "deduction": SECTION_MAXIMUM - remaining[section_id],
        }
        for section_id, label in SECTION_DEFINITIONS
    ]
    total = sum(section["score"] for section in sections)
    total_issue_deduction = sum(issue["deduction"] for issue in issues)
    total_section_deduction = sum(section["deduction"] for section in sections)
    if (
        total_issue_deduction != total_section_deduction
        or total_section_deduction != ASSESSMENT_MAXIMUM - total
    ):
        raise RuntimeError("assessment deduction totals are inconsistent")
    assessment["score"] = {
        "total": total,
        "maximum": ASSESSMENT_MAXIMUM,
        "label": _score_label(total),
        "sections": sections,
    }
    assessment["issues"] = issues
    return assessment
