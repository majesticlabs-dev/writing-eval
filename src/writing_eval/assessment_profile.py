"""Profile-metric issues and source locations."""

from __future__ import annotations

from typing import Any

from .assessment_core import (
    absolute_gap,
    comparison_direction,
    direction,
    metric_comparison,
    profile_issue,
    relative_gap,
    round_half_up,
    scaled_deduction,
)
from .segmentation import segment, sentence_opener


def _line_and_column(text: str, char_offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, char_offset) + 1
    column = char_offset - text.rfind("\n", 0, char_offset)
    return line, column


def _excerpt(text: str, start: int, end: int, limit: int = 180) -> str:
    value = " ".join(text[start:end].split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _repeated_opening_patterns(text: str) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for group in segment(text):
        sentences: list[tuple[str, int, int, int]] = []
        for span_start, span_end in group:
            opener = sentence_opener(text, span_start, span_end)
            sentences.append(
                (text[opener[0] : opener[1]], opener[0], span_start, span_end)
            )
        run_start = 0
        while run_start < len(sentences):
            run_end = run_start + 1
            opener = sentences[run_start][0]
            while (
                run_end < len(sentences)
                and sentences[run_end][0].casefold() == opener.casefold()
            ):
                run_end += 1
            if run_end - run_start >= 2:
                first = sentences[run_start]
                last = sentences[run_end - 1]
                line, column = _line_and_column(text, first[1])
                patterns.append(
                    {
                        "line": line,
                        "column": column,
                        "opener": opener,
                        "sentence_count": run_end - run_start,
                        "excerpt": _excerpt(text, first[2], last[3]),
                    }
                )
            run_start = run_end
    return patterns


def gap_map(style_gap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    from .assessment_core import PROFILE_METRIC_DETAILS

    return {
        str(metric["metric"]): metric
        for metric in style_gap.get("metrics", [])
        if metric.get("metric") in PROFILE_METRIC_DETAILS
    }


def profile_issues(
    text: str,
    findings: list[dict[str, Any]],
    gaps: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    ease = gaps.get("flesch_reading_ease")
    grade = gaps.get("flesch_kincaid_grade")
    if ease is not None and grade is not None:
        readability_raw = scaled_deduction(
            absolute_gap(ease.get("draft"), ease.get("profile")), 5.0, 30.0, 6.0
        ) + scaled_deduction(
            absolute_gap(grade.get("draft"), grade.get("profile")), 1.0, 4.0, 6.0
        )
        if readability_raw > 0:
            ease_direction = comparison_direction(
                "flesch_reading_ease", ease.get("draft"), ease.get("profile")
            )
            grade_direction = comparison_direction(
                "flesch_kincaid_grade", grade.get("draft"), grade.get("profile")
            )
            ease_action = (
                "Keep reading ease near the target"
                if ease_direction == "maintain"
                else f"{ease_direction.capitalize()} reading ease toward the target"
            )
            grade_action = (
                "keep estimated reading level near the target"
                if grade_direction == "maintain"
                else f"{grade_direction} estimated reading level toward the target"
            )
            issues.append(
                profile_issue(
                    issue_id="readability_alignment",
                    section="readability",
                    requested_deduction=round_half_up(readability_raw),
                    summary="Reading complexity differs from the target profile.",
                    comparisons=[metric_comparison(ease), metric_comparison(grade)],
                    instruction=(
                        f"{ease_action} and {grade_action} by adjusting sentence and "
                        "word complexity selectively. Do not add jargon or complexity "
                        "solely to hit a metric."
                    ),
                    success_criteria=[
                        "Keep reading ease within 5 points of the target or move it closer.",
                        "Keep estimated reading level within 1 grade of the target or move it closer.",
                        "Preserve clarity while changing complexity.",
                    ],
                )
            )
    mean_length = gaps.get("mean_sentence_length")
    variance = gaps.get("sentence_length_variance")
    if mean_length is not None and variance is not None:
        rhythm_raw = scaled_deduction(
            relative_gap(mean_length.get("draft"), mean_length.get("profile")), 0.15, 1.0, 8.0
        ) + scaled_deduction(
            relative_gap(variance.get("draft"), variance.get("profile")), 0.25, 1.0, 7.0
        )
        if rhythm_raw > 0:
            current_mean = mean_length.get("draft")
            target_mean = mean_length.get("profile")
            mean_direction = comparison_direction(
                "mean_sentence_length", mean_length.get("draft"), mean_length.get("profile")
            )
            if mean_direction == "increase":
                action = "Combine selected explanatory sentences"
            elif mean_direction == "decrease":
                action = "Split selected long or multi-part sentences"
            else:
                action = "Preserve the current average sentence length"
            instruction = (
                f"{action} and adjust the mixture of short, medium, and long "
                "sentences toward the target profile. Preserve deliberate "
                "emphasis; do not mechanically force every sentence to the "
                f"{float(target_mean):.1f}-word target."
                if current_mean is not None and target_mean is not None
                else (
                    f"{action} and adjust sentence-length variation toward "
                    "the target profile without mechanically forcing exact values."
                )
            )
            issues.append(
                profile_issue(
                    issue_id="sentence_rhythm",
                    section="rhythm_structure",
                    requested_deduction=round_half_up(rhythm_raw),
                    summary="Sentence rhythm differs from the target profile.",
                    comparisons=[metric_comparison(mean_length), metric_comparison(variance)],
                    instruction=instruction,
                    success_criteria=[
                        "Move average sentence length closer to the target.",
                        "Move sentence-length variation closer to the target.",
                        "Preserve short or long sentences that serve a clear rhetorical purpose.",
                    ],
                )
            )
    repeated = gaps.get("repeated_opening_rate")
    patterns = _repeated_opening_patterns(text)
    repeated_findings = [
        finding for finding in findings if finding["rule_id"] == "repeated_openings"
    ]
    if repeated is not None:
        repeated_raw = scaled_deduction(
            absolute_gap(repeated.get("draft"), repeated.get("profile")), 0.03, 0.20, 10.0
        )
        if repeated_raw > 0:
            repeated_direction = direction(repeated.get("delta"))
            if repeated_direction == "decrease":
                instruction = (
                    "Vary or combine nonessential repeated openings. Review each run "
                    "for intent and retain deliberate anaphora when it strengthens the passage."
                )
            elif repeated_direction == "increase":
                instruction = (
                    "Consider whether selective parallel openings would better match "
                    "the target rhythm. Add repetition only when it improves emphasis."
                )
            else:
                instruction = "Preserve the current use of repeated openings."
            issues.append(
                profile_issue(
                    issue_id="repeated_openings",
                    section="rhythm_structure",
                    requested_deduction=round_half_up(repeated_raw),
                    summary="Repeated sentence openings differ from the target profile.",
                    comparisons=[metric_comparison(repeated)],
                    instruction=instruction,
                    success_criteria=[
                        "Move the repeated-opening rate toward the target profile.",
                        "Retain rhetorical repetition that clearly improves the passage.",
                    ],
                    locations=patterns,
                )
            )
        elif repeated_findings:
            issues.append(
                {
                    "id": "repeated_openings",
                    "kind": "review_candidate",
                    "section": "rhythm_structure",
                    "priority": "low",
                    "deduction": 0,
                    "summary": (
                        f"Repeated sentence openings appear in {len(patterns)} pattern"
                        f"{'' if len(patterns) == 1 else 's'}."
                    ),
                    "comparisons": [metric_comparison(repeated)],
                    "instruction": (
                        "Review each run for intent. Vary accidental repetition and "
                        "retain deliberate anaphora when it strengthens the passage."
                    ),
                    "success_criteria": [
                        "Every retained repeated opening serves a clear rhetorical purpose."
                    ],
                    "locations": patterns,
                    "_requested_deduction": 0,
                    "_profile_issue": False,
                }
            )
    return issues
