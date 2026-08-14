"""Tests for profile-relative scored assessments."""

import pytest

from writing_eval.assessment import (
    _relative_gap,
    _scaled_deduction,
    build_assessment,
    build_rule_baseline,
    render_assessment,
)
from writing_eval.assessment_core import (
    ASSESSMENT_MAXIMUM,
    SECTION_DEFINITIONS,
    SECTION_MAXIMUM,
)
from tests.helpers_assessment import (
    _metrics,
    _profile_statistics,
    _quality,
    _style_gap,
)

def test_scaled_deduction_has_exact_tolerance_and_cap_boundaries() -> None:
    assert _scaled_deduction(5.0, 5.0, 30.0, 6.0) == 0.0
    assert _scaled_deduction(30.0, 5.0, 30.0, 6.0) == 6.0
    assert _scaled_deduction(100.0, 5.0, 30.0, 6.0) == 6.0


def test_scaled_deduction_rejects_invalid_bounds_for_every_gap() -> None:
    with pytest.raises(ValueError):
        _scaled_deduction(None, 30.0, 30.0, 6.0)
    with pytest.raises(ValueError):
        _scaled_deduction(4.0, 30.0, 30.0, 6.0)
    with pytest.raises(ValueError):
        _scaled_deduction(40.0, 35.0, 30.0, 6.0)
    assert _scaled_deduction(6.0, 5.0, 30.0, 6.0) == pytest.approx(0.24)


def test_score_and_section_maxima_come_from_shared_constants() -> None:
    assert SECTION_MAXIMUM * len(SECTION_DEFINITIONS) == ASSESSMENT_MAXIMUM
    assessment = build_assessment(
        "Aligned prose. Editors revise.",
        [],
        _metrics(),
        _quality(),
        _style_gap(),
        _profile_statistics(),
    )
    assert assessment["score"]["maximum"] == ASSESSMENT_MAXIMUM
    assert [
        section["maximum"] for section in assessment["score"]["sections"]
    ] == [SECTION_MAXIMUM] * len(SECTION_DEFINITIONS)


def test_relative_gap_handles_zero_profile_target() -> None:
    assert _relative_gap(0.5, 0.0) == 0.5
    assert _relative_gap(0.0, 0.0) == 0.0


def test_score_deductions_are_exact_and_info_findings_do_not_lower_score() -> None:
    findings = [
        {
            "rule_id": "polish_vocab",
            "severity": "warn",
            "message": "Use specific language.",
            "line": 1,
            "column": 1,
            "span": "leverage",
        },
        {
            "rule_id": "hedging",
            "severity": "info",
            "message": "Review the hedge.",
            "line": 1,
            "column": 12,
            "span": "perhaps",
        },
    ]
    assessment = build_assessment(
        "Leverage perhaps. Editors revise.",
        findings,
        _metrics(),
        _quality(),
        _style_gap(),
        _profile_statistics(),
    )

    assert assessment["status"] == "scored"
    assert assessment["score"]["total"] == 98
    assert sum(issue["deduction"] for issue in assessment["issues"]) == 2
    assert sum(
        section["deduction"] for section in assessment["score"]["sections"]
    ) == 2
    hedging = next(issue for issue in assessment["issues"] if issue["id"] == "hedging")
    polish = next(
        issue for issue in assessment["issues"] if issue["id"] == "polish_vocab"
    )
    assert polish["priority"] == "medium"
    assert hedging["kind"] == "review_candidate"
    assert hedging["priority"] == "low"
    assert hedging["deduction"] == 0


