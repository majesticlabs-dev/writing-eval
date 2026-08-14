"""Validated style-rule and finding data types."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
import re

VALID_SEVERITIES = frozenset({"warn", "info"})


@dataclass(frozen=True, slots=True)
class Finding:
    """A single style rule match."""

    rule_id: str
    severity: str
    message: str
    matched_text: str
    char_offset: int
    line_number: int


@dataclass(frozen=True, slots=True)
class Candidate:
    matched_text: str
    char_offset: int
    context_start: int | None = None
    context_end: int | None = None


DetectorFunction = Callable[[str], Iterable[Candidate]]


@dataclass(frozen=True, slots=True)
class Rule:
    """A validated style rule."""

    id: str
    severity: str
    detector: str
    message: str
    exceptions: tuple[str, ...] = ()
    compiled_pattern: re.Pattern[str] | None = field(
        default=None, repr=False, compare=False
    )
    detector_function: DetectorFunction | None = field(
        default=None, repr=False, compare=False
    )
