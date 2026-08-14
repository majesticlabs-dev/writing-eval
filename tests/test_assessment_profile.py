"""Tests for profile-relative scored assessments."""

from writing_eval.assessment import (
    _relative_gap,
    _scaled_deduction,
    build_assessment,
    build_rule_baseline,
)
from tests.helpers_assessment import (
    _metrics,
    _profile_statistics,
    _quality,
    _style_gap,
)

def test_profile_gap_deductions_sum_to_section_and_total() -> None:
    assessment = build_assessment(
        "Short line. Another short line.",
        [],
        _metrics(),
        _quality(),
        _style_gap(
            {
                "mean_sentence_length": (5.0, 10.0),
                "sentence_length_variance": (5.0, 20.0),
                "repeated_opening_rate": (0.25, 0.05),
                "flesch_kincaid_grade": (6.0, 8.0),
            }
        ),
        _profile_statistics(),
    )

    issue_deduction = sum(issue["deduction"] for issue in assessment["issues"])
    section_deduction = sum(
        section["deduction"] for section in assessment["score"]["sections"]
    )
    assert issue_deduction == section_deduction
    assert issue_deduction == 100 - assessment["score"]["total"]
    assert {issue["id"] for issue in assessment["issues"]} == {
        "readability_alignment",
        "repeated_openings",
        "sentence_rhythm",
    }


def test_repeated_opening_findings_are_grouped_into_runs() -> None:
    text = (
        "The first moves. The second follows. The third stops.\n\n"
        "Some stay. Some leave."
    )
    findings = [
        {
            "rule_id": "repeated_openings",
            "severity": "info",
            "message": "Vary openings.",
            "line": 1,
            "column": 18,
            "span": "The",
        },
        {
            "rule_id": "repeated_openings",
            "severity": "info",
            "message": "Vary openings.",
            "line": 1,
            "column": 38,
            "span": "The",
        },
        {
            "rule_id": "repeated_openings",
            "severity": "info",
            "message": "Vary openings.",
            "line": 3,
            "column": 12,
            "span": "Some",
        },
    ]
    assessment = build_assessment(
        text,
        findings,
        _metrics(),
        _quality(),
        _style_gap({"repeated_opening_rate": (0.6, 0.1)}),
        _profile_statistics(),
    )
    repeated = next(
        issue for issue in assessment["issues"] if issue["id"] == "repeated_openings"
    )

    assert len(repeated["locations"]) == 2
    assert [location["sentence_count"] for location in repeated["locations"]] == [
        3,
        2,
    ]


def test_empty_draft_has_explicit_unscored_contract() -> None:
    assessment = build_assessment(
        "",
        [],
        _metrics(word_count=0),
        _quality(reading_ease=None),
        _style_gap(
            {
                "mean_sentence_length": (0.0, 10.0),
                "sentence_length_variance": (0.0, 20.0),
                "repeated_opening_rate": (0.0, 0.1),
                "flesch_reading_ease": (None, 60.0),
                "flesch_kincaid_grade": (None, 8.0),
                "mtld": (None, 70.0),
            }
        ),
        _profile_statistics(),
    )

    assert assessment["status"] == "unscored"
    assert assessment["reason"] == "Draft has no scorable prose sentences."
    assert assessment["score"]["total"] is None
    assert assessment["score"]["label"] is None
    assert all(
        section["score"] is None for section in assessment["score"]["sections"]
    )
    assert assessment["issues"] == []


def test_empty_draft_with_incomplete_gap_map_keeps_every_statistic() -> None:
    gap = _style_gap({"mean_sentence_length": (0.0, 10.0), "mtld": (None, 70.0)})
    gap["metrics"] = [
        metric
        for metric in gap["metrics"]
        if metric["metric"] in {"mean_sentence_length", "mtld"}
    ]
    assessment = build_assessment(
        "",
        [],
        _metrics(word_count=0),
        _quality(reading_ease=None),
        gap,
        _profile_statistics(),
    )

    assert assessment["status"] == "unscored"
    assert [statistic["id"] for statistic in assessment["statistics"]] == [
        "word_count",
        "mean_sentence_length",
        "sentence_length_variance",
        "repeated_opening_rate",
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "mtld",
        "paragraph_count",
        "mean_paragraph_sentence_count",
        "single_sentence_paragraph_rate",
    ]
    missing = next(
        statistic
        for statistic in assessment["statistics"]
        if statistic["id"] == "sentence_length_variance"
    )
    assert missing["value"] is None
    assert missing["target"] is None
    assert missing["interpretation"] == "unavailable"
    assert assessment["issues"] == []


def test_scored_draft_missing_gap_skips_dependent_issue_and_stays_visible() -> None:
    gap = _style_gap(
        {
            "flesch_reading_ease": (20.0, 60.0),
            "mean_sentence_length": (10.0, 10.0),
            "sentence_length_variance": (20.0, 20.0),
            "repeated_opening_rate": (0.1, 0.1),
            "mtld": (70.0, 70.0),
        }
    )
    gap["metrics"] = [
        metric
        for metric in gap["metrics"]
        if metric["metric"] != "flesch_kincaid_grade"
    ]
    assessment = build_assessment(
        "Clear prose. Editors revise.",
        [],
        _metrics(),
        _quality(),
        gap,
        _profile_statistics(),
    )

    assert assessment["status"] == "scored"
    assert assessment["score"]["total"] == 100
    assert not any(
        issue["id"] == "readability_alignment" for issue in assessment["issues"]
    )
    grade = next(
        statistic
        for statistic in assessment["statistics"]
        if statistic["id"] == "flesch_kincaid_grade"
    )
    assert grade["value"] is None
    assert grade["target"] is None
    assert grade["interpretation"] == "unavailable"
