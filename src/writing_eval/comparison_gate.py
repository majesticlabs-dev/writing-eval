"""Pre-registered decision-gate analysis and rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import style_audit
from .comparison_shared import format_value
from .metrics import tell_rate, token_1gram_l2, tokenize
from .preservation import compare_record_literals

_LENGTH_MIN_WORDS = 50
_LENGTH_MIN_FRACTION = 0.30


def _length_adequacy_criterion(
    audited_records: Sequence[Mapping[str, Any]],
    audited_texts: Sequence[str],
    eval_reference_word_counts: Mapping[str, int],
) -> dict:
    """Build criterion 5 (length adequacy) over the audited records."""

    below = 0
    shortest_words: int | None = None
    shortest_id: str | None = None
    for record, text in zip(audited_records, audited_texts):
        words = len(tokenize(text))
        record_id = record.get("id")
        ref_words = eval_reference_word_counts.get(record_id) if record_id is not None else None
        required = float(_LENGTH_MIN_WORDS)
        if ref_words is not None:
            required = max(required, _LENGTH_MIN_FRACTION * float(ref_words))
        if words < required:
            below += 1
        if shortest_words is None or words < shortest_words:
            shortest_words = words
            shortest_id = record_id
    return {
        "id": 5,
        "description": (
            "Length adequacy: every audited record has at least "
            f"{_LENGTH_MIN_WORDS} words and at least "
            f"{int(_LENGTH_MIN_FRACTION * 100)} percent of its eval-set "
            "reference word count."
        ),
        "measured": {
            "record_count": len(audited_texts),
            "below_threshold_count": below,
            "min_words": _LENGTH_MIN_WORDS,
            "reference_fraction": _LENGTH_MIN_FRACTION,
            "shortest_id": shortest_id if shortest_id is not None else "n/a",
            "shortest_words": shortest_words if shortest_words is not None else 0,
        },
        "status": "pass" if below == 0 else "fail",
    }


def decision_gate(
    current_records: Sequence[Mapping[str, Any]],
    audited_records: Sequence[Mapping[str, Any]],
    reference_corpus: Sequence[str],
    rules_path: Path,
    l2_noise_floor: float | None,
    *,
    tell_rate_threshold: float,
    eval_reference_word_counts: Mapping[str, int] | None = None,
) -> dict:
    """Apply the pre-registered decision-gate criteria."""

    rules = style_audit.load_rules(rules_path)
    current_texts = [str(record["text"]) for record in current_records]
    audited_texts = [str(record["text"]) for record in audited_records]
    findings_per_text = [style_audit.audit_text(text, rules) for text in audited_texts]
    all_findings = [finding for group in findings_per_text for finding in group]
    warn_findings = [finding for finding in all_findings if finding.severity == "warn"]
    combined_word_count = sum(len(tokenize(text)) for text in audited_texts)
    overall_tell_rate = tell_rate(all_findings, combined_word_count)
    audited_l2 = [token_1gram_l2(text, reference_corpus) for text in audited_texts]
    current_l2 = [token_1gram_l2(text, reference_corpus) for text in current_texts]
    n_null_audited = sum(value is None for value in audited_l2)
    n_null_current = sum(value is None for value in current_l2)
    audited_valid = [value for value in audited_l2 if value is not None]
    current_valid = [value for value in current_l2 if value is not None]
    mean_audited = sum(audited_valid) / len(audited_valid) if audited_valid else None
    mean_current = sum(current_valid) / len(current_valid) if current_valid else None
    l2_delta = (
        mean_audited - mean_current
        if mean_audited is not None and mean_current is not None
        else None
    )
    criterion_1_status = "fail" if warn_findings else "pass"
    # A zero-word audited set is degenerate and must not vacuously pass.
    criterion_2_status = (
        "fail"
        if combined_word_count == 0
        else ("pass" if overall_tell_rate <= tell_rate_threshold else "fail")
    )
    if l2_noise_floor is None:
        criterion_3_status = "blocked"
    elif l2_delta is None:
        criterion_3_status = "fail"
    elif l2_delta <= l2_noise_floor:
        criterion_3_status = "pass"
    else:
        criterion_3_status = "fail"
    if l2_delta is None or l2_noise_floor is None:
        label = "n/a"
    elif abs(l2_delta) <= l2_noise_floor:
        label = "inconclusive"
    else:
        label = "conclusive"
    criteria = [
        {
            "id": 1,
            "description": "Zero warn-severity findings across the audited set.",
            "measured": {"warn_finding_count": len(warn_findings)},
            "status": criterion_1_status,
        },
        {
            "id": 2,
            "description": (
                f"Overall tell rate (all severities) at most {tell_rate_threshold} "
                "findings per 1,000 words over the audited set."
            ),
            "measured": {
                "tell_rate": overall_tell_rate,
                "word_count": combined_word_count,
                "finding_count": len(all_findings),
                "threshold": tell_rate_threshold,
            },
            "status": criterion_2_status,
        },
        {
            "id": 3,
            "description": (
                "Mean per-record token 1-gram L2 of audited minus mean "
                "per-record L2 of current at most the 2.4 noise floor."
            ),
            "measured": {
                "mean_l2_audited": mean_audited,
                "mean_l2_current": mean_current,
                "delta": l2_delta,
                "noise_floor": l2_noise_floor,
            },
            "status": criterion_3_status,
            "label": label,
        },
        {
            "id": 4,
            "description": (
                "No record in either system has a null token 1-gram L2 "
                "(degenerate output)."
            ),
            "measured": {
                "n_null_current": n_null_current,
                "n_null_audited": n_null_audited,
            },
            "status": "fail" if n_null_audited or n_null_current else "pass",
        },
    ]
    if eval_reference_word_counts is not None:
        criteria.append(
            _length_adequacy_criterion(
                audited_records, audited_texts, eval_reference_word_counts
            )
        )
    statuses = {criterion["id"]: criterion["status"] for criterion in criteria}
    # A failing criterion outranks a blocked one: an actually-judged failure
    # must not be masked by missing noise-floor data.
    if any(status == "fail" for status in statuses.values()):
        verdict = "insufficient"
    elif any(status == "blocked" for status in statuses.values()):
        verdict = "blocked"
    else:
        verdict = "sufficient"
    return {
        "criteria": criteria,
        "diagnostics": {
            "literal_preservation": compare_record_literals(
                current_records, audited_records
            )
        },
        "verdict": verdict,
    }


def render_gate_markdown(gate: dict) -> str:
    """Render deterministic Markdown for a decision-gate result."""

    lines = ["# Decision Gate Report", ""]
    for criterion in gate["criteria"]:
        lines.extend(
            [f"## Criterion {criterion['id']}", "", criterion["description"], ""]
        )
        for key in sorted(criterion["measured"]):
            lines.append(f"- {key}: {format_value(criterion['measured'][key])}")
        if "label" in criterion:
            lines.append(f"- label: {criterion['label']}")
        lines.append(f"- status: {criterion['status']}")
        lines.append("")
    preservation = gate.get("diagnostics", {}).get("literal_preservation")
    if preservation is not None:
        lines.extend(
            [
                "## Informational diagnostics", "",
                "Literal preservation compares normalized quoted spans, URLs, dates, "
                "and numbers. It does not affect the registered decision-gate verdict.", "",
                f"- status: {preservation['status']}",
                f"- failed_record_count: {preservation['failed_record_count']}",
                f"- missing_literal_count: {preservation['missing_literal_count']}",
                f"- added_literal_count: {preservation['added_literal_count']}", "",
            ]
        )
    lines.append(f"Verdict: {gate['verdict']}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
