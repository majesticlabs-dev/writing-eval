"""Shape and core-rule behavior of the builtin style-audit rule set."""

from pathlib import Path

import pytest
import yaml

import writing_eval
from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor

from tests.helpers_rules_content import builtin_auditor, findings_for


@pytest.fixture(scope="module")
def auditor() -> StyleAuditor:
    return builtin_auditor()


def test_builtin_rules_path_lives_inside_the_installed_package() -> None:
    package_root = Path(writing_eval.__file__).resolve().parent
    assert BUILTIN_RULES_PATH.is_file()
    assert BUILTIN_RULES_PATH.parent.parent == package_root
    assert BUILTIN_RULES_PATH.name == "style-audit.yaml"


def test_rule_count_and_severity_census(auditor: StyleAuditor) -> None:
    severities = [rule.severity for rule in auditor.rules]
    assert len(auditor.rules) == 34
    assert severities.count("warn") == 16
    assert severities.count("info") == 18


def test_rule_ids_are_unique_and_ordered_by_file_position(auditor: StyleAuditor) -> None:
    rule_ids = [rule.id for rule in auditor.rules]
    assert len(set(rule_ids)) == len(rule_ids)
    document = yaml.safe_load(BUILTIN_RULES_PATH.read_text(encoding="utf-8"))
    assert document["version"] == 1
    assert [entry["id"] for entry in document["rules"]] == rule_ids


def test_em_dash_ban_triggers(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "em_dash_ban", "Clear" + chr(0x2014) + "concise.")
    assert [finding.matched_text for finding in findings] == [chr(0x2014)]
    assert findings[0].severity == "warn"


def test_en_dash_ban_triggers_on_en_dash_and_horizontal_bar(
    auditor: StyleAuditor,
) -> None:
    for dash in (chr(0x2013), chr(0x2015)):
        findings = findings_for(auditor, "en_dash_ban", "Clear" + dash + "concise.")
        assert [finding.matched_text for finding in findings] == [dash]
        assert findings[0].severity == "warn"


def test_dash_rules_do_not_overlap(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "en_dash_ban", "Clear" + chr(0x2014) + "concise.")
    assert not findings_for(auditor, "em_dash_ban", "Clear" + chr(0x2013) + "concise.")


def test_passive_voice_triggers_on_be_plus_past_participle(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "passive_voice", "The report was written by the intern.")
    assert [finding.matched_text for finding in findings] == ["was written"]


def test_passive_voice_triggers_on_regular_participle(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "passive_voice", "The draft is reviewed each week.")
    assert [finding.matched_text for finding in findings] == ["is reviewed"]


def test_passive_voice_ignores_active_voice(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "passive_voice", "The intern wrote the report.")


def test_passive_voice_exception_suppresses_adjectival_participle(
    auditor: StyleAuditor,
) -> None:
    assert not findings_for(auditor, "passive_voice", "The team is interested in the results.")


def test_passive_voice_triggers_on_regular_participle_at_punctuation(
    auditor: StyleAuditor,
) -> None:
    findings = findings_for(auditor, "passive_voice", "The report was updated.")
    assert [finding.matched_text for finding in findings] == ["was updated"]


def test_passive_voice_triggers_on_by_phrase_and_prepositions(
    auditor: StyleAuditor,
) -> None:
    assert findings_for(auditor, "passive_voice", "The config was stored in the vault.")
    assert findings_for(auditor, "passive_voice", "The notes were shared with the team.")
    assert findings_for(auditor, "passive_voice", "The logs were rotated by the scheduler.")


def test_passive_voice_ignores_adjectival_continuation(auditor: StyleAuditor) -> None:
    # "indeed the" is not a supported relationship continuation, so the
    # precision-first regular branch leaves this unmatched.
    assert not findings_for(auditor, "passive_voice", "It is indeed the case.")


def test_passive_voice_added_exceptions_suppress_matches(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "passive_voice", "The plan was indeed, however, wrong.")
    assert not findings_for(auditor, "passive_voice", "The plan was naked.")
    assert not findings_for(auditor, "passive_voice", "This is beloved by all.")
    assert not findings_for(auditor, "passive_voice", "The story was wicked.")
    assert not findings_for(auditor, "passive_voice", "The flag was ragged.")


def test_passive_finding_survives_distant_same_line_exception(
    auditor: StyleAuditor,
) -> None:
    text = "The code was written by the team and he was interested in art."
    findings = findings_for(auditor, "passive_voice", text)
    assert [finding.matched_text for finding in findings] == ["was written"]


