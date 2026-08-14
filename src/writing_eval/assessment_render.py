"""Render human- and LLM-readable profile assessments."""

from __future__ import annotations

from typing import Any

from .assessment_core import SECTION_DEFINITIONS, SECTION_ORDER


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any, unit: str) -> str:
    if value is None:
        return "n/a"
    numeric = float(value)
    if unit == "proportion":
        return f"{numeric * 100:.1f}%"
    if unit in {"words", "paragraphs", "occurrences"}:
        return str(int(numeric))
    if unit == "words_per_sentence":
        return f"{numeric:.1f} words"
    if unit == "grade":
        return f"Grade {numeric:.1f}"
    return f"{numeric:.1f}"


def _render_issue(lines: list[str], number: int, issue: dict[str, Any]) -> None:
    lines.append(f"### {number}. {issue['summary']}")
    lines.append("")
    lines.append(f"- Section: {SECTION_DEFINITIONS[SECTION_ORDER[issue['section']]][1]}")
    lines.append(f"- Priority: {issue['priority'].capitalize()}")
    deduction = issue["deduction"]
    deduction_text = f"-{deduction} points" if deduction else "0 points"
    lines.append(f"- Deduction: {deduction_text}")
    lines.append("")
    if issue["comparisons"]:
        lines.append("| Measure | Article | Target profile | Direction |")
        lines.append("|---|---:|---:|---|")
        for comparison in issue["comparisons"]:
            lines.append(
                f"| {_escape_table(comparison['label'])} "
                f"| {_format_value(comparison['current'], comparison['unit'])} "
                f"| {_format_value(comparison['target'], comparison['unit'])} "
                f"| {comparison['direction']} |"
            )
        lines.append("")
    if issue["locations"]:
        lines.append("Locations:")
        lines.append("")
        for location in issue["locations"]:
            if "opener" in location:
                lines.append(
                    f"- Line {location['line']}, column {location['column']}: "
                    f"“{location['opener']}” begins {location['sentence_count']} "
                    f"consecutive sentences — {location['excerpt']}"
                )
            else:
                lines.append(
                    f"- Line {location['line']}, column {location['column']}: "
                    f"`{location['span']}`"
                )
        lines.append("")
    lines.extend(["Editing instruction:", "", issue["instruction"], "", "Success criteria:", ""])
    for criterion in issue["success_criteria"]:
        lines.append(f"- {criterion}")
    lines.append("")


def render_assessment(display_name: str, assessment: dict[str, Any]) -> str:
    """Render a human- and LLM-readable Markdown assessment."""

    lines = ["# Writing Evaluation", "", f"File: `{display_name}`", ""]
    lines.extend(["## Article score (heuristic)", ""])
    score = assessment["score"]
    if assessment["status"] == "unscored":
        lines.append(f"**Unscored — {assessment['reason']}**")
    else:
        lines.append(f"**{score['total']}/{score['maximum']} — {score['label']}**")
    lines.extend(
        [
            "",
            "This score measures detected style patterns and alignment with the "
            "target profile. It does not measure factual accuracy or overall content quality.",
            "", "| Section | Score |", "|---|---:|",
        ]
    )
    for section in score["sections"]:
        rendered_score = (
            "n/a" if section["score"] is None else f"{section['score']}/{section['maximum']}"
        )
        lines.append(f"| {section['label']} | {rendered_score} |")
    if score["total"] is not None:
        lines.append(f"| **Total** | **{score['total']}/{score['maximum']}** |")
    lines.append("")
    improvements = [issue for issue in assessment["issues"] if issue["kind"] == "improvement"]
    review_candidates = [
        issue for issue in assessment["issues"] if issue["kind"] == "review_candidate"
    ]
    lines.extend(["## Issues to improve", ""])
    if improvements:
        for number, issue in enumerate(improvements, start=1):
            _render_issue(lines, number, issue)
    else:
        lines.extend(["No scored issues were detected.", ""])
    if review_candidates:
        lines.extend(["## Review candidates", ""])
        for number, issue in enumerate(review_candidates, start=1):
            _render_issue(lines, number, issue)
    lines.extend(
        [
            "## General statistics", "",
            "| Statistic | Article | Target profile | Interpretation |",
            "|---|---:|---:|---|",
        ]
    )
    for statistic in assessment["statistics"]:
        lines.append(
            f"| {_escape_table(statistic['label'])} "
            f"| {_format_value(statistic['value'], statistic['unit'])} "
            f"| {_format_value(statistic['target'], statistic['unit'])} "
            f"| {_escape_table(statistic['interpretation'])} |"
        )
    return "\n".join(lines) + "\n"
