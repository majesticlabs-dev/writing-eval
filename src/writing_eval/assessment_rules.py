"""Profile-relative style-rule baselines and issues."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .assessment_core import (
    CLARITY_RULES,
    SEVERITY_DEDUCTION,
    SEVERITY_PRIORITY,
)


def build_rule_baseline(
    profile_rule_counts: Mapping[str, int],
    profile_word_count: int,
    draft_findings: list[dict[str, Any]],
    draft_word_count: int,
) -> dict[str, Any]:
    """Return profile-relative occurrence allowances for style rules."""

    if profile_word_count <= 0:
        raise ValueError("profile_word_count must be greater than zero")
    if draft_word_count < 0:
        raise ValueError("draft_word_count must not be negative")

    draft_counts = Counter(finding["rule_id"] for finding in draft_findings)
    entries: list[dict[str, Any]] = []
    for current_rule_id in sorted(set(profile_rule_counts) | draft_counts.keys()):
        profile_count = profile_rule_counts.get(current_rule_id, 0)
        profile_rate = profile_count * 1000.0 / profile_word_count
        # Integer ceiling keeps the allowance exact; a float round-trip of the
        # rate can round an exact count up by one and hide a real excess.
        allowance = (
            -(-profile_count * draft_word_count // profile_word_count)
            if profile_count
            else 0
        )
        draft_count = draft_counts[current_rule_id]
        entries.append(
            {
                "id": current_rule_id,
                "profile_count": profile_count,
                "profile_rate_per_1000": profile_rate,
                "draft_count": draft_count,
                "allowance": allowance,
                "excess": max(0, draft_count - allowance),
            }
        )
    return {
        "basis": "profile_reference_corpus",
        "profile_word_count": profile_word_count,
        "draft_word_count": draft_word_count,
        "rules": entries,
    }


def rule_issues(
    findings: list[dict[str, Any]],
    rule_baseline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        if finding["rule_id"] != "repeated_openings":
            grouped[finding["rule_id"]].append(finding)
    baseline_by_id = {
        str(entry["id"]): entry for entry in (rule_baseline or {}).get("rules", [])
    }
    issues: list[dict[str, Any]] = []
    for rule_id in sorted(grouped):
        matches = sorted(
            grouped[rule_id],
            key=lambda item: (item["line"], item["column"], item["span"]),
        )
        first = matches[0]
        severity = first["severity"]
        count = len(matches)
        baseline = baseline_by_id.get(rule_id)
        excess = int(baseline["excess"]) if baseline is not None else count
        if baseline is not None and excess == 0:
            continue
        label = rule_id.replace("_", " ")
        section = "clarity_directness" if rule_id in CLARITY_RULES else "vocabulary_style"
        requested = SEVERITY_DEDUCTION.get(severity, 0) * excess
        if baseline is None:
            summary = f"{label.capitalize()} appears {count} time{'' if count == 1 else 's'}."
            target = 0
            success = f"Reduce {label} occurrences from {count} toward 0."
        else:
            allowance = int(baseline["allowance"])
            summary = (
                f"{label.capitalize()} appears {count} time"
                f"{'' if count == 1 else 's'}, {excess} above the profile allowance."
            )
            target = allowance
            success = (
                f"Reduce {label} occurrences from {count} to the profile allowance "
                f"of {allowance}."
            )
        issues.append(
            {
                "id": rule_id,
                "kind": "review_candidate" if severity == "info" else "improvement",
                "section": section,
                "priority": SEVERITY_PRIORITY.get(severity, "low"),
                "deduction": 0,
                "summary": summary,
                "comparisons": [
                    {
                        "metric": f"{rule_id}_occurrences",
                        "label": f"{label.capitalize()} occurrences",
                        "current": count,
                        "target": target,
                        "delta": excess,
                        "direction": "decrease",
                        "unit": "occurrences",
                    }
                ],
                "instruction": first["message"],
                "success_criteria": [success],
                "locations": [
                    {"line": item["line"], "column": item["column"], "span": item["span"]}
                    for item in matches
                ],
                "_requested_deduction": requested,
                "_profile_issue": False,
            }
        )
    return issues
