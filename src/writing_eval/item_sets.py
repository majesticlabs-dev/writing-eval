"""Deterministic structural observations about Markdown lists and record leads."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Any

from .segmentation import LIST_MARKER_RE, tokenize

MIN_SET_ITEMS = 3
LEAD_WORDS = 2
LABEL_MAX_WORDS = 4
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^[ \t]*#{1,6} ")
_LABEL_RE = re.compile(r"^(?:\*\*[^*\n]+\*\*|__[^_\n]+__)")
_COLON_RE = re.compile(r":(?=\s+\S)")
_TASK_RE = re.compile(r"\[[ xX]\]\s+")
_UNIT_RE = re.compile(r"\S+")
_URL_RE = re.compile(r"(?:https?://|www\.)", flags=re.IGNORECASE)
_UNIT_LEADING = "*_`\"'([{"
_UNIT_TRAILING = "*_`\"')]}.,!?;:"


def _lead_units(text: str, start: int, end: int) -> tuple[tuple[int, int], ...]:
    units = []
    for match in _UNIT_RE.finditer(text, start, end):
        raw = match.group()
        left = match.start() + len(raw) - len(raw.lstrip(_UNIT_LEADING))
        right = match.end() - (len(raw) - len(raw.rstrip(_UNIT_TRAILING)))
        if left < right and tokenize(text[left:right]):
            units.append((left, right))
    return tuple(units)


@dataclass(frozen=True)
class Item:
    """One item's source/prose bounds and first-line lead offsets."""

    start: int
    end: int
    prose_end: int
    first_line_end: int
    words: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ItemSet:
    """A set of sibling list items in source order."""

    marker: str
    items: tuple[Item, ...]


def find_item_sets(text: str) -> list[ItemSet]:
    """Find sibling list sets, including loose and nested Markdown lists."""

    results: list[ItemSet] = []
    stack: list[tuple[int, str, list[Item]]] = []
    fence: tuple[str, int] | None = None
    blank = False
    offset = 0

    def close() -> None:
        _, marker, items = stack.pop()
        if len(items) >= MIN_SET_ITEMS:
            results.append(ItemSet(marker, tuple(items)))

    def extend(end: int, *, prose: bool) -> None:
        items = stack[-1][2]
        item = items[-1]
        items[-1] = Item(
            item.start, end, end if prose else item.prose_end,
            item.first_line_end, item.words,
        )

    for line in text.split("\n"):
        start = offset
        offset += len(line) + 1
        indent = len(line) - len(line.lstrip(" \t"))
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            if stack:
                extend(start + len(line.rstrip()), prose=False)
            if (fence_match is not None
                    and fence_match[1][0] == fence[0]
                    and len(fence_match[1]) >= fence[1]
                    and not fence_match[2].strip()):
                fence = None
                blank = True
            continue
        if fence_match is not None:
            while stack and stack[-1][0] >= indent:
                close()
            if stack:
                extend(start + len(line.rstrip()), prose=False)
            fence = (fence_match[1][0], len(fence_match[1]))
            blank = False
            continue
        if not line.strip():
            blank = True
            continue
        marker = LIST_MARKER_RE.match(line)
        if marker is not None:
            while stack and stack[-1][0] > indent:
                close()
            kind = "ordered" if line.lstrip()[0].isdigit() else "bullet"
            if stack and stack[-1][0] == indent and stack[-1][1] != kind:
                close()
            content_start = marker.end()
            task = _TASK_RE.match(line, content_start)
            if task is not None:
                content_start = task.end()
            line_end = start + len(line.rstrip())
            words = _lead_units(text, start + content_start, line_end)
            if words:
                if not stack or stack[-1][0] != indent:
                    stack.append((indent, kind, []))
                stack[-1][2].append(Item(
                    start + content_start, line_end, line_end, line_end, words,
                ))
            blank = False
            continue
        if _HEADING_RE.match(line):
            while stack:
                close()
        else:
            if blank:
                while stack and indent <= stack[-1][0]:
                    close()
            else:
                while len(stack) > 1 and indent <= stack[-1][0]:
                    close()
            if stack:
                extend(start + len(line.rstrip()), prose=True)
        blank = False
    while stack:
        close()
    return sorted(results, key=lambda group: group.items[0].start)


