"""Atomic dest-directory staging for profile publication and cache sidecars."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stage_bytes(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        try:
            handle = os.fdopen(fd, "wb")
        except Exception:
            os.close(fd)
            raise
        with handle:
            handle.write(payload)
            handle.flush()
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return tmp_name


def _stage_text(path: Path, text: str) -> str:
    return _stage_bytes(path, text.encode("utf-8"))


def _commit_staged(pairs: Sequence[tuple[str, Path]]) -> None:
    backups: dict[Path, str | None] = {}
    pending = list(pairs)
    replaced: list[Path] = []
    try:
        for _, dest in pairs:
            if dest.is_file():
                backups[dest] = _stage_bytes(dest, dest.read_bytes())
            else:
                backups[dest] = None
        while pending:
            staged, dest = pending[0]
            os.replace(staged, dest)
            replaced.append(dest)
            pending.pop(0)
    except Exception:
        for dest in reversed(replaced):
            backup = backups.get(dest)
            if backup is None:
                dest.unlink(missing_ok=True)
            else:
                try:
                    os.replace(backup, dest)
                    backups[dest] = None
                except OSError:
                    backups.pop(dest, None)
        raise
    finally:
        for staged, _ in pending:
            Path(staged).unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None:
                Path(backup).unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    replaced = False
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        except Exception:
            os.close(fd)
            raise
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        os.replace(tmp_name, path)
        replaced = True
    finally:
        if not replaced:
            Path(tmp_name).unlink(missing_ok=True)
