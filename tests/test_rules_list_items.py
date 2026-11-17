"""List rules, profile guidance, and repetition share public behavior."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from tests.helpers_cli import run_cli
from writing_eval.assessment_profile import _repeated_opening_patterns
from writing_eval.metrics_structure import repeated_opening_corpus_rate
from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor, load_rules

SHARED = "- Users complain about crashes.\n- Users complain about billing.\n- Users complain about login.\n"


def test_shared_lead_exception_sees_the_whole_set() -> None:
    rules = [rule for rule in load_rules(BUILTIN_RULES_PATH) if rule.id == "list_shared_lead"]
    auditor = StyleAuditor([replace(rules[0], exceptions=("login",))])
    assert auditor.audit(SHARED) == []
    finding, = StyleAuditor(rules).audit(SHARED)
    assert finding.char_offset == 2
    assert finding.matched_text == "Users complain about"


def test_form_exception_sees_continuation_but_not_other_items() -> None:
    text = "- First item.\n- Second item.\n- Third item\n  documented exception\n"
    rule, = [r for r in load_rules(BUILTIN_RULES_PATH) if r.id == "list_inconsistent_form"]
    assert StyleAuditor([replace(rule, exceptions=("documented exception",))]).audit(text) == []
    finding, = StyleAuditor([replace(rule, exceptions=("First item",))]).audit(text)
    assert finding.matched_text == "Third item"


@pytest.mark.parametrize("text,rate,lines,counts", [
    ("We tested. We measured. We checked.", 1.0, [1], [3]),
    ("We begin.\n- We test. We measure.\n- We finish.", 1.0, [2], [2]),
    ("- We test. We measure.\n- We finish. We check.", 1.0, [1, 2], [2, 2]),
    ("We begin.\n- We test.\n- We finish.", 0.0, [], []),
    ("- Add one\n- Add two\n\nWe test. We measure.", 1.0, [4], [2]),
])
def test_pairs_agree_across_cli_metric_detector_and_profile_locations(
    text: str, rate: float, lines: list[int], counts: list[int]
) -> None:
    result = run_cli("check", "-", "--format", "json", stdin=text)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["metrics"]["repeated_opening_rate"] == rate
    patterns = _repeated_opening_patterns(text)
    assert [p["line"] for p in patterns] == lines
    assert [p["sentence_count"] for p in patterns] == counts
    assert sum(p["sentence_count"] - 1 for p in patterns) == sum(
        f["rule_id"] == "repeated_openings" for f in payload["findings"]
    )
    assert repeated_opening_corpus_rate([text, "Different words."]) == rate


def test_overlay_disables_findings_not_observations(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        "extends: builtin\nrules:\n"
        "  - id: list_shared_lead\n    enabled: false\n"
        "  - id: list_inconsistent_form\n    enabled: false\n"
    )
    result = run_cli("check", "-", "--rules", overlay, "--format", "json", stdin=SHARED)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["findings"] == []
    assert payload["item_sets"][0]["shared_lead"] == "Users complain about"


def test_profile_review_candidates_and_version_rebuild(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "reference.md").write_text("Editors write clear instructions. Readers follow them.\n")
    root = tmp_path / "profiles"
    built = run_cli("profile", "build", "demo", "--from", sources, "--profiles-root", root)
    assert built.returncode == 0, built.stderr
    draft = SHARED.replace("login.", "login")
    args = ("check", "-", "--style", "demo", "--profiles-root", root)
    result = run_cli(*args, "--format", "json", stdin=draft)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assessment = payload["assessment"]
    issues = [i for i in assessment["issues"] if i["kind"] == "review_candidate"]
    list_issues = {issue["id"]: issue for issue in issues if issue["id"].startswith("list_")}
    assert set(list_issues) == {"list_shared_lead", "list_inconsistent_form"}
    for issue in list_issues.values():
        assert issue["section"] == "rhythm_structure"
        assert issue["deduction"] == 0
        assert "Reduce" not in issue["success_criteria"][0]
    assert "deliberate repetition" in list_issues["list_shared_lead"]["success_criteria"][0]
    text = run_cli(*args, stdin=draft)
    assert text.returncode == 0, text.stderr
    assert "## Review candidates" in text.stdout
    assert "Section: Rhythm and structure" in text.stdout
    path = root / "demo" / "profile.json"
    profile = json.loads(path.read_text())
    assert profile["metrics_version"] == 3
    profile["metrics_version"] = 2
    path.write_text(json.dumps(profile))
    rejected = run_cli(*args, stdin=draft)
    assert rejected.returncode != 0
    assert "rebuild" in rejected.stderr.lower()


def test_profile_own_shared_leads_receive_allowance(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "reference.md").write_text(SHARED)
    root = tmp_path / "profiles"
    built = run_cli("profile", "build", "demo", "--from", sources, "--profiles-root", root)
    assert built.returncode == 0, built.stderr
    result = run_cli("check", "-", "--style", "demo", "--profiles-root", root,
                     "--format", "json", stdin=SHARED)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    finding, = payload["findings"]
    assert finding["within_allowance"] is True
    assert not [i for i in payload["assessment"]["issues"]
                if i["id"] == "list_shared_lead"]