def _lead_key(text: str, item: Item) -> tuple[str, ...]:
    return tuple(text[start:end].lower() for start, end in item.words[:LEAD_WORDS])


def shared_lead_span(text: str, item_set: ItemSet) -> tuple[int, int] | None:
    """Return a source span for shared prose lead units, not URLs or code."""

    for item in item_set.items:
        first_unit = text[item.words[0][0]:item.words[0][1]]
        if text[item.start:item.first_line_end].startswith("`") or _URL_RE.match(first_unit):
            return None
    first = item_set.items[0]
    key = _lead_key(text, first)
    if len(key) < LEAD_WORDS or any(
        _lead_key(text, item) != key for item in item_set.items[1:]
    ):
        return None
    count = min(len(item.words) for item in item_set.items)
    shared = LEAD_WORDS
    while shared < count:
        start, end = first.words[shared]
        word = text[start:end].lower()
        if any(text[item.words[shared][0]:item.words[shared][1]].lower() != word
               for item in item_set.items[1:]):
            break
        shared += 1
    return first.words[0][0], first.words[shared - 1][1]


def _form(text: str, item: Item) -> tuple[bool, bool, bool]:
    first_line = text[item.start:item.first_line_end]
    colon = _COLON_RE.search(first_line)
    bold_label = _LABEL_RE.match(first_line) is not None
    colon_label = (
        colon is not None and 0 < len(tokenize(first_line[:colon.start()])) <= LABEL_MAX_WORDS
    )
    content = text[item.start:item.prose_end].rstrip(" *_`)'\"\u2019\u201d")
    return bold_label, colon_label, content.endswith((".", "!", "?"))


def form_outliers(text: str, item_set: ItemSet) -> list[Item]:
    """Return minority forms only when at least two thirds share one form."""

    observed = [_form(text, item) for item in item_set.items]
    labeled_majority = sum(bold or colon for bold, colon, _ in observed) * 3 >= len(observed) * 2
    # Infer label usage before normalizing sentence colons; bold and colon
    # labels can jointly establish a labeled majority.
    forms = [
        (bold or (colon and labeled_majority), terminated)
        for bold, colon, terminated in observed
    ]
    modal, count = Counter(forms).most_common(1)[0]
    if count * 3 < len(forms) * 2:
        return []
    return [item for item, form in zip(item_set.items, forms) if form != modal]


def summarize_item_sets(text: str) -> list[dict[str, Any]]:
    """Return JSON-ready list observations independent of enabled rules."""

    summaries = []
    for group in find_item_sets(text):
        shared = shared_lead_span(text, group)
        summaries.append({
            "line": text.count("\n", 0, group.items[0].start) + 1,
            "marker": group.marker,
            "item_count": len(group.items),
            "distinct_lead_count": len({_lead_key(text, item) for item in group.items}),
            "shared_lead": (
                " ".join(text[start:end] for start, end in group.items[0].words
                         if end <= shared[1])
                if shared is not None else None
            ),
            "form_outlier_lines": [
                text.count("\n", 0, item.start) + 1 for item in form_outliers(text, group)
            ],
        })
    return summaries


def record_openings(texts: Iterable[str]) -> dict[str, Any]:
    """Count shared first-word windows without making a quality judgment."""

    counts: Counter[str] = Counter()
    record_count = 0
    for text in texts:
        record_count += 1
        words = tokenize(text)
        if words:
            counts[" ".join(words[:LEAD_WORDS])] += 1
    shared = sorted(
        ((lead, count) for lead, count in counts.items() if count > 1),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return {
        "record_count": record_count,
        "distinct_lead_count": len(counts),
        "shared_lead_record_rate": (
            sum(count for _, count in shared) / record_count if counts else None
        ),
        "top_shared_leads": [
            {"lead": lead, "record_count": count} for lead, count in shared[:5]
        ],
    }
