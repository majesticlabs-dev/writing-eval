from pathlib import Path

import pytest

from writing_eval.profiles import build_profile, load_profile

from tests.helpers_profiles import _write_sources


def test_build_atomic_writes_leave_no_tmp_files(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    assert list(out.glob(".*.tmp")) == []
    assert list((out / "cache").glob(".*.tmp")) == []


def test_failed_profile_write_does_not_install_partial_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    original_replace = __import__("os").replace

    def _fail_profile_replace(src, dst):
        if Path(dst).name == "profile.json":
            raise OSError("disk full")
        return original_replace(src, dst)

    monkeypatch.setattr("writing_eval.profile_atomic.os.replace", _fail_profile_replace)
    with pytest.raises(OSError, match="disk full"):
        build_profile("demo", [sources], out, "2026-07-23")
    assert not (out / "profile.json").exists()
    assert list(out.glob(".*.tmp")) == []


def test_failed_metadata_commit_preserves_existing_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    profile_path = out / "profile.json"
    references_path = out / "references.jsonl"
    original_profile = profile_path.read_bytes()
    original_references = references_path.read_bytes()

    replacement = tmp_path / "replacement"
    replacement.mkdir()
    (replacement / "other.md").write_text(
        "Different prose for a later rebuild that must not stick.\n",
        encoding="utf-8",
    )
    original_replace = __import__("os").replace

    def _fail_profile_replace(src, dst):
        if Path(dst).name == "profile.json":
            raise OSError("disk full")
        return original_replace(src, dst)

    monkeypatch.setattr("writing_eval.profile_atomic.os.replace", _fail_profile_replace)
    with pytest.raises(OSError, match="disk full"):
        build_profile("demo", [replacement], out, "2026-08-01")

    assert profile_path.read_bytes() == original_profile
    assert references_path.read_bytes() == original_references
    assert list(out.glob(".*.tmp")) == []
    loaded = load_profile(tmp_path / "profiles", "demo")
    assert loaded.data["created"] == "2026-07-23"
    assert loaded.data["name"] == "demo"


def test_failed_rollback_replace_keeps_backup_without_truncating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    profile_path = out / "profile.json"
    references_path = out / "references.jsonl"
    original_profile = profile_path.read_bytes()
    original_references = references_path.read_bytes()

    replacement = tmp_path / "replacement"
    replacement.mkdir()
    (replacement / "other.md").write_text(
        "Different prose for a later rebuild that must not stick.\n",
        encoding="utf-8",
    )
    original_replace = __import__("os").replace
    reference_replaces = 0

    def _fail_restore_replace(src, dst):
        nonlocal reference_replaces
        dest = Path(dst)
        if dest.name == "profile.json":
            raise OSError("disk full")
        if dest.name == "references.jsonl":
            reference_replaces += 1
            if reference_replaces > 1:
                raise OSError("rollback replace failed")
        return original_replace(src, dst)

    monkeypatch.setattr("writing_eval.profile_atomic.os.replace", _fail_restore_replace)
    with pytest.raises(OSError, match="disk full"):
        build_profile("demo", [replacement], out, "2026-08-01")

    assert profile_path.read_bytes() == original_profile
    assert profile_path.stat().st_size == len(original_profile)
    assert references_path.is_file()
    assert references_path.stat().st_size > 0
    leftovers = [path for path in out.glob(".*.tmp") if path.is_file()]
    assert any(path.read_bytes() == original_references for path in leftovers)
