import hashlib
import json
from pathlib import Path

import pytest

from writing_eval.profile_models import METRICS_VERSION
from writing_eval.profiles import ProfileError, build_profile, load_profile

from tests.helpers_profiles import (
    PROSE_ONE,
    PROSE_TWO,
    _write_sources,
)


def test_build_writes_references_jsonl_schema(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")

    lines = (out / "references.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert [record["id"] for record in records] == ["alpha", "beta"]
    for record in records:
        assert set(record) == {"id", "text", "file"}
        assert record["text"].strip()


def test_build_writes_profile_json_schema(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    data = build_profile("demo", [sources], out, "2026-07-23")

    profile = json.loads((out / "profile.json").read_text(encoding="utf-8"))
    assert profile == data
    assert profile["name"] == "demo"
    assert profile["created"] == "2026-07-23"
    assert profile["metrics_version"] == METRICS_VERSION
    assert [source["id"] for source in profile["sources"]] == ["alpha", "beta"]
    for source in profile["sources"]:
        assert set(source) == {"id", "file", "word_count"}
    assert profile["total_words"] == sum(
        source["word_count"] for source in profile["sources"]
    )
    expected_hash = hashlib.sha256(
        (out / "references.jsonl").read_bytes()
    ).hexdigest()
    assert profile["references_sha256"] == expected_hash
    assert len(profile["references_sha256"]) == 64
    statistics = profile["statistics"]
    assert set(statistics) == {
        "mean_sentence_length",
        "sentence_length_variance",
        "repeated_opening_rate",
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "mtld",
        "paragraph_stats",
        "top_tokens",
    }
    assert len(statistics["top_tokens"]) <= 20
    assert all(set(token) == {"token", "count"} for token in statistics["top_tokens"])
    # Stopwords are excluded so the token list characterizes style vocabulary.
    assert "the" not in {token["token"] for token in statistics["top_tokens"]}


def test_load_profile_rejects_missing_or_older_metrics_version(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    profile_path = out / "profile.json"
    data = json.loads(profile_path.read_text(encoding="utf-8"))

    data.pop("metrics_version")
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="rebuild it with"):
        load_profile(tmp_path / "profiles", "demo")

    data["metrics_version"] = 0
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="metric semantics version 0"):
        load_profile(tmp_path / "profiles", "demo")


def test_build_is_deterministic(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    first = tmp_path / "one"
    second = tmp_path / "two"
    build_profile("demo", [sources], first, "2026-07-23")
    build_profile("demo", [sources], second, "2026-07-23")
    assert (first / "profile.json").read_text(encoding="utf-8") == (
        second / "profile.json"
    ).read_text(encoding="utf-8")
    assert (first / "references.jsonl").read_text(encoding="utf-8") == (
        second / "references.jsonl"
    ).read_text(encoding="utf-8")


def test_build_strips_frontmatter(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "doc.md").write_text(
        "---\ntitle: Secret\nauthor: X\n---\n" + PROSE_ONE, encoding="utf-8"
    )
    out = tmp_path / "profile"
    build_profile("demo", [sources], out, "2026-07-23")
    record = json.loads(
        (out / "references.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert "title: Secret" not in record["text"]
    assert record["text"].startswith("The founder")


def test_source_ids_are_slugified_stems(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "My Great Post!.md").write_text(PROSE_ONE, encoding="utf-8")
    out = tmp_path / "profile"
    data = build_profile("demo", [sources], out, "2026-07-23")
    assert data["sources"][0]["id"] == "my-great-post"


def test_duplicate_source_ids_raise(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "post.md").write_text(PROSE_ONE, encoding="utf-8")
    (second / "post.txt").write_text(PROSE_TWO, encoding="utf-8")
    with pytest.raises(ProfileError):
        build_profile("demo", [first, second], tmp_path / "profile", "2026-07-23")


def test_empty_source_raises(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "empty.md").write_text("   \n", encoding="utf-8")
    with pytest.raises(ProfileError):
        build_profile("demo", [sources], tmp_path / "profile", "2026-07-23")


def test_source_without_word_tokens_raises(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "punctuation.md").write_text("... !!!\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="no word tokens"):
        build_profile("demo", [sources], tmp_path / "profile", "2026-07-23")


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(ProfileError):
        build_profile(
            "demo", [tmp_path / "nope.md"], tmp_path / "profile", "2026-07-23"
        )


def test_no_source_files_raises(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    with pytest.raises(ProfileError):
        build_profile("demo", [sources], tmp_path / "profile", "2026-07-23")


def test_unsupported_source_type_raises(tmp_path: Path) -> None:
    doc = tmp_path / "notes.rst"
    doc.write_text(PROSE_ONE, encoding="utf-8")
    with pytest.raises(ProfileError):
        build_profile("demo", [doc], tmp_path / "profile", "2026-07-23")


def test_invalid_utf8_source_raises_clean_error(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "invalid.md").write_bytes(b"\xff\xfe invalid UTF-8")

    with pytest.raises(ProfileError, match="could not decode.*as UTF-8"):
        build_profile("demo", [sources], tmp_path / "profile", "2026-07-23")


def test_load_profile_rejects_invalid_utf8_metadata(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    out = tmp_path / "profiles" / "demo"
    build_profile("demo", [sources], out, "2026-07-23")
    (out / "profile.json").write_bytes(b'{"name": "\xff\xfe"}')

    with pytest.raises(ProfileError, match="could not decode"):
        load_profile(tmp_path / "profiles", "demo")
