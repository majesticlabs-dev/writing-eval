"""Named detectors used by style rules."""

from __future__ import annotations

from collections.abc import Iterable
import re

from .segmentation import (
    LIST_MARKER_RE,
    segment,
    sentence_opener,
    tokenize,
)
from .style_audit_models import Candidate, DetectorFunction


def detect_repeated_openings(text: str) -> Iterable[Candidate]:
    for group in segment(text):
        previous_word = ""
        previous_start = -1
        for span_start, span_end in group:
            opener = sentence_opener(text, span_start, span_end)
            word = text[opener[0] : opener[1]]
            if previous_word and word.casefold() == previous_word.casefold():
                yield Candidate(word, opener[0], previous_start, span_end)
            previous_word = word
            previous_start = span_start


def detect_negative_listing(text: str) -> Iterable[Candidate]:
    for group in segment(text):
        # A sentinel span after the group flushes a run that reaches the end.
        run_first: tuple[int, int] | None = None
        run_last_end = 0
        run_count = 0
        for span_start, span_end in (*group, (len(text), len(text))):
            opener = (
                sentence_opener(text, span_start, span_end)
                if span_end > span_start
                else None
            )
            is_not = (
                opener is not None
                and text[opener[0] : opener[1]].casefold() == "not"
            )
            if is_not:
                if run_count == 0:
                    run_first = (span_start, span_end)
                run_count += 1
                run_last_end = span_end
                continue
            if run_count >= 2:
                assert run_first is not None
                yield Candidate(
                    text[run_first[0] : run_first[1]],
                    run_first[0],
                    run_first[0],
                    run_last_end,
                )
            run_first = None
            run_count = 0


def _is_list_item_span(text: str, span_start: int) -> bool:
    line_start = text.rfind("\n", 0, span_start) + 1
    prefix = text[line_start:span_start]
    return LIST_MARKER_RE.fullmatch(prefix) is not None


def detect_manufactured_staccato(text: str) -> Iterable[Candidate]:
    """Find runs of four short prose sentences, excluding list items."""

    for group in segment(text):
        run: list[tuple[int, int]] = []
        for span_start, span_end in group:
            word_count = len(tokenize(text[span_start:span_end]))
            if 0 < word_count <= 5 and not _is_list_item_span(text, span_start):
                run.append((span_start, span_end))
                continue
            if len(run) >= 4:
                yield Candidate(
                    text[run[0][0] : run[-1][1]], run[0][0], run[0][0], run[-1][1]
                )
            run = []
        if len(run) >= 4:
            yield Candidate(
                text[run[0][0] : run[-1][1]], run[0][0], run[0][0], run[-1][1]
            )


_FRAGMENTED_HEADER_RE = re.compile(
    r"(?m)^#{1,6}[ \t]+[^\n]+\n(?:[ \t]*\n)+"
    r"(?P<warmup>[^\n]+)\n(?:[ \t]*\n)+(?=[^#\s])"
)


def detect_fragmented_header(text: str) -> Iterable[Candidate]:
    """Find a heading followed by a very short standalone warmup paragraph."""

    for match in _FRAGMENTED_HEADER_RE.finditer(text):
        warmup = match.group("warmup").strip()
        if warmup.startswith(("#", "- ", "* ", "+ ")):
            continue
        if 0 < len(tokenize(warmup)) <= 6:
            start = match.start("warmup") + len(match.group("warmup")) - len(
                match.group("warmup").lstrip()
            )
            yield Candidate(warmup, start, start, start + len(warmup))


_CONNECTOR_OPENER_RE = re.compile(
    r"(?:^|[.!?][ \t]+)(?P<connector>furthermore|moreover|additionally)\b",
    re.IGNORECASE | re.MULTILINE,
)


def detect_connector_openers(text: str) -> Iterable[Candidate]:
    """Find formal additive connectors at sentence starts."""

    for match in _CONNECTOR_OPENER_RE.finditer(text):
        connector = match.group("connector")
        start = match.start("connector")
        yield Candidate(connector, start, start, start + len(connector))


_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")
_BOLDFACE_RE = re.compile(r"\*\*[^*\n]+\*\*")


def detect_boldface_density(text: str) -> Iterable[Candidate]:
    """Find paragraphs with dense inline bold emphasis."""

    paragraph_start = 0
    paragraph_bounds = [
        (match.start(), match.end()) for match in _PARAGRAPH_BREAK_RE.finditer(text)
    ]
    paragraph_bounds.append((len(text), len(text)))
    for paragraph_end, next_start in paragraph_bounds:
        paragraph = text[paragraph_start:paragraph_end]
        bold_spans: list[re.Match[str]] = []
        for match in _BOLDFACE_RE.finditer(paragraph):
            line_start = paragraph.rfind("\n", 0, match.start()) + 1
            line_end = paragraph.find("\n", match.end())
            if line_end == -1:
                line_end = len(paragraph)
            if paragraph[line_start:line_end].strip() == match.group(0).strip():
                continue
            bold_spans.append(match)
        if bold_spans:
            total_words = len(tokenize(paragraph))
            bold_words = sum(
                len(tokenize(match.group(0)[2:-2])) for match in bold_spans
            )
            if len(bold_spans) >= 3 or bold_words > total_words * 0.1:
                first = bold_spans[0]
                yield Candidate(
                    first.group(0),
                    paragraph_start + first.start(),
                    paragraph_start,
                    paragraph_end,
                )
        paragraph_start = next_start


NAMED_DETECTORS: dict[str, DetectorFunction] = {
    "repeated_openings": detect_repeated_openings,
    "negative_listing": detect_negative_listing,
    "manufactured_staccato": detect_manufactured_staccato,
    "fragmented_header": detect_fragmented_header,
    "boldface_density": detect_boldface_density,
    "connector_openers": detect_connector_openers,
}
