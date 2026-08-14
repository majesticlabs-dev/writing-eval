#!/usr/bin/env python3
"""Build a reference holdout, eval set, and prompts from a sample manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from writing_eval.corpus import (
    collect_samples,
    load_manifest,
    split_holdout,
    write_outputs,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect real writing samples, split into a reference holdout "
            "and eval set, and emit both plus templated eval prompts"
        )
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out-dir", default=Path("fixtures"), type=Path)
    parser.add_argument("--eval-fraction", default=0.4, type=float)
    parser.add_argument("--seed", default=20260717, type=int)
    return parser


def _summary(holdout: list[dict], eval_set: list[dict]) -> str:
    use_cases = sorted({sample["use_case"] for sample in holdout + eval_set})
    parts = []
    for use_case in use_cases:
        holdout_count = sum(1 for s in holdout if s["use_case"] == use_case)
        eval_count = sum(1 for s in eval_set if s["use_case"] == use_case)
        parts.append(f"{use_case}: holdout={holdout_count} eval={eval_count}")
    total = len(holdout) + len(eval_set)
    return f"collected {total} samples; " + "; ".join(parts)


def run(args: argparse.Namespace) -> str:
    manifest = load_manifest(args.manifest)
    samples = collect_samples(manifest, args.root)
    holdout, eval_set = split_holdout(
        samples, eval_fraction=args.eval_fraction, seed=args.seed
    )
    write_outputs(holdout, eval_set, args.out_dir)
    return _summary(holdout, eval_set)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = run(args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
