"""Corpus-evaluation command implementation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli_support import CommandContext, Parser, UserError
from .report import build_provenance, build_report, render_markdown
from .style_audit import BUILTIN_RULES_PATH, rules_fingerprint


def parser() -> argparse.ArgumentParser:
    command = Parser(description="Evaluate writing outputs against references")
    command.add_argument("--outputs", required=True, type=Path)
    command.add_argument("--references", required=True, type=Path)
    command.add_argument("--report", required=True, type=Path)
    command.add_argument("--json", dest="json_path", type=Path)
    command.add_argument("--rules", type=Path, default=BUILTIN_RULES_PATH)
    return command


def run(args: argparse.Namespace, context: CommandContext) -> None:
    if not args.outputs.is_dir():
        raise UserError(f"outputs directory not found: {args.outputs}")
    if not args.references.is_file():
        raise UserError(f"references file not found: {args.references}")
    output_files = sorted(args.outputs.glob("*.jsonl"), key=lambda path: path.name)
    if not output_files:
        raise UserError(f"no .jsonl output files found in: {args.outputs}")
    reference_records = context.load_jsonl(args.references, "references")
    reference_texts = [record["text"] for record in reference_records]
    rules = context.load_rules(args.rules)
    rules_path = args.rules
    reports = []
    expected_output_ids: set[str] | None = None
    for output_file in output_files:
        output_records = context.load_jsonl(output_file, "output")
        output_ids = {record["id"] for record in output_records}
        if expected_output_ids is None:
            expected_output_ids = output_ids
        elif output_ids != expected_output_ids:
            missing = sorted(expected_output_ids - output_ids)
            extra = sorted(output_ids - expected_output_ids)
            details: list[str] = []
            if missing:
                details.append(f"missing ids: {', '.join(missing)}")
            if extra:
                details.append(f"extra ids: {', '.join(extra)}")
            raise UserError(
                f"output files must contain identical id sets; {output_file} "
                f"{'; '.join(details)}"
            )
        texts = [record["text"] for record in output_records]
        findings = [context.audit_text(text, rules) for text in texts]
        reports.append(build_report(output_file.stem, texts, reference_texts, findings))
    try:
        provenance = build_provenance(
            args.references,
            reference_records,
            rules_path,
            len(rules),
            context.rules_version(rules_path),
            rules_fingerprint(rules),
        )
    except OSError as exc:
        raise UserError(f"could not read provenance source: {exc}") from None
    report_data = {"provenance": provenance, "systems": reports}
    context.write_text(args.report, render_markdown(report_data))
    if args.json_path is not None:
        context.write_text(
            args.json_path, json.dumps(report_data, indent=2, sort_keys=True) + "\n"
        )
