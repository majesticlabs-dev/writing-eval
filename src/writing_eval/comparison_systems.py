"""Two-system comparison data and Markdown."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from .comparison_shared import format_value, system_map


def _finite_number(value: Any, what: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{what} is not a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{what} is not a finite number")
    return number


def compare_systems(
    report_a: Mapping[str, Any],
    report_b: Mapping[str, Any] | None,
    floor: Mapping[str, Any] | None,
    system_a: str,
    system_b: str,
) -> dict:
    """Compare two named systems drawn from one or two reports."""

    systems_a = system_map(report_a)
    systems_b = system_map(report_b) if report_b is not None else systems_a
    if system_a not in systems_a:
        raise ValueError(f"system {system_a!r} not found in report_a")
    if system_b not in systems_b:
        raise ValueError(f"system {system_b!r} not found in report_b")
    entry_a = systems_a[system_a]
    entry_b = systems_b[system_b]
    metrics_a = entry_a.get("metrics", {})
    metrics_b = entry_b.get("metrics", {})
    metrics_out: dict[str, dict[str, Any]] = {}
    for metric_name in sorted(set(metrics_a) | set(metrics_b)):
        value_a = metrics_a.get(metric_name)
        value_b = metrics_b.get(metric_name)
        if value_a is None or value_b is None:
            delta = None
            verdict = "undefined"
        else:
            number_a = _finite_number(value_a, f"metric {metric_name!r} value_a")
            number_b = _finite_number(value_b, f"metric {metric_name!r} value_b")
            delta = number_b - number_a
            metric_floor = floor.get(metric_name) if floor else None
            floor_value = metric_floor.get("floor") if metric_floor else None
            if floor is None or metric_floor is None or floor_value is None:
                verdict = "no_floor"
            else:
                floor_number = _finite_number(
                    floor_value, f"metric {metric_name!r} floor"
                )
                if abs(delta) <= floor_number:
                    verdict = "inconclusive_below_noise_floor"
                else:
                    verdict = "actionable"
        metrics_out[metric_name] = {
            "value_a": value_a,
            "value_b": value_b,
            "delta": delta,
            "verdict": verdict,
        }
    severity_a = entry_a.get("findings_by_severity", {})
    severity_b = entry_b.get("findings_by_severity", {})
    return {
        "system_a": system_a,
        "system_b": system_b,
        "metrics": metrics_out,
        "word_count_a": entry_a.get("word_count"),
        "word_count_b": entry_b.get("word_count"),
        "warn_findings_a": severity_a.get("warn", 0),
        "warn_findings_b": severity_b.get("warn", 0),
        "soft_findings_a": severity_a.get("info", 0),
        "soft_findings_b": severity_b.get("info", 0),
    }


def render_comparison_markdown(comparison: dict) -> str:
    """Render deterministic Markdown for a two-system comparison."""

    lines = [
        "# System Comparison Report", "",
        f"System A: {comparison['system_a']}",
        f"System B: {comparison['system_b']}", "",
        f"- Words A: {comparison.get('word_count_a')}",
        f"- Words B: {comparison.get('word_count_b')}",
        f"- Warn findings A: {comparison.get('warn_findings_a')}",
        f"- Warn findings B: {comparison.get('warn_findings_b')}",
        f"- Info findings A: {comparison.get('soft_findings_a')}",
        f"- Info findings B: {comparison.get('soft_findings_b')}", "",
        "## Metric Deltas", "",
        "| Metric | Value A | Value B | Delta | Verdict |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for metric_name in sorted(comparison["metrics"]):
        entry = comparison["metrics"][metric_name]
        lines.append(
            f"| {metric_name} | {format_value(entry['value_a'])} | "
            f"{format_value(entry['value_b'])} | {format_value(entry['delta'])} | "
            f"{entry['verdict']} |"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
