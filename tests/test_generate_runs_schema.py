"""Prompt-schema validation for generation runs."""

from __future__ import annotations

from pathlib import Path

from tests.helpers_generate_runs import (
    make_fake_codex,
    run_generate_runs,
    write_config,
    write_jsonl,
)


def test_generate_rejects_invalid_use_case_with_line_error(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(
        prompts_path,
        [
            {
                "id": "p-1",
                "use_case": "article_section",
                "prompt": "Valid prompt.",
            },
            {"id": "p-2", "use_case": "poetry", "prompt": "Bad use case."},
        ],
    )

    result = run_generate_runs(
        tmp_path,
        "--prompts",
        prompts_path,
        "--config",
        config_path,
        "--out",
        tmp_path / "out.jsonl",
        "--mode",
        "generate",
        "--codex-cmd",
        fake_codex,
        behavior="default",
    )

    assert result.returncode == 2
    assert "at line 2" in result.stderr
    assert "use_case must be one of article_section, product_writing, exec_communication" in result.stderr
    assert "Traceback" not in result.stderr


def test_generate_rejects_missing_and_blank_use_case(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "prompt": "No use case."}])

    result = run_generate_runs(
        tmp_path,
        "--prompts",
        prompts_path,
        "--config",
        config_path,
        "--out",
        tmp_path / "out.jsonl",
        "--mode",
        "generate",
        "--codex-cmd",
        fake_codex,
        behavior="default",
    )

    assert result.returncode == 2
    assert "at line 1" in result.stderr
    assert "expected a nonempty string use_case" in result.stderr
    assert "Traceback" not in result.stderr

    write_jsonl(
        prompts_path,
        [{"id": "p-1", "use_case": "   ", "prompt": "Blank use case."}],
    )
    result = run_generate_runs(
        tmp_path,
        "--prompts",
        prompts_path,
        "--config",
        config_path,
        "--out",
        tmp_path / "out.jsonl",
        "--mode",
        "generate",
        "--codex-cmd",
        fake_codex,
        behavior="default",
    )
    assert result.returncode == 2
    assert "at line 1" in result.stderr
    assert "expected a nonempty string use_case" in result.stderr
    assert "Traceback" not in result.stderr
