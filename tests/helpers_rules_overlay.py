"""Shared fixtures and builders for overlay merge tests."""

from pathlib import Path

BASE_YAML = """version: 1
rules:
  - id: alpha
    severity: warn
    detector: '(?i)\\balpha\\b'
    message: Alpha message.
    exceptions: []

  - id: beta
    severity: info
    detector: '(?i)\\bbeta\\b'
    message: Beta message.
    exceptions: [beta exception]

  - id: gamma
    severity: warn
    detector: '(?i)\\bgamma\\b'
    message: Gamma message.
    exceptions: []
"""


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def base_file(rules_root: Path) -> Path:
    return write(rules_root / "base.yaml", BASE_YAML)


def ids_of(raw_rules: list[dict]) -> list[str]:
    return [rule["id"] for rule in raw_rules]
