"""Corpus CLI input validation."""

from pathlib import Path

import pytest

from tests.helpers_cli import cli_with_inputs, load_run_eval_module, run_cli, write_jsonl

def test_invalid_utf8_references_is_clean_user_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system.jsonl", [{"id": "out-1", "text": "Output."}])
    references = tmp_path / "references.jsonl"
    references.write_bytes(b'{"id": "one", "text": "bad \xff byte"}\n')
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
    )
    assert result.returncode == 1
    assert "could not decode" in result.stderr
    assert "UTF-8" in result.stderr
    assert "Traceback" not in result.stderr

def test_empty_reference_file_is_clean_user_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system.jsonl", [{"id": "out-1", "text": "Output."}])
    references = tmp_path / "references.jsonl"
    references.write_text("\n", encoding="utf-8")
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
    )
    assert result.returncode == 1
    assert "references file is empty" in result.stderr
    assert "Traceback" not in result.stderr


def test_empty_output_file_is_clean_user_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "system.jsonl").write_text("\n", encoding="utf-8")
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "ref-1", "text": "Reference."}])
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
    )
    assert result.returncode == 1
    assert "output file is empty" in result.stderr
    assert "Traceback" not in result.stderr


def test_blank_output_text_is_clean_user_error(tmp_path: Path) -> None:
    result = cli_with_inputs(
        tmp_path,
        [{"id": "ref-1", "text": "Reference."}],
        {"system-a": [{"id": "out-1", "text": "  \t"}]},
    )
    assert result.returncode == 1
    assert "nonempty string text" in result.stderr
    assert "Traceback" not in result.stderr


def test_blank_reference_text_is_clean_user_error(tmp_path: Path) -> None:
    result = cli_with_inputs(
        tmp_path,
        [{"id": "ref-1", "text": "\n  "}],
        {"system-a": [{"id": "out-1", "text": "Output."}]},
    )
    assert result.returncode == 1
    assert "nonempty string text" in result.stderr
    assert "Traceback" not in result.stderr


def test_zero_word_token_text_is_clean_user_error(tmp_path: Path) -> None:
    result = cli_with_inputs(
        tmp_path,
        [{"id": "ref-1", "text": "Reference."}],
        {"system-a": [{"id": "out-1", "text": "!!! ???"}]},
    )
    assert result.returncode == 1
    assert "at least one word token" in result.stderr
    assert "Traceback" not in result.stderr



def test_empty_and_duplicate_ids_are_clean_user_errors(tmp_path: Path) -> None:
    duplicate_result = cli_with_inputs(
        tmp_path / "duplicate",
        [{"id": "ref-1", "text": "Reference."}],
        {
            "system-a": [
                {"id": "out-1", "text": "Output."},
                {"id": "out-1", "text": "Again."},
            ]
        },
    )
    assert duplicate_result.returncode == 1
    assert "duplicate id" in duplicate_result.stderr

    empty_id_result = cli_with_inputs(
        tmp_path / "empty-id",
        [{"id": "ref-1", "text": "Reference."}],
        {"system-a": [{"id": "", "text": "Output."}]},
    )
    assert empty_id_result.returncode == 1
    assert "nonempty string id" in empty_id_result.stderr


def test_output_systems_require_identical_ids_but_references_can_differ(
    tmp_path: Path,
) -> None:
    allowed = cli_with_inputs(
        tmp_path / "allowed",
        [{"id": "reference-only", "text": "Reference."}],
        {
            "system-a": [{"id": "prompt-1", "text": "Output."}],
            "system-b": [{"id": "prompt-1", "text": "Another output."}],
        },
    )
    assert allowed.returncode == 0, allowed.stderr

    rejected = cli_with_inputs(
        tmp_path / "rejected",
        [{"id": "reference-only", "text": "Reference."}],
        {
            "system-a": [{"id": "prompt-1", "text": "Output."}],
            "system-b": [{"id": "prompt-2", "text": "Another output."}],
        },
    )
    assert rejected.returncode == 1
    assert "identical id sets" in rejected.stderr


def test_invalid_utf8_rules_file_is_clean_user_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system.jsonl", [{"id": "out-1", "text": "Output text here."}])
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "ref-1", "text": "Reference text here."}])
    rules = tmp_path / "rules.yaml"
    rules.write_bytes(b"rules:\n  - id: probe\n    severity: warn\n    detector: x\n    message: bad \xff\n")
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
        "--rules",
        rules,
    )
    assert result.returncode == 1
    assert "could not load style-audit rules" in result.stderr
    assert "Traceback" not in result.stderr
