"""Public-boundary regressions found in the list implementation review."""

import json
from pathlib import Path

import pytest

from tests.helpers_cli import run_cli
from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor, load_rules


def check(text: str) -> dict:
    result = run_cli("check", "-", "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def list_findings(payload: dict) -> list[dict]:
    return [f for f in payload["findings"] if f["rule_id"].startswith("list_")]


@pytest.mark.parametrize("boxes", [("x", "x", "x"), (" ", " ", " "), ("x", " ", "X")])
def test_task_boxes_do_not_become_lead_words(boxes: tuple[str, ...]) -> None:
    text = "\n".join(f"- [{box}] Add {word}" for box, word in zip(boxes, ("tests", "docs", "CI")))
    payload = check(text)
    assert payload["item_sets"][0]["distinct_lead_count"] == 3
    assert list_findings(payload) == []


def test_mixed_task_boxes_preserve_real_shared_lead_and_offsets() -> None:
    payload = check("- [x] Fix the parser\n- [ ] Fix the cache\n- [X] Fix the report\n")
    finding, = list_findings(payload)
    assert (finding["rule_id"], finding["line"], finding["column"], finding["span"]) == (
        "list_shared_lead", 1, 7, "Fix the",
    )
    assert payload["item_sets"][0]["shared_lead"] == "Fix the"


@pytest.mark.parametrize("text", [
    "- Follow-up on billing\n- Follow-up with support\n- Follow-up for sales\n",
    "- `writing-eval check`\n- `writing-eval profile`\n- `writing-eval eval`\n",
    "- `Fix the parser`\n- `Fix the cache`\n- `Fix the report`\n",
    "- https://example.com/a\n- https://example.com/b\n- https://example.com/c\n",
    "- https://example.com same first\n- https://example.com same next\n- https://example.com same last\n",
])
def test_single_units_urls_and_code_do_not_produce_shared_lead_advice(text: str) -> None:
    payload = check(text)
    assert payload["item_sets"][0]["shared_lead"] is None
    assert not [f for f in list_findings(payload) if f["rule_id"] == "list_shared_lead"]


def test_hyphenated_lead_units_can_still_share_two_words() -> None:
    payload = check("- Follow-up with billing\n- Follow-up with support\n- Follow-up with sales\n")
    assert payload["item_sets"][0]["shared_lead"] == "Follow-up with"


@pytest.mark.parametrize("suffix", ["   ", "\r"])
def test_form_outlier_library_span_is_trimmed(suffix: str) -> None:
    text = f"- Alpha one.\n- Beta two.\n- Gamma three{suffix}\n"
    rules = [r for r in load_rules(BUILTIN_RULES_PATH) if r.id == "list_inconsistent_form"]
    finding, = StyleAuditor(rules).audit(text)
    assert finding.matched_text == "Gamma three"
    assert text[finding.char_offset:].startswith("Gamma three")


def test_display_lead_omits_emphasis_but_finding_is_a_source_slice() -> None:
    text = "- *Fix* the parser\n- **Fix** the cache\n- Fix the report\n"
    payload = check(text)
    assert payload["item_sets"][0]["shared_lead"] == "Fix the"
    finding, = [f for f in list_findings(payload) if f["rule_id"] == "list_shared_lead"]
    assert (finding["column"], finding["span"]) == (4, "Fix* the")


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fenced_continuation_preserves_the_parent_list(fence: str) -> None:
    text = (
        "1. Open the file.\n2. Open the cache.\n"
        f"   {fence}text\n   - Not a sibling\n   {fence}\n"
        "3. Open the report.\n4. Open the log.\n"
    )
    payload = check(text)
    group, = payload["item_sets"]
    assert (group["item_count"], group["shared_lead"]) == (4, "Open the")
    assert group["form_outlier_lines"] == []
    assert len([f for f in list_findings(payload) if f["rule_id"] == "list_shared_lead"]) == 1


def test_parent_colon_is_not_a_label_without_following_text() -> None:
    payload = check("- Install:\n  - Local dependencies\n- Run the tests\n- Deploy the build\n- Tag the release\n")
    assert payload["item_sets"][0]["form_outlier_lines"] == []
    assert list_findings(payload) == []


@pytest.mark.parametrize("lead", ["Open the", "Don't use", 'Use foo"bar', "Open C:\\cache"])
def test_text_leads_always_use_json_double_quotes(lead: str) -> None:
    result = run_cli("check", "-", stdin="\n".join(f"- {lead} {s}" for s in ("parser", "cache", "report")))
    assert result.returncode == 0, result.stderr
    assert f"shared lead {json.dumps(lead)}" in result.stdout


def test_mixed_document_acceptance_observes_list_form_and_prose_repetition() -> None:
    text = (
        "# Release notes\n\nThe release changes three areas.\n\n"
        "- **Cache:** The cache now stores parsed rules.\n"
        "- **Reports:** The report lists provenance first.\n"
        "- The CLI is faster\n\n"
        "We tested the build on three machines. We measured the runtime twice.\n"
    )
    payload = check(text)
    assert payload["metrics"]["repeated_opening_rate"] == 1.0
    assert [(f["rule_id"], f["line"]) for f in payload["findings"]] == [
        ("fragmented_header", 3), ("inline_header_list", 4),
        ("boldface_density", 5), ("inline_header_list", 6),
        ("list_inconsistent_form", 7), ("repeated_openings", 9),
    ]


@pytest.mark.parametrize("prefix,expected_rate,expected_sets", [("> - ", 1.0, 0), ("    - ", 0.0, 1)])
def test_documented_blockquote_and_indented_code_limits(
    prefix: str, expected_rate: float, expected_sets: int,
) -> None:
    payload = check("\n".join(prefix + f"Fix the {word}" for word in ("parser", "cache", "report")))
    assert len(payload["item_sets"]) == expected_sets
    assert payload["metrics"]["repeated_opening_rate"] == expected_rate


@pytest.fixture
def repeating_profile(tmp_path: Path) -> tuple[str, ...]:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "reference.md").write_text("Editors test the parser. Editors measure the runtime.\n")
    root = tmp_path / "profiles"
    result = run_cli("profile", "build", "demo", "--from", sources, "--profiles-root", root)
    assert result.returncode == 0, result.stderr
    return "--style", "demo", "--profiles-root", str(root)


