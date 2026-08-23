"""CLI behavior for the benchmark wrapper scripts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUTS = FIXTURES / "sample_outputs"
REFERENCES = FIXTURES / "references.sample.jsonl"
RUN_EVAL = ROOT / "scripts" / "run_eval.py"
DECISION_GATE = ROOT / "benchmark" / "decision_gate.py"
NOISE_FLOOR = ROOT / "benchmark" / "noise_floor.py"
COMPARE_SYSTEMS = ROOT / "benchmark" / "compare_systems.py"


def run_script(script: Path, *arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def _eval_report(tmp_path: Path, name: str) -> Path:
    report_json = tmp_path / f"{name}.json"
    result = run_script(
        RUN_EVAL,
        "--outputs", OUTPUTS,
        "--references", REFERENCES,
        "--report", tmp_path / f"{name}.md",
        "--json", report_json,
    )
    assert result.returncode == 0, result.stderr
    return report_json


def _reset_gate_inputs(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "current.jsonl",
        [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}],
    )
    write_jsonl(
        tmp_path / "audited.jsonl",
        [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}],
    )
    write_jsonl(
        tmp_path / "references.jsonl",
        [{"id": "r1", "text": "Clear plans use direct words in references today."}],
    )
    write_jsonl(
        tmp_path / "eval_set.jsonl",
        [{"id": "a1", "word_count": 9}],
    )


def _gate_arguments(tmp_path: Path) -> list[object]:
    _reset_gate_inputs(tmp_path)
    return [
        "--current", tmp_path / "current.jsonl",
        "--audited", tmp_path / "audited.jsonl",
        "--references", tmp_path / "references.jsonl",
        "--eval-set", tmp_path / "eval_set.jsonl",
        "--tell-rate-threshold", "50",
        "--markdown", tmp_path / "gate.md",
        "--json", tmp_path / "gate.json",
    ]


def _blocked_path(tmp_path: Path) -> Path:
    blocker = tmp_path / "blocker"
    blocker.write_text("file blocks the directory", encoding="utf-8")
    return blocker / "out.md"


def test_decision_gate_happy_path_writes_outputs(tmp_path: Path) -> None:
    result = run_script(DECISION_GATE, *_gate_arguments(tmp_path))

    assert result.returncode == 0, result.stderr
    gate = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert gate["verdict"] in {"sufficient", "insufficient", "blocked"}
    assert "Decision Gate Report" in (tmp_path / "gate.md").read_text(encoding="utf-8")


def test_decision_gate_rejects_bad_inputs_with_exit_2(tmp_path: Path) -> None:
    arguments = _gate_arguments(tmp_path)

    missing = list(arguments)
    missing[1] = tmp_path / "missing.jsonl"
    result = run_script(DECISION_GATE, *missing)
    assert result.returncode == 2
    assert "current outputs file not found" in result.stderr
    assert "Traceback" not in result.stderr

    (tmp_path / "audited.jsonl").write_text("{not json}\n", encoding="utf-8")
    result = run_script(DECISION_GATE, *arguments)
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr

    _reset_gate_inputs(tmp_path)
    (tmp_path / "references.jsonl").write_bytes(b'{"id": "r1", "text": "\xff\xfe"}\n')
    result = run_script(DECISION_GATE, *arguments)
    assert result.returncode == 2
    assert "could not decode" in result.stderr
    assert "Traceback" not in result.stderr

    _reset_gate_inputs(tmp_path)
    unwritable = list(arguments)
    unwritable[13] = _blocked_path(tmp_path)
    result = run_script(DECISION_GATE, *unwritable)
    assert result.returncode == 2
    assert "could not write" in result.stderr


def test_noise_floor_happy_path_writes_outputs(tmp_path: Path) -> None:
    first = _eval_report(tmp_path, "run-one")
    second = _eval_report(tmp_path, "run-two")

    result = run_script(
        NOISE_FLOOR,
        "--runs", first, second,
        "--markdown", tmp_path / "floor.md",
        "--json", tmp_path / "floor.json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "floor.json").read_text(encoding="utf-8"))
    assert "aggregate" in payload
    assert "noise_floor" in payload


def test_noise_floor_rejects_bad_inputs_with_exit_2(tmp_path: Path) -> None:
    result = run_script(
        NOISE_FLOOR,
        "--runs", tmp_path / "missing.json",
        "--markdown", tmp_path / "floor.md",
        "--json", tmp_path / "floor.json",
    )
    assert result.returncode == 2
    assert "run report not found" in result.stderr
    assert "Traceback" not in result.stderr

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    result = run_script(
        NOISE_FLOOR,
        "--runs", malformed,
        "--markdown", tmp_path / "floor.md",
        "--json", tmp_path / "floor.json",
    )
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr

    undecodable = tmp_path / "undecodable.json"
    undecodable.write_bytes(b'{"systems": "\xff\xfe"}')
    result = run_script(
        NOISE_FLOOR,
        "--runs", undecodable,
        "--markdown", tmp_path / "floor.md",
        "--json", tmp_path / "floor.json",
    )
    assert result.returncode == 2
    assert "could not decode" in result.stderr

    result = run_script(
        NOISE_FLOOR,
        "--runs", _eval_report(tmp_path, "run-one"), _eval_report(tmp_path, "run-two"),
        "--markdown", _blocked_path(tmp_path),
        "--json", tmp_path / "floor.json",
    )
    assert result.returncode == 2
    assert "could not write" in result.stderr


def test_compare_systems_happy_path_writes_outputs(tmp_path: Path) -> None:
    report = _eval_report(tmp_path, "report")

    result = run_script(
        COMPARE_SYSTEMS,
        "--report", report,
        "--system-a", "baseline-a",
        "--system-b", "baseline-b",
        "--markdown", tmp_path / "compare.md",
        "--json", tmp_path / "compare.json",
    )

    assert result.returncode == 0, result.stderr
    comparison = json.loads((tmp_path / "compare.json").read_text(encoding="utf-8"))
    assert comparison["system_a"] == "baseline-a"
    assert "System Comparison" in (tmp_path / "compare.md").read_text(encoding="utf-8")


def test_compare_systems_rejects_bad_inputs_with_exit_2(tmp_path: Path) -> None:
    result = run_script(
        COMPARE_SYSTEMS,
        "--report", tmp_path / "missing.json",
        "--system-a", "baseline-a",
        "--system-b", "baseline-b",
        "--markdown", tmp_path / "compare.md",
        "--json", tmp_path / "compare.json",
    )
    assert result.returncode == 2
    assert "report not found" in result.stderr
    assert "Traceback" not in result.stderr

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    result = run_script(
        COMPARE_SYSTEMS,
        "--report", malformed,
        "--system-a", "baseline-a",
        "--system-b", "baseline-b",
        "--markdown", tmp_path / "compare.md",
        "--json", tmp_path / "compare.json",
    )
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr

    undecodable = tmp_path / "undecodable.json"
    undecodable.write_bytes(b'{"systems": "\xff\xfe"}')
    result = run_script(
        COMPARE_SYSTEMS,
        "--report", undecodable,
        "--system-a", "baseline-a",
        "--system-b", "baseline-b",
        "--markdown", tmp_path / "compare.md",
        "--json", tmp_path / "compare.json",
    )
    assert result.returncode == 2
    assert "could not decode" in result.stderr

    result = run_script(
        COMPARE_SYSTEMS,
        "--report", _eval_report(tmp_path, "report"),
        "--system-a", "baseline-a",
        "--system-b", "baseline-b",
        "--markdown", tmp_path / "compare.md",
        "--json", _blocked_path(tmp_path),
    )
    assert result.returncode == 2
    assert "could not write" in result.stderr
