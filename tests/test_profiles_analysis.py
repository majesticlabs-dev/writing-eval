from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import pytest

from writing_eval.metrics import tokenize
from writing_eval.profiles import (
    _STOPWORDS,
    ProfileError,
    build_profile,
    build_style_gap,
    list_profiles,
    load_profile,
)


from tests.helpers_profiles import (
    PROSE_ONE,
    PROSE_TWO,
    _build_demo,
    _write_sources,
    run_cli,
)

def test_list_profiles_reports_counts_sorted(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    build_profile("beta", [_write_sources(tmp_path / "sb")], root / "beta", "2026-07-23")
    build_profile("alpha", [_write_sources(tmp_path / "sa")], root / "alpha", "2026-07-23")
    summaries = list_profiles(root)
    assert [summary["name"] for summary in summaries] == ["alpha", "beta"]
    assert summaries[0]["sources"] == 2
    assert summaries[0]["total_words"] > 0


def test_list_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(ProfileError):
        list_profiles(tmp_path / "nope")


def test_load_missing_profile_raises(tmp_path: Path) -> None:
    with pytest.raises(ProfileError):
        load_profile(tmp_path, "ghost")


def test_load_missing_references_raises(tmp_path: Path) -> None:
    directory = tmp_path / "profiles" / "demo"
    directory.mkdir(parents=True)
    (directory / "profile.json").write_text(
        json.dumps({"name": "demo", "statistics": {}}), encoding="utf-8"
    )
    with pytest.raises(ProfileError):
        load_profile(tmp_path / "profiles", "demo")


def test_load_returns_profile_with_statistics(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    assert profile.name == "demo"
    assert profile.references_path.is_file()
    assert "mean_sentence_length" in profile.statistics


def test_build_style_gap_schema(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    reference_texts = [
        json.loads(line)["text"]
        for line in profile.references_path.read_text(encoding="utf-8").splitlines()
    ]
    reference_counts: Counter[str] = Counter()
    for reference_text in reference_texts:
        reference_counts.update(tokenize(reference_text))
    gap = build_style_gap(
        "demo",
        "Builders ship early and often. Momentum favors them decisively every day.",
        profile.statistics,
        reference_counts,
    )
    assert gap["profile"] == "demo"
    assert [metric["metric"] for metric in gap["metrics"]] == [
        "mean_sentence_length",
        "sentence_length_variance",
        "repeated_opening_rate",
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "mtld",
    ]
    for metric in gap["metrics"]:
        assert set(metric) == {"metric", "draft", "profile", "delta"}
    assert isinstance(gap["token_1gram_l2"], float)
    assert isinstance(gap["top_overrepresented"], list)


def test_build_style_gap_excludes_stopwords_from_overrepresented() -> None:
    # The draft leans on function words far more than the reference corpus; the
    # style-gap ranking must surface the distinctive content word ("beacon") and
    # never a function word like "the" or "and".
    reference_texts = [
        "Founders ship products. Networks compound advantage over quarters.",
        "Attention guards scarce resources. Patience makes flywheels spin.",
    ]
    statistics = {
        "mean_sentence_length": 8.0,
        "sentence_length_variance": 4.0,
        "repeated_opening_rate": 0.0,
        "flesch_reading_ease": 60.0,
        "flesch_kincaid_grade": 8.0,
        "mtld": 30.0,
    }
    reference_counts: Counter[str] = Counter()
    for reference_text in reference_texts:
        reference_counts.update(tokenize(reference_text))
    draft = "The beacon and the beacon and the beacon on the beacon shines."
    gap = build_style_gap("demo", draft, statistics, reference_counts)
    tokens = {item["token"] for item in gap["top_overrepresented"]}
    assert tokens, "expected at least one overrepresented content term"
    assert tokens.isdisjoint(_STOPWORDS)
    assert "the" not in tokens
    assert "and" not in tokens
    assert "beacon" in tokens


def test_list_profiles_stays_silent_without_callback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "profiles"
    root.mkdir()
    broken = root / "broken"
    broken.mkdir()
    (broken / "profile.json").write_text("[]", encoding="utf-8")

    assert list_profiles(root) == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_list_profiles_reports_invalid_entries_through_callback(
    tmp_path: Path,
) -> None:
    root = _build_demo(tmp_path)
    invalid_documents = {
        "bad_json": "{not json",
        "bad_object": "[]",
        "bad_sources": '{"sources": 3, "total_words": 100}',
        "bad_total_words": '{"sources": [], "total_words": true}',
    }
    for name, document in invalid_documents.items():
        directory = root / name
        directory.mkdir()
        (directory / "profile.json").write_text(document, encoding="utf-8")
    notes: list[tuple[str, str]] = []

    summaries = list_profiles(
        root,
        on_skip=lambda path, error: notes.append((path.name, error)),
    )

    assert [summary["name"] for summary in summaries] == ["demo"]
    assert len(notes) == len(invalid_documents)
    errors = dict(notes)
    assert "non-object top-level JSON" in errors["bad_object"]
    assert "sources field is not a list" in errors["bad_sources"]
    assert "total_words field is not a number" in errors["bad_total_words"]
