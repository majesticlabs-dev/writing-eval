"""Generation-run behavior tests."""

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

def test_generate_happy_path_orders_records_and_records_meta_status(
    tmp_path: Path,
) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(
        prompts_path,
        [
            {"id": "p-003", "use_case": "a", "prompt": "First prompt café."},
            {"id": "p-001", "use_case": "a", "prompt": "Second prompt."},
            {"id": "p-002", "use_case": "a", "prompt": "Third prompt."},
        ],
    )
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="default",
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    assert [record["id"] for record in records] == ["p-003", "p-001", "p-002"]
    assert records[0]["text"] == "GEN[0]:First prompt café."

    raw_bytes = out_path.read_bytes()
    assert b"\xc3\xa9" not in raw_bytes  # no raw UTF-8 encoded e-acute
    assert b"\\u00e9" in raw_bytes  # ensure_ascii escape present

    meta_path = tmp_path / "out.jsonl.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["mode"] == "generate"
    assert meta["source"] is None
    assert meta["config"]["model"] == "gpt-5.6-terra"
    assert meta["config"]["reasoning_effort"] == "medium"
    assert meta["status"] == {"p-003": "ok", "p-001": "ok", "p-002": "ok"}
    assert meta["started"] <= meta["finished"]


def test_generate_reads_text_from_lastmsg_file_not_stdout(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "a", "prompt": "Hello."}])
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="default",
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    # The fake prints "codex" / "tokens used" / "10" to stdout as noise; the
    # real generated text only ever lives in the -o file, so none of that
    # stdout noise should leak into the captured text.
    assert records[0]["text"] == "GEN[0]:Hello."
    assert "tokens used" not in records[0]["text"]
    assert "codex" != records[0]["text"]


def test_codex_argv_shape_matches_confirmed_invocation(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path, model="gpt-5.6-terra", reasoning_effort="medium")
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "a", "prompt": "Hello."}])
    out_path = tmp_path / "out.jsonl"
    argv_dump = tmp_path / "argv.json"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="default",
        argv_dump=argv_dump,
    )

    assert result.returncode == 0, result.stderr
    argv = json.loads(argv_dump.read_text(encoding="utf-8"))
    assert argv[0] == str(fake_codex)
    assert argv[1:9] == [
        "exec",
        "--model", "gpt-5.6-terra",
        "-c", 'model_reasoning_effort="medium"',
        "--skip-git-repo-check",
        "--sandbox", "read-only",
    ]
    assert argv[9] == "--cd"
    assert Path(argv[10]).is_absolute()
    assert argv[11] == "-o"
    assert Path(argv[12]).is_absolute()
    assert argv[13] == "-"


def test_retry_then_skip_sets_exit_code_1_and_skips_only_failed_id(
    tmp_path: Path,
) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(
        prompts_path,
        [
            {"id": "p-ok", "use_case": "a", "prompt": "Fine prompt."},
            {"id": "p-bad", "use_case": "a", "prompt": "Fine prompt."},
        ],
    )
    out_path = tmp_path / "out.jsonl"
    call_log = tmp_path / "calls.json"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="fail_always",
        call_log=call_log,
    )

    assert result.returncode == 1
    assert "id=p-ok" in result.stderr
    assert "id=p-bad" in result.stderr
    assert "Traceback" not in result.stderr
    records = read_jsonl(out_path)
    assert records == []
    calls = json.loads(call_log.read_text(encoding="utf-8"))
    assert len(calls) == 4  # 2 ids x 2 attempts each

    meta_path = tmp_path / "out.jsonl.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == {"p-ok": "failed", "p-bad": "failed"}


def test_retry_recovers_after_one_failed_attempt(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "a", "prompt": "Hi."}])
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="fail_once",
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    assert records == [{"id": "p-1", "text": "Recovered clean text."}]


def test_empty_lastmsg_file_treated_as_failure_then_recovers(tmp_path: Path) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(prompts_path, [{"id": "p-1", "use_case": "a", "prompt": "Hi."}])
    out_path = tmp_path / "out.jsonl"

    result = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="empty_once",
    )

    assert result.returncode == 0, result.stderr
    records = read_jsonl(out_path)
    assert records == [
        {"id": "p-1", "text": "Recovered after empty last-message file."}
    ]


def test_resume_skips_existing_ids_and_only_calls_codex_for_new_ones(
    tmp_path: Path,
) -> None:
    fake_codex = make_fake_codex(tmp_path)
    config_path = write_config(tmp_path)
    prompts_path = tmp_path / "prompts.jsonl"
    write_jsonl(
        prompts_path,
        [
            {"id": "p-1", "use_case": "a", "prompt": "First."},
            {"id": "p-2", "use_case": "a", "prompt": "Second."},
        ],
    )
    out_path = tmp_path / "out.jsonl"
    call_log = tmp_path / "calls.json"

    first = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        behavior="default",
        call_log=call_log,
    )
    assert first.returncode == 0, first.stderr
    calls_after_first = json.loads(call_log.read_text(encoding="utf-8"))
    assert len(calls_after_first) == 2

    write_jsonl(
        prompts_path,
        [
            {"id": "p-1", "use_case": "a", "prompt": "First."},
            {"id": "p-2", "use_case": "a", "prompt": "Second."},
            {"id": "p-3", "use_case": "a", "prompt": "Third."},
        ],
    )

    second = run_generate_runs(
        tmp_path,
        "--prompts", prompts_path,
        "--config", config_path,
        "--out", out_path,
        "--mode", "generate",
        "--codex-cmd", fake_codex,
        "--resume",
        behavior="default",
        call_log=call_log,
    )
    assert second.returncode == 0, second.stderr
    calls_after_second = json.loads(call_log.read_text(encoding="utf-8"))
    assert len(calls_after_second) == 3  # only p-3 triggered a new call

    records = read_jsonl(out_path)
    assert [record["id"] for record in records] == ["p-1", "p-2", "p-3"]
    assert records[0]["text"] == "GEN[1]:First."  # unchanged from first run
    assert records[2]["text"] == "GEN[3]:Third."
