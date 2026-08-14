"""Shared helpers for comparison reports."""

from collections.abc import Mapping
from typing import Any


def system_map(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    systems = report.get("systems")
    if systems is None:
        raise ValueError("report is missing a 'systems' list")
    result: dict[str, Mapping[str, Any]] = {}
    for system in systems:
        name = system.get("system_name")
        if not isinstance(name, str) or not name:
            raise ValueError("system entry is missing a valid 'system_name'")
        if name in result:
            raise ValueError(f"duplicate system_name {name!r} within one report")
        result[name] = system
    return result


def format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
