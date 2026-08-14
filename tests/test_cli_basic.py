"""Basic corpus CLI behavior."""

from importlib.metadata import version

import json
from pathlib import Path

from tests.helpers_cli import run_cli, write_jsonl

def test_version_reports_installed_release() -> None:
    result = run_cli("--version")

    assert result.returncode == 0
    assert result.stdout == f"writing-eval {version('writing-eval')}\n"
    assert result.stderr == ""


def test_unknown_command_is_a_focused_user_error() -> None:
    result = run_cli("chekc", "--outputs", "x")

    assert result.returncode == 1
    assert result.stderr == (
        "error: unknown command 'chekc'; expected one of: check, profile, eval\n"
    )


def test_help_still_prints_the_eval_parser() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "--outputs" in result.stdout


def test_missing_outputs_directory_is_clean_user_error(tmp_path: Path) -> None:
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "one", "text": "Reference."}])
    result = run_cli(
        "--outputs",
        tmp_path / "missing",
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
    )
    assert result.returncode == 1
    assert "outputs directory not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_references_file_is_clean_user_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system.jsonl", [{"id": "one", "text": "Output."}])
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        tmp_path / "missing.jsonl",
        "--report",
        tmp_path / "report.md",
    )
    assert result.returncode == 1
    assert "references file not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_valid_run_writes_markdown_and_json(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(
        outputs / "system-a.jsonl",
        [{"id": "one", "text": "We write. We revise."}],
    )
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "one", "text": "Editors write clearly."}])
    report = tmp_path / "report.md"
    json_report = tmp_path / "report.json"

    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        report,
        "--json",
        json_report,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert report.is_file() and report.stat().st_size > 0
    assert "## System: system-a" in report.read_text(encoding="utf-8")
    data = json.loads(json_report.read_text(encoding="utf-8"))
    assert data["systems"][0]["system_name"] == "system-a"
