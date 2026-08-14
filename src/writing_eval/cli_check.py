"""Single-draft check command implementation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any

from .assessment import build_assessment, build_rule_baseline
from .cli_check_render import render_check_text
from .cli_support import CommandContext, Parser, UserError
from .metrics import (
    mtld,
    paragraph_stats,
    repeated_opening_rate,
    tell_rates_by_severity,
    tokenize,
)
from .metrics_distribution import token_1gram_l2_from_counts
from .metrics_quality import readability_scores
from .metrics_structure import sentence_length_stats
from .profile_cache import load_reference_stats
from .profiles import ProfileError, build_style_gap, load_profile
from .style_audit import BUILTIN_RULES_PATH, rules_fingerprint


def parser() -> argparse.ArgumentParser:
    command = Parser(
        prog="writing-eval check",
        description="Audit a single Markdown or plain-text draft, linter style",
    )
    command.add_argument("path", help="draft file to audit, or - for standard input")
    command.add_argument("--rules", type=Path, default=BUILTIN_RULES_PATH)
    command.add_argument("--references", type=Path, default=None)
    command.add_argument("--style", default=None)
    command.add_argument(
        "--profiles-root", dest="profiles_root", type=Path,
        default=Path("data/profiles"),
    )
    command.add_argument("--format", choices=("text", "json"), default="text")
    command.add_argument("--json", dest="json_path", type=Path, default=None)
    return command


def _read_input(path: str) -> str:
    if path == "-":
        reconfigure = getattr(sys.stdin, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="strict")
        try:
            return sys.stdin.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise UserError(f"could not read standard input: {exc}") from None
    file_path = Path(path)
    if not file_path.is_file():
        raise UserError(f"input file not found: {path}")
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UserError(f"could not decode {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UserError(f"could not read {path}: {exc}") from None


def _line_and_column(text: str, char_offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, char_offset) + 1
    column = char_offset - text.rfind("\n", 0, char_offset)
    return line, column


def _check_result(
    display_name: str,
    text: str,
    findings: list[Any],
    word_count: int,
    token_1gram_l2_value: float | None,
) -> dict[str, Any]:
    positioned = []
    for finding in findings:
        line, column = _line_and_column(text, finding.char_offset)
        positioned.append(
            {
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "message": finding.message,
                "line": line,
                "column": column,
                "span": finding.matched_text,
                "within_allowance": False,
            }
        )
    positioned.sort(key=lambda item: (item["line"], item["column"], item["rule_id"]))
    sentence_mean, sentence_variance = sentence_length_stats(text)
    reading_ease, reading_grade = readability_scores(text)
    return {
        "file": display_name,
        "findings": positioned,
        "metrics": {
            "word_count": word_count,
            "tell_rates_by_severity": tell_rates_by_severity(findings, word_count),
            "mean_sentence_length": sentence_mean,
            "sentence_length_variance": sentence_variance,
            "repeated_opening_rate": repeated_opening_rate(text),
            "token_1gram_l2": token_1gram_l2_value,
        },
        "quality_metrics": {
            "flesch_reading_ease": reading_ease,
            "flesch_kincaid_grade": reading_grade,
            "mtld": mtld(text),
            "paragraph_stats": paragraph_stats(text),
        },
    }


def _mark_within_allowance(
    findings: list[dict[str, Any]], rule_baseline: dict[str, Any]
) -> None:
    """Flag the earliest findings per rule that fall within its profile allowance."""

    allowance_by_id = {
        entry["id"]: int(entry["allowance"]) for entry in rule_baseline["rules"]
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        grouped[finding["rule_id"]].append(finding)
    for rule_id, group in grouped.items():
        allowance = allowance_by_id.get(rule_id, 0)
        ordered = sorted(group, key=lambda item: (item["line"], item["column"]))
        for index, finding in enumerate(ordered):
            finding["within_allowance"] = index < allowance


def run(args: argparse.Namespace, context: CommandContext) -> int:
    style = getattr(args, "style", None)
    if style is not None and args.references is not None:
        raise UserError("--style and --references are mutually exclusive")
    text = _read_input(args.path)
    rules = context.load_rules(args.rules)
    findings = context.audit_text(text, rules)
    profile = None
    if style is not None:
        try:
            profile = load_profile(args.profiles_root, style)
        except ProfileError as exc:
            raise UserError(str(exc)) from None
    draft_counts = Counter(tokenize(text))
    word_count = sum(draft_counts.values())
    display_name = "<stdin>" if args.path == "-" else args.path
    if profile is not None:
        reference_stats, cache_status = load_reference_stats(
            profile, rules, rules_fingerprint(rules)
        )
        if cache_status != "cache":
            print(
                f"note: profile {profile.name!r} reference cache unavailable "
                "(recomputed); run `writing-eval profile cache` to refresh it",
                file=sys.stderr,
            )
        l2 = token_1gram_l2_from_counts(draft_counts, reference_stats.token_counts)
        result = _check_result(display_name, text, findings, word_count, l2)
        rule_baseline = build_rule_baseline(
            reference_stats.rule_counts,
            reference_stats.word_count,
            result["findings"],
            result["metrics"]["word_count"],
        )
        _mark_within_allowance(result["findings"], rule_baseline)
        result["style_gap"] = build_style_gap(
            profile.name, text, profile.statistics, reference_stats.token_counts
        )
        result["assessment"] = build_assessment(
            text, result["findings"], result["metrics"], result["quality_metrics"],
            result["style_gap"], profile.statistics, rule_baseline,
        )
    else:
        references_path = args.references
        references_provided = references_path is not None
        reference_texts: list[str] = []
        if references_provided:
            if not references_path.is_file():
                raise UserError(f"references file not found: {references_path}")
            reference_records = context.load_jsonl(references_path, "references")
            reference_texts = [record["text"] for record in reference_records]
        l2 = (
            token_1gram_l2_from_counts(
                draft_counts, Counter(token for t in reference_texts for token in tokenize(t))
            )
            if references_provided
            else None
        )
        result = _check_result(display_name, text, findings, word_count, l2)
        if not references_provided:
            print(
                "note: no references provided; token 1-gram L2 skipped (n/a)",
                file=sys.stderr,
            )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.format == "json":
        sys.stdout.write(payload)
    else:
        sys.stdout.write(render_check_text(result))
    if args.json_path is not None:
        context.write_text(args.json_path, payload)
    return 0
