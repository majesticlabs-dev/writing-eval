"""Regression tests for the within_allowance finding flag."""

import json
from pathlib import Path

from tests.helpers_profiles import run_cli


def test_cli_check_without_style_findings_have_within_allowance_false(
    tmp_path: Path,
) -> None:
    dash = chr(0x2014)
    draft = tmp_path / "draft.md"
    draft.write_text(f"Clear{dash}concise.\n", encoding="utf-8")
    result = run_cli("check", draft, "--format", "json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["findings"]
    assert all(finding["within_allowance"] is False for finding in payload["findings"])
    text_result = run_cli("check", draft)
    assert text_result.returncode == 0, text_result.stderr
    assert f"{draft}:1:6 [warn] em_dash_ban:" in text_result.stdout
    assert "within profile allowance:" not in text_result.stdout


def test_cli_check_style_within_allowance_marks_earliest_findings(
    tmp_path: Path,
) -> None:
    profiles_root = tmp_path / "profiles"
    sources = tmp_path / "sources"
    sources.mkdir()
    dash = chr(0x2014)
    (sources / "voice.md").write_text(
        f"Clear{dash}direct writing keeps teams aligned today.\n",
        encoding="utf-8",
    )
    built = run_cli(
        "profile", "build", "dashed", "--from", sources, "--profiles-root", profiles_root,
    )
    assert built.returncode == 0, built.stderr

    aligned_draft = tmp_path / "aligned.md"
    aligned_draft.write_text(
        f"Clear{dash}direct notes keep teams aligned.\n", encoding="utf-8"
    )
    aligned = run_cli(
        "check", aligned_draft, "--style", "dashed", "--profiles-root", profiles_root,
        "--format", "json",
    )
    assert aligned.returncode == 0, aligned.stderr
    aligned_payload = json.loads(aligned.stdout)
    aligned_dash_findings = [
        finding
        for finding in aligned_payload["findings"]
        if finding["rule_id"] == "em_dash_ban"
    ]
    assert aligned_dash_findings
    assert all(finding["within_allowance"] is True for finding in aligned_dash_findings)

    excess_draft = tmp_path / "excess.md"
    excess_draft.write_text(
        f"Clear{dash}direct notes stay short{dash}and specific.\n", encoding="utf-8",
    )
    excess = run_cli(
        "check", excess_draft, "--style", "dashed", "--profiles-root", profiles_root,
        "--format", "json",
    )
    assert excess.returncode == 0, excess.stderr
    excess_payload = json.loads(excess.stdout)
    excess_dash_findings = sorted(
        (
            finding
            for finding in excess_payload["findings"]
            if finding["rule_id"] == "em_dash_ban"
        ),
        key=lambda item: (item["line"], item["column"]),
    )
    assert len(excess_dash_findings) == 2
    assert excess_dash_findings[0]["within_allowance"] is True
    assert excess_dash_findings[1]["within_allowance"] is False
    assert excess_dash_findings[1]["severity"] == "warn"
