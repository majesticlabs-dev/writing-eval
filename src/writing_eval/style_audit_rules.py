"""Merged-rule validation for style rules."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
from pathlib import Path
import re
from typing import Any

from .style_audit_detectors import NAMED_DETECTORS
from .style_audit_models import Rule, VALID_SEVERITIES
from .style_audit_overlay import resolve_raw_rules

_REQUIRED_FIELDS = ("id", "severity", "detector", "message")
_ALLOWED_FIELDS = (*_REQUIRED_FIELDS, "exceptions")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _rule_label(raw_rule: Any, index: int) -> str:
    """Name a rule by id when possible; merged indices mean little to authors."""

    if isinstance(raw_rule, dict):
        rule_id = raw_rule.get("id")
        if isinstance(rule_id, str) and rule_id.strip():
            return f"Rule {rule_id!r}"
    return f"Rule at index {index}"


def _require_nonempty_string(value: Any, field_name: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} has invalid {field_name!r}; expected a nonempty string")
    return value


def _parse_rule(raw_rule: Any, index: int) -> Rule:
    label = _rule_label(raw_rule, index)
    if not isinstance(raw_rule, dict):
        raise ValueError(f"{label} must be a mapping")
    missing = [field for field in _REQUIRED_FIELDS if field not in raw_rule]
    if missing:
        raise ValueError(f"{label} is missing required field(s): {', '.join(missing)}")
    unknown = [key for key in raw_rule if key not in _ALLOWED_FIELDS]
    if unknown:
        allowed = ", ".join(_ALLOWED_FIELDS)
        raise ValueError(
            f"{label} has unsupported field(s): "
            f"{', '.join(str(key) for key in unknown)}; "
            f"allowed fields are: {allowed}"
        )
    rule_id = _require_nonempty_string(raw_rule["id"], "id", label)
    severity = _require_nonempty_string(raw_rule["severity"], "severity", label)
    detector = _require_nonempty_string(raw_rule["detector"], "detector", label)
    message = _require_nonempty_string(raw_rule["message"], "message", label)
    if severity not in VALID_SEVERITIES:
        allowed = ", ".join(sorted(VALID_SEVERITIES))
        raise ValueError(
            f"{label} has invalid severity {severity!r}; expected one of: {allowed}"
        )
    raw_exceptions = raw_rule.get("exceptions", [])
    if not isinstance(raw_exceptions, list) or not all(
        isinstance(exception, str) for exception in raw_exceptions
    ):
        raise ValueError(f"{label} exceptions must be a list of strings")
    if any(not exception.strip() for exception in raw_exceptions):
        raise ValueError(f"{label} exceptions must not contain empty strings")
    detector_function = NAMED_DETECTORS.get(detector)
    compiled_pattern: re.Pattern[str] | None = None
    if detector_function is None:
        if _IDENTIFIER_RE.fullmatch(detector):
            raise ValueError(
                f"{label} references unknown named detector {detector!r}; "
                "write an explicit regex detector (for example (?i)\\bword\\b)"
            )
        try:
            compiled_pattern = re.compile(detector)
        except re.error as error:
            raise ValueError(f"{label} has invalid regex detector: {error}") from error
    return Rule(
        id=rule_id,
        severity=severity,
        detector=detector,
        message=message,
        exceptions=tuple(raw_exceptions),
        compiled_pattern=compiled_pattern,
        detector_function=detector_function,
    )


def load_rules(path: str | Path) -> list[Rule]:
    """Load a rule file, merge any `extends` overlay chain, and validate."""

    raw_rules = resolve_raw_rules(path)
    rules = [_parse_rule(raw_rule, index) for index, raw_rule in enumerate(raw_rules)]
    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            raise ValueError(f"Duplicate rule id: {rule.id!r}")
        seen.add(rule.id)
    return rules


def rules_fingerprint(rules: Sequence[Rule]) -> str:
    """Return a stable sha256 digest of the effective rule content and order."""

    digest = hashlib.sha256()
    for rule in rules:
        digest.update(
            f"{rule.id}\0{rule.severity}\0{rule.detector}\0{rule.message}\0".encode("utf-8")
        )
        digest.update("\x01".join(rule.exceptions).encode("utf-8"))
        digest.update(b"\x02")
    return digest.hexdigest()
