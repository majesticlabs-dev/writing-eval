"""CLI validation for benchmark wrapper scripts."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_benchmark_cli import (
    COMPARE_SYSTEMS,
    DECISION_GATE,
    _gate_arguments,
    run_script,
    write_jsonl,
)


def test_decision_gate_rejects_duplicate_and_invalid_word_counts_with_exit_2(
    tmp_path: Path,
) -> None:
    arguments = _gate_arguments(tmp_path)
    write_jsonl(
        tmp_path / "eval_set.jsonl",
        [{"id": "a1", "word_count": 9}, {"id": "a1", "word_count": 4}],
    )
    result = run_script(DECISION_GATE, *arguments)
    assert result.returncode == 2
    assert "duplicate id 'a1'" in result.stderr
    assert "at line 2" in result.stderr
    assert "Traceback" not in result.stderr

    write_jsonl(tmp_path / "eval_set.jsonl", [{"id": "a1", "word_count": -1}])
    result = run_script(DECISION_GATE, *arguments)
    assert result.returncode == 2
    assert "expected a non-negative integer word_count" in result.stderr
    assert "at line 1" in result.stderr
    assert "Traceback" not in result.stderr

    write_jsonl(tmp_path / "eval_set.jsonl", [{"id": "a1", "word_count": True}])
    result = run_script(DECISION_GATE, *arguments)
    assert result.returncode == 2
    assert "expected a non-negative integer word_count" in result.stderr
    assert "Traceback" not in result.stderr


def test_compare_systems_rejects_nonfinite_values_with_exit_2(tmp_path: Path) -> None:
    report = {
        "systems": [
            {
                "system_name": "baseline-a",
                "metrics": {"tell_rate": float("nan")},
                "findings_by_severity": {},
            },
            {
                "system_name": "baseline-b",
                "metrics": {"tell_rate": 1.0},
                "findings_by_severity": {},
            },
        ]
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report, allow_nan=True), encoding="utf-8")
    result = run_script(
        COMPARE_SYSTEMS,
        "--report",
        report_path,
        "--system-a",
        "baseline-a",
        "--system-b",
        "baseline-b",
        "--markdown",
        tmp_path / "compare.md",
        "--json",
        tmp_path / "compare.json",
    )
    assert result.returncode == 2
    assert "metric 'tell_rate' value_a is not a finite number" in result.stderr
    assert "Traceback" not in result.stderr


def test_decision_gate_rejects_invalid_utf8_eval_set_with_exit_2(tmp_path: Path) -> None:
    """Decision gate with invalid UTF-8 eval set should exit with code 2 and no traceback."""
    arguments = _gate_arguments(tmp_path)

    # Create invalid UTF-8 eval_set.jsonl
    (tmp_path / "eval_set.jsonl").write_bytes(b'{"id": "a1", "word_count": \xff\xfe}\n')
    result = run_script(DECISION_GATE, *arguments)

    assert result.returncode == 2
    assert "could not decode" in result.stderr
    assert "UTF-8" in result.stderr
    assert "Traceback" not in result.stderr
