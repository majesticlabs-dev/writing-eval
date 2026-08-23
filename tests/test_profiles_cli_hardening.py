import json
from pathlib import Path

from tests.helpers_profiles import _build_demo, _write_sources, run_cli


def test_cli_profile_list_omits_unloadable_profiles(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    invalid = root / "invalid"
    invalid.mkdir()
    (invalid / "profile.json").write_text(
        '{"sources": 3, "total_words": 100}',
        encoding="utf-8",
    )
    mixed = root / "mixed"
    mixed.mkdir()
    (mixed / "profile.json").write_text(
        (root / "demo" / "profile.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (mixed / "references.jsonl").write_text(
        '{"id": "x", "text": "Only this side of the pair."}\n',
        encoding="utf-8",
    )

    result = run_cli("profile", "list", "--profiles-root", root)

    assert result.returncode == 0
    assert "demo: 2 sources" in result.stdout
    assert "invalid:" not in result.stdout
    assert "mixed:" not in result.stdout
    assert result.stderr.count("skipped unreadable profile") == 2
    assert "invalid" in result.stderr
    assert "mixed" in result.stderr
    assert "rebuild it with" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_profile_cache_smoke_and_errors(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    cache_dir = root / "demo" / "cache"
    tokens = (cache_dir / "tokens.json").read_bytes()
    (cache_dir / "tokens.json").unlink()

    refreshed = run_cli("profile", "cache", "demo", "--profiles-root", root)
    assert refreshed.returncode == 0, refreshed.stderr
    assert "refreshed cache" in refreshed.stdout
    assert (cache_dir / "tokens.json").is_file()
    assert (cache_dir / "tokens.json").read_bytes() == tokens
    assert "Traceback" not in refreshed.stderr

    missing = tmp_path / "empty-root"
    missing.mkdir()
    missing_result = run_cli("profile", "cache", "demo", "--profiles-root", missing)
    assert missing_result.returncode == 1
    assert "references not found" in missing_result.stderr
    assert "Traceback" not in missing_result.stderr



def test_cli_rejects_profile_name_traversal(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    root = tmp_path / "profiles"
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early.\n", encoding="utf-8")
    names = ("..", ".", str(tmp_path / "escaped"), "nested/name")
    for name in names:
        built = run_cli(
            "profile", "build", name, "--from", sources, "--profiles-root", root
        )
        assert built.returncode == 1, built.stderr
        assert "invalid profile name" in built.stderr
        assert "Traceback" not in built.stderr
        cached = run_cli("profile", "cache", name, "--profiles-root", root)
        assert cached.returncode == 1
        assert "invalid profile name" in cached.stderr
        assert "Traceback" not in cached.stderr
        checked = run_cli(
            "check", draft, "--style", name, "--profiles-root", root
        )
        assert checked.returncode == 1
        assert "invalid profile name" in checked.stderr
        assert "Traceback" not in checked.stderr
    assert not (tmp_path / "escaped").exists()
    assert list(root.glob("**/*")) == []


def test_cli_check_style_rejects_mixed_reference_pair(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    references = root / "demo" / "references.jsonl"
    with references.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"id": "gamma", "text": "Extra prose after the original build.", "file": "gamma.md"}
            )
            + "\n"
        )
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early.\n", encoding="utf-8")
    result = run_cli(
        "check", draft, "--style", "demo", "--profiles-root", root
    )
    assert result.returncode == 1
    assert "rebuild it with" in result.stderr
    assert "Traceback" not in result.stderr
