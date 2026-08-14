"""Tests for deterministic literal-preservation diagnostics."""

import pytest

from writing_eval.preservation import (
    compare_literal_preservation,
    compare_record_literals,
    extract_protected_literals,
)


def test_extract_literals_uses_nonoverlapping_precedence() -> None:
    text = (
        'She said "Revenue reached $1,200 on July 4, 2026." '
        "See https://example.com/report/2026?month=7. Outside the quote: 25%."
    )
    literals = extract_protected_literals(text)
    assert [(item["kind"], item["value"]) for item in literals] == [
        ("quote", "Revenue reached $1,200 on July 4, 2026."),
        ("url", "https://example.com/report/2026?month=7"),
        ("number", "25%"),
    ]


def test_equivalent_literal_formatting_normalizes_safely() -> None:
    source = "Revenue was $1,200 on July 4, 2026. See https://example.com/report."
    revised = "On july 4 2026, revenue was $1200. See https://example.com/report."
    result = compare_literal_preservation(source, revised)
    assert result["status"] == "pass"
    assert result["missing"] == []
    assert result["added"] == []


def test_missing_and_added_literals_fail_with_multiset_counts() -> None:
    source = 'Use code "SAVE20" twice: 20% now and 20% later.'
    revised = 'Use code "SAVE25" once: 25% now.'
    result = compare_literal_preservation(source, revised)
    assert result["status"] == "fail"
    assert result["missing_count"] == 3
    assert result["added_count"] == 2
    assert result["missing"] == [
        {"kind": "number", "value": "20%", "count": 2},
        {"kind": "quote", "value": "SAVE20", "count": 1},
    ]
    assert result["added"] == [
        {"kind": "number", "value": "25%", "count": 1},
        {"kind": "quote", "value": "SAVE25", "count": 1},
    ]


def test_record_comparison_is_ordered_and_summarized() -> None:
    source = [
        {"id": "a", "text": "Ship 2 builds."},
        {"id": "b", "text": "Open https://example.com."},
    ]
    revised = [
        {"id": "a", "text": "Ship 3 builds."},
        {"id": "b", "text": "Open https://example.com."},
    ]
    result = compare_record_literals(source, revised)
    assert result["status"] == "fail"
    assert result["record_count"] == 2
    assert result["failed_record_count"] == 1
    assert result["missing_literal_count"] == 1
    assert result["added_literal_count"] == 1
    assert [record["source_id"] for record in result["records"]] == ["a", "b"]


def test_record_comparison_aligns_reordered_records_by_id() -> None:
    source = [
        {"id": "a", "text": "Ship 2 builds."},
        {"id": "b", "text": "Ship 3 builds."},
    ]
    revised = [
        {"id": "b", "text": "Ship 3 builds."},
        {"id": "a", "text": "Ship 2 builds."},
    ]
    result = compare_record_literals(source, revised)
    assert result["status"] == "pass"
    assert [record["source_id"] for record in result["records"]] == ["a", "b"]


def test_compare_record_literals_validates_both_collections() -> None:
    good = [{"id": "a", "text": "One."}]
    with pytest.raises(ValueError, match=r"source record at index 1 .* nonempty string id"):
        compare_record_literals(good + [{"text": "Two."}], good)
    with pytest.raises(ValueError, match=r"revised record at index 0 .* nonempty string id"):
        compare_record_literals(good, [{"id": "", "text": "Two."}])
    with pytest.raises(ValueError, match=r"source record at index 0 .* string text"):
        compare_record_literals([{"id": "a", "text": 3}], good)
    with pytest.raises(ValueError, match=r"duplicate id 'a' in revised records at index 1"):
        compare_record_literals(good, good + [{"id": "a", "text": "Two."}])


def test_compare_record_literals_rejects_whitespace_only_ids_and_preserves_nonblank_ids() -> None:
    with pytest.raises(ValueError, match=r"revised record at index 0 .* nonempty string id"):
        compare_record_literals(
            [{"id": "a", "text": "One."}],
            [{"id": "   ", "text": "Two."}],
        )

    result = compare_record_literals(
        [{"id": "  a  ", "text": "One."}],
        [{"id": "  a  ", "text": "One."}],
    )
    assert result["records"][0]["source_id"] == "  a  "
    assert result["records"][0]["revised_id"] == "  a  "
