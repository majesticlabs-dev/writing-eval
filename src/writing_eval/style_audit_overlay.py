"""Merge `extends` rule overlays into one effective raw rule list.

Merging is shape-only. Severity enums, named detectors, regex compilation, and
the final duplicate-id check all stay downstream in `style_audit_rules`, so they
run exactly once against the fully merged list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .style_audit_paths import BUILTIN_RULES_PATH

_MAX_EXTENDS_DEPTH = 16
_BUILTIN_TARGET = "builtin"
_OVERLAY_FIELDS = ("id", "severity", "detector", "message", "exceptions", "enabled")
_OVERRIDABLE_FIELDS = ("severity", "detector", "message", "exceptions")
_NEW_RULE_FIELDS = ("id", "severity", "detector", "message", "exceptions")
_NEW_RULE_REQUIRED = ("id", "severity", "detector", "message")


def _load_document(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError as error:
        raise ValueError(f"Rule file not found: {path}") from error
    except OSError as error:
        raise ValueError(f"Could not read rule file {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error


def _own_rules(document: Any, path: Path) -> list[Any]:
    if isinstance(document, dict):
        if "rules" not in document:
            raise ValueError(f"Rule YAML mapping in {path} must contain a 'rules' list")
        raw_rules = document["rules"]
    else:
        raw_rules = document
    if not isinstance(raw_rules, list):
        raise ValueError(
            f"Rule YAML in {path} must be a list or a mapping containing a 'rules' list"
        )
    return raw_rules


def _base_path(overlay_path: Path, extends: Any) -> Path:
    if not isinstance(extends, str) or not extends.strip():
        raise ValueError(f"'extends' in {overlay_path} must be a nonempty string")
    if extends == _BUILTIN_TARGET:
        base_path = BUILTIN_RULES_PATH
    else:
        base_path = (overlay_path.parent / extends).resolve()
    if not base_path.is_file():
        raise ValueError(
            f"'extends' target of {overlay_path} was not found: {base_path}"
        )
    return base_path


def _index_of(rules: list[Any], rule_id: str) -> int | None:
    for index, rule in enumerate(rules):
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            return index
    return None


def _overlay_id(entry: Any, index: int, overlay_path: Path) -> str:
    if not isinstance(entry, dict):
        raise ValueError(
            f"Overlay rule at index {index} in {overlay_path} must be a mapping"
        )
    rule_id = entry.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError(
            f"Overlay rule at index {index} in {overlay_path} "
            "must have a nonempty string 'id'"
        )
    unknown = [key for key in entry if key not in _OVERLAY_FIELDS]
    if unknown:
        raise ValueError(
            f"Overlay rule {rule_id!r} in {overlay_path} has unsupported "
            f"field(s): {', '.join(str(key) for key in unknown)}; "
            f"allowed fields are: {', '.join(_OVERLAY_FIELDS)}"
        )
    return rule_id


def _new_rule(entry: dict[str, Any], rule_id: str, overlay_path: Path) -> dict[str, Any]:
    if entry.get("enabled") is False:
        raise ValueError(
            f"Overlay {overlay_path} sets 'enabled: false' on unknown id {rule_id!r}"
        )
    missing = [field for field in _NEW_RULE_REQUIRED if field not in entry]
    if missing:
        raise ValueError(
            f"New overlay rule {rule_id!r} in {overlay_path} is missing required "
            f"field(s): {', '.join(missing)}"
        )
    return {field: entry[field] for field in _NEW_RULE_FIELDS if field in entry}


def _override(base_rule: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_rule)
    for field in _OVERRIDABLE_FIELDS:
        if field in entry:
            merged[field] = entry[field]
    return merged


def _apply_overlay(
    overlay_path: Path, own_rules: list[Any], base_rules: list[Any]
) -> list[Any]:
    working = list(base_rules)
    seen_ids: set[str] = set()
    for index, entry in enumerate(own_rules):
        rule_id = _overlay_id(entry, index, overlay_path)
        if rule_id in seen_ids:
            raise ValueError(
                f"Duplicate overlay rule id {rule_id!r} in {overlay_path}"
            )
        seen_ids.add(rule_id)
        position = _index_of(working, rule_id)
        if position is None:
            working.append(_new_rule(entry, rule_id, overlay_path))
        elif entry.get("enabled") is False:
            del working[position]
        else:
            working[position] = _override(working[position], entry)
    return working


def _resolve(path: Path, chain: list[Path]) -> list[Any]:
    if len(chain) > _MAX_EXTENDS_DEPTH:
        raise ValueError(
            f"'extends' chain reached {path} beyond the maximum depth "
            f"of {_MAX_EXTENDS_DEPTH}"
        )
    document = _load_document(path)
    own_rules = _own_rules(document, path)
    extends = document.get("extends") if isinstance(document, dict) else None
    if extends is None:
        return list(own_rules)
    base_path = _base_path(path, extends)
    if base_path == path or base_path in chain:
        raise ValueError(f"Circular 'extends' chain: {path} extends {base_path}")
    base_rules = _resolve(base_path, [*chain, path])
    return _apply_overlay(path, own_rules, base_rules)


def resolve_raw_rules(path: str | Path) -> list[dict]:
    """Return the effective raw rule mappings for a rule file, overlays merged.

    Raises ValueError for any malformed rule file, overlay entry, or
    `extends` chain.
    """

    return _resolve(Path(path).resolve(), [])
