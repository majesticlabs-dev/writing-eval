#!/usr/bin/env python3
"""Command-line facade for writing-eval."""

from __future__ import annotations

import argparse
from importlib.metadata import version as package_version
from pathlib import Path
import sys
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import yaml

from writing_eval import cli_check, cli_eval, cli_profile
from writing_eval.cli_check_render import render_check_text as _render_check_text
from writing_eval.cli_support import (
    CommandContext,
    Parser,
    UserError,
    load_jsonl_records,
    write_text_file,
)
from writing_eval.style_audit_engine import audit_text
from writing_eval.style_audit_rules import load_rules


def _load_rules(rules_path: Path) -> Any:
    if not rules_path.is_file():
        raise UserError(f"style-audit rules file not found: {rules_path}")
    try:
        rules = load_rules(rules_path)
        if len(rules) == 0:
            raise ValueError("load_rules returned an empty rule set")
        return rules
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise UserError(f"could not load style-audit rules: {exc}") from None


def _audit_text(text: str, rules: Any) -> list[Any]:
    return list(audit_text(text, rules))


def _rules_version(rules_path: Path) -> Any:
    try:
        with rules_path.open(encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
    except UnicodeDecodeError as exc:
        raise UserError(f"could not decode {rules_path} as UTF-8: {exc}") from None
    except (OSError, yaml.YAMLError) as exc:
        raise UserError(f"could not read style-audit rules metadata: {exc}") from None
    if isinstance(document, dict):
        version = document.get("version")
        if version is not None and not isinstance(version, (str, int, float)):
            version = str(version)
        return version
    return None


def _context() -> CommandContext:
    return CommandContext(
        load_jsonl_records, _load_rules, _audit_text, _rules_version, write_text_file,
    )


def _parser() -> argparse.ArgumentParser:
    return cli_eval.parser()


def _check_parser() -> argparse.ArgumentParser:
    return cli_check.parser()


def _profile_parser() -> argparse.ArgumentParser:
    return cli_profile.parser()


def run(args: argparse.Namespace) -> None:
    cli_eval.run(args, _context())


def run_check(args: argparse.Namespace) -> int:
    return cli_check.run(args, _context())


def run_profile(args: argparse.Namespace) -> int:
    return cli_profile.run(args)


def _run_eval(argv: list[str]) -> int:
    try:
        run(_parser().parse_args(argv))
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_check(argv: list[str]) -> int:
    try:
        return run_check(_check_parser().parse_args(argv))
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_profile(argv: list[str]) -> int:
    try:
        return run_profile(_profile_parser().parse_args(argv))
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    if tokens == ["--version"]:
        print(f"writing-eval {package_version('writing-eval')}")
        return 0
    if tokens and tokens[0] == "check":
        return _run_check(tokens[1:])
    if tokens and tokens[0] == "profile":
        return _run_profile(tokens[1:])
    if tokens and tokens[0] == "eval":
        return _run_eval(tokens[1:])
    if tokens and not tokens[0].startswith("-"):
        print(
            f"error: unknown command '{tokens[0]}'; "
            "expected one of: check, profile, eval",
            file=sys.stderr,
        )
        return 1
    return _run_eval(tokens)


if __name__ == "__main__":
    raise SystemExit(main())
