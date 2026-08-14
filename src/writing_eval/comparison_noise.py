"""Cross-run aggregation and conservative noise-floor reports."""

from __future__ import annotations

from collections.abc import Mapping
import statistics
from typing import Any

from .comparison_shared import format_value, system_map


def _summarize(values: list[float], n_null: int) -> dict[str, Any]:
    n_runs = len(values)
    if n_runs == 0:
        return {
            "min": None, "max": None, "mean": None, "stddev": None,
            "spread": None, "n_runs": 0, "n_null": n_null,
        }
    minimum = min(values)
    maximum = max(values)
    return {
        "min": minimum,
        "max": maximum,
        "mean": sum(values) / n_runs,
        "stddev": statistics.pstdev(values),
        "spread": maximum - minimum,
        "n_runs": n_runs,
        "n_null": n_null,
    }


def aggregate_runs(run_reports: list[dict]) -> dict:
    """Aggregate scalar corpus-level metrics across repeat runs."""

    if len(run_reports) < 2:
        raise ValueError("aggregate_runs requires at least 2 runs")
    run_system_maps = [system_map(report) for report in run_reports]
    reference_names = sorted(run_system_maps[0])
    for run_index, systems in enumerate(run_system_maps[1:], start=2):
        if sorted(systems) != reference_names:
            raise ValueError(
                "inconsistent system names across runs: "
                f"run 1 has {reference_names}, run {run_index} has {sorted(systems)}"
            )
    reference_metric_keys: list[str] | None = None
    for system_name in reference_names:
        for run_index, systems in enumerate(run_system_maps, start=1):
            metrics = systems[system_name].get("metrics")
            if not isinstance(metrics, Mapping):
                raise ValueError(
                    f"system {system_name!r} in run {run_index} is missing a "
                    "'metrics' mapping"
                )
            metric_keys = sorted(metrics)
            if reference_metric_keys is None:
                reference_metric_keys = metric_keys
            elif metric_keys != reference_metric_keys:
                raise ValueError(
                    "inconsistent metric keys across runs: "
                    f"expected {reference_metric_keys}, system {system_name!r} "
                    f"in run {run_index} has {metric_keys}"
                )
    assert reference_metric_keys is not None
    systems_out: dict[str, dict[str, dict[str, Any]]] = {}
    for system_name in reference_names:
        metrics_out: dict[str, dict[str, Any]] = {}
        for metric_name in reference_metric_keys:
            values: list[float] = []
            n_null = 0
            for systems in run_system_maps:
                value = systems[system_name]["metrics"][metric_name]
                if value is None:
                    n_null += 1
                elif isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(
                        f"metric {metric_name!r} for system {system_name!r} is "
                        "not scalar numeric"
                    )
                else:
                    values.append(float(value))
            metrics_out[metric_name] = _summarize(values, n_null)
        systems_out[system_name] = metrics_out
    return {"n_runs": len(run_reports), "systems": systems_out}


def noise_floor(aggregate: dict) -> dict:
    """Compute a conservative per-metric noise floor."""

    systems = aggregate.get("systems", {})
    metric_names = {
        metric for system_metrics in systems.values() for metric in system_metrics
    }
    floor: dict[str, dict[str, Any]] = {}
    for metric_name in sorted(metric_names):
        best_spread: float | None = None
        best_system: str | None = None
        n_runs_values: list[int] = []
        for system_name in sorted(systems):
            stats = systems[system_name].get(metric_name)
            if stats is None:
                continue
            n_runs_values.append(stats["n_runs"])
            spread = stats["spread"]
            if spread is not None and (best_spread is None or spread > best_spread):
                best_spread = spread
                best_system = system_name
        n_runs_min = min(n_runs_values) if n_runs_values else 0
        floor[metric_name] = {
            "floor": best_spread,
            "system": best_system,
            "n_runs_min": n_runs_min,
            "bound_only": n_runs_min < 5,
        }
    return floor


def render_noise_floor_markdown(aggregate: dict, floor: dict) -> str:
    """Render deterministic Markdown for a noise-floor report."""

    bound_only = any(entry.get("bound_only") for entry in floor.values())
    lines = ["# Noise Floor Report", ""]
    if bound_only:
        lines.extend(["BOUND ONLY (runs < 5)", ""])
    lines.extend(
        [
            f"Runs aggregated: {aggregate.get('n_runs', 0)}", "",
            "Deltas at or below a metric's noise floor are inconclusive and "
            "must not be read as evidence of improvement or regression.", "",
            "## Per-System Spread", "",
        ]
    )
    systems = aggregate.get("systems", {})
    for system_name in sorted(systems):
        lines.extend(
            [
                f"### System: {system_name}", "",
                "| Metric | Min | Max | Mean | Stddev | Spread | N Runs | N Null |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for metric_name in sorted(systems[system_name]):
            stats = systems[system_name][metric_name]
            lines.append(
                f"| {metric_name} | {format_value(stats['min'])} | "
                f"{format_value(stats['max'])} | {format_value(stats['mean'])} | "
                f"{format_value(stats['stddev'])} | {format_value(stats['spread'])} | "
                f"{stats['n_runs']} | {stats['n_null']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Noise Floor", "",
            "| Metric | Floor | System | N Runs Min | Bound Only |",
            "| --- | ---: | --- | ---: | --- |",
        ]
    )
    for metric_name in sorted(floor):
        entry = floor[metric_name]
        system_label = entry["system"] if entry["system"] is not None else "n/a"
        bound_label = "yes" if entry["bound_only"] else "no"
        lines.append(
            f"| {metric_name} | {format_value(entry['floor'])} | {system_label} | "
            f"{entry['n_runs_min']} | {bound_label} |"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