@pytest.mark.parametrize("text", [
    "- Users complain about crashes.\n- Users complain about billing.\n- Users complain about login\n",
    "One sentence alone is not a pair.\n",
])
def test_no_eligible_pairs_means_no_profile_repetition_comparison(
    text: str, repeating_profile: tuple[str, ...],
) -> None:
    result = run_cli("check", "-", *repeating_profile, "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["metrics"]["repeated_opening_rate"] == 0.0
    assert not [i for i in payload["assessment"]["issues"] if i["id"] == "repeated_openings"]
    statistic, = [s for s in payload["assessment"]["statistics"] if s["id"] == "repeated_opening_rate"]
    assert statistic["value"] is None
    assert statistic["interpretation"] == "unavailable"


@pytest.mark.parametrize("copies,summary", [(1, "1 list opens"), (2, "2 lists open")])
def test_list_candidate_summaries_pluralize(
    repeating_profile: tuple[str, ...], copies: int, summary: str,
) -> None:
    text = "\n# Next\n".join(
        ["- Users report crashes\n- Users report billing\n- Users report login"] * copies
    )
    result = run_cli("check", "-", *repeating_profile, "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    issue, = [i for i in payload["assessment"]["issues"] if i["id"] == "list_shared_lead"]
    assert issue["summary"].startswith(summary)
    assert "(s)" not in issue["summary"]


def test_real_zero_rate_still_compares_to_profile(repeating_profile: tuple[str, ...]) -> None:
    result = run_cli("check", "-", *repeating_profile, "--format", "json",
                     stdin="Editors test the parser. Readers measure the runtime.\n")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    issue, = [i for i in payload["assessment"]["issues"] if i["id"] == "repeated_openings"]
    assert issue["comparisons"][0]["direction"] == "increase"
    assert issue["deduction"] > 0
