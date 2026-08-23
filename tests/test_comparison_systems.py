"""Two-system comparison tests."""

from __future__ import annotations

import math

import pytest

from writing_eval.comparison import compare_systems, render_comparison_markdown
from tests.helpers_comparison import base_metrics, make_report, make_system

def test_compare_systems_verdict_boundaries() -> None:
    report_a = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=3.0)),
        ]
    )

    floor_equal = {
        "tell_rate": {"floor": 2.0, "system": "sys-a", "n_runs_min": 5, "bound_only": False}
    }
    comparison_equal = compare_systems(report_a, None, floor_equal, "sys-a", "sys-b")
    assert comparison_equal["metrics"]["tell_rate"]["delta"] == pytest.approx(2.0)
    assert (
        comparison_equal["metrics"]["tell_rate"]["verdict"]
        == "inconclusive_below_noise_floor"
    )

    floor_smaller = {
        "tell_rate": {"floor": 1.9, "system": "sys-a", "n_runs_min": 5, "bound_only": False}
    }
    comparison_actionable = compare_systems(report_a, None, floor_smaller, "sys-a", "sys-b")
    assert comparison_actionable["metrics"]["tell_rate"]["verdict"] == "actionable"


def test_compare_systems_no_floor_verdict() -> None:
    report_a = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=3.0)),
        ]
    )
    comparison = compare_systems(report_a, None, None, "sys-a", "sys-b")
    assert comparison["metrics"]["tell_rate"]["verdict"] == "no_floor"


def test_compare_systems_word_counts_and_finding_totals_included() -> None:
    report_a = make_report(
        [
            make_system(
                "sys-a",
                base_metrics(),
                findings_by_severity={"warn": 2, "info": 1},
                word_count=50,
            ),
            make_system(
                "sys-b",
                base_metrics(),
                findings_by_severity={"warn": 1, "info": 3},
                word_count=75,
            ),
        ]
    )
    comparison = compare_systems(report_a, None, None, "sys-a", "sys-b")
    assert comparison["word_count_a"] == 50
    assert comparison["word_count_b"] == 75
    assert comparison["warn_findings_a"] == 2
    assert comparison["warn_findings_b"] == 1
    assert comparison["soft_findings_a"] == 1
    assert comparison["soft_findings_b"] == 3
    markdown = render_comparison_markdown(comparison)
    assert "- Warn findings A: 2" in markdown
    assert "- Warn findings B: 1" in markdown
    assert "- Info findings A: 1" in markdown
    assert "- Info findings B: 3" in markdown


def test_comparison_markdown_is_deterministic() -> None:
    report_a = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=3.0)),
        ]
    )
    comparison = compare_systems(report_a, None, None, "sys-a", "sys-b")
    first = render_comparison_markdown(comparison)
    second = render_comparison_markdown(comparison)
    assert first == second
    assert chr(0x2014) not in first
    assert chr(0x2013) not in first


def test_compare_systems_rejects_nonfinite_metric_values() -> None:
    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=math.nan)),
            make_system("sys-b", base_metrics(tell_rate=1.0)),
        ]
    )
    with pytest.raises(ValueError, match="metric 'tell_rate' value_a is not a finite number"):
        compare_systems(report, None, None, "sys-a", "sys-b")

    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=math.inf)),
        ]
    )
    with pytest.raises(ValueError, match="metric 'tell_rate' value_b is not a finite number"):
        compare_systems(report, None, None, "sys-a", "sys-b")


def test_compare_systems_rejects_nonfinite_floor() -> None:
    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=3.0)),
        ]
    )
    floor = {
        "tell_rate": {
            "floor": math.nan,
            "system": "sys-a",
            "n_runs_min": 5,
            "bound_only": False,
        }
    }
    with pytest.raises(ValueError, match="metric 'tell_rate' floor is not a finite number"):
        compare_systems(report, None, floor, "sys-a", "sys-b")


def test_compare_systems_rejects_boolean_metric_values() -> None:
    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=True)),
            make_system("sys-b", base_metrics(tell_rate=1.0)),
        ]
    )
    with pytest.raises(ValueError, match="metric 'tell_rate' value_a is not a finite number"):
        compare_systems(report, None, None, "sys-a", "sys-b")

    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=False)),
        ]
    )
    with pytest.raises(ValueError, match="metric 'tell_rate' value_b is not a finite number"):
        compare_systems(report, None, None, "sys-a", "sys-b")


def test_compare_systems_rejects_boolean_floor() -> None:
    report = make_report(
        [
            make_system("sys-a", base_metrics(tell_rate=1.0)),
            make_system("sys-b", base_metrics(tell_rate=3.0)),
        ]
    )
    floor = {
        "tell_rate": {
            "floor": True,
            "system": "sys-a",
            "n_runs_min": 5,
            "bound_only": False,
        }
    }
    with pytest.raises(ValueError, match="metric 'tell_rate' floor is not a finite number"):
        compare_systems(report, None, floor, "sys-a", "sys-b")

