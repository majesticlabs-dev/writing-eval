"""Diagnostic-family behavior of the builtin style-audit rule set."""

import pytest

from writing_eval.style_audit import StyleAuditor

from tests.helpers_rules_content import builtin_auditor, findings_for


@pytest.fixture(scope="module")
def auditor() -> StyleAuditor:
    return builtin_auditor()


@pytest.mark.parametrize(
    ("rule_id", "text"),
    [
        ("collaborative_artifacts", "I hope this helps. Let me know if you'd like more."),
        ("knowledge_gap_boilerplate", "Based on available information, the date is unknown."),
        ("copula_avoidance", "The room serves as the main gallery."),
        ("generic_positive_conclusion", "The future looks bright for the company."),
        ("inline_header_list", "- **Speed:** Pages load in 20 milliseconds."),
        ("aphorism_formula", "Attention is the currency of the internet."),
        ("theatrical_opener", "Honestly? The price depends on usage."),
    ],
)
def test_phrase_diagnostics_trigger(
    auditor: StyleAuditor, rule_id: str, text: str
) -> None:
    findings = findings_for(auditor, rule_id, text)
    assert findings
    assert all(finding.severity == "info" for finding in findings)


@pytest.mark.parametrize(
    ("rule_id", "text"),
    [
        ("collaborative_artifacts", "The guide includes three worked examples."),
        ("knowledge_gap_boilerplate", "The source does not state a founding date."),
        ("copula_avoidance", "The room is the main gallery."),
        ("generic_positive_conclusion", "The company will open its second store in May."),
        ("inline_header_list", "- Pages load in 20 milliseconds."),
        ("aphorism_formula", "Attention affects which posts people remember."),
        ("theatrical_opener", "The price depends on usage."),
    ],
)
def test_phrase_diagnostics_ignore_plain_alternatives(
    auditor: StyleAuditor, rule_id: str, text: str
) -> None:
    assert not findings_for(auditor, rule_id, text)


def test_fragmented_header_finds_short_warmup(auditor: StyleAuditor) -> None:
    text = "## Performance\n\nSpeed matters.\n\nUsers leave slow pages."
    findings = findings_for(auditor, "fragmented_header", text)
    assert [finding.matched_text for finding in findings] == ["Speed matters."]


def test_fragmented_header_ignores_substantive_opening(auditor: StyleAuditor) -> None:
    text = (
        "## Performance\n\n"
        "Users leave pages that take several seconds to respond.\n\n"
        "Caching removes repeated database work."
    )
    assert not findings_for(auditor, "fragmented_header", text)


def test_fragmented_header_does_not_cross_into_next_heading(
    auditor: StyleAuditor,
) -> None:
    text = "## Introduction\n\nA short note.\n\n## Next section\n\nDetails follow."
    assert not findings_for(auditor, "fragmented_header", text)


def test_manufactured_staccato_finds_four_short_sentences(auditor: StyleAuditor) -> None:
    text = "The launch slipped. Customers waited. Sales stalled. Support calls grew."
    findings = findings_for(auditor, "manufactured_staccato", text)
    assert len(findings) == 1
    assert findings[0].matched_text == text


def test_manufactured_staccato_ignores_three_sentences_and_lists(
    auditor: StyleAuditor,
) -> None:
    assert not findings_for(
        auditor, "manufactured_staccato", "The launch slipped. Customers waited. Sales stalled."
    )
    list_text = "- Review logs.\n- Compare traces.\n- Reproduce locally.\n- Patch the cause."
    assert not findings_for(auditor, "manufactured_staccato", list_text)


@pytest.mark.parametrize(
    ("rule_id", "severity", "text"),
    [
        ("filler_phrases", "warn", "Use a lock in order to protect the file."),
        ("predicate_hyphenation", "info", "The report is high-quality."),
        (
            "false_range",
            "info",
            "The guide covers everything from databases to design philosophy.",
        ),
        ("diff_anchored", "warn", "This replaces the previous cache policy."),
        ("title_case_heading", "info", "## A Complete Guide To System Design Patterns"),
        ("emoji_usage", "warn", "The deployment succeeded. \U0001F680"),
        ("subjectless_fragment", "info", "No configuration needed."),
        (
            "boldface_density",
            "info",
            "Use **short names**, record **exact times**, and cite **primary sources**.",
        ),
    ],
)
def test_late_diagnostics_trigger(
    auditor: StyleAuditor, rule_id: str, severity: str, text: str
) -> None:
    findings = findings_for(auditor, rule_id, text)
    assert findings
    assert all(finding.severity == severity for finding in findings)


@pytest.mark.parametrize(
    ("rule_id", "text"),
    [
        ("filler_phrases", "Use a lock to protect the file."),
        ("predicate_hyphenation", "The team hired a cross-functional group."),
        ("false_range", "The store is open from 9 to 5."),
        ("diff_anchored", "The cache stores the current policy."),
        ("diff_anchored", "Our deployment pipeline used to be a mess, honestly."),
        ("title_case_heading", "## Using the API correctly"),
        ("emoji_usage", "The deployment succeeded."),
        ("subjectless_fragment", "The configuration is not needed here."),
        ("boldface_density", "**Heading-like line**"),
    ],
)
def test_late_diagnostics_ignore_near_misses(
    auditor: StyleAuditor, rule_id: str, text: str
) -> None:
    assert not findings_for(auditor, rule_id, text)


def test_subjectless_fragment_ignores_reference_phrase(auditor: StyleAuditor) -> None:
    assert not findings_for(auditor, "subjectless_fragment", "No data yet.")


def test_subjectless_fragment_finds_bare_participle(auditor: StyleAuditor) -> None:
    findings = findings_for(
        auditor, "subjectless_fragment", "Results preserved automatically."
    )
    assert [finding.matched_text for finding in findings] == [
        "Results preserved automatically."
    ]


def test_boldface_density_anchors_one_finding_per_paragraph(
    auditor: StyleAuditor,
) -> None:
    text = "Keep this paragraph mostly plain but mark **one important detail**."
    findings = findings_for(auditor, "boldface_density", text)
    assert len(findings) == 1
    assert findings[0].matched_text == "**one important detail**"
    assert findings[0].char_offset == text.index("**one important detail**")
