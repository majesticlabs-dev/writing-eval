"""Style-rule execution engine."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path
import re

from .style_audit_models import Candidate, Finding, Rule
from .style_audit_rules import load_rules


@lru_cache(maxsize=None)
def _exception_pattern(exception: str) -> re.Pattern[str]:
    # Exceptions match whole words or phrases, case-insensitively, so an
    # exception like "red" cannot suppress a match on "stored".
    return re.compile(
        rf"(?<![\w'\u2019]){re.escape(exception)}(?![\w'\u2019])",
        re.IGNORECASE,
    )


def _is_excepted(rule: Rule, context: str) -> bool:
    return any(
        _exception_pattern(exception).search(context) for exception in rule.exceptions
    )


def _regex_candidates(text: str, pattern: re.Pattern[str]) -> Iterable[Candidate]:
    for match in pattern.finditer(text):
        yield Candidate(match.group(0), match.start(), match.start(), match.end())


def audit_text(text: str, rules: Sequence[Rule]) -> list[Finding]:
    """Apply validated rules to text and return findings in source order."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    newline_offsets = [
        index for index, char in enumerate(text) if char == "\n"
    ]
    findings: list[Finding] = []
    for rule in rules:
        if rule.detector_function is not None:
            candidates = rule.detector_function(text)
        elif rule.compiled_pattern is not None:
            candidates = _regex_candidates(text, rule.compiled_pattern)
        else:
            raise ValueError(f"Rule {rule.id!r} has no usable detector")
        for candidate in candidates:
            context_start = (
                candidate.context_start
                if candidate.context_start is not None
                else candidate.char_offset
            )
            context_end = (
                candidate.context_end
                if candidate.context_end is not None
                else candidate.char_offset + len(candidate.matched_text)
            )
            # Exceptions apply only to the candidate's own context.
            if _is_excepted(rule, text[context_start:context_end]):
                continue
            findings.append(
                Finding(
                    rule.id,
                    rule.severity,
                    rule.message,
                    candidate.matched_text,
                    candidate.char_offset,
                    bisect_right(newline_offsets, candidate.char_offset - 1) + 1,
                )
            )
    return sorted(findings, key=lambda finding: (finding.char_offset, finding.rule_id))


class StyleAuditor:
    """Reusable auditor backed by an immutable sequence of validated rules."""

    def __init__(self, rules: Sequence[Rule]) -> None:
        self.rules = tuple(rules)

    @classmethod
    def from_yaml(cls, path: str | Path) -> StyleAuditor:
        return cls(load_rules(path))

    def audit(self, text: str) -> list[Finding]:
        return audit_text(text, self.rules)
