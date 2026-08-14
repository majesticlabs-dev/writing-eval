#!/usr/bin/env python3
"""Apply the pre-registered decision gate from benchmark/THRESHOLDS.md."""

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
    load_jsonl_records,
    write_text_file,
)
from writing_eval.comparison import decision_gate, render_gate_markdown
from writing_eval.style_audit import BUILTIN_RULES_PATH

_DEFAULT_RULES_PATH = BUILTIN_RULES_PATH


def _parser() -> argparse.ArgumentParser:
    parser = Parser(description="Apply the Phase 4 decision gate")
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--audited", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--eval-set", dest="eval_set", required=True, type=Path)
    parser.add_argument("--rules", type=Path, default=_DEFAULT_RULES_PATH)
    parser.add_argument("--noise-floor", type=Path)
    parser.add_argument(
        "--tell-rate-threshold", type=float, required=True
    )
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--json", dest="json_path", required=True, type=Path)
    return parser


def _load_l2_noise_floor(path: Path | None) -> float | None:
    if path is None:
        return None
    document = load_json_document(path)
    floor = document.get("noise_floor", document)
    if not isinstance(floor, dict):
        raise UserError(f"noise floor file has unexpected shape: {path}")
    entry = floor.get("token_1gram_l2")
    if not isinstance(entry, dict):
        raise UserError(
            f"noise floor file has no 'token_1gram_l2' entry: {path}"
        )
    value = entry.get("floor")
    if value is not None and not isinstance(value, (int, float)):
        raise UserError(f"noise floor file has a non numeric L2 floor: {path}")
    return float(value) if value is not None else None


def _load_eval_word_counts(path: Path) -> dict[str, int]:
    # The eval-set file (eval_set.jsonl from benchmark/build_corpus.py) carries a
    # "word_count" per sample; criterion 5 uses it as the reference length that
    # each audited output must reach at least 30 percent of.
    counts: dict[str, int] = {}
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise UserError(
                        f"invalid JSON in {path} at line {line_number}: {exc.msg}"
                    ) from None
                if not isinstance(record, dict):
                    raise UserError(
                        f"invalid record in {path} at line {line_number}: expected object"
                    )
                record_id = record.get("id")
                if not isinstance(record_id, str) or not record_id.strip():
                    raise UserError(
                        f"invalid record in {path} at line {line_number}: "
                        "expected a nonempty string id"
                    )
                word_count = record.get("word_count")
                if isinstance(word_count, bool) or not isinstance(word_count, int):
                    raise UserError(
                        f"invalid record in {path} at line {line_number}: "
                        "expected an integer word_count"
                    )
                counts[record_id] = word_count
    except UnicodeDecodeError as exc:
        raise UserError(f"could not decode {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UserError(f"could not read {path}: {exc}") from None
    if not counts:
        raise UserError(f"eval-set file is empty: {path}")
    return counts


def run(args: argparse.Namespace) -> None:
    if not args.current.is_file():
        raise UserError(f"current outputs file not found: {args.current}")
    if not args.audited.is_file():
        raise UserError(f"audited outputs file not found: {args.audited}")
    if not args.references.is_file():
        raise UserError(f"references file not found: {args.references}")
    if not args.eval_set.is_file():
        raise UserError(f"eval-set file not found: {args.eval_set}")
    if not args.rules.is_file():
        raise UserError(f"style-audit rules file not found: {args.rules}")
    if args.noise_floor is not None and not args.noise_floor.is_file():
        raise UserError(f"noise-floor file not found: {args.noise_floor}")

    current_records = load_jsonl_records(args.current, "current")
    audited_records = load_jsonl_records(args.audited, "audited")
    reference_records = load_jsonl_records(args.references, "references")
    reference_texts = [record["text"] for record in reference_records]
    eval_word_counts = _load_eval_word_counts(args.eval_set)
    l2_noise_floor = _load_l2_noise_floor(args.noise_floor)

    try:
        gate = decision_gate(
            current_records,
            audited_records,
            reference_texts,
            args.rules,
            l2_noise_floor,
            tell_rate_threshold=args.tell_rate_threshold,
            eval_reference_word_counts=eval_word_counts,
        )
    except ValueError as exc:
        raise UserError(str(exc)) from None

    write_text_file(args.markdown, render_gate_markdown(gate))
    write_text_file(
        args.json_path,
        json.dumps(gate, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
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
