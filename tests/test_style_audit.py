from dataclasses import replace
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from writing_eval.style_audit import (
    BUILTIN_RULES_PATH, StyleAuditor, audit_text, load_rules,
)


RULE_PATH = BUILTIN_RULES_PATH


@pytest.fixture(scope="module")
def auditor() -> StyleAuditor:
    return StyleAuditor.from_yaml(RULE_PATH)


def findings_for(auditor: StyleAuditor, rule_id: str, text: str):
    return [finding for finding in auditor.audit(text) if finding.rule_id == rule_id]


def test_em_dash_ban_triggers(auditor: StyleAuditor) -> None:
    text = "Clear" + chr(0x2014) + "concise."
    findings = findings_for(auditor, "em_dash_ban", text)
    assert len(findings) == 1
    assert findings[0].matched_text == chr(0x2014)
    assert findings[0].char_offset == 5
    assert findings[0].line_number == 1
    assert findings[0].severity == "warn"


def test_em_dash_ban_ignores_ascii_punctuation(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "em_dash_ban", "Clear, concise, and direct.")


def test_en_dash_ban_triggers_on_en_dash_and_horizontal_bar(
    auditor: StyleAuditor,
) -> None:
    for dash in (chr(0x2013), chr(0x2015)):
        text = "Clear" + dash + "concise."
        findings = findings_for(auditor, "en_dash_ban", text)
        assert len(findings) == 1
        assert findings[0].severity == "warn"
        assert findings[0].matched_text == dash


def test_en_dash_ban_ignores_hyphen_and_double_hyphen(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "en_dash_ban", "Clear-concise summary.")
    assert not findings_for(auditor, "en_dash_ban", "Clear--concise summary.")


def test_dash_rules_do_not_overlap(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "en_dash_ban", "Clear" + chr(0x2014) + "concise.")
    assert not findings_for(auditor, "em_dash_ban", "Clear" + chr(0x2013) + "concise.")


def test_negative_parallelism_triggers(auditor: StyleAuditor) -> None:
    text = "This is not a shortcut, but a safer route."
    assert findings_for(auditor, "negative_parallelism", text)


def test_negative_parallelism_ignores_direct_statement(auditor: StyleAuditor) -> None:
    text = "This safer route takes more time."
    assert not findings_for(auditor, "negative_parallelism", text)


def test_polish_vocab_triggers(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "polish_vocab", "Use this tool to leverage the data.")
    assert [finding.matched_text for finding in findings] == ["leverage"]


def test_polish_vocab_ignores_specific_language(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "polish_vocab", "Use the tool to compare both files.")


def test_polish_vocab_flags_pillar_not_the_name_pilar(auditor: StyleAuditor) -> None:
    triggered = findings_for(auditor, "polish_vocab", "a key pillar of the plan")
    assert [finding.matched_text for finding in triggered] == ["pillar"]
    assert not findings_for(auditor, "polish_vocab", "Pilar reviewed the draft")


def test_metadiscourse_openers_triggers(auditor: StyleAuditor) -> None:
    text = "In this article, we compare the plans."
    assert findings_for(auditor, "metadiscourse_openers", text)


def test_metadiscourse_openers_ignores_direct_opening(auditor: StyleAuditor) -> None:
    text = "The plans differ in cost and storage."
    assert not findings_for(auditor, "metadiscourse_openers", text)


def test_repeated_openings_across_adjacent_sentences(auditor: StyleAuditor) -> None:
    text = "Teams review the draft. Teams approve the final copy. Editors publish it."
    findings = findings_for(auditor, "repeated_openings", text)
    assert len(findings) == 1
    assert findings[0].matched_text == "Teams"
    assert findings[0].char_offset == text.index("Teams", 1)


def test_repeated_openings_ignores_different_first_words(auditor: StyleAuditor) -> None:
    text = "Teams review the draft. Editors approve the final copy."
    assert not findings_for(auditor, "repeated_openings", text)


def test_repeated_openings_do_not_cross_headings(auditor: StyleAuditor) -> None:
    text = "We shipped it.\n\n## We learned a lot\n\nNothing broke."
    assert not findings_for(auditor, "repeated_openings", text)


