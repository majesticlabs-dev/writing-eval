"""Canonical filesystem location of the builtin style-audit rule set."""

from __future__ import annotations

from pathlib import Path

BUILTIN_RULES_PATH = Path(__file__).resolve().parent / "rules" / "style-audit.yaml"
