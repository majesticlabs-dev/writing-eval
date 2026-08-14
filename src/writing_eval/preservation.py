"""Deterministic literal-preservation checks for revision workflows."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any


_QUOTE_RE = re.compile(r'"(?P<straight>[^"\n]+)"|\u201c(?P<curly>[^\u201d\n]+)\u201d')
_URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"'\u201c\u201d]+", re.IGNORECASE)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_RE = re.compile(
    rf"(?i)\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|"
    rf"{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*|\s+)\d{{4}})\b"
)
_NUMBER_RE = re.compile(
    r"(?<![\w])[-+]?[$\u20ac\u00a3]?(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?%?(?![\w])"
)
_URL_TRAILING = ".,;:!?"


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    return any(start < used_end and end > used_start for used_start, used_end in occupied)


def _normalize(kind: str, value: str) -> str:
    if kind == "quote":
        return re.sub(r"\s+", " ", value.strip())
    if kind == "url":
        return value.rstrip(_URL_TRAILING)
    if kind == "date":
        return re.sub(r"\s+", " ", value.replace(",", " ").strip()).casefold()
    if kind == "number":
        return value.replace(",", "")
    raise ValueError(f"unsupported literal kind: {kind}")


def extract_protected_literals(text: str) -> list[dict[str, Any]]:
    """Extract protected literal values without overlapping categories.

    Double-quoted spans take precedence, followed by URLs, dates, and numbers.
    A number inside a quote or URL is protected by the enclosing literal instead
    of being counted twice.
    """

    literals: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []

    for match in _QUOTE_RE.finditer(text):
        value = match.group("straight") or match.group("curly")
        literals.append(
            {
                "kind": "quote",
                "value": _normalize("quote", value),
                "start": match.start(),
                "end": match.end(),
            }
        )
        occupied.append((match.start(), match.end()))

    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(_URL_TRAILING)
        end = match.start() + len(raw)
        if _overlaps(match.start(), end, occupied):
            continue
        literals.append(
            {
                "kind": "url",
                "value": _normalize("url", raw),
                "start": match.start(),
                "end": end,
            }
        )
        occupied.append((match.start(), end))

    for kind, pattern in (("date", _DATE_RE), ("number", _NUMBER_RE)):
        for match in pattern.finditer(text):
            if _overlaps(match.start(), match.end(), occupied):
                continue
            literals.append(
                {
                    "kind": kind,
                    "value": _normalize(kind, match.group(0)),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
            occupied.append((match.start(), match.end()))

    return sorted(literals, key=lambda item: (item["start"], item["kind"], item["value"]))


def _counter(text: str) -> Counter[tuple[str, str]]:
    return Counter(
        (str(item["kind"]), str(item["value"]))
        for item in extract_protected_literals(text)
    )


def _counter_items(counter: Counter[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"kind": kind, "value": value, "count": count}
        for (kind, value), count in sorted(counter.items())
    ]


def compare_literal_preservation(source: str, revised: str) -> dict[str, Any]:
    """Compare protected literal multisets in source and revised prose."""

    source_literals = _counter(source)
    revised_literals = _counter(revised)
    missing = source_literals - revised_literals
    added = revised_literals - source_literals
    missing_count = sum(missing.values())
    added_count = sum(added.values())
    return {
        "status": "pass" if missing_count == 0 and added_count == 0 else "fail",
        "source_literal_count": sum(source_literals.values()),
        "revised_literal_count": sum(revised_literals.values()),
        "missing_count": missing_count,
        "added_count": added_count,
        "missing": _counter_items(missing),
        "added": _counter_items(added),
    }


def _validated_id_map(
    records: Sequence[Mapping[str, Any]], collection: str
) -> dict[str, Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"{collection} record at index {index} is not an object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(
                f"{collection} record at index {index} must have a nonempty string id"
            )
        if not isinstance(record.get("text"), str):
            raise ValueError(
                f"{collection} record at index {index} must have a string text"
            )
        if record_id in by_id:
            raise ValueError(
                f"duplicate id {record_id!r} in {collection} records at index {index}"
            )
        by_id[record_id] = record
    return by_id


def compare_record_literals(
    source_records: Sequence[Mapping[str, Any]],
    revised_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare source and revised record collections by stable record ID."""

    records: list[dict[str, Any]] = []
    source_by_id = _validated_id_map(source_records, "source")
    revised_by_id = _validated_id_map(revised_records, "revised")
    for record_id in sorted(source_by_id.keys() | revised_by_id.keys()):
        source = source_by_id.get(record_id)
        revised = revised_by_id.get(record_id)
        if source is None or revised is None:
            result: dict[str, Any] = {
                "status": "fail",
                "source_literal_count": 0,
                "revised_literal_count": 0,
                "missing_count": 0,
                "added_count": 0,
                "missing": [],
                "added": [],
                "reason": (
                    "record_missing_from_source"
                    if source is None
                    else "record_missing_from_revision"
                ),
            }
        else:
            result = compare_literal_preservation(
                str(source["text"]), str(revised["text"])
            )
        result["source_id"] = source.get("id") if source is not None else None
        result["revised_id"] = revised.get("id") if revised is not None else None
        records.append(result)

    failed = sum(1 for record in records if record["status"] == "fail")
    return {
        "status": "pass" if failed == 0 else "fail",
        "record_count": len(records),
        "failed_record_count": failed,
        "missing_literal_count": sum(record["missing_count"] for record in records),
        "added_literal_count": sum(record["added_count"] for record in records),
        "records": records,
    }
