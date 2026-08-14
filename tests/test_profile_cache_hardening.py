"""Hardening tests for code-digest binding and cache-write hygiene."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_eval.profile_cache import (
    _reference_texts,
    load_reference_stats,
    refresh_reference_caches,
    write_reference_caches,
)
from writing_eval.profiles import ProfileError, load_profile
from writing_eval.style_audit import BUILTIN_RULES_PATH, load_rules, rules_fingerprint

from tests.helpers_profiles import _build_demo


def _builtin_rules():
    return load_rules(BUILTIN_RULES_PATH)


def test_missing_code_digest_is_a_cache_miss(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)
    tokens_path = profile.directory / "cache" / "tokens.json"
    payload = json.loads(tokens_path.read_text(encoding="utf-8"))
    del payload["code_sha256"]
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")
    stats, status = load_reference_stats(profile, rules, fingerprint)
    assert status == "recomputed"
    assert stats.word_count > 0


def test_changed_code_digest_invalidates_both_entries(
    tmp_path: Path, monkeypatch
) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    fingerprint = rules_fingerprint(rules)
    before_stats, before_status = load_reference_stats(profile, rules, fingerprint)
    assert before_status == "cache"

    monkeypatch.setattr("writing_eval.profile_cache._CODE_SHA256", "0" * 64)
    stats, status = load_reference_stats(profile, rules, fingerprint)
    assert status == "recomputed"
    assert stats.word_count == before_stats.word_count
    assert dict(stats.token_counts) == dict(before_stats.token_counts)
    assert dict(stats.rule_counts) == dict(before_stats.rule_counts)


def test_write_failure_cleans_up_temporary_file(tmp_path: Path, monkeypatch) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    rules = _builtin_rules()
    cache_dir = profile.directory / "cache"
    tokens_path = cache_dir / "tokens.json"
    original = tokens_path.read_bytes()

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("writing_eval.profile_cache.json.dump", _boom)
    with pytest.raises(OSError):
        write_reference_caches(
            profile.directory, profile.references_path, ["text."], rules
        )
    monkeypatch.undo()
    assert list(cache_dir.glob(".*.tmp")) == []
    assert tokens_path.read_bytes() == original


def test_reference_texts_rejects_malformed_references(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile = load_profile(root, "demo")
    path = profile.references_path
    rules = _builtin_rules()

    path.write_text(
        '{"id": "a", "text": "One."}\n{"id": "a", "text": "Two."}\n', encoding="utf-8"
    )
    with pytest.raises(ProfileError, match=r"duplicate reference id 'a'.*line 2"):
        refresh_reference_caches(profile.directory, path, rules)

    path.write_text('{"text": "No id."}\n', encoding="utf-8")
    with pytest.raises(ProfileError, match=r"line 1.*nonempty string id"):
        refresh_reference_caches(profile.directory, path, rules)

    path.write_text('{"id": "a", "text": 3}\n', encoding="utf-8")
    with pytest.raises(ProfileError, match=r"line 1.*string text"):
        refresh_reference_caches(profile.directory, path, rules)

    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ProfileError, match=r"invalid JSON.*line 1"):
        refresh_reference_caches(profile.directory, path, rules)

    path.write_bytes(b'{"id": "a", "text": "\xff\xfe"}\n')
    with pytest.raises(ProfileError, match="could not decode .* as UTF-8"):
        refresh_reference_caches(profile.directory, path, rules)


def test_reference_texts_rejects_whitespace_only_ids_and_preserves_nonblank_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "references.jsonl"
    path.write_text('{"id": "   ", "text": "Only spaces."}\n', encoding="utf-8")
    with pytest.raises(ProfileError, match=r"line 1.*nonempty string id"):
        _reference_texts(path)

    path.write_text(
        '{"id": "  a  ", "text": "One."}\n'
        '{"id": "  a  ", "text": "Two."}\n',
        encoding="utf-8",
    )
    with pytest.raises(ProfileError, match=r"duplicate reference id '  a  '.*line 2"):
        _reference_texts(path)
