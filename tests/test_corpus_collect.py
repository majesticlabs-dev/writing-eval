"""Corpus sample-collection tests."""

from pathlib import Path
import pytest

from writing_eval.corpus import collect_samples
from tests.helpers_corpus import write_sample

def test_collect_samples_strips_frontmatter_and_whitespace(tmp_path: Path) -> None:
    write_sample(
        tmp_path,
        "a.md",
        "---\ntitle: A\n---\n\n  Real content here.  \n",
    )
    manifest = [{"path": "a.md", "use_case": "article_section", "title": "A"}]
    samples = collect_samples(manifest, tmp_path)
    assert len(samples) == 1
    assert samples[0]["text"] == "Real content here."
    assert samples[0]["word_count"] == 3


def test_collect_samples_without_frontmatter_keeps_text(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "  Plain content.  ")
    manifest = [{"path": "a.md", "use_case": "article_section", "title": "A"}]
    samples = collect_samples(manifest, tmp_path)
    assert samples[0]["text"] == "Plain content."


def test_collect_samples_rejects_empty_text(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "---\ntitle: A\n---\n\n   \n")
    manifest = [{"path": "a.md", "use_case": "article_section", "title": "A"}]
    with pytest.raises(ValueError, match="a.md"):
        collect_samples(manifest, tmp_path)


def test_collect_samples_stable_id_is_deterministic(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "Some content that is real prose.")
    manifest = [{"path": "a.md", "use_case": "article_section", "title": "A"}]
    first = collect_samples(manifest, tmp_path)
    second = collect_samples(manifest, tmp_path)
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["id"].startswith("sample-")


def test_collect_samples_record_shape(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "Some content that is real prose.")
    manifest = [{"path": "a.md", "use_case": "article_section", "title": "A"}]
    sample = collect_samples(manifest, tmp_path)[0]
    assert set(sample) == {
        "id",
        "use_case",
        "title",
        "source_path",
        "text",
        "word_count",
    }
    assert sample["source_path"] == "a.md"


def test_collect_samples_rejects_duplicate_ids(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "Some content that is real prose.")
    manifest = [
        {"path": "a.md", "use_case": "article_section", "title": "A"},
        {"path": "./a.md", "use_case": "product_writing", "title": "A again"},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        collect_samples(manifest, tmp_path)


def test_collect_samples_missing_file_raises_clear_error(tmp_path: Path) -> None:
    manifest = [{"path": "missing.md", "use_case": "article_section", "title": "A"}]
    with pytest.raises(ValueError, match="missing.md"):
        collect_samples(manifest, tmp_path)


def test_collect_samples_carries_holdout_only_through(tmp_path: Path) -> None:
    write_sample(tmp_path, "a.md", "Some content that is real prose.")
    write_sample(tmp_path, "b.md", "Other content that is also real prose.")
    manifest = [
        {
            "path": "a.md",
            "use_case": "article_section",
            "title": "A",
            "holdout_only": True,
        },
        {"path": "b.md", "use_case": "article_section", "title": "B"},
    ]
    samples = collect_samples(manifest, tmp_path)
    by_path = {sample["source_path"]: sample for sample in samples}
    assert by_path["a.md"]["holdout_only"] is True
    assert "holdout_only" not in by_path["b.md"]
