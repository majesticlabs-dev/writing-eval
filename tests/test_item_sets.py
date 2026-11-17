"""Markdown list structure through the single-document CLI boundary."""

import json

import pytest

from tests.helpers_cli import run_cli


def check(text: str) -> dict:
    result = run_cli("check", "-", "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_parallel_items_keep_consistency_without_prose_repetition() -> None:
    payload = check("- Add retry logic\n- Add a timeout\n- Add tests\n")
    assert payload["findings"] == []
    assert payload["metrics"]["repeated_opening_rate"] == 0.0
    assert payload["item_sets"] == [{
        "line": 1, "marker": "bullet", "item_count": 3,
        "distinct_lead_count": 3, "shared_lead": None, "form_outlier_lines": [],
    }]


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
def test_shared_lead_offsets_case_and_loose_lists(separator: str) -> None:
    payload = check(separator.join([
        "- Users complain about crashes.",
        "- users complain about billing.",
        "- USERS complain about login.",
    ]))
    assert payload["item_sets"][0]["shared_lead"] == "Users complain about"
    assert payload["item_sets"][0]["item_count"] == 3
    assert [(f["rule_id"], f["line"], f["column"], f["span"])
            for f in payload["findings"]] == [
        ("list_shared_lead", 1, 3, "Users complain about")
    ]


def test_nested_sets_marker_changes_headings_and_paragraph_boundaries() -> None:
    payload = check(
        "- Parent one\n"
        "  - Fix cache keys\n  - Fix cache paths\n  - Fix cache sizes\n"
        "- Parent two\n- Parent three\n"
        "1. Open the settings\n2. Open the account\n3. Open the invoice\n"
        "\nA new paragraph.\n\n- A single item\n"
        "# Boundary\n- Another item\n- Last item\n"
    )
    assert [(s["line"], s["marker"], s["item_count"], s["shared_lead"])
            for s in payload["item_sets"]] == [
        (1, "bullet", 3, None),
        (2, "bullet", 3, "Fix cache"),
        (7, "ordered", 3, "Open the"),
    ]


def test_continuations_do_not_change_leads_and_prose_pairs_remain() -> None:
    payload = check(
        "1. Open the settings.\n   It is under Account.\n"
        "2. Open the billing.\n3. Open the invoices.\n"
    )
    assert payload["item_sets"][0]["shared_lead"] == "Open the"
    assert payload["metrics"]["repeated_opening_rate"] == 0.0


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fenced_list_lookalikes_are_not_sets(fence: str) -> None:
    payload = check(
        f"{fence}text\n- Same lead one\n- Same lead two\n- Same lead three\n"
        f"{fence}\n- Add one\n- Add two\n- Add three\n"
    )
    assert [s["line"] for s in payload["item_sets"]] == [6]
    assert not [f for f in payload["findings"] if f["rule_id"].startswith("list_")]


def test_other_fence_or_shorter_fence_does_not_close_code() -> None:
    payload = check(
        "````\n~~~\n```\n- Same lead one\n- Same lead two\n- Same lead three\n````\n"
    )
    assert payload["item_sets"] == []


def test_form_outliers_labels_termination_and_unestablished_form() -> None:
    payload = check("- **Cache:** Stores data.\n- **Reports:** Lists sources.\n- Faster CLI\n")
    assert payload["item_sets"][0]["form_outlier_lines"] == [3]
    assert [(f["line"], f["span"]) for f in payload["findings"]
            if f["rule_id"] == "list_inconsistent_form"] == [(3, "Faster CLI")]
    split = check("- Alpha.\n- Beta.\n- Gamma\n- Delta\n")
    assert split["item_sets"][0]["form_outlier_lines"] == []


def test_label_limit_and_punctuation_wrappers() -> None:
    payload = check(
        '- A label: Finished.\n- Other label: "Done."\n'
        '- A label with five words: Pending.\n'
    )
    assert payload["item_sets"][0]["form_outlier_lines"] == [3]


def test_dedented_continuation_returns_to_parent_item() -> None:
    payload = check(
        "- Parent one.\n"
        "  - Child one.\n  - Child two.\n  - Child three.\n"
        "  Parent continuation\n"
        "- Parent two.\n- Parent three.\n"
    )
    parent, child = payload["item_sets"]
    assert parent["form_outlier_lines"] == [1]
    assert child["form_outlier_lines"] == []


def test_one_word_items_and_minimum_set_size() -> None:
    payload = check("- Yes\n- Yes\n- Yes\n\n# Next\n- One\n- Two\n")
    assert len(payload["item_sets"]) == 1
    assert payload["item_sets"][0]["shared_lead"] is None
    assert payload["findings"] == []


def test_grammatical_forms_are_not_inferred_from_words() -> None:
    payload = check("- KV persistence\n- Switching to main\n- Fine-tune model on personal writing\n")
    assert payload["findings"] == []
    assert payload["item_sets"][0]["distinct_lead_count"] == 3


def test_plain_text_reports_set_facts() -> None:
    result = run_cli("check", "-", stdin="- Users report crashes\n- Users report billing\n- Users report login\n")
    assert result.returncode == 0, result.stderr
    assert "item_sets:\n  line 1: 3 bullet items, 1 distinct lead" in result.stdout
    assert 'shared lead "Users report"' in result.stdout