def test_false_range_flags_line_final_and_end_of_string_ranges(
    auditor: StyleAuditor,
) -> None:
    findings = findings_for(auditor, "false_range", "We went from draft to final\nNext line.")
    assert [finding.matched_text for finding in findings] == ["from draft to final"]
    findings = findings_for(auditor, "false_range", "We went from draft to final.")
    assert [finding.matched_text for finding in findings] == ["from draft to final"]


def test_theatrical_opener_requires_punctuation(auditor: StyleAuditor) -> None:
    assert findings_for(auditor, "theatrical_opener", "Real talk: the market shifted.")
    assert findings_for(auditor, "theatrical_opener", "Real talk, the market shifted.")
    assert not findings_for(auditor, "theatrical_opener", "Real talk about scaling follows.")


def test_hedging_triggers_on_single_word(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "hedging", "The plan is somewhat risky.")
    assert [finding.matched_text for finding in findings] == ["somewhat"]


def test_hedging_triggers_on_phrase(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "hedging", "To some extent, that is true.")
    assert [finding.matched_text.lower() for finding in findings] == ["to some extent"]


def test_hedging_ignores_confident_statement(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "hedging", "The plan is risky.")


def test_hedging_exception_suppresses_taxonomic_kind_of(auditor: StyleAuditor) -> None:
    # "a kind of" names a category rather than hedging, so the exception applies.
    assert not findings_for(auditor, "hedging", "It is a kind of tree.")
    # "kind of" without the category framing is still a review candidate.
    assert findings_for(auditor, "hedging", "It is kind of slow.")


def test_passive_and_hedging_are_info_severity(auditor: StyleAuditor) -> None:
    passive = findings_for(auditor, "passive_voice", "The report was written today.")
    hedging = findings_for(auditor, "hedging", "It is perhaps too soon.")
    assert all(finding.severity == "info" for finding in passive + hedging)


def test_hype_and_superficial_analysis_trigger_together(auditor: StyleAuditor) -> None:
    text = "This is huge, underscoring the point"
    assert findings_for(auditor, "hype_phrases", text)
    assert findings_for(auditor, "superficial_analysis", text)


def test_negative_listing_triggers_on_stacked_not_openers(auditor: StyleAuditor) -> None:
    findings = findings_for(auditor, "negative_listing", "Not fast. Not cheap. Pick one.")
    assert findings
    assert findings[0].matched_text.startswith("Not")


def test_negative_listing_ignores_single_not_opener(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "negative_listing", "Not fast. Pick one.")


def test_negative_parallelism_triggers(auditor: StyleAuditor) -> None:
    assert findings_for(
        auditor, "negative_parallelism", "This is not a shortcut, but a safer route."
    )


def test_negative_parallelism_ignores_direct_statement(auditor: StyleAuditor) -> None:
    assert not findings_for(
        auditor, "negative_parallelism", "This safer route takes more time."
    )


def test_negative_parallelism_accepts_its_contraction(auditor: StyleAuditor) -> None:
    assert findings_for(
        auditor, "negative_parallelism", "It was not a bug, it's a feature"
    )


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
    assert findings_for(
        auditor, "metadiscourse_openers", "In this article, we compare the plans."
    )


def test_metadiscourse_openers_ignores_direct_opening(auditor: StyleAuditor) -> None:
    assert not findings_for(
        auditor, "metadiscourse_openers", "The plans differ in cost and storage."
    )


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


def test_importance_puffery_triggers(auditor: StyleAuditor) -> None:
    assert findings_for(
        auditor, "importance_puffery", "This was a pivotal moment for the team."
    )


def test_throat_clearing_triggers(auditor: StyleAuditor) -> None:
    assert findings_for(auditor, "throat_clearing", "Here's the thing about speed.")


def test_faux_insight_triggers(auditor: StyleAuditor) -> None:
    assert findings_for(auditor, "faux_insight", "What most people get wrong is timing.")


def test_recap_endings_triggers(auditor: StyleAuditor) -> None:
    assert findings_for(auditor, "recap_endings", "In conclusion, ship the smaller change.")
    assert findings_for(auditor, "recap_endings", "Ultimately, ship the smaller change.")


def test_recap_endings_requires_comma_after_ultimately(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "recap_endings", "He ultimately succeeded.")
    assert findings_for(auditor, "recap_endings", "Ultimately, ship it.")
