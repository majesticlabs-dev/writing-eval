from pathlib import Path

import pytest

from writing_eval.report import build_report, render_markdown
from writing_eval.schema import Finding


def sample_report() -> dict:
    finding = Finding("promo", "warning", "Avoid promo words", "best", 0, 1)
    return build_report(
        "system-a",
        ["We write clearly. We edit carefully."],
        ["They write simply. Editors revise."],
        [[finding]],
    )


def test_report_has_expected_structure_and_non_empty_metrics() -> None:
    report = sample_report()
    assert report["system_name"] == "system-a"
    assert report["document_count"] == 1
    assert report["word_count"] > 0
    assert report["finding_count"] == 1
    assert list(report["metrics"]) == [
        "tell_rate",
        "token_1gram_l2",
        "mean_sentence_length",
        "sentence_length_variance",
        "repeated_opening_rate",
    ]
    assert all(isinstance(value, float) for value in report["metrics"].values())
    assert any(value > 0 for value in report["metrics"].values())


def test_report_emits_severity_specific_tell_rates() -> None:
    finding = Finding("warn-rule", "warn", "Fix it", "match", 0, 1)
    report = build_report("system-a", ["One two."], ["Reference."], [[finding]])
    assert report["metrics"]["tell_rate"] == 500.0
    assert report["tell_rates_by_severity"] == {"warn": 500.0}


def test_report_repeated_opening_rate_does_not_cross_documents() -> None:
    first = build_report(
        "system-a", ["We start.", "We continue."], ["Reference."], [[]]
    )
    second = build_report(
        "system-a", ["We continue.", "We start."], ["Reference."], [[]]
    )
    assert first["metrics"]["repeated_opening_rate"] == 0.0
    assert second["metrics"]["repeated_opening_rate"] == 0.0


def test_provenance_contains_counts_hashes_paths_and_version(tmp_path: Path) -> None:
    from writing_eval.report import build_provenance

    references = tmp_path / "references.jsonl"
    rules = tmp_path / "rules.yaml"
    references.write_text('{"id":"r1","text":"One two."}\n', encoding="utf-8")
    rules.write_text("version: 1\nrules: []\n", encoding="utf-8")
    provenance = build_provenance(
        references,
        [{"id": "r1", "text": "One two."}],
        rules,
        0,
        1,
        "deadbeef",
    )
    assert provenance["reference_corpus"]["record_count"] == 1
    assert provenance["reference_corpus"]["word_count"] == 2
    assert provenance["reference_corpus"]["path"] == str(references)
    assert len(provenance["reference_corpus"]["sha256"]) == 64
    assert provenance["rule_set"]["rule_count"] == 0
    assert provenance["rule_set"]["version"] == 1
    assert len(provenance["rule_set"]["sha256"]) == 64
    assert provenance["rule_set"]["fingerprint"] == "deadbeef"


def test_findings_by_rule_counts_and_markdown_section() -> None:
    findings = [
        Finding("promo", "warn", "m", "best", 0, 1),
        Finding("promo", "warn", "m", "great", 5, 1),
        Finding("em_dash_ban", "warn", "m", "x", 9, 1),
    ]
    report = build_report("sys", ["Text one. Text two."], ["Ref text."], [findings])
    assert report["findings_by_rule"] == {"em_dash_ban": 1, "promo": 2}

    markdown = render_markdown({"systems": [report]})
    assert "### Findings by Rule" in markdown
    assert "- em_dash_ban: 1" in markdown
    assert "- promo: 2" in markdown
    assert markdown.index("### Findings by Severity") < markdown.index(
        "### Findings by Rule"
    )


def test_findings_by_rule_renders_none_when_empty() -> None:
    report = build_report("sys", ["Short text."], ["Ref text."], [[]])
    markdown = render_markdown({"systems": [report]})
    section = markdown.split("### Findings by Rule", 1)[1]
    assert section.lstrip().startswith("- None")


def test_missing_metric_key_raises_in_markdown() -> None:
    system = {
        "system_name": "sys",
        "document_count": 1,
        "word_count": 1,
        "finding_count": 0,
        "findings_by_severity": {},
        "findings_by_rule": {},
        "tell_rates_by_severity": {},
        "metrics": {},
        "top_overrepresented": [],
    }
    with pytest.raises(KeyError):
        render_markdown({"systems": [system]})


def test_none_metric_renders_as_na_in_markdown() -> None:
    report = sample_report()
    report["metrics"]["token_1gram_l2"] = None
    markdown = render_markdown({"systems": [report]})
    assert "| Token 1-gram L2 | n/a |" in markdown


def test_markdown_is_deterministic_and_contains_system_sections() -> None:
    data = {"systems": [sample_report(), build_report("system-b", ["Short text."], ["Reference text."], [[]])]}
    first = render_markdown(data)
    second = render_markdown(data)
    assert first == second
    assert "## System: system-a" in first
    assert "## System: system-b" in first
    assert "| Tell rate per 1,000 words |" in first
    assert first.index("Tell rate per 1,000 words") < first.index("Token 1-gram L2")


def test_render_accepts_one_system_report() -> None:
    markdown = render_markdown(sample_report())
    assert markdown.startswith("# Writing Evaluation Report\n")
    assert markdown.endswith("\n")


def test_markdown_renders_provenance_and_severity_rates() -> None:
    data = {
        "provenance": {
            "reference_corpus": {
                "path": "references.jsonl",
                "record_count": 1,
                "word_count": 2,
                "sha256": "ref-hash",
            },
            "rule_set": {
                "path": "rules.yaml",
                "version": 1,
                "rule_count": 1,
                "sha256": "rules-hash",
                "fingerprint": "some-fingerprint",
            },
        },
        "systems": [sample_report()],
    }
    markdown = render_markdown(data)
    assert "### Reference Corpus" in markdown
    assert "- SHA-256: ref-hash" in markdown
    assert "### Rule Set" in markdown
    assert "- Version: 1" in markdown
    assert "- Fingerprint: some-fingerprint" in markdown
    assert "### Tell Rates by Severity" in markdown
    assert "| warning |" in markdown


def test_markdown_renders_unknown_for_missing_rules_version() -> None:
    data = {
        "provenance": {
            "reference_corpus": {
                "path": "references.jsonl",
                "record_count": 1,
                "word_count": 2,
                "sha256": "ref-hash",
            },
            "rule_set": {
                "path": "rules.yaml",
                "version": None,
                "rule_count": 1,
                "sha256": "rules-hash",
                "fingerprint": "some-fingerprint",
            },
        },
        "systems": [sample_report()],
    }
    markdown = render_markdown(data)
    assert "- Version: unknown" in markdown
    assert "- Version: None" not in markdown
