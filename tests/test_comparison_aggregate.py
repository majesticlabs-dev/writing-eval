"""Cross-run aggregation and noise-floor tests."""

from __future__ import annotations

import math
import pytest

from writing_eval.comparison import aggregate_runs, noise_floor, render_noise_floor_markdown
from tests.helpers_comparison import base_metrics, make_report, make_system

def test_aggregate_runs_computes_exact_stats_across_three_runs() -> None:
    runs = [
        make_report([make_system("sys-a", base_metrics(tell_rate=value))])
        for value in (1.0, 2.0, 3.0)
    ]
    aggregate = aggregate_runs(runs)
    assert aggregate["n_runs"] == 3
    stats = aggregate["systems"]["sys-a"]["tell_rate"]
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0
    assert stats["mean"] == 2.0
    assert stats["spread"] == 2.0
    assert stats["n_runs"] == 3
    assert stats["n_null"] == 0
    assert stats["stddev"] == pytest.approx(math.sqrt(2.0 / 3.0))


def test_aggregate_runs_raises_on_inconsistent_systems() -> None:
    run1 = make_report([make_system("sys-a", base_metrics())])
    run2 = make_report([make_system("sys-b", base_metrics())])
    with pytest.raises(ValueError):
        aggregate_runs([run1, run2])


def test_aggregate_runs_raises_on_inconsistent_metric_keys() -> None:
    run1 = make_report([make_system("sys-a", base_metrics())])
    incomplete_metrics = base_metrics()
    del incomplete_metrics["repeated_opening_rate"]
    run2 = make_report([make_system("sys-a", incomplete_metrics)])
    with pytest.raises(ValueError):
        aggregate_runs([run1, run2])


def test_aggregate_runs_raises_with_fewer_than_two_runs() -> None:
    run1 = make_report([make_system("sys-a", base_metrics())])
    with pytest.raises(ValueError):
        aggregate_runs([run1])


def test_aggregate_runs_excludes_null_l2_but_counts_it() -> None:
    values = [0.1, None, 0.3]
    runs = [
        make_report([make_system("sys-a", base_metrics(token_1gram_l2=value))])
        for value in values
    ]
    aggregate = aggregate_runs(runs)
    l2_stats = aggregate["systems"]["sys-a"]["token_1gram_l2"]
    assert l2_stats["n_runs"] == 2
    assert l2_stats["n_null"] == 1
    assert l2_stats["min"] == pytest.approx(0.1)
    assert l2_stats["max"] == pytest.approx(0.3)
    assert l2_stats["mean"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# noise_floor
# ---------------------------------------------------------------------------


def test_noise_floor_bound_only_flag_depends_on_run_count() -> None:
    runs_3 = [
        make_report([make_system("sys-a", base_metrics(tell_rate=value))])
        for value in (1.0, 2.0, 3.0)
    ]
    floor_3 = noise_floor(aggregate_runs(runs_3))
    assert floor_3["tell_rate"]["bound_only"] is True
    assert floor_3["tell_rate"]["n_runs_min"] == 3

    runs_5 = [
        make_report([make_system("sys-a", base_metrics(tell_rate=value))])
        for value in (1.0, 2.0, 3.0, 4.0, 5.0)
    ]
    floor_5 = noise_floor(aggregate_runs(runs_5))
    assert floor_5["tell_rate"]["bound_only"] is False
    assert floor_5["tell_rate"]["n_runs_min"] == 5


def test_noise_floor_is_max_spread_across_systems() -> None:
    tell_a_values = (1.0, 2.0, 5.0, 5.0, 5.0)
    tell_b_values = (1.0, 1.5, 2.0, 2.0, 2.0)
    runs = [
        make_report(
            [
                make_system("sys-a", base_metrics(tell_rate=tell_a)),
                make_system("sys-b", base_metrics(tell_rate=tell_b)),
            ]
        )
        for tell_a, tell_b in zip(tell_a_values, tell_b_values)
    ]
    aggregate = aggregate_runs(runs)
    floor = noise_floor(aggregate)
    assert floor["tell_rate"]["floor"] == pytest.approx(4.0)
    assert floor["tell_rate"]["system"] == "sys-a"
    assert floor["tell_rate"]["bound_only"] is False


def test_noise_floor_markdown_labels_bound_only_and_states_inconclusive_rule() -> None:
    runs = [
        make_report([make_system("sys-a", base_metrics(tell_rate=value))])
        for value in (1.0, 2.0, 3.0)
    ]
    aggregate = aggregate_runs(runs)
    floor = noise_floor(aggregate)
    markdown = render_noise_floor_markdown(aggregate, floor)
    assert "BOUND ONLY (runs < 5)" in markdown
    assert "inconclusive" in markdown.lower()
    assert chr(0x2014) not in markdown
    assert chr(0x2013) not in markdown


def test_noise_floor_markdown_is_deterministic() -> None:
    runs = [
        make_report([make_system("sys-a", base_metrics(tell_rate=value))])
        for value in (1.0, 2.0, 3.0, 4.0, 5.0)
    ]
    aggregate = aggregate_runs(runs)
    floor = noise_floor(aggregate)
    first = render_noise_floor_markdown(aggregate, floor)
    second = render_noise_floor_markdown(aggregate, floor)
    assert first == second
    assert "BOUND ONLY" not in first
