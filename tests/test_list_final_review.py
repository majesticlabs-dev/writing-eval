"""Regressions for the final review's fence and label findings."""

from dataclasses import replace
import json

import pytest

from tests.helpers_cli import run_cli
from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor, load_rules


def check(text: str) -> dict:
    result = run_cli("check", "-", "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fences_do_not_change_item_prose_termination(fence: str) -> None:
    text = (
        "1. Open the file.\n2. Open the cache.\n"
        f"   {fence}text\n   - Not a sibling\n   {fence}\n"
        "3. Open the report.\n4. Open the log.\n"
    )
    payload = check(text)
    group, = payload["item_sets"]
    assert group["form_outlier_lines"] == []
    assert group["shared_lead"] == "Open the"
    assert not [f for f in payload["findings"] if f["rule_id"] == "list_inconsistent_form"]


def test_prose_after_fence_still_decides_termination() -> None:
    text = (
        "- First item.\n- Second item.\n- Third item.\n"
        "  ```\n  code\n  ```\n  An unterminated continuation\n"
    )
    payload = check(text)
    assert payload["item_sets"][0]["form_outlier_lines"] == [3]


def test_unindented_paragraph_after_fence_is_not_item_continuation() -> None:
    payload = check(
        "- Install it.\n- Configure it.\n- Run it.\n"
        "  ```\n  run\n  ```\nThen check the output\n"
    )
    assert payload["item_sets"][0]["form_outlier_lines"] == []
    assert not [f for f in payload["findings"] if f["rule_id"] == "list_inconsistent_form"]


def test_fence_remains_inside_form_exception_context() -> None:
    text = (
        "- First item.\n- Second item.\n- Third item\n"
        "  ```\n  documented exception\n  ```\n"
    )
    rule, = [r for r in load_rules(BUILTIN_RULES_PATH) if r.id == "list_inconsistent_form"]
    finding, = StyleAuditor([rule]).audit(text)
    assert finding.matched_text == "Third item"
    assert StyleAuditor([replace(rule, exceptions=("documented exception",))]).audit(text) == []


@pytest.mark.parametrize("opening", ["For example", "Ask yourself", "If you"])
def test_sentence_colons_do_not_create_label_outliers(opening: str) -> None:
    payload = check(
        f"- Start with a goal.\n- Choose clear words.\n- {opening}: use labels.\n"
        "- Keep each item short.\n"
    )
    assert payload["item_sets"][0]["form_outlier_lines"] == []


@pytest.mark.parametrize("labels", [
    ("First: Alpha.", "Second: Beta."),
    ("**First:** Alpha.", "Second: Beta."),
    ("First: Alpha.", "**Second:** Beta."),
])
def test_colon_and_bold_labels_jointly_establish_majority(labels: tuple[str, str]) -> None:
    payload = check(f"- {labels[0]}\n- {labels[1]}\n- A plain sentence.\n")
    assert payload["item_sets"][0]["form_outlier_lines"] == [3]


def test_colon_minority_does_not_hide_bold_outlier() -> None:
    payload = check(
        "- **First:** Alpha.\n- For example: beta.\n"
        "- Continue the work.\n- Finish the work.\n"
    )
    assert payload["item_sets"][0]["form_outlier_lines"] == [1]


def test_ignored_colon_label_does_not_hide_punctuation_outlier() -> None:
    payload = check(
        "- Start with a goal.\n- Choose clear words.\n- For example: use labels\n"
        "- Keep each item short.\n"
    )
    assert payload["item_sets"][0]["form_outlier_lines"] == [3]


@pytest.mark.parametrize("children", ["  - x\n", "  - x\n  - y\n  - z\n"])
def test_fence_at_nested_indent_retains_the_outer_list(children: str) -> None:
    text = (
        f"- Open the a\n{children}  ```\n  code\n  ```\n"
        "- Open the b\n- Open the c\n"
    )
    payload = check(text)
    outer = payload["item_sets"][0]
    assert (outer["line"], outer["item_count"], outer["shared_lead"]) == (1, 3, "Open the")
    assert len(payload["item_sets"]) == (2 if children.count("\n") == 3 else 1)


def test_dedented_fence_closes_only_nested_sets_at_or_deeper_than_it() -> None:
    text = (
        "- Open the a\n  - Midlevel item\n    - Deep item\n"
        "  ```\n  code\n  ```\n- Open the b\n- Open the c\n"
    )
    group, = check(text)["item_sets"]
    assert (group["item_count"], group["shared_lead"]) == (3, "Open the")
