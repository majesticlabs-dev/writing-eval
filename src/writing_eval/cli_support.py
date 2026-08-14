"""Shared types and input helpers for writing-eval command implementations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from .metrics import tokenize


class UserError(Exception):
    """An expected command-line or input-data error."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UserError(message)


def load_jsonl_records(path: Path, description: str = "JSONL") -> list[dict[str, Any]]:
    """Read one JSON object per line with a nonempty unique string ``id``."""

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
                record_text = record.get("text")
                if not isinstance(record_text, str) or not record_text.strip():
                    raise UserError(
                        f"invalid record in {path} at line {line_number}: "
                        "expected a nonempty string text"
                    )
                if not tokenize(record_text):
                    raise UserError(
                        f"invalid record in {path} at line {line_number}: "
                        "expected text with at least one word token"
                    )
                if record_id in seen_ids:
                    raise UserError(
                        f"duplicate id {record_id!r} in {path} at line {line_number}"
                    )
                seen_ids.add(record_id)
                records.append(record)
    except UnicodeDecodeError as exc:
        raise UserError(f"could not decode {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UserError(f"could not read {path}: {exc}") from None
    if not records:
        raise UserError(f"{description} file is empty: {path}")
    return records


def load_json_document(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except UnicodeDecodeError as exc:
        raise UserError(f"could not decode {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise UserError(f"could not read {path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise UserError(f"invalid JSON in {path}: {exc.msg}") from None


def write_text_file(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise UserError(f"could not write {path}: {exc}") from None


@dataclass(frozen=True)
class CommandContext:
    """Live facade dependencies passed to extracted command modules."""

    load_jsonl: Callable[..., list[dict[str, Any]]]
    load_rules: Callable[[Path], Any]
    audit_text: Callable[[str, Any], list[Any]]
    rules_version: Callable[[Path], Any]
    write_text: Callable[[Path, str], None]
