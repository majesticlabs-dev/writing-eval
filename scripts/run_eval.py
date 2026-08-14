#!/usr/bin/env python3
"""Run writing evaluation for a directory of system output JSONL files."""

from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from writing_eval.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
