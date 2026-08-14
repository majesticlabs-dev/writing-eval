"""Orchestrate repeat-run generation and revision."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import time
from typing import Any

from .generation_io import (
    UsageError,
    load_config,
    load_id_text_map,
    load_prompts,
    write_meta,
    write_output,
)
from .generation_prompts import build_generation_prompt, build_revision_prompt
from .preservation import compare_literal_preservation
from .style_audit import Finding, Rule, audit_text, load_rules

MAX_REVISION_ITERATIONS = 2


@dataclass(frozen=True)
class GenerationContext:
    """Live launcher dependencies used by a generation run."""

    call_model: Any
    load_prompts: Any = load_prompts
    load_config: Any = load_config
    load_id_text_map: Any = load_id_text_map
    load_rules: Any = load_rules
    audit_text: Any = audit_text
    compare_literal_preservation: Any = compare_literal_preservation
    build_generation_prompt: Any = build_generation_prompt
    build_revision_prompt: Any = build_revision_prompt
    write_output: Any = write_output
    write_meta: Any = write_meta
    max_revision_iterations: int = MAX_REVISION_ITERATIONS


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "message": finding.message,
        "matched_text": finding.matched_text,
    }


def _validate_args(args: argparse.Namespace) -> None:
    if args.mode == "revise" and args.source is None:
        raise UsageError("--source is required when --mode revise")
    if args.mode == "generate" and args.source is not None:
        raise UsageError("--source is only valid when --mode revise")
    if args.max_records is not None and args.max_records < 0:
        raise UsageError("--max-records must not be negative")
    if (
        isinstance(args.sleep, bool)
        or not isinstance(args.sleep, (int, float))
        or not math.isfinite(args.sleep)
    ):
        raise UsageError(
            "--sleep must be a finite value greater than or equal to zero, "
            f"got {args.sleep!r}"
        )
    if args.sleep < 0:
        raise UsageError("--sleep must not be negative")
    if (
        isinstance(args.timeout, bool)
        or not isinstance(args.timeout, (int, float))
        or not math.isfinite(args.timeout)
        or args.timeout <= 0
    ):
        raise UsageError(
            f"--timeout must be a finite value greater than zero, got {args.timeout!r}"
        )


def run(
    args: argparse.Namespace,
    context: GenerationContext,
) -> int:
    started = time.time()
    _validate_args(args)
    if not args.prompts.is_file():
        raise UsageError(f"prompts file not found: {args.prompts}")
    if not args.config.is_file():
        raise UsageError(f"config file not found: {args.config}")
    prompts = context.load_prompts(args.prompts)
    if args.max_records is not None:
        prompts = prompts[: args.max_records]
    config = context.load_config(args.config)
    rules: list[Rule] = []
    source_texts: dict[str, str] = {}
    if args.mode == "revise":
        if not args.source.is_file():
            raise UsageError(f"source file not found: {args.source}")
        source_texts = context.load_id_text_map(args.source, "text", "source")
        missing_ids = [record["id"] for record in prompts if record["id"] not in source_texts]
        if missing_ids:
            raise UsageError(
                f"source file {args.source} is missing id(s): {', '.join(missing_ids)}"
            )
        if not args.rules.is_file():
            raise UsageError(f"rules file not found: {args.rules}")
        try:
            rules = context.load_rules(args.rules)
        except ValueError as exc:
            raise UsageError(f"could not load style-audit rules: {exc}") from None
    existing: dict[str, str] = {}
    if args.resume and args.out.is_file():
        existing = context.load_id_text_map(args.out, "text", "output")
    records: list[dict[str, str]] = []
    status: dict[str, str] = {}
    revision_iterations: dict[str, int] = {}
    residual_findings: dict[str, list[dict[str, Any]]] = {}
    literal_preservation: dict[str, dict[str, Any]] = {}
    diagnostics_by_id: dict[str, dict[str, Any]] = {}
    any_failed = False
    for prompt_record in prompts:
        record_id = prompt_record["id"]
        if args.resume and record_id in existing:
            existing_text = existing[record_id]
            records.append({"id": record_id, "text": existing_text})
            if args.mode == "revise":
                literal_preservation[record_id] = context.compare_literal_preservation(
                    source_texts[record_id], existing_text
                )
            continue
        if args.mode == "generate":
            prompt_text = context.build_generation_prompt(
                config["system_prompt"], prompt_record["prompt"]
            )
            text, diagnostics = context.call_model(
                config["model"], config["reasoning_effort"], prompt_text,
                args.sleep, record_id, args.timeout,
            )
            if text is None:
                any_failed = True
                status[record_id] = "failed"
                if diagnostics is not None:
                    diagnostics_by_id[record_id] = diagnostics
            else:
                status[record_id] = "ok"
                records.append({"id": record_id, "text": text})
            continue
        source_text = source_texts[record_id]
        findings = context.audit_text(source_text, rules)
        if not findings:
            status[record_id] = "clean"
            revision_iterations[record_id] = 0
            residual_findings[record_id] = []
            literal_preservation[record_id] = context.compare_literal_preservation(
                source_text, source_text
            )
            records.append({"id": record_id, "text": source_text})
            continue
        current_text = source_text
        iteration = 0
        failed = False
        final_diagnostics: dict[str, Any] | None = None
        while True:
            revision_prompt = context.build_revision_prompt(
                config["system_prompt"], findings, current_text
            )
            text, diagnostics = context.call_model(
                config["model"], config["reasoning_effort"], revision_prompt,
                args.sleep, record_id, args.timeout,
            )
            if text is None:
                failed = True
                final_diagnostics = diagnostics
                break
            current_text = text
            iteration += 1
            findings = context.audit_text(current_text, rules)
            warn_findings = [finding for finding in findings if finding.severity == "warn"]
            if not warn_findings or iteration >= context.max_revision_iterations:
                break
        if failed:
            any_failed = True
            status[record_id] = "failed"
            if final_diagnostics is not None:
                diagnostics_by_id[record_id] = final_diagnostics
            continue
        status[record_id] = "revised"
        revision_iterations[record_id] = iteration
        residual_findings[record_id] = [_finding_to_dict(finding) for finding in findings]
        literal_preservation[record_id] = context.compare_literal_preservation(
            source_text, current_text
        )
        records.append({"id": record_id, "text": current_text})
    context.write_output(args.out, records)
    context.write_meta(
        args, config, status, revision_iterations, residual_findings,
        literal_preservation, diagnostics_by_id, started, time.time(),
    )
    return 1 if any_failed else 0
