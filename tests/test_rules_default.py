"""One canonical default rules path drives every entry point."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from writing_eval import cli_check, cli_eval
from writing_eval.style_audit import BUILTIN_RULES_PATH

from tests.helpers_cli import ROOT, SCRIPT, load_run_eval_module, write_jsonl

OVERLAY_YAML = """extends: builtin
rules:
  - id: passive_voice
    enabled: false
  - id: overlay_probe
    severity: warn
    detector: '(?i)\\boverlay probe\\b'
    message: Overlay probe fired.
"""


def load_script(name: str):
    path = ROOT / "benchmark" / name
    spec = importlib.util.spec_from_file_location(f"{path.stem}_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_for(parser, option: str) -> Path:
    (action,) = [item for item in parser._actions if option in item.option_strings]
    return action.default


def test_check_and_eval_parsers_default_to_the_builtin_rules_path() -> None:
    assert default_for(cli_check.parser(), "--rules") is BUILTIN_RULES_PATH
    assert default_for(cli_eval.parser(), "--rules") is BUILTIN_RULES_PATH


def test_decision_gate_defaults_to_the_builtin_rules_path() -> None:
    module = load_script("decision_gate.py")
    assert module._DEFAULT_RULES_PATH is BUILTIN_RULES_PATH
    assert default_for(module._parser(), "--rules") is BUILTIN_RULES_PATH


def test_generate_runs_defaults_to_the_builtin_rules_path() -> None:
    module = load_script("generate_runs.py")
    assert default_for(module._parser(), "--rules") is BUILTIN_RULES_PATH


def test_builtin_rules_path_is_absolute_and_present() -> None:
    assert BUILTIN_RULES_PATH.is_absolute()
    assert BUILTIN_RULES_PATH.is_file()


def _eval_inputs(tmp_path: Path) -> tuple[Path, Path]:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(
        outputs / "system.jsonl",
        [{"id": "out-1", "text": "The overlay probe ran. The draft was reviewed."}],
    )
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "ref-1", "text": "Reference text here."}])
    return outputs, references


def test_eval_rules_option_drives_both_loading_and_provenance(tmp_path: Path) -> None:
    module = load_run_eval_module()
    outputs, references = _eval_inputs(tmp_path)
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(OVERLAY_YAML, encoding="utf-8")
    json_report = tmp_path / "report.json"

    result = module.main(
        [
            "eval",
            "--outputs", str(outputs),
            "--references", str(references),
            "--report", str(tmp_path / "report.md"),
            "--json", str(json_report),
            "--rules", str(overlay),
        ]
    )
    assert result == 0
    data = json.loads(json_report.read_text(encoding="utf-8"))
    rule_set = data["provenance"]["rule_set"]
    # The path that was loaded is the path that is reported; there is one variable.
    assert rule_set["path"] == str(overlay)
    assert rule_set["rule_count"] == 34
    assert len(rule_set["fingerprint"]) == 64
    findings_by_rule = data["systems"][0]["findings_by_rule"]
    assert findings_by_rule.get("overlay_probe") == 1
    assert "passive_voice" not in findings_by_rule


def test_eval_default_rules_report_the_builtin_path(tmp_path: Path) -> None:
    module = load_run_eval_module()
    outputs, references = _eval_inputs(tmp_path)
    json_report = tmp_path / "report.json"

    result = module.main(
        [
            "eval",
            "--outputs", str(outputs),
            "--references", str(references),
            "--report", str(tmp_path / "report.md"),
            "--json", str(json_report),
        ]
    )
    assert result == 0
    data = json.loads(json_report.read_text(encoding="utf-8"))
    assert data["provenance"]["rule_set"]["path"] == str(BUILTIN_RULES_PATH)
    assert data["provenance"]["rule_set"]["rule_count"] == 34


def test_check_missing_rules_file_exits_one_without_traceback(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("The draft is short.\n", encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable, "-m", "writing_eval.cli", "check", str(draft),
            "--rules", str(tmp_path / "absent.yaml"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert process.returncode == 1
    assert "style-audit rules file not found" in process.stderr
    assert "Traceback" not in process.stderr
    assert len(process.stderr.strip().splitlines()) == 1


def test_eval_missing_rules_file_exits_one_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_run_eval_module()
    outputs, references = _eval_inputs(tmp_path)
    result = module.main(
        [
            "eval",
            "--outputs", str(outputs),
            "--references", str(references),
            "--report", str(tmp_path / "report.md"),
            "--rules", str(tmp_path / "absent.yaml"),
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    assert "style-audit rules file not found" in captured.err
    assert "Traceback" not in captured.err


def test_run_eval_script_still_wraps_the_eval_command(tmp_path: Path) -> None:
    outputs, references = _eval_inputs(tmp_path)
    process = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--outputs", str(outputs),
            "--references", str(references),
            "--report", str(tmp_path / "report.md"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert f"- Path: {BUILTIN_RULES_PATH}" in report
    assert "- Fingerprint: " in report
