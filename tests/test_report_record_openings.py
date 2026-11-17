"""Record-opening diagnostics remain ordered, informational, and transparent."""

import json
from pathlib import Path

from tests.helpers_cli import run_cli
from writing_eval.item_sets import record_openings
from writing_eval.report import build_report, render_markdown


def test_email_subjects_show_cross_record_shared_leads() -> None:
    texts = [
        "Your order #1001 has shipped.",
        "Your order #1002 was delivered.",
        "Your order #1003 was refunded.",
        "Shipped: order #1004.",
    ]
    report = build_report("emails", texts, ["Orders arrive."], [])
    assert report["record_openings"] == {
        "record_count": 4, "distinct_lead_count": 2,
        "shared_lead_record_rate": 0.75,
        "top_shared_leads": [{"lead": "your order", "record_count": 3}],
    }
    assert build_report("emails", reversed(texts), ["Orders arrive."], []) == report
    assert "record_openings" not in report["metrics"]
    rendered = render_markdown(report)
    assert "### Record Openings (informational)" in rendered
    assert "| your order | 3 |" in rendered
    assert "do not affect the decision gate" in rendered


def test_ties_are_lexical_and_only_top_five_are_displayed() -> None:
    texts = [f"{word} lead" for word in ("z", "y", "x", "w", "v", "u") for _ in range(2)]
    result = record_openings(texts)
    assert result["distinct_lead_count"] == 6
    assert result["shared_lead_record_rate"] == 1.0
    assert [row["lead"] for row in result["top_shared_leads"]] == [
        "u lead", "v lead", "w lead", "x lead", "y lead",
    ]


def test_empty_and_tokenless_data_do_not_become_shared_leads() -> None:
    assert record_openings([]) == {
        "record_count": 0, "distinct_lead_count": 0,
        "shared_lead_record_rate": None, "top_shared_leads": [],
    }
    assert record_openings(["", "!!!", "Yes", "yes"]) == {
        "record_count": 4, "distinct_lead_count": 1,
        "shared_lead_record_rate": 0.5,
        "top_shared_leads": [{"lead": "yes", "record_count": 2}],
    }
    assert record_openings(["", "!!!"])["shared_lead_record_rate"] is None
    rendered = render_markdown(build_report("empty", [], [], []))
    assert "Shared-lead record rate: n/a" in rendered


def test_sample_corpus_opening_counts_through_cli(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = run_cli(
        "--outputs", "tests/fixtures/sample_outputs",
        "--references", "tests/fixtures/references.sample.jsonl",
        "--report", tmp_path / "report.md", "--json", output,
    )
    assert result.returncode == 0, result.stderr
    systems = {s["system_name"]: s for s in json.loads(output.read_text())["systems"]}
    assert systems["baseline-a"]["record_openings"] == {
        "record_count": 12, "distinct_lead_count": 12,
        "shared_lead_record_rate": 0.0, "top_shared_leads": [],
    }
    for name in ("baseline-b", "baseline-c"):
        assert systems[name]["record_openings"] == {
            "record_count": 12, "distinct_lead_count": 10,
            "shared_lead_record_rate": 0.25,
            "top_shared_leads": [{"lead": "it is", "record_count": 3}],
        }


def test_old_report_payload_without_opening_counts_still_renders() -> None:
    report = build_report("old", ["Editors write clearly."], [], [])
    del report["record_openings"]
    assert "Record Openings" not in render_markdown(report)
