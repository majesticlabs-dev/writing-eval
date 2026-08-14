"""Tests for precomputed, validated per-profile reference-corpus caches."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from writing_eval.profile_cache import (
    ReferenceStats,
    load_reference_stats,
    refresh_reference_caches,
    write_reference_caches,
)
from writing_eval.profiles import load_profile
from writing_eval.style_audit import BUILTIN_RULES_PATH, load_rules, rules_fingerprint

from tests.helpers_profiles import _build_demo


def _builtin_rules():
    return load_rules(BUILTIN_RULES_PATH)


def test_load_reference_stats_returns_cache_after_build(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    stats, status = load_reference_stats(profile, rules, rules_fingerprint(rules))
    assert status == "cache"
    assert isinstance(stats, ReferenceStats)
    assert stats.word_count > 0
    assert sum(stats.token_counts.values()) == stats.word_count


def test_cached_and_cold_recompute_produce_identical_check_output(tmp_path: Path) -> None:
    """The single most important guarantee: a cache hit and a cold recompute
    against the same corpus and rule set must be byte-identical for every
    downstream value derived from ReferenceStats."""

    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)

    cached_stats, cached_status = load_reference_stats(profile, rules, fingerprint)
    assert cached_status == "cache"

    shutil.rmtree(profile.directory / "cache")
    cold_stats, cold_status = load_reference_stats(profile, rules, fingerprint)
    assert cold_status == "recomputed"

    assert cached_stats.word_count == cold_stats.word_count
    assert dict(cached_stats.token_counts) == dict(cold_stats.token_counts)
    assert dict(cached_stats.rule_counts) == dict(cold_stats.rule_counts)


def test_check_never_parses_references_when_fully_cached(tmp_path: Path, monkeypatch) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()

    def _boom(path):
        raise AssertionError(f"references.jsonl must not be parsed on a cache hit: {path}")

    monkeypatch.setattr("writing_eval.profile_cache._reference_texts", _boom)
    stats, status = load_reference_stats(profile, rules, rules_fingerprint(rules))
    assert status == "cache"
    assert stats.word_count > 0


def test_rule_set_change_invalidates_only_the_rule_cache(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    base_rules = _builtin_rules()
    base_fingerprint = rules_fingerprint(base_rules)

    overlay_path = tmp_path / "overlay.yaml"
    overlay_path.write_text(
        "extends: builtin\n"
        "rules:\n"
        "  - id: em_dash_ban\n"
        "    severity: info\n"
        "    detector: '\\u2014'\n"
        "    message: Overlay message for em dash.\n"
        "    exceptions: []\n",
        encoding="utf-8",
    )
    overlay_rules = load_rules(overlay_path)
    overlay_fingerprint = rules_fingerprint(overlay_rules)
    assert overlay_fingerprint != base_fingerprint

    base_stats, base_status = load_reference_stats(profile, base_rules, base_fingerprint)
    assert base_status == "cache"

    overlay_stats, overlay_status = load_reference_stats(
        profile, overlay_rules, overlay_fingerprint
    )
    assert overlay_status == "recomputed"
    assert overlay_stats.word_count == base_stats.word_count
    assert dict(overlay_stats.token_counts) == dict(base_stats.token_counts)

    cache_dir = profile.directory / "cache"
    assert (cache_dir / f"rules-{base_fingerprint[:16]}.json").is_file()
    assert (cache_dir / f"rules-{overlay_fingerprint[:16]}.json").is_file() is False


def test_refresh_prunes_stale_rules_cache(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    base_rules = _builtin_rules()
    base_fingerprint = rules_fingerprint(base_rules)

    overlay_path = tmp_path / "overlay.yaml"
    overlay_path.write_text(
        "extends: builtin\n"
        "rules:\n"
        "  - id: em_dash_ban\n"
        "    severity: info\n"
        "    detector: '\\u2014'\n"
        "    message: Overlay message for em dash.\n"
        "    exceptions: []\n",
        encoding="utf-8",
    )
    overlay_rules = load_rules(overlay_path)
    overlay_fingerprint = rules_fingerprint(overlay_rules)

    refresh_reference_caches(profile.directory, profile.references_path, overlay_rules)

    cache_dir = profile.directory / "cache"
    assert not (cache_dir / f"rules-{base_fingerprint[:16]}.json").exists()
    assert (cache_dir / f"rules-{overlay_fingerprint[:16]}.json").is_file()

    base_stats, base_status = load_reference_stats(profile, base_rules, base_fingerprint)
    overlay_stats, overlay_status = load_reference_stats(
        profile, overlay_rules, overlay_fingerprint
    )
    assert base_status == "recomputed"
    assert overlay_status == "cache"
    assert dict(base_stats.rule_counts) == dict(overlay_stats.rule_counts)


def test_refresh_removes_unrelated_stale_rules_files(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    cache_dir = profile.directory / "cache"
    stale = cache_dir / "rules-deadbeefdeadbeef.json"
    stale.write_text("{}", encoding="utf-8")

    refresh_reference_caches(
        profile.directory, profile.references_path, _builtin_rules()
    )

    fingerprint = rules_fingerprint(_builtin_rules())
    assert (cache_dir / f"rules-{fingerprint[:16]}.json").is_file()
    assert not stale.exists()


def test_appending_to_references_invalidates_both_caches(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)

    before_stats, before_status = load_reference_stats(profile, rules, fingerprint)
    assert before_status == "cache"

    with profile.references_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps({"id": "gamma", "text": "Extra prose added after the build.", "file": "gamma.md"})
            + "\n"
        )

    after_stats, after_status = load_reference_stats(profile, rules, fingerprint)
    assert after_status == "recomputed"
    assert after_stats.word_count > before_stats.word_count


def test_cold_cache_fallback_for_a_profile_built_before_caching(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    shutil.rmtree(profile.directory / "cache")
    rules = _builtin_rules()
    stats, status = load_reference_stats(profile, rules, rules_fingerprint(rules))
    assert status == "recomputed"
    assert stats.word_count > 0


def test_corrupt_tokens_cache_falls_through_without_raising(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    (profile.directory / "cache" / "tokens.json").write_text("{not valid json", encoding="utf-8")
    stats, status = load_reference_stats(profile, rules, rules_fingerprint(rules))
    assert status == "recomputed"
    assert stats.word_count > 0


def test_corrupt_rules_cache_falls_through_without_raising(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)
    rules_cache_path = profile.directory / "cache" / f"rules-{fingerprint[:16]}.json"
    rules_cache_path.write_text("not even json", encoding="utf-8")
    stats, status = load_reference_stats(profile, rules, fingerprint)
    assert status == "recomputed"
    assert stats.word_count > 0


def test_stale_references_digest_is_treated_as_a_miss(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)
    tokens_path = profile.directory / "cache" / "tokens.json"
    payload = json.loads(tokens_path.read_text(encoding="utf-8"))
    payload["references_sha256"] = "0" * 64
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")
    stats, status = load_reference_stats(profile, rules, fingerprint)
    assert status == "recomputed"
    assert stats.word_count > 0


def test_missing_word_count_field_is_treated_as_a_miss(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)
    tokens_path = profile.directory / "cache" / "tokens.json"
    payload = json.loads(tokens_path.read_text(encoding="utf-8"))
    del payload["word_count"]
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")
    stats, status = load_reference_stats(profile, rules, fingerprint)
    assert status == "recomputed"
    assert stats.word_count > 0


def test_write_reference_caches_is_atomic_and_leaves_no_tmp_file(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    cache_dir = profile.directory / "cache"
    leftover = list(cache_dir.glob(".*.tmp"))
    assert leftover == []
    write_reference_caches(
        profile.directory,
        profile.references_path,
        [json.loads(line)["text"] for line in profile.references_path.read_text("utf-8").splitlines()],
        rules,
    )
    assert list(cache_dir.glob(".*.tmp")) == []


def test_check_never_writes_a_cache(tmp_path: Path) -> None:
    """check --style must only read caches, never write or refresh them."""

    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    cache_dir = profile.directory / "cache"
    before = {path.name: path.read_bytes() for path in cache_dir.iterdir()}
    load_reference_stats(profile, rules, rules_fingerprint(rules))
    after = {path.name: path.read_bytes() for path in cache_dir.iterdir()}
    assert before == after
