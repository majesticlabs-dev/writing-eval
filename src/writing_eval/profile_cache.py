"""Precomputed per-profile reference-corpus statistics, cached under ``cache/``.

``check --style`` used to re-tokenize and re-audit the whole reference corpus
on every invocation. This module lets ``profile build`` (and ``profile
cache``) precompute the two things a check needs from the corpus, unigram
token counts and per-rule finding counts, and cache them as small sidecar
JSON files next to ``references.jsonl``.

A cache entry is trusted only when its ``schema`` key, its
``references_sha256`` (a streaming digest of the live ``references.jsonl``),
its ``code_sha256`` (a digest of the detector, engine, and tokenizer sources),
and, for the rule-count cache, its ``rules_fingerprint`` all match the live
inputs. Any mismatch or malformed JSON is a silent miss: it falls through to
live recomputation and never raises and never partially trusts a stale value.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .profile_atomic import _atomic_write_json, _hash_file
from .profile_models import Profile, ProfileError
from .segmentation import tokenize
from .style_audit import Rule, audit_text, rules_fingerprint

_SCHEMA_VERSION = 1
_TOKENS_FILENAME = "tokens.json"
_CACHE_DIRNAME = "cache"

# Caches depend on detector and tokenizer behavior, not only on rule content
# and the corpus digest. This digest ties every cache entry to the source of
# the modules that produce it, so upgrades invalidate stale counts.
_CODE_DIGEST_MODULES = (
    "style_audit_detectors.py",
    "style_audit_engine.py",
    "segmentation.py",
)


def _compute_code_sha256() -> str:
    digest = hashlib.sha256()
    package_dir = Path(__file__).resolve().parent
    for filename in _CODE_DIGEST_MODULES:
        payload = (package_dir / filename).read_bytes()
        digest.update(filename.encode("utf-8") + payload)
    return digest.hexdigest()


_CODE_SHA256 = _compute_code_sha256()


@dataclass(frozen=True, slots=True)
class ReferenceStats:
    """Word count, unigram token counts, and rule counts for a reference corpus."""

    word_count: int
    token_counts: Mapping[str, int]
    rule_counts: Mapping[str, int]


def _rules_cache_filename(fingerprint: str) -> str:
    return f"rules-{fingerprint[:16]}.json"


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """Read and decode a cache file. Any failure is a silent miss, never a raise."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _exact_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_count_mapping(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(key, str) and _exact_nonnegative_int(count)
        for key, count in value.items()
    )


def _valid_entry(
    data: dict[str, Any] | None,
    references_sha256: str,
    fingerprint: str | None = None,
) -> dict[str, Any] | None:
    """Validate one cache entry; ``fingerprint`` additionally gates rule caches."""

    if data is None:
        return None
    if data.get("schema") != _SCHEMA_VERSION:
        return None
    if data.get("references_sha256") != references_sha256:
        return None
    if data.get("code_sha256") != _CODE_SHA256:
        return None
    if fingerprint is not None and data.get("rules_fingerprint") != fingerprint:
        return None
    counts_key = "rule_counts" if fingerprint is not None else "token_counts"
    if not _exact_nonnegative_int(data.get("word_count")):
        return None
    if not _is_count_mapping(data.get(counts_key)):
        return None
    return data


def _prune_stale_rules_caches(cache_dir: Path, current_filename: str) -> None:
    for child in cache_dir.iterdir():
        if child.name == current_filename:
            continue
        if not child.name.startswith("rules-") or not child.name.endswith(".json"):
            continue
        try:
            child.unlink()
        except OSError as exc:
            raise ProfileError(
                f"could not prune stale rules cache {child}: {exc}"
            ) from None


def _reference_texts(references_path: Path) -> list[str]:
    texts: list[str] = []
    seen_ids: set[str] = set()
    try:
        with references_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ProfileError(
                        f"invalid JSON in {references_path} at line {line_number}: {exc}"
                    ) from None
                record_id = record.get("id") if isinstance(record, dict) else None
                if not isinstance(record_id, str) or not record_id.strip():
                    raise ProfileError(
                        f"invalid reference record in {references_path} at line "
                        f"{line_number}: expected a JSON object with a nonempty string id"
                    )
                if record_id in seen_ids:
                    raise ProfileError(
                        f"duplicate reference id {record_id!r} in "
                        f"{references_path} at line {line_number}"
                    )
                if not isinstance(record.get("text"), str):
                    raise ProfileError(
                        f"invalid reference record in {references_path} at line "
                        f"{line_number}: expected a string text"
                    )
                seen_ids.add(record_id)
                texts.append(record["text"])
    except UnicodeDecodeError as exc:
        raise ProfileError(
            f"could not decode {references_path} as UTF-8: {exc}"
        ) from None
    except OSError as exc:
        raise ProfileError(f"could not read {references_path}: {exc}") from None
    return texts


