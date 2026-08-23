"""Input validation and atomic output for generation runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

_PROMPT_USE_CASES = (
    "article_section",
    "product_writing",
    "exec_communication",
)
_PROMPT_USE_CASE_SET = frozenset(_PROMPT_USE_CASES)


class UsageError(Exception):
    """An expected command-line, configuration, or input-data error."""


def load_jsonl_records(
    path: Path,
    field_name: str,
    description: str,
    *,
    validate_prompt_use_case: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise UsageError(
                        f"invalid JSON in {path} at line {line_number}: {exc.msg}"
                    ) from None
                if not isinstance(record, dict):
                    raise UsageError(
                        f"invalid record in {path} at line {line_number}: expected object"
                    )
                record_id = record.get("id")
                if not isinstance(record_id, str) or not record_id.strip():
                    raise UsageError(
                        f"invalid record in {path} at line {line_number}: "
                        "expected a nonempty string id"
                    )
                field_value = record.get(field_name)
                if not isinstance(field_value, str) or not field_value.strip():
                    raise UsageError(
                        f"invalid record in {path} at line {line_number}: "
                        f"expected a nonempty string {field_name!r}"
                    )
                if validate_prompt_use_case:
                    use_case = record.get("use_case")
                    if not isinstance(use_case, str) or not use_case.strip():
                        raise UsageError(
                            f"invalid record in {path} at line {line_number}: "
                            "expected a nonempty string use_case"
                        )
                    if use_case not in _PROMPT_USE_CASE_SET:
                        allowed = ", ".join(_PROMPT_USE_CASES)
                        raise UsageError(
                            f"invalid record in {path} at line {line_number}: "
                            f"use_case must be one of {allowed}"
                        )
                if record_id in seen_ids:
                    raise UsageError(
                        f"duplicate id {record_id!r} in {path} at line {line_number}"
                    )
                seen_ids.add(record_id)
                records.append(record)
    except UnicodeDecodeError as exc:
        raise UsageError(f"could not decode {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UsageError(f"could not read {path}: {exc}") from None
    if not records:
        raise UsageError(f"{description} file is empty: {path}")
    return records


def load_prompts(path: Path) -> list[dict[str, Any]]:
    return load_jsonl_records(
        path, "prompt", "prompts", validate_prompt_use_case=True
    )


def load_id_text_map(path: Path, field_name: str, description: str) -> dict[str, str]:
    records = load_jsonl_records(path, field_name, description)
    return {record["id"]: record[field_name] for record in records}


def load_config(path: Path) -> dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"could not decode config {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UsageError(f"could not read config {path}: {exc}") from None
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"invalid JSON in config {path}: {exc.msg}") from None
    frozen = document.get("frozen_decoding") if isinstance(document, dict) else None
    if not isinstance(frozen, dict):
        raise UsageError(f"config {path} is missing a 'frozen_decoding' object")
    result: dict[str, str] = {}
    for name in ("model", "reasoning_effort", "system_prompt"):
        value = frozen.get(name)
        if not isinstance(value, str) or not value.strip():
            raise UsageError(
                f"config {path} frozen_decoding is missing a nonempty {name!r}"
            )
        result[name] = value
    return result


def write_output(path: Path, records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True))
                handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_meta(
    args: argparse.Namespace,
    config: dict[str, str],
    status: dict[str, str],
    revision_iterations: dict[str, int],
    residual_findings: dict[str, list[dict[str, Any]]],
    literal_preservation: dict[str, dict[str, Any]],
    diagnostics_by_id: dict[str, dict[str, Any]],
    started: float,
    finished: float,
) -> None:
    meta = {
        "config": {
            "model": config["model"],
            "reasoning_effort": config["reasoning_effort"],
            "system_prompt": config["system_prompt"],
        },
        "prompts": str(args.prompts),
        "mode": args.mode,
        "source": str(args.source) if args.source is not None else None,
        "status": status,
        "revision_iterations": revision_iterations,
        "residual_findings": residual_findings,
        "literal_preservation": literal_preservation,
        "diagnostics": diagnostics_by_id,
        "started": started,
        "finished": finished,
    }
    meta_path = args.out.parent / f"{args.out.name}.meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
