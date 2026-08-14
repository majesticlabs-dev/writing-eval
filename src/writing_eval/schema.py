"""Shared data structures for writing evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentAssignment:
    """The structured requirements for a writing assignment."""

    purpose: str
    audience: str
    use_case: str
    facts_quotes: list[str]
    outline: list[str]
    target_length: int
    voice_constraints: list[str]
    forbidden_tendencies: list[str]


@dataclass(frozen=True, slots=True)
class EvalRecord:
    """One identified text used as an output or reference record."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class Finding:
    """One style rule match and its source location."""

    rule_id: str
    severity: str
    message: str
    matched_text: str
    char_offset: int
    line_number: int
