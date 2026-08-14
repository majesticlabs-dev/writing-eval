"""Shared markdown-aware sentence segmentation for writing evaluation.

The corpora in this project use newlines structurally: headings, list markers,
and blank lines carry meaning. Segmentation is therefore processed line by line.
Hard-wrapping prose mid-sentence across lines splits that sentence by design,
because a line boundary always terminates the current sentence.
"""

from __future__ import annotations

import re

# Keep apostrophe contractions together so ``we'll`` and ``we’ll`` each count
# as one token. The surrounding ``\w+`` keeps the v1 behavior for numbers and
# underscores while allowing apostrophes only between token characters.
_WORD_RE = re.compile(r"\w+(?:['\u2019]\w+)*", flags=re.UNICODE)
_HEADING_RE = re.compile(r"\s*#{1,6} ")
LIST_MARKER_RE = re.compile(r"\s*(?:\d{1,3}[.)]|[-*+])\s+")
_OPENER_RE = re.compile(r"[^\W\d_][\w'-]*", flags=re.UNICODE)
_TERMINATORS = frozenset(".!?")


def tokenize(text: str) -> list[str]:
    r"""Return lowercase word tokens using the shared ``\w+`` pattern."""

    return _WORD_RE.findall((text or "").lower())


def _is_decimal_dot(line: str, index: int) -> bool:
    return (
        line[index] == "."
        and index > 0
        and line[index - 1].isdigit()
        and index + 1 < len(line)
        and line[index + 1].isdigit()
    )


def _line_spans(line: str, content_start: int, line_start: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    length = len(line)
    sentence_start = content_start
    index = content_start
    while index < length:
        if line[index] in _TERMINATORS and not _is_decimal_dot(line, index):
            run_end = index
            while run_end < length and line[run_end] in _TERMINATORS:
                if _is_decimal_dot(line, run_end):
                    break
                run_end += 1
            spans.append((line_start + sentence_start, line_start + run_end))
            index = run_end
            sentence_start = index
            continue
        index += 1
    if sentence_start < length:
        spans.append((line_start + sentence_start, line_start + length))
    return spans


def _finalize_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    raw = text[start:end]
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    trimmed_start = start + leading
    trimmed_end = end - trailing
    if trimmed_start >= trimmed_end:
        return None
    if _OPENER_RE.search(text, trimmed_start, trimmed_end) is None:
        return None
    return (trimmed_start, trimmed_end)


def segment(text: str) -> list[list[tuple[int, int]]]:
    """Return paragraph groups of sentence spans over the original ``text``.

    Each span is a ``(start, end)`` pair whose offsets index into the original
    string. Processing is line by line:

    a. A heading line (optional whitespace, 1-6 ``#``, then a space) yields no
       spans and closes the current paragraph group.
    b. A blank line closes the current paragraph group.
    c. A list-marker prefix (``\\s*(?:\\d{1,3}[.)]|[-*+])\\s+``) is excluded from
       the span so digit markers never become sentences.
    d. Within a line a sentence terminator is a maximal run of ``[.!?]`` except
       a ``.`` flanked by digits (a decimal such as ``3.5``). The end of a line
       always terminates the current sentence.
    e. Span edges are trimmed of whitespace and spans with no letter-led token
       (no match of the opener pattern) are dropped, so mid-line digit markers
       such as ``2.`` never become sentences.

    Hard-wrapping prose mid-sentence across lines splits sentences by design;
    the corpora use newlines structurally.
    """

    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    offset = 0
    for line in text.split("\n"):
        line_start = offset
        offset += len(line) + 1
        if not line.strip():
            if current:
                groups.append(current)
                current = []
            continue
        if _HEADING_RE.match(line):
            if current:
                groups.append(current)
                current = []
            continue
        marker = LIST_MARKER_RE.match(line)
        content_start = marker.end() if marker is not None else 0
        for start, end in _line_spans(line, content_start, line_start):
            finalized = _finalize_span(text, start, end)
            if finalized is not None:
                current.append(finalized)
    if current:
        groups.append(current)
    return groups


def sentence_opener(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Return the ``(start, end)`` span of a sentence's first letter-led word.

    The opener is the first match of ``[^\\W\\d_][\\w'-]*`` inside ``text`` on the
    half-open range ``[start, end)``. Sentences with no letter-led word return
    ``None``.
    """

    match = _OPENER_RE.search(text, start, end)
    if match is None:
        return None
    return (match.start(), match.end())
