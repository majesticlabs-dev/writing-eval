"""Text rendering for the single-draft check command."""

from __future__ import annotations

from typing import Any

from .assessment import render_assessment


def _format_number(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.6f}"


def _format_signed(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):+.6f}"


def _render_style_gap(lines: list[str], style_gap: dict[str, Any] | None) -> None:
    if style_gap is None:
        return
    lines.append(f"Style gap vs {style_gap['profile']}:")
    for metric in style_gap["metrics"]:
        lines.append(
            f"  {metric['metric']}: draft {_format_number(metric['draft'])} "
            f"profile {_format_number(metric['profile'])} "
            f"delta {_format_signed(metric['delta'])}"
        )
    lines.append(f"  token_1gram_l2: {_format_number(style_gap['token_1gram_l2'])}")
    terms = style_gap["top_overrepresented"]
    if terms:
        lines.append("  top_overrepresented (draft vs profile):")
        for item in terms:
            lines.append(f"    {item['token']}: {float(item['rate_difference']):.6f}")
    else:
        lines.append("  top_overrepresented (draft vs profile): none")


def _render_check_quality(
    lines: list[str], quality: dict[str, Any] | None
) -> None:
    if quality is None:
        return
    lines.append("quality_metrics (informational):")
    lines.append(
        f"  flesch_reading_ease: {_format_number(quality.get('flesch_reading_ease'))}"
    )
    lines.append(
        f"  flesch_kincaid_grade: {_format_number(quality.get('flesch_kincaid_grade'))}"
    )
    lines.append(f"  mtld: {_format_number(quality.get('mtld'))}")
    paragraph = quality.get("paragraph_stats")
    if paragraph is None:
        lines.append("  paragraph_stats: n/a")
    else:
        lines.append("  paragraph_stats:")
        lines.append(
            f"    paragraph_count: {_format_number(paragraph.get('paragraph_count'))}"
        )
        lines.append(
            "    mean_paragraph_sentence_count: "
            f"{_format_number(paragraph.get('mean_paragraph_sentence_count'))}"
        )
        lines.append(
            "    single_sentence_paragraph_rate: "
            f"{_format_number(paragraph.get('single_sentence_paragraph_rate'))}"
        )


def _render_finding_line(display: str, finding: dict[str, Any], label: str) -> str:
    span = finding["span"].replace("\r", "\\r").replace("\n", "\\n")
    return (
        f"{display}:{finding['line']}:{finding['column']} "
        f"[{label}] {finding['rule_id']}: {finding['message']} "
        f"| span: {span}"
    )


def render_check_text(result: dict[str, Any]) -> str:
    assessment = result.get("assessment")
    if assessment is not None:
        return render_assessment(result["file"], assessment)
    display = result["file"]
    lines: list[str] = []
    for finding in result["findings"]:
        lines.append(_render_finding_line(display, finding, finding["severity"]))
    metrics = result["metrics"]
    lines.extend(["metrics:", f"  word_count: {metrics['word_count']}"])
    tell_rates = metrics["tell_rates_by_severity"]
    if tell_rates:
        lines.append("  tell_rates_by_severity:")
        for severity in sorted(tell_rates):
            lines.append(f"    {severity}: {_format_number(tell_rates[severity])}")
    else:
        lines.append("  tell_rates_by_severity: none")
    lines.append(f"  mean_sentence_length: {_format_number(metrics['mean_sentence_length'])}")
    lines.append(
        "  sentence_length_variance: "
        f"{_format_number(metrics['sentence_length_variance'])}"
    )
    lines.append(f"  repeated_opening_rate: {_format_number(metrics['repeated_opening_rate'])}")
    lines.append(f"  token_1gram_l2: {_format_number(metrics['token_1gram_l2'])}")
    _render_check_quality(lines, result.get("quality_metrics"))
    _render_style_gap(lines, result.get("style_gap"))
    return "\n".join(lines) + "\n"