def test_rule_baseline_scales_profile_rate_and_counts_only_excess() -> None:
    profile_rule_counts = {"em_dash_ban": 2}
    draft_findings = [{"rule_id": "em_dash_ban"}] * 3
    baseline = build_rule_baseline(
        profile_rule_counts,
        profile_word_count=1000,
        draft_findings=draft_findings,
        draft_word_count=600,
    )
    assert baseline == {
        "basis": "profile_reference_corpus",
        "profile_word_count": 1000,
        "draft_word_count": 600,
        "rules": [
            {
                "id": "em_dash_ban",
                "profile_count": 2,
                "profile_rate_per_1000": 2.0,
                "draft_count": 3,
                "allowance": 2,
                "excess": 1,
            }
        ],
    }


def test_rule_baseline_keeps_zero_profile_occurrences_at_zero() -> None:
    baseline = build_rule_baseline(
        {},
        profile_word_count=100,
        draft_findings=[{"rule_id": "polish_vocab"}],
        draft_word_count=10,
    )
    assert baseline["rules"][0]["allowance"] == 0
    assert baseline["rules"][0]["excess"] == 1


def test_rule_baseline_allowance_uses_exact_integer_ceiling() -> None:
    one = build_rule_baseline(
        {"polish_vocab": 1},
        profile_word_count=229,
        draft_findings=[{"rule_id": "polish_vocab"}] * 2,
        draft_word_count=229,
    )
    assert one["rules"][0]["allowance"] == 1
    assert one["rules"][0]["excess"] == 1

    fifteen = build_rule_baseline(
        {"polish_vocab": 15},
        profile_word_count=233,
        draft_findings=[{"rule_id": "polish_vocab"}] * 16,
        draft_word_count=233,
    )
    assert fifteen["rules"][0]["allowance"] == 15
    assert fifteen["rules"][0]["excess"] == 1


def test_rendered_deduction_omits_minus_sign_for_zero() -> None:
    findings = [
        {
            "rule_id": "polish_vocab",
            "severity": "warn",
            "message": "Use specific language.",
            "line": 1,
            "column": 1,
            "span": "leverage",
        },
        {
            "rule_id": "hedging",
            "severity": "info",
            "message": "Review the hedge.",
            "line": 1,
            "column": 12,
            "span": "perhaps",
        },
    ]
    assessment = build_assessment(
        "Leverage perhaps. Editors revise.",
        findings,
        _metrics(),
        _quality(),
        _style_gap(),
        _profile_statistics(),
    )
    rendered = render_assessment("draft.md", assessment)

    assert "- Deduction: -2 points" in rendered
    assert "- Deduction: 0 points" in rendered
    assert "- Deduction: -0 points" not in rendered


def test_assessment_omits_within_baseline_rule_and_penalizes_only_excess() -> None:
    findings = [
        {
            "rule_id": "polish_vocab",
            "severity": "warn",
            "message": "Use specific language.",
            "line": 1,
            "column": 1,
            "span": "leverage",
        },
        {
            "rule_id": "polish_vocab",
            "severity": "warn",
            "message": "Use specific language.",
            "line": 1,
            "column": 10,
            "span": "robust",
        },
    ]
    within = build_rule_baseline(
        {"polish_vocab": 1},
        profile_word_count=10,
        draft_findings=findings[:1],
        draft_word_count=10,
    )
    aligned = build_assessment(
        "Leverage clear prose. Editors revise.",
        findings[:1],
        _metrics(),
        _quality(),
        _style_gap(),
        _profile_statistics(),
        within,
    )
    assert not any(issue["id"] == "polish_vocab" for issue in aligned["issues"])

    excess = build_rule_baseline(
        {"polish_vocab": 1},
        profile_word_count=10,
        draft_findings=findings,
        draft_word_count=10,
    )
    penalized = build_assessment(
        "Leverage robust prose. Editors revise.",
        findings,
        _metrics(),
        _quality(),
        _style_gap(),
        _profile_statistics(),
        excess,
    )
    issue = next(issue for issue in penalized["issues"] if issue["id"] == "polish_vocab")
    assert issue["deduction"] == 2
    assert issue["comparisons"][0]["target"] == 1
    assert issue["comparisons"][0]["delta"] == 1
