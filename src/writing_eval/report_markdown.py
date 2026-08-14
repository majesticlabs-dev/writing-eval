"""Render deterministic Markdown writing-evaluation reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_METRIC_ORDER = (
    "tell_rate",
    "token_1gram_l2",
    "mean_sentence_length",
    "sentence_length_variance",
    "repeated_opening_rate",
)
_METRIC_LABELS = {
    "tell_rate": "Tell rate per 1,000 words",
    "token_1gram_l2": "Token 1-gram L2",
    "mean_sentence_length": "Mean sentence length",
    "sentence_length_variance": "Sentence length variance",
    "repeated_opening_rate": "Repeated opening rate",
}
_QUALITY_SCALAR_ORDER = ("flesch_reading_ease", "flesch_kincaid_grade", "mtld")
_QUALITY_SCALAR_LABELS = {
    "flesch_reading_ease": "Flesch reading ease",
    "flesch_kincaid_grade": "Flesch-Kincaid grade",
    "mtld": "MTLD (lexical diversity)",
}
_QUALITY_PARAGRAPH_ORDER = (
    "paragraph_count",
    "mean_paragraph_sentence_count",
    "single_sentence_paragraph_rate",
)
_QUALITY_PARAGRAPH_LABELS = {
    "paragraph_count": "Paragraphs",
    "mean_paragraph_sentence_count": "Mean sentences per paragraph",
    "single_sentence_paragraph_rate": "Single-sentence paragraph rate",
}


def _systems(report_data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    systems = report_data.get("systems")
    return [report_data] if systems is None else list(systems)


def _quality_value(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.6f}"


def _render_quality_metrics(
    lines: list[str], quality: Mapping[str, Any] | None
) -> None:
    if quality is None:
        return
    lines.extend(
        [
            "",
            "### Quality Metrics (informational)",
            "",
            "These diagnostics are report-only and do not affect the decision gate.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
    )
    for name in _QUALITY_SCALAR_ORDER:
        lines.append(f"| {_QUALITY_SCALAR_LABELS[name]} | {_quality_value(quality.get(name))} |")
    paragraph = quality.get("paragraph_stats")
    for name in _QUALITY_PARAGRAPH_ORDER:
        value = None if paragraph is None else paragraph.get(name)
        lines.append(f"| {_QUALITY_PARAGRAPH_LABELS[name]} | {_quality_value(value)} |")


def render_markdown(report_data: Mapping[str, Any]) -> str:
    """Render report data as deterministic Markdown with ordered metrics."""

    lines = ["# Writing Evaluation Report", ""]
    provenance = report_data.get("provenance")
    if provenance:
        reference = provenance.get("reference_corpus", {})
        rule_set = provenance.get("rule_set", {})
        lines.extend(
            [
                "## Provenance", "", "### Reference Corpus", "",
                f"- Path: {reference.get('path', 'unknown')}",
                f"- Records: {reference.get('record_count', 0)}",
                f"- Words: {reference.get('word_count', 0)}",
                f"- SHA-256: {reference.get('sha256', 'unknown')}", "",
                "### Rule Set", "",
                f"- Path: {rule_set.get('path', 'unknown')}",
                f"- Version: "
                f"{rule_set['version'] if rule_set.get('version') is not None else 'unknown'}",
                f"- Rules: {rule_set.get('rule_count', 0)}",
                f"- SHA-256: {rule_set.get('sha256', 'unknown')}",
                f"- Fingerprint: {rule_set.get('fingerprint', 'unknown')}", "",
            ]
        )
    for system in _systems(report_data):
        lines.extend(
            [
                f"## System: {system['system_name']}", "",
                f"- Documents: {system['document_count']}",
                f"- Words: {system['word_count']}",
                f"- Findings: {system['finding_count']}", "",
                "### Metrics", "", "| Metric | Value |", "| --- | ---: |",
            ]
        )
        metrics = system["metrics"]
        for name in _METRIC_ORDER:
            value = metrics[name]
            rendered = "n/a" if value is None else f"{float(value):.6f}"
            lines.append(f"| {_METRIC_LABELS[name]} | {rendered} |")
        _render_quality_metrics(lines, system.get("quality_metrics"))
        lines.extend(["", "### Tell Rates by Severity", ""])
        tell_rates = system.get("tell_rates_by_severity", {})
        if tell_rates:
            lines.extend(["| Severity | Rate per 1,000 words |", "| --- | ---: |"])
            for severity in sorted(tell_rates):
                lines.append(f"| {severity} | {float(tell_rates[severity]):.6f} |")
        else:
            lines.append("None.")
        lines.extend(["", "### Findings by Severity", ""])
        severity_counts = system.get("findings_by_severity", {})
        if severity_counts:
            for severity in sorted(severity_counts):
                lines.append(f"- {severity}: {severity_counts[severity]}")
        else:
            lines.append("- None")
        lines.extend(["", "### Findings by Rule", ""])
        rule_counts = system.get("findings_by_rule", {})
        if rule_counts:
            for rule_id in sorted(rule_counts):
                lines.append(f"- {rule_id}: {rule_counts[rule_id]}")
        else:
            lines.append("- None")
        lines.extend(["", "### Top Overrepresented Terms", ""])
        terms = system.get("top_overrepresented", [])
        if terms:
            lines.extend(["| Token | Rate Difference |", "| --- | ---: |"])
            for item in terms:
                lines.append(f"| {item['token']} | {float(item['rate_difference']):.6f} |")
        else:
            lines.append("None.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
