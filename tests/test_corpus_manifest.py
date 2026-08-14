"""Corpus manifest tests."""

from pathlib import Path
import pytest

from writing_eval.corpus import collect_samples, load_manifest
from tests.helpers_corpus import write_manifest

def test_load_manifest_reads_valid_records(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {"path": "a.md", "use_case": "article_section", "title": "A"},
            {"path": "b.md", "use_case": "product_writing", "title": "B"},
        ],
    )
    records = load_manifest(manifest)
    assert [record["path"] for record in records] == ["a.md", "b.md"]


def test_load_manifest_rejects_missing_key(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [{"path": "a.md", "use_case": "article_section"}],
    )
    with pytest.raises(ValueError, match="line 1"):
        load_manifest(manifest)


def test_load_manifest_rejects_bad_use_case(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [{"path": "a.md", "use_case": "poetry", "title": "A"}],
    )
    with pytest.raises(ValueError, match="line 1"):
        load_manifest(manifest)


def test_load_manifest_rejects_duplicate_path(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {"path": "a.md", "use_case": "article_section", "title": "A"},
            {"path": "a.md", "use_case": "product_writing", "title": "A2"},
        ],
    )
    with pytest.raises(ValueError, match="line 2"):
        load_manifest(manifest)


def test_load_manifest_rejects_empty_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(manifest)


def test_load_manifest_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="could not read manifest"):
        load_manifest(tmp_path / "missing.jsonl")


def test_load_manifest_accepts_bool_holdout_only(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {
                "path": "a.md",
                "use_case": "article_section",
                "title": "A",
                "holdout_only": True,
            },
            {
                "path": "b.md",
                "use_case": "article_section",
                "title": "B",
                "holdout_only": False,
            },
        ],
    )
    records = load_manifest(manifest)
    assert records[0]["holdout_only"] is True
    assert records[1]["holdout_only"] is False


def test_load_manifest_rejects_non_bool_holdout_only(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {
                "path": "a.md",
                "use_case": "article_section",
                "title": "A",
                "holdout_only": "yes",
            }
        ],
    )
    with pytest.raises(ValueError, match="line 1"):
        load_manifest(manifest)


def test_load_manifest_rejects_invalid_utf8(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_bytes(b'{"path": "\xff\xfe.md", "use_case": "a", "title": "A"}\n')
    with pytest.raises(ValueError, match="could not decode manifest .* as UTF-8"):
        load_manifest(manifest)


def test_collect_samples_rejects_invalid_utf8_sample(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [{"path": "a.md", "use_case": "article_section", "title": "A"}],
    )
    (tmp_path / "a.md").write_bytes(b"Text with \xff bytes.\n")
    with pytest.raises(ValueError, match="could not decode sample .* as UTF-8"):
        collect_samples(load_manifest(manifest), tmp_path)
