"""Shared corpus-test data and subprocess helpers."""

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmark" / "build_corpus.py"

EM_DASH = chr(0x2014)


def write_manifest(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def write_sample(root: Path, relative: str, text: str) -> None:
    sample_path = root / relative
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(text, encoding="utf-8")

def make_samples(use_case: str, count: int, prefix: str) -> list[dict]:
    return [
        {
            "id": f"sample-{prefix}{index:02d}",
            "use_case": use_case,
            "title": f"{prefix}{index}",
            "source_path": f"{prefix}{index}.md",
            "text": "Some words go here for this sample of prose.",
            "word_count": 9,
        }
        for index in range(count)
    ]


def mixed_samples() -> list[dict]:
    return (
        make_samples("article_section", 5, "art")
        + make_samples("product_writing", 4, "prod")
        + make_samples("exec_communication", 3, "exec")
    )


def flag_holdout_only(samples: list[dict], ids: set[str]) -> list[dict]:
    return [
        {**sample, "holdout_only": True} if sample["id"] in ids else sample
        for sample in samples
    ]


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
