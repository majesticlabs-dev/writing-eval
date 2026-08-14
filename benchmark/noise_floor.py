#!/usr/bin/env python3
"""Aggregate repeat-run report JSON files and compute a noise floor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from writing_eval.cli_support import (
    Parser,
    UserError,
    load_json_document,
    write_text_file,
)
from writing_eval.comparison import (
    aggregate_runs,
    noise_floor,
    render_noise_floor_markdown,
)


def _parser() -> argparse.ArgumentParser:
    parser = Parser(
        description="Aggregate repeat-run report JSON files into a noise floor"
    )
    parser.add_argument("--runs", required=True, type=Path, nargs="+")
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--json", dest="json_path", required=True, type=Path)
    return parser


def run(args: argparse.Namespace) -> None:
    for path in args.runs:
        if not path.is_file():
            raise UserError(f"run report not found: {path}")

    run_reports = [load_json_document(path) for path in args.runs]
    try:
        aggregate = aggregate_runs(run_reports)
    except ValueError as exc:
        raise UserError(str(exc)) from None

    floor = noise_floor(aggregate)
    write_text_file(args.markdown, render_noise_floor_markdown(aggregate, floor))
    write_text_file(
        args.json_path,
        json.dumps(
            {"aggregate": aggregate, "noise_floor": floor},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        run(args)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
