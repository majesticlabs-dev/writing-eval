"""Behavior of the anti-ai overlay that extends the builtin rule set."""

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor, load_rules

OVERLAY_PATH = PROJECT_ROOT / "rules" / "anti-ai.yaml"
BUILTIN_IDS = [rule.id for rule in load_rules(BUILTIN_RULES_PATH)]


@pytest.fixture(scope="module")
def auditor() -> StyleAuditor:
    return StyleAuditor.from_yaml(OVERLAY_PATH)


def findings_for(auditor: StyleAuditor, rule_id: str, text: str):
    return [finding for finding in auditor.audit(text) if finding.rule_id == rule_id]


def test_overlay_extends_builtin_in_place_and_appends() -> None:
    rules = load_rules(OVERLAY_PATH)
    ids = [rule.id for rule in rules]
    assert ids[: len(BUILTIN_IDS)] == BUILTIN_IDS
    assert ids[len(BUILTIN_IDS) :] == [
        "narrative_cliches",
        "significance_markers",
        "generation_artifacts",
        "connector_openers",
    ]


def test_overrides_keep_builtin_severity_and_message() -> None:
    builtin = {rule.id: rule for rule in load_rules(BUILTIN_RULES_PATH)}
    merged = {rule.id: rule for rule in load_rules(OVERLAY_PATH)}
    for rule_id in ("polish_vocab", "recap_endings", "throat_clearing", "faux_insight"):
        assert merged[rule_id].severity == builtin[rule_id].severity
        assert merged[rule_id].message == builtin[rule_id].message


def test_narrative_cliches_flags_stock_phrases(auditor: StyleAuditor) -> None:
    text = (
        "I couldn't help but smile as nostalgia washed over me. "
        "Little did I know what the box held. "
        "We stumbled upon letters nestled in a drawer, in a bustling hallway."
    )
    matched = [finding.matched_text.lower() for finding in findings_for(auditor, "narrative_cliches", text)]
    assert "couldn't help but" in matched
    assert "washed over me" in matched
    assert "little did i know" in matched
    assert "stumbled upon" in matched
    assert "nestled in" in matched
    assert "bustling" in matched
    assert len(matched) == 6


def test_narrative_cliches_ignores_literal_uses(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "narrative_cliches", "The tide washed over the pilings at dawn.")


def test_significance_markers_flag_meta_commentary(auditor: StyleAuditor) -> None:
    text = (
        "That's the part that got me. Let that sink in. "
        "Thats what kills me. Which is exactly the problem."
    )
    findings = findings_for(auditor, "significance_markers", text)
    assert len(findings) == 4
    assert all(finding.severity == "warn" for finding in findings)
    assert findings[-1].matched_text == "Which is exactly the problem"


def test_significance_markers_ignore_plain_part_phrases(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "significance_markers", "The part that got wet was the cellar.")


def test_significance_markers_ignore_factual_comparisons(auditor: StyleAuditor) -> None:
    text = "The key is 42, which is exactly the value returned."
    assert not findings_for(auditor, "significance_markers", text)


def test_generation_artifacts_flag_placeholders_and_leaks(auditor: StyleAuditor) -> None:
    assert len(findings_for(auditor, "generation_artifacts", "See [insert example] for details.")) == 1
    assert len(findings_for(auditor, "generation_artifacts", "Read more at https://x.dev/a?utm_source=chatgpt.com")) == 1
    assert len(findings_for(auditor, "generation_artifacts", "As an AI language model, I cannot browse.")) == 1


def test_generation_artifacts_ignore_plain_model_mentions(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "generation_artifacts", "The draft reads like a language model wrote it.")


def test_generation_artifacts_ignore_markdown_links(auditor: StyleAuditor) -> None:
    text = "See the [example](https://example.com)."
    assert not findings_for(auditor, "generation_artifacts", text)


def test_connector_openers_flag_sentence_initial_connectors(auditor: StyleAuditor) -> None:
    text = "The plan failed. Furthermore, the budget collapsed. Moreover, trust eroded."
    findings = findings_for(auditor, "connector_openers", text)
    assert len(findings) == 2
    assert [finding.matched_text for finding in findings] == [
        "Furthermore",
        "Moreover",
    ]
    assert [finding.char_offset for finding in findings] == [
        text.index("Furthermore"),
        text.index("Moreover"),
    ]
    assert findings[0].severity == "info"
    line_start = findings_for(auditor, "connector_openers", "Additionally, we shipped late.")
    assert len(line_start) == 1


def test_connector_openers_ignore_mid_sentence_connectors(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "connector_openers", "The data, furthermore, is final.")


def test_polish_vocab_override_flags_added_vocabulary(auditor: StyleAuditor) -> None:
    text = "The synergy bolstered our unwavering endeavor."
    findings = findings_for(auditor, "polish_vocab", text)
    assert len(findings) == 4
    assert all(finding.severity == "warn" for finding in findings)
    assert not findings_for(auditor, "polish_vocab", "Use the tool.")


def test_recap_endings_override_flags_added_recap_openers(auditor: StyleAuditor) -> None:
    text = "In summary, it worked. Overall, the plan held. In conclusion, we agree."
    assert len(findings_for(auditor, "recap_endings", text)) == 3


def test_throat_clearing_override_flags_added_openers(auditor: StyleAuditor) -> None:
    text = "That being said, let's unpack the budget. In today's fast-paced world, speed wins."
    findings = findings_for(auditor, "throat_clearing", text)
    assert [finding.matched_text for finding in findings] == [
        "That being said",
        "let's unpack",
        "In today's fast-paced world",
    ]


def test_faux_insight_override_flags_false_suspense(auditor: StyleAuditor) -> None:
    assert len(findings_for(auditor, "faux_insight", "Here's the kicker: it worked.")) == 1
    assert len(findings_for(auditor, "faux_insight", "The best part?")) == 1
    assert not findings_for(auditor, "faux_insight", "The best part of the trip was the ferry.")


def test_importance_puffery_override_flags_role_phrases(auditor: StyleAuditor) -> None:
    assert len(findings_for(auditor, "importance_puffery", "Design plays a crucial role here.")) == 1


def test_collaborative_artifacts_override_flags_scaffolding(auditor: StyleAuditor) -> None:
    assert len(findings_for(auditor, "collaborative_artifacts", "I hope this email finds you well.")) == 1
    assert len(findings_for(auditor, "collaborative_artifacts", "Certainly! Here is the summary.")) == 1
    assert len(findings_for(auditor, "collaborative_artifacts", "I hope this helps.")) == 1
