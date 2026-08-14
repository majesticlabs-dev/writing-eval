#!/usr/bin/env python3
"""Generate repeat-run output corpora via the Codex CLI."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_BENCHMARK = _ROOT / "benchmark"
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_BENCHMARK) not in sys.path:
    sys.path.insert(0, str(_BENCHMARK))

from codex_runner import call_codex as _call_codex  # noqa: E402
from writing_eval.generation_io import UsageError  # noqa: E402
from writing_eval.generation_io import load_config as _load_config  # noqa: E402
from writing_eval.generation_io import load_id_text_map as _load_id_text_map  # noqa: E402
from writing_eval.generation_io import load_jsonl_records as _load_jsonl_records  # noqa: E402
from writing_eval.generation_io import load_prompts as _load_prompts  # noqa: E402
from writing_eval.generation_io import write_meta as _write_meta  # noqa: E402
from writing_eval.generation_io import write_output as _write_output  # noqa: E402
from writing_eval.generation_prompts import (  # noqa: E402
    REVISION_INSTRUCTION as _REVISION_INSTRUCTION,
)
from writing_eval.generation_prompts import (  # noqa: E402
    build_generation_prompt as _build_generation_prompt,
)
from writing_eval.generation_prompts import build_revision_prompt as _build_revision_prompt  # noqa: E402
from writing_eval.generation_prompts import format_findings as _format_findings  # noqa: E402
from writing_eval.generation_runner import (  # noqa: E402
    MAX_REVISION_ITERATIONS as _MAX_REVISION_ITERATIONS,
)
from writing_eval.generation_runner import GenerationContext  # noqa: E402
from writing_eval.generation_runner import run as _run  # noqa: E402
from writing_eval.preservation import (  # noqa: E402
    compare_literal_preservation as _compare_literal_preservation,
)
from writing_eval.style_audit import BUILTIN_RULES_PATH  # noqa: E402
from writing_eval.style_audit import Finding, Rule  # noqa: E402
from writing_eval.style_audit import audit_text as _audit_text  # noqa: E402
from writing_eval.style_audit import load_rules as _load_rules  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate repeat-run output corpora via the codex CLI"
    )
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--config", default=_ROOT / "benchmark" / "eval-config.json", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("generate", "revise"))
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--rules", default=BUILTIN_RULES_PATH, type=Path)
    parser.add_argument("--codex-cmd", dest="codex_cmd", default="codex")
    parser.add_argument("--max-records", dest="max_records", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--resume", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    context = GenerationContext(
        load_prompts=_load_prompts,
        load_config=_load_config,
        load_id_text_map=_load_id_text_map,
        load_rules=_load_rules,
        audit_text=_audit_text,
        compare_literal_preservation=_compare_literal_preservation,
        call_model=partial(_call_codex, args.codex_cmd),
        build_generation_prompt=_build_generation_prompt,
        build_revision_prompt=_build_revision_prompt,
        write_output=_write_output,
        write_meta=_write_meta,
        max_revision_iterations=_MAX_REVISION_ITERATIONS,
    )
    return _run(args, context)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(_parser().parse_args(argv))
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
