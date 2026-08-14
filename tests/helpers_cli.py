"""Shared helpers for corpus CLI tests."""

import json
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_eval.py"
CLI_MODULE = ROOT / "src" / "writing_eval" / "cli.py"


def run_cli(
    *arguments: object, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        input=stdin,
    )


def load_run_eval_module():
    spec = importlib.util.spec_from_file_location("run_eval_under_test", CLI_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def cli_with_inputs(
    tmp_path: Path,
    reference_records: list[dict[str, str]],
    output_records: dict[str, list[dict[str, str]]],
) -> subprocess.CompletedProcess[str]:
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    for name, records in output_records.items():
        write_jsonl(outputs / f"{name}.jsonl", records)
    references = tmp_path / "references.jsonl"
    write_jsonl(references, reference_records)
    return run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        tmp_path / "report.md",
    )
