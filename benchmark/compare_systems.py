#!/usr/bin/env python3
"""Compare two systems drawn from one or two evaluation report JSON files."""

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
from writing_eval.comparison import compare_systems, render_comparison_markdown


def _parser() -> argparse.ArgumentParser:
    parser = Parser(description="Compare two systems from evaluation report JSON")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--report-b", type=Path)
    parser.add_argument("--system-a", required=True)
    parser.add_argument("--system-b", required=True)
    parser.add_argument("--noise-floor", type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--json", dest="json_path", required=True, type=Path)
    return parser


def _load_floor(path: Path | None) -> dict | None:
    if path is None:
        return None
    document = load_json_document(path)
    floor = document.get("noise_floor", document)
    if not isinstance(floor, dict):
        raise UserError(f"noise floor file has unexpected shape: {path}")
    return floor


def run(args: argparse.Namespace) -> None:
    if not args.report.is_file():
        raise UserError(f"report not found: {args.report}")
    if args.report_b is not None and not args.report_b.is_file():
        raise UserError(f"report-b not found: {args.report_b}")
    if args.noise_floor is not None and not args.noise_floor.is_file():
        raise UserError(f"noise-floor file not found: {args.noise_floor}")

    report_a = load_json_document(args.report)
    report_b = load_json_document(args.report_b) if args.report_b is not None else None
    floor = _load_floor(args.noise_floor)

    try:
        comparison = compare_systems(
            report_a, report_b, floor, args.system_a, args.system_b
        )
    except ValueError as exc:
        raise UserError(str(exc)) from None

    write_text_file(args.markdown, render_comparison_markdown(comparison))
    write_text_file(
        args.json_path,
        json.dumps(comparison, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
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
