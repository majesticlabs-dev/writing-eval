"""Failure, timeout, and validation behavior for generation runs."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers_generate_runs import (
    make_fake_codex,
    read_jsonl,
    run_generate_runs,
    write_config,
    write_jsonl,
)


def _write_prompt(tmp_path: Path, prompt: str = "Hi.") -> Path:
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "a", "prompt": prompt}])
    return prompts_path


def test_timeout_retries_then_fails_with_timeout_diagnostics(
    tmp_path: Path,
) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        "--timeout", "1",
        behavior="hang",
    )

    assert result.returncode == 1
    assert "failure_kind=timeout" in result.stderr
    assert "Traceback" not in result.stderr
    assert read_jsonl(out_path) == []
    meta = json.loads((tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8"))
    diagnostics = meta["diagnostics"]["p-1"]
    assert diagnostics["failure_kind"] == "timeout"
    assert diagnostics["returncode"] is None


def test_nonzero_exit_diagnostics_name_the_failure_kind(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="fail_always",
    )

    assert result.returncode == 1
    assert "failure_kind=nonzero_exit, exit=1" in result.stderr
    meta = json.loads(
        (tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8")
    )
    diagnostics = meta["diagnostics"]["p-1"]
    assert diagnostics["failure_kind"] == "nonzero_exit"
    assert diagnostics["returncode"] == 1


def test_empty_output_diagnostics_name_the_failure_kind(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="empty_always",
    )

    assert result.returncode == 1
    assert "failure_kind=empty_output" in result.stderr
    meta = json.loads(
        (tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8")
    )
    diagnostics = meta["diagnostics"]["p-1"]
    assert diagnostics["failure_kind"] == "empty_output"
    assert diagnostics["returncode"] == 0


def test_missing_codex_executable_is_a_clean_user_error(tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", tmp_path / "definitely_missing_codex",
    )

    assert result.returncode == 2
    assert "codex executable not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_undecodable_lastmsg_output_is_a_clean_user_error(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="bad_utf8_lastmsg",
    )

    assert result.returncode == 2
    assert "could not decode codex output" in result.stderr
    assert "Traceback" not in result.stderr


def test_generate_mode_rejects_source_argument(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--source", prompts_path,
        "--codex-cmd", fake_codex,
    )

    assert result.returncode == 2
    assert "--source is only valid when --mode revise" in result.stderr
    assert "Traceback" not in result.stderr


def test_nonnegative_argument_validation(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = _write_prompt(tmp_path)
    common = (
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
    )

    result = run_generate_runs(tmp_path, *common, "--max-records", "-1")
    assert result.returncode == 2
    assert "--max-records must not be negative" in result.stderr

    result = run_generate_runs(tmp_path, *common, "--sleep", "-0.5")
    assert result.returncode == 2
    assert "--sleep must not be negative" in result.stderr

    result = run_generate_runs(tmp_path, *common, "--sleep", "nan")
    assert result.returncode == 2
    assert "--sleep must be a finite value greater than or equal to zero" in result.stderr
    assert "Traceback" not in result.stderr

    result = run_generate_runs(tmp_path, *common, "--sleep", "inf")
    assert result.returncode == 2
    assert "--sleep must be a finite value greater than or equal to zero" in result.stderr
    assert "Traceback" not in result.stderr

    result = run_generate_runs(tmp_path, *common, "--timeout", "0")
    assert result.returncode == 2
    assert "--timeout must be a finite value greater than zero" in result.stderr

    result = run_generate_runs(tmp_path, *common, "--timeout", "nan")
    assert result.returncode == 2
    assert "--timeout must be a finite value greater than zero" in result.stderr


def test_invalid_utf8_prompts_and_config_are_clean_user_errors(
    tmp_path: Path,
) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    prompts_path.write_bytes(b'{"id": "p-1", "prompt": "\xff\xfe"}\n')

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
    )
    assert result.returncode == 2
    assert "could not decode" in result.stderr
    assert "UTF-8" in result.stderr
    assert "Traceback" not in result.stderr

    config_path.write_bytes(b'{"frozen_decoding": {"model": "\xff"}}')
    prompts_path.write_text('{"id": "p-1", "prompt": "Hi."}\n', encoding="utf-8")
    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", tmp_path / "out.jsonl",
        "--mode", "generate",
        "--codex-cmd", fake_codex,
    )
    assert result.returncode == 2
    assert "could not decode config" in result.stderr
    assert "Traceback" not in result.stderr
