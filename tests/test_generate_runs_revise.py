"""Revision-run behavior tests."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers_generate_runs import (
    _EM_DASH,
    make_fake_codex,
    read_jsonl,
    run_generate_runs,
    write_config,
    write_jsonl,
)

def test_revise_mode_zero_findings_makes_no_codex_call(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "article_section", "prompt": "Ignored."}])
    source_path = tmp_path / "source.jsonl"
    clean_text = "This text has no style violations of any kind present."
    write_jsonl(source_path, [{"id": "p-1", "text": clean_text}])
    out_path = tmp_path / "out.jsonl"
    call_log = tmp_path / "calls.json"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "revise",
        "--source", source_path,
        "--codex-cmd", fake_codex,
        behavior="default",
        call_log=call_log,
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    assert records == [{"id": "p-1", "text": clean_text}]
    assert not call_log.exists()

    meta = json.loads((tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == {"p-1": "clean"}
    assert meta["residual_findings"] == {"p-1": []}
    assert meta["literal_preservation"]["p-1"]["status"] == "pass"


def test_revise_mode_loop_stops_once_reaudit_is_clean(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "article_section", "prompt": "Ignored."}])
    source_path = tmp_path / "source.jsonl"
    dirty_text = "This text has an em" + _EM_DASH + "dash violation in it."
    write_jsonl(source_path, [{"id": "p-1", "text": dirty_text}])
    out_path = tmp_path / "out.jsonl"
    call_log = tmp_path / "calls.json"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "revise",
        "--source", source_path,
        "--codex-cmd", fake_codex,
        behavior="revise_then_clean",
        call_log=call_log,
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    assert records == [
        {"id": "p-1", "text": "Fully revised clean text with no issues at all."}
    ]
    calls = json.loads(call_log.read_text(encoding="utf-8"))
    assert len(calls) == 2

    meta = json.loads((tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == {"p-1": "revised"}
    assert meta["revision_iterations"] == {"p-1": 2}
    assert meta["residual_findings"] == {"p-1": []}
    # First call's prompt must include the rule id and matched evidence.
    assert "em_dash_ban" in calls[0]
    assert _EM_DASH in calls[0]


def test_revise_loop_is_capped_at_two_iterations(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "article_section", "prompt": "Ignored."}])
    source_path = tmp_path / "source.jsonl"
    dirty_text = "This text has an em" + _EM_DASH + "dash violation in it."
    write_jsonl(source_path, [{"id": "p-1", "text": dirty_text}])
    out_path = tmp_path / "out.jsonl"
    call_log = tmp_path / "calls.json"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "revise",
        "--source", source_path,
        "--codex-cmd", fake_codex,
        behavior="revise_always_bad",
        call_log=call_log,
    )

    assert result.returncode == 0, result.stderr
    calls = json.loads(call_log.read_text(encoding="utf-8"))
    assert len(calls) == 2  # capped, not retried indefinitely

    meta = json.loads((tmp_path / "out.jsonl.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == {"p-1": "revised"}
    assert meta["revision_iterations"] == {"p-1": 2}
    residual = meta["residual_findings"]["p-1"]
    assert any(finding["rule_id"] == "em_dash_ban" for finding in residual)
    preservation = meta["literal_preservation"]["p-1"]
    assert preservation["status"] == "fail"
    assert preservation["added"] == [
        {"kind": "number", "value": "2", "count": 1}
    ]

    records = read_jsonl(out_path)
    assert records[0]["text"] == "Still bad em" + _EM_DASH + "dash text call 2."


def test_missing_source_id_is_a_clean_usage_error_exit_2(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(
        prompts_path,
        [
            {"id": "p-1", "use_case": "article_section", "prompt": "First."},
            {"id": "p-missing", "use_case": "article_section", "prompt": "Second."},
        ],
    )
    source_path = tmp_path / "source.jsonl"
    write_jsonl(source_path, [{"id": "p-1", "text": "Only one id here."}])
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "revise",
        "--source", source_path,
        "--codex-cmd", fake_codex,
        behavior="default",
    )

    assert result.returncode == 2
    assert "p-missing" in result.stderr
    assert "Traceback" not in result.stderr
    assert not out_path.exists()


def test_revise_mode_requires_source_argument(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "article_section", "prompt": "First."}])
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "revise",
        "--codex-cmd", fake_codex,
        behavior="default",
    )

    assert result.returncode == 2
    assert "--source" in result.stderr
    assert "Traceback" not in result.stderr