def test_repeated_openings_broken_by_blank_line(auditor: StyleAuditor) -> None:
    text = "Teams review the draft.\n\nTeams approve the final copy."
    assert not findings_for(auditor, "repeated_openings", text)


def test_repeated_openings_skip_opener_less_sentences(auditor: StyleAuditor) -> None:
    text = "Teams win. 7. Teams grow."
    findings = findings_for(auditor, "repeated_openings", text)
    assert len(findings) == 1
    assert findings[0].matched_text == "Teams"
    assert findings[0].char_offset == text.index("Teams", 1)


def test_vague_authority_triggers(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "vague_authority", "Research shows the change helps.")
    assert [finding.matched_text for finding in findings] == ["Research shows"]


def test_vague_authority_ignores_named_source(auditor: StyleAuditor) -> None:
    text = "The 2025 Acme survey reports a lower error rate."
    assert not findings_for(auditor, "vague_authority", text)


def test_promotional_adjectives_triggers(auditor: StyleAuditor) -> None:
    findings = findings_for(
        auditor, "promotional_adjectives", "The vendor calls it a game-changing release."
    )
    assert [finding.matched_text for finding in findings] == ["game-changing"]


def test_promotional_adjectives_ignores_measurable_claim(auditor: StyleAuditor) -> None:
    text = "The release reduced median response time by 20 percent."
    assert not findings_for(auditor, "promotional_adjectives", text)


def test_exception_within_match_context_suppresses_finding() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    excepted_rule = replace(rule, exceptions=("leverage",))
    assert audit_text("We leverage the API here.", [excepted_rule]) == []


def test_capitalized_exception_suppresses_case_insensitively() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    excepted_rule = replace(rule, exceptions=("Leverage",))
    assert audit_text("We leverage the API here.", [excepted_rule]) == []


def test_distant_same_line_exception_does_not_suppress_finding() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    excepted_rule = replace(rule, exceptions=("approved technical usage",))
    text = "We leverage the API here. approved technical usage"
    findings = audit_text(text, [excepted_rule])
    assert [finding.matched_text for finding in findings] == ["leverage"]


def test_exception_on_another_line_does_not_suppress_finding() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    excepted_rule = replace(rule, exceptions=("approved technical usage",))
    text = "We leverage the API here.\napproved technical usage"
    assert len(audit_text(text, [excepted_rule])) == 1


def test_finding_line_numbers_are_stable_across_newlines() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    text = "We leverage the API.\n\n\nThe tool can leverage existing workflows."
    findings = audit_text(text, [rule])
    assert [finding.line_number for finding in findings] == [1, 4]


def test_exception_text_adjacent_to_candidate_does_not_suppress() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "polish_vocab")
    excepted_rule = replace(rule, exceptions=("approved",))
    text_before = "approved leverage the API here"
    text_after = "leverage the API approved here"
    findings_before = audit_text(text_before, [excepted_rule])
    findings_after = audit_text(text_after, [excepted_rule])
    assert [finding.matched_text for finding in findings_before] == ["leverage"]
    assert [finding.matched_text for finding in findings_after] == ["leverage"]


def test_exception_red_does_not_suppress_candidate_stored() -> None:
    rule = next(rule for rule in load_rules(RULE_PATH) if rule.id == "passive_voice")
    excepted_rule = replace(rule, exceptions=("red",))
    text = "The red car was stored in the garage."
    findings = audit_text(text, [excepted_rule])
    assert [finding.matched_text for finding in findings] == ["was stored"]


def test_invalid_rule_raises_value_error(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid-rules.yaml"
    invalid_path.write_text(
        "rules:\n  - id: missing_detector\n    severity: warn\n    message: Fix it.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required field.*detector"):
        load_rules(invalid_path)


def test_unknown_named_detector_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n  - id: typo_rule\n    severity: info\n"
        "    detector: repeated_openigns\n    message: Fix it.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="typo_rule.*unknown named detector"):
        load_rules(path)


def test_known_named_detector_still_resolves(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n  - id: openings\n    severity: info\n"
        "    detector: repeated_openings\n    message: Vary openings.\n",
        encoding="utf-8",
    )
    rule = load_rules(path)[0]
    assert rule.detector_function is not None
    assert rule.compiled_pattern is None
