"""Codex subprocess invocation for generation runs."""

from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

from writing_eval.generation_io import UsageError


def codex_argv(
    codex_cmd: str,
    model: str,
    reasoning_effort: str,
    cwd: str,
    lastmsg_path: str,
) -> list[str]:
    return [
        codex_cmd, "exec", "--model", model, "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--skip-git-repo-check", "--sandbox", "read-only", "--cd", cwd,
        "-o", lastmsg_path, "-",
    ]


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def call_codex(
    codex_cmd: str,
    model: str,
    reasoning_effort: str,
    prompt: str,
    sleep: float,
    record_id: str,
    timeout: float = 600.0,
) -> tuple[str | None, dict[str, Any] | None]:
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise UsageError(
            f"timeout must be a finite value greater than zero, got {timeout!r}"
        )
    diagnostics: dict[str, Any] | None = None
    for _attempt in range(2):
        with tempfile.TemporaryDirectory() as cwd:
            lastmsg_fd, lastmsg_path = tempfile.mkstemp(
                prefix="generate_runs_lastmsg_", suffix=".txt"
            )
            os.close(lastmsg_fd)
            Path(lastmsg_path).unlink()
            try:
                argv = codex_argv(
                    codex_cmd, model, reasoning_effort, cwd, lastmsg_path
                )
                try:
                    result = subprocess.run(
                        argv, input=prompt, capture_output=True, text=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired as exc:
                    diagnostics = {
                        "failure_kind": "timeout",
                        "returncode": None,
                        "stdout": _as_text(exc.stdout),
                        "stderr": _as_text(exc.stderr),
                    }
                except FileNotFoundError:
                    raise UsageError(f"codex executable not found: {codex_cmd!r}")
                else:
                    lastmsg_file = Path(lastmsg_path)
                    text = ""
                    if lastmsg_file.is_file():
                        try:
                            text = lastmsg_file.read_text(encoding="utf-8").strip()
                        except UnicodeDecodeError as exc:
                            raise UsageError(
                                f"could not decode codex output {lastmsg_path} "
                                f"as UTF-8: {exc}"
                            ) from None
                        except OSError as exc:
                            raise UsageError(
                                f"could not read codex output {lastmsg_path}: {exc}"
                            ) from None
                    if sleep:
                        time.sleep(sleep)
                    if result.returncode == 0 and text:
                        return text, None
                    diagnostics = {
                        "failure_kind": (
                            "empty_output" if result.returncode == 0 else "nonzero_exit"
                        ),
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
            finally:
                Path(lastmsg_path).unlink(missing_ok=True)
    failure_kind = diagnostics["failure_kind"] if diagnostics else "unknown"
    detail = (
        f", exit={diagnostics['returncode']}" if failure_kind == "nonzero_exit" else ""
    )
    print(
        f"error: codex call failed for id={record_id} after retry "
        f"(failure_kind={failure_kind}{detail})",
        file=sys.stderr,
    )
    return None, diagnostics
