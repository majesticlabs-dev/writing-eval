import json
from pathlib import Path

import pytest

from writing_eval.profile_io import validate_profile_name
from writing_eval.profiles import ProfileError, build_profile, list_profiles, load_profile

from tests.helpers_profiles import _build_demo, _write_sources


def test_load_profile_rejects_mixed_reference_pair(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    with (out / "references.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"id": "gamma", "text": "Extra prose after the original build.", "file": "gamma.md"}
            )
            + "\n"
        )
    with pytest.raises(ProfileError, match="rebuild it with"):
        load_profile(tmp_path / "profiles", "demo")


def test_load_profile_rejects_missing_or_invalid_references_hash(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    profile_path = out / "profile.json"
    data = json.loads(profile_path.read_text(encoding="utf-8"))

    data.pop("references_sha256")
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="missing or invalid references_sha256"):
        load_profile(tmp_path / "profiles", "demo")

    data["references_sha256"] = "not-a-hash"
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="missing or invalid references_sha256"):
        load_profile(tmp_path / "profiles", "demo")

    data["references_sha256"] = "0" * 64
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="does not match installed references"):
        load_profile(tmp_path / "profiles", "demo")


def test_load_profile_rejects_bool_metrics_version(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    profile_path = out / "profile.json"
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    data["metrics_version"] = True
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="rebuild it with"):
        load_profile(tmp_path / "profiles", "demo")


def test_validate_profile_name_rejects_traversal_and_nesting() -> None:
    for name in ("", ".", "..", "/tmp/evil", "foo/bar", "foo/../bar"):
        with pytest.raises(ProfileError, match="invalid profile name"):
            validate_profile_name(name)
    assert validate_profile_name("demo") == "demo"


def test_build_and_load_reject_traversal_names(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    with pytest.raises(ProfileError, match="invalid profile name"):
        build_profile("..", [sources], tmp_path / "profiles" / "escaped", "2026-07-23")
    with pytest.raises(ProfileError, match="invalid profile name"):
        load_profile(tmp_path / "profiles", "..")
    with pytest.raises(ProfileError, match="invalid profile name"):
        load_profile(tmp_path / "profiles", str(tmp_path / "escaped"))


def test_list_profiles_omits_unloadable_silently(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    broken = root / "broken"
    broken.mkdir()
    (broken / "profile.json").write_text("{}", encoding="utf-8")
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
    skipped: dict[str, str] = {}
    listed = list_profiles(
        root, on_skip=lambda path, text: skipped.__setitem__(path.name, text)
    )
    assert [item["name"] for item in listed] == ["demo"]
    assert list_profiles(root) == listed
    assert "broken" in skipped
    assert "rebuild it with" in skipped["mixed"]
