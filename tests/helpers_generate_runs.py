"""Shared fake-Codex helpers for generation-run tests."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmark" / "generate_runs.py"

_EM_DASH = chr(0x2014)

_FAKE_CODEX_SOURCE = '''#!/usr/bin/env python3
"""Fake codex CLI for tests. Writes canned output to the -o file."""
import json
import os
import sys
import time as time_module


def _lastmsg_path(argv):
    index = argv.index("-o")
    return argv[index + 1]


def _log_call(stdin_text):
    log_path = os.environ.get("FAKE_CODEX_LOG")
    if not log_path:
        return 0
    calls = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as handle:
            calls = json.load(handle)
    calls.append(stdin_text)
    with open(log_path, "w", encoding="utf-8") as handle:
        json.dump(calls, handle)
    return len(calls)


def main():
    stdin_text = sys.stdin.read()
    call_index = _log_call(stdin_text)
    lastmsg_path = _lastmsg_path(sys.argv)
    behavior = os.environ.get("FAKE_CODEX_BEHAVIOR", "default")

    dump_path = os.environ.get("FAKE_CODEX_ARGV_DUMP")
    if dump_path:
        with open(dump_path, "w", encoding="utf-8") as handle:
            json.dump(sys.argv, handle)

    if behavior == "fail_always":
        sys.stderr.write("fake codex: boom\\n")
        return 1

    if behavior == "fail_once":
        if call_index == 1:
            sys.stderr.write("fake codex: boom\\n")
            return 1
        with open(lastmsg_path, "w", encoding="utf-8") as handle:
            handle.write("Recovered clean text.")
        print("tokens used: 3")
        return 0

    if behavior == "empty_once":
        if call_index == 1:
            with open(lastmsg_path, "w", encoding="utf-8") as handle:
                handle.write("")
            return 0
        with open(lastmsg_path, "w", encoding="utf-8") as handle:
            handle.write("Recovered after empty last-message file.")
        print("tokens used: 3")
        return 0

    if behavior == "empty_always":
        with open(lastmsg_path, "w", encoding="utf-8") as handle:
            handle.write("")
        return 0

    if behavior == "hang":
        time_module.sleep(30)
        return 0

    if behavior == "bad_utf8_lastmsg":
        with open(lastmsg_path, "wb") as handle:
            handle.write(b"\\xff\\xfe broken")
        return 0

    if behavior == "revise_then_clean":
        if call_index == 1:
            text = "Still has an em" + chr(0x2014) + "dash problem here."
        else:
            text = "Fully revised clean text with no issues at all."
        with open(lastmsg_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("codex")
        print("tokens used")
        print("42")
        return 0

    if behavior == "revise_always_bad":
        text = "Still bad em" + chr(0x2014) + "dash text call " + str(call_index) + "."
        with open(lastmsg_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("tokens used")
        print("7")
        return 0

    # default: happy-path generation, deterministic on stdin content
    last_line = stdin_text.strip().splitlines()[-1] if stdin_text.strip() else ""
    text = "GEN[" + str(call_index) + "]:" + last_line
    with open(lastmsg_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("codex")
    print("tokens used")
    print("10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def make_fake_codex(tmp_path: Path) -> Path:
    fake_path = tmp_path / "fake_codex.py"
    fake_path.write_text(_FAKE_CODEX_SOURCE, encoding="utf-8")
    mode = fake_path.stat().st_mode
    fake_path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return fake_path


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def write_config(tmp_path: Path, **overrides: str) -> Path:
    config = {
        "frozen_decoding": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": "medium",
            "system_prompt": "You are a concise assistant.",
        }
    }
    config["frozen_decoding"].update(overrides)
    config_path = tmp_path / "eval-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def run_generate_runs(
    tmp_path: Path,
    *arguments: object,
    behavior: str | None = None,
    call_log: Path | None = None,
    argv_dump: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if behavior is not None:
        env["FAKE_CODEX_BEHAVIOR"] = behavior
    if call_log is not None:
        env["FAKE_CODEX_LOG"] = str(call_log)
    if argv_dump is not None:
        env["FAKE_CODEX_ARGV_DUMP"] = str(argv_dump)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def load_module():
    spec = importlib.util.spec_from_file_location("generate_runs_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records
