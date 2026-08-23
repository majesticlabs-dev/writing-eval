"""Corpus CLI rule-loading behavior driven by the `--rules` option."""

import json
from pathlib import Path

import pytest

from tests.helpers_cli import load_run_eval_module, write_jsonl


def eval_inputs(tmp_path: Path) -> tuple[Path, Path]:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system.jsonl", [{"id": "out-1", "text": "Output text here."}])
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "ref-1", "text": "Reference text here."}])
    return outputs, references


def run_eval(tmp_path: Path, rules_path: Path, json_path: Path | None = None) -> int:
    module = load_run_eval_module()
    outputs, references = eval_inputs(tmp_path)
    argv = [
        "eval",
        "--outputs", str(outputs),
        "--references", str(references),
        "--report", str(tmp_path / "report.md"),
        "--rules", str(rules_path),
    ]
    if json_path is not None:
        argv.extend(["--json", str(json_path)])
    return module.main(argv)


def test_rules_version_date_scalar_is_coerced_and_serialized(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        "version: 2026-07-16\n"
        "rules:\n"
        "  - id: em_dash_ban\n"
        "    severity: warn\n"
        "    detector: '\\u2014'\n"
        "    message: Replace it.\n"
        "    exceptions: []\n",
        encoding="utf-8",
    )
    json_report = tmp_path / "report.json"

    assert run_eval(tmp_path, rules_path, json_report) == 0
    raw = json_report.read_text(encoding="utf-8")
    assert json.loads(raw)["provenance"]["rule_set"]["version"] == "2026-07-16"
    assert '"2026-07-16"' in raw


def test_style_rule_load_failure_is_clean_user_error(tmp_path: Path, capsys) -> None:
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        "rules:\n"
        "  - id: typo_rule\n"
        "    severity: info\n"
        "    detector: repeated_openigns\n"
        "    message: Fix it.\n",
        encoding="utf-8",
    )

    result = run_eval(tmp_path, rules_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "could not load style-audit rules" in captured.err
    assert "unknown named detector" in captured.err
    assert "Traceback" not in captured.err
    assert len(captured.err.strip().splitlines()) == 1


def test_empty_style_rule_set_is_clean_user_error(tmp_path: Path, capsys) -> None:
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("version: 1\nrules: []\n", encoding="utf-8")

    result = run_eval(tmp_path, rules_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "empty rule set" in captured.err
    assert "Traceback" not in captured.err


def test_style_audit_programming_defect_propagates(tmp_path: Path) -> None:
    module = load_run_eval_module()

    def boom(_text: str, _rules: object) -> list:
        raise RuntimeError("engine exploded")

    module._audit_text = boom
    outputs, references = eval_inputs(tmp_path)
    with pytest.raises(RuntimeError, match="engine exploded"):
        module.main(
            [
                "eval",
                "--outputs", str(outputs),
                "--references", str(references),
                "--report", str(tmp_path / "report.md"),
            ]
        )


def test_check_audit_programming_defect_propagates(tmp_path: Path) -> None:
    module = load_run_eval_module()

    def boom(_text: str, _rules: object) -> list:
        raise RuntimeError("engine exploded")

    module._audit_text = boom
    draft = tmp_path / "draft.md"
    draft.write_text("Hello world.\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="engine exploded"):
        module.main(["check", str(draft)])
