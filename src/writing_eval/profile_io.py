"""Build, load, and list named style profiles."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import json
from pathlib import Path
import re

from .profile_analysis import profile_statistics
from .profile_cache import write_reference_caches
from .profile_models import METRICS_VERSION, Profile, ProfileError
from .segmentation import tokenize
from .style_audit import BUILTIN_RULES_PATH, Rule, load_rules

_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SOURCE_SUFFIXES = frozenset({".md", ".txt"})


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    match = _FRONTMATTER_RE.match(text)
    return text if match is None else text[match.end() :]


def _slug(stem: str) -> str:
    return _SLUG_RE.sub("-", stem.lower()).strip("-") or "doc"


def _resolve_sources(source_paths: Iterable[Path | str]) -> list[Path]:
    resolved: dict[str, Path] = {}
    for raw in source_paths:
        path = Path(raw)
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in _SOURCE_SUFFIXES:
                    resolved[str(child.resolve())] = child
        elif path.is_file():
            if path.suffix.lower() not in _SOURCE_SUFFIXES:
                raise ProfileError(
                    f"unsupported source file type: {path} (expected .md or .txt)"
                )
            resolved[str(path.resolve())] = path
        else:
            raise ProfileError(f"source not found: {path}")
    return [resolved[key] for key in sorted(resolved)]


def _write_references(path: Path, records: Sequence[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: item["id"]):
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


def _validate_profile_summary(data: object) -> str | None:
    if not isinstance(data, dict):
        return "non-object top-level JSON"
    if not isinstance(data.get("sources"), list):
        return "sources field is not a list"
    total_words = data.get("total_words")
    if isinstance(total_words, bool) or not isinstance(total_words, (int, float)):
        return "total_words field is not a number"
    return None


def build_profile(
    name: str,
    source_paths: Iterable[Path | str],
    out_dir: Path,
    created: str,
    *,
    rules: Sequence[Rule] | None = None,
) -> dict:
    """Build a style profile from local prose and write it to ``out_dir``.

    ``rules`` are the style rules used to precompute the reference-corpus
    cache under ``out_dir/cache/``; ``None`` uses the builtin rule set.
    """

    files = _resolve_sources(source_paths)
    if not files:
        raise ProfileError("no .md or .txt source files found")
    records: list[dict] = []
    sources: list[dict] = []
    texts: list[str] = []
    seen_ids: dict[str, Path] = {}
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ProfileError(f"could not decode {path} as UTF-8: {exc}") from None
        except OSError as exc:
            raise ProfileError(f"could not read source {path}: {exc}") from None
        text = _strip_frontmatter(raw).strip()
        if not text:
            raise ProfileError(f"source text is empty: {path}")
        word_count = len(tokenize(text))
        if word_count == 0:
            raise ProfileError(f"source text has no word tokens: {path}")
        source_id = _slug(path.stem)
        if source_id in seen_ids:
            raise ProfileError(
                f"duplicate source id {source_id!r} for {path.name!r} "
                f"(already produced by {seen_ids[source_id].name!r})"
            )
        seen_ids[source_id] = path
        records.append({"id": source_id, "text": text, "file": path.name})
        sources.append({"id": source_id, "file": path.name, "word_count": word_count})
        texts.append(text)
    sources.sort(key=lambda source: source["id"])
    profile_data = {
        "name": name,
        "created": created,
        "metrics_version": METRICS_VERSION,
        "sources": sources,
        "total_words": sum(source["word_count"] for source in sources),
        "statistics": profile_statistics(texts),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    references_path = out_dir / "references.jsonl"
    _write_references(references_path, records)
    (out_dir / "profile.json").write_text(
        json.dumps(profile_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    effective_rules = load_rules(BUILTIN_RULES_PATH) if rules is None else rules
    write_reference_caches(out_dir, references_path, texts, effective_rules)
    return profile_data


def load_profile(profiles_root: Path | str, name: str) -> Profile:
    """Load a named profile from ``profiles_root/name``."""

    directory = Path(profiles_root) / name
    if not directory.is_dir():
        raise ProfileError(f"profile not found: {name} (looked in {directory})")
    profile_path = directory / "profile.json"
    references_path = directory / "references.jsonl"
    if not profile_path.is_file():
        raise ProfileError(f"profile metadata not found: {profile_path}")
    if not references_path.is_file():
        raise ProfileError(f"profile references not found: {references_path}")
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ProfileError(f"could not decode {profile_path} as UTF-8: {exc}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"could not read profile {name}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("statistics"), dict):
        raise ProfileError(f"invalid profile metadata: {profile_path}")
    found_version = data.get("metrics_version")
    if found_version != METRICS_VERSION:
        raise ProfileError(
            f"profile {name!r} uses metric semantics version {found_version!r}, "
            f"expected {METRICS_VERSION}; rebuild it with "
            f"`writing-eval profile build {name} --from <sources>`"
        )
    return Profile(name, directory, references_path, data)


def list_profiles(
    profiles_root: Path | str,
    *,
    on_skip: Callable[[Path, str], None] | None = None,
) -> list[dict]:
    """Return profile summaries ordered by name.

    ``on_skip``, when provided, receives the profile directory and error text
    for every profile that cannot be read; without it the function stays
    silent and simply omits unreadable profiles.
    """

    root = Path(profiles_root)
    if not root.is_dir():
        raise ProfileError(f"profiles root not found: {root}")
    summaries: list[dict] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        profile_path = child / "profile.json"
        if not child.is_dir() or not profile_path.is_file():
            continue
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            if on_skip is not None:
                on_skip(child, str(exc))
            continue
        error = _validate_profile_summary(data)
        if error is not None:
            if on_skip is not None:
                on_skip(child, error)
            continue
        summaries.append(
            {
                "name": child.name,
                "sources": len(data["sources"]),
                "total_words": data["total_words"],
            }
        )
    return summaries