def _count_tokens(texts: Sequence[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(tokenize(text))
    return counts


def _count_rule_matches(texts: Sequence[str], rules: Sequence[Rule]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(finding.rule_id for finding in audit_text(text, rules))
    return counts


def load_reference_stats(
    profile: Profile, rules: Sequence[Rule], fingerprint: str
) -> tuple[ReferenceStats, str]:
    """Return reference-corpus statistics for ``profile``, cached or computed live.

    Returns ``(stats, "cache")`` when both sidecar files are present and
    valid for the live corpus digest and rule fingerprint, in which case
    ``references.jsonl`` is hashed but never parsed. Otherwise returns
    ``(stats, "recomputed")`` after computing whichever parts were missing
    or stale; this call never writes to the profile directory.
    """

    cache_dir = profile.directory / _CACHE_DIRNAME
    references_sha256 = _hash_file(profile.references_path)
    tokens_entry = _valid_entry(
        _read_json_object(cache_dir / _TOKENS_FILENAME), references_sha256
    )
    rules_entry = _valid_entry(
        _read_json_object(cache_dir / _rules_cache_filename(fingerprint)),
        references_sha256,
        fingerprint,
    )
    if tokens_entry is not None and rules_entry is not None:
        stats = ReferenceStats(
            word_count=tokens_entry["word_count"],
            token_counts=tokens_entry["token_counts"],
            rule_counts=rules_entry["rule_counts"],
        )
        return stats, "cache"

    texts = _reference_texts(profile.references_path)
    if tokens_entry is not None:
        word_count = tokens_entry["word_count"]
        token_counts: Mapping[str, int] = tokens_entry["token_counts"]
    else:
        token_counts = _count_tokens(texts)
        word_count = sum(token_counts.values())
    if rules_entry is not None:
        rule_counts: Mapping[str, int] = rules_entry["rule_counts"]
    else:
        rule_counts = _count_rule_matches(texts, rules)
    return ReferenceStats(word_count, token_counts, rule_counts), "recomputed"


def write_reference_caches(
    directory: Path, references_path: Path, texts: Sequence[str], rules: Sequence[Rule]
) -> None:
    """Compute and atomically write both cache sidecars for a profile.

    Only ``profile build`` and ``profile cache`` call this; ``check`` never
    writes caches.
    """

    references_sha256 = _hash_file(references_path)
    token_counts = _count_tokens(texts)
    word_count = sum(token_counts.values())
    fingerprint = rules_fingerprint(rules)
    rule_counts = _count_rule_matches(texts, rules)
    cache_dir = directory / _CACHE_DIRNAME
    _atomic_write_json(
        cache_dir / _TOKENS_FILENAME,
        {
            "schema": _SCHEMA_VERSION,
            "references_sha256": references_sha256,
            "code_sha256": _CODE_SHA256,
            "word_count": word_count,
            "token_counts": dict(token_counts),
        },
    )
    current_filename = _rules_cache_filename(fingerprint)
    _atomic_write_json(
        cache_dir / current_filename,
        {
            "schema": _SCHEMA_VERSION,
            "references_sha256": references_sha256,
            "code_sha256": _CODE_SHA256,
            "rules_fingerprint": fingerprint,
            "rule_count": len(rules),
            "word_count": word_count,
            "rule_counts": dict(rule_counts),
        },
    )
    _prune_stale_rules_caches(cache_dir, current_filename)


def refresh_reference_caches(
    directory: Path, references_path: Path, rules: Sequence[Rule]
) -> None:
    """Rebuild both cache sidecars for an existing profile from its corpus alone."""

    if not references_path.is_file():
        raise ProfileError(f"profile references not found: {references_path}")
    texts = _reference_texts(references_path)
    write_reference_caches(directory, references_path, texts, rules)
