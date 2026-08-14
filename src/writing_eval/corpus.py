"""Sample collection, holdout/eval split, and prompt templates (roadmap 2.2/2.3)."""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
import os
from pathlib import Path
import random
import re
import tempfile

from .segmentation import tokenize

_USE_CASES = frozenset(
    {"article_section", "product_writing", "exec_communication"}
)
_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)
_PROMPT_TEMPLATES = {
    "article_section": (
        "Write an article section titled '{title}'. Target length about "
        "{word_count} words. Plain prose paragraphs, no headings unless the "
        "content demands one."
    ),
    "product_writing": (
        "Write product copy titled '{title}'. Target length about "
        "{word_count} words. Concrete benefits, no hype adjectives."
    ),
    "exec_communication": (
        "Write a concise executive communication titled '{title}'. Target "
        "length about {word_count} words. Lead with the decision or ask."
    ),
}


def load_manifest(path: Path) -> list[dict]:
    """Read and validate a JSONL sample manifest.

    Each record requires ``path``, ``use_case`` (one of ``article_section``,
    ``product_writing``, ``exec_communication``), and ``title``, plus an
    optional boolean ``holdout_only`` (default false). Duplicate ``path``
    values are rejected. Errors name the offending line number.
    """

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"could not decode manifest {path} as UTF-8: {exc}") from None
    except OSError as exc:
        raise ValueError(f"could not read manifest {path}: {exc}") from None

    records: list[dict] = []
    seen_paths: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON in {path} at line {line_number}: {exc.msg}"
            ) from None
        if not isinstance(record, dict):
            raise ValueError(
                f"invalid manifest record in {path} at line {line_number}: "
                "expected object"
            )
        missing = [key for key in ("path", "use_case", "title") if key not in record]
        if missing:
            raise ValueError(
                f"invalid manifest record in {path} at line {line_number}: "
                f"missing key(s) {', '.join(missing)}"
            )
        if record["use_case"] not in _USE_CASES:
            raise ValueError(
                f"invalid manifest record in {path} at line {line_number}: "
                f"unknown use_case {record['use_case']!r}"
            )
        if "holdout_only" in record and not isinstance(record["holdout_only"], bool):
            raise ValueError(
                f"invalid manifest record in {path} at line {line_number}: "
                f"holdout_only must be a boolean, got {record['holdout_only']!r}"
            )
        record_path = record["path"]
        if record_path in seen_paths:
            raise ValueError(
                f"duplicate path {record_path!r} in {path} at line {line_number} "
                f"(first seen at line {seen_paths[record_path]})"
            )
        seen_paths[record_path] = line_number
        records.append(record)

    if not records:
        raise ValueError(f"manifest is empty: {path}")
    return records


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return text
    return text[match.end() :]


def _relative_to_root(full_path: Path, root: Path, candidate: Path) -> str:
    try:
        return str(full_path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(candidate)


def collect_samples(manifest: list[dict], root: Path) -> list[dict]:
    """Read manifest sample files into normalized sample records.

    Each source file is read as UTF-8 text, a leading YAML frontmatter block
    is stripped if present, and surrounding whitespace is trimmed. Empty
    texts and duplicate resulting IDs raise ``ValueError``. A manifest record
    flagged ``holdout_only`` carries ``"holdout_only": True`` on its sample
    record; unflagged samples omit the key.
    """

    samples: list[dict] = []
    seen_ids: dict[str, str] = {}
    for record in manifest:
        raw_path = record["path"]
        candidate = Path(raw_path)
        full_path = candidate if candidate.is_absolute() else root / candidate
        try:
            text = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"could not decode sample {full_path} as UTF-8: {exc}"
            ) from None
        except OSError as exc:
            raise ValueError(f"could not read sample {full_path}: {exc}") from None

        text = _strip_frontmatter(text).strip()
        if not text:
            raise ValueError(f"sample text is empty: {full_path}")

        relative_path = _relative_to_root(full_path, root, candidate)
        sample_id = (
            "sample-"
            + hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12]
        )
        if sample_id in seen_ids:
            raise ValueError(
                f"duplicate sample id {sample_id!r} for {relative_path!r} "
                f"(already produced by {seen_ids[sample_id]!r})"
            )
        seen_ids[sample_id] = relative_path

        sample = {
            "id": sample_id,
            "use_case": record["use_case"],
            "title": record["title"],
            "source_path": relative_path,
            "text": text,
            "word_count": len(tokenize(text)),
        }
        if record.get("holdout_only", False):
            sample["holdout_only"] = True
        samples.append(sample)
    return samples


def split_holdout(
    samples: list[dict],
    eval_fraction: float = 0.4,
    seed: int = 20260717,
) -> tuple[list[dict], list[dict]]:
    """Deterministically split samples into a reference holdout and eval set.

    Samples flagged ``holdout_only`` go straight to holdout. The remaining
    samples are grouped by ``use_case``, sorted by ``id``, and shuffled with
    ``random.Random(seed)`` so the same seed always reproduces the same
    split. Each non-empty group in that pool contributes at least one sample
    to eval and, once it holds at least two samples, at least one sample to
    holdout; a use case whose samples are all ``holdout_only`` simply has no
    eval entries. The resulting ID sets are asserted disjoint and covering,
    then both lists are returned sorted by ``id``.
    """

    holdout: list[dict] = [
        sample for sample in samples if sample.get("holdout_only", False)
    ]
    groups: dict[str, list[dict]] = {}
    for sample in samples:
        if sample.get("holdout_only", False):
            continue
        groups.setdefault(sample["use_case"], []).append(sample)

    rng = random.Random(seed)
    eval_set: list[dict] = []
    for use_case in sorted(groups):
        group = sorted(groups[use_case], key=lambda item: item["id"])
        rng.shuffle(group)
        eval_count = round(len(group) * eval_fraction)
        if group:
            eval_count = max(eval_count, 1)
        if len(group) >= 2:
            eval_count = min(eval_count, len(group) - 1)
        eval_count = min(eval_count, len(group))
        eval_set.extend(group[:eval_count])
        holdout.extend(group[eval_count:])

    holdout_ids = {sample["id"] for sample in holdout}
    eval_ids = {sample["id"] for sample in eval_set}
    all_ids = {sample["id"] for sample in samples}
    if holdout_ids & eval_ids:
        raise AssertionError("holdout and eval sets overlap")
    if (holdout_ids | eval_ids) != all_ids:
        raise AssertionError("holdout and eval sets do not cover all samples")

    holdout.sort(key=lambda item: item["id"])
    eval_set.sort(key=lambda item: item["id"])
    return holdout, eval_set


def build_prompt(sample: dict) -> str:
    """Return a generation prompt templated for the sample's use case."""

    template = _PROMPT_TEMPLATES.get(sample["use_case"])
    if template is None:
        raise ValueError(f"unknown use_case: {sample['use_case']!r}")
    return template.format(title=sample["title"], word_count=sample["word_count"])


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True))
                handle.write("\n")
            handle.flush()
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_outputs(
    holdout: list[dict], eval_set: list[dict], out_dir: Path
) -> dict[str, Path]:
    """Write the reference holdout, eval set, and eval prompts; return paths.

    ``references.holdout.jsonl`` records contain ``id``, ``text``, ``source``
    (fixed as ``"holdout-2.2"``), and ``file``. ``eval_set.jsonl`` holds the
    full sample records.
    ``prompts.eval.jsonl`` keys are ``id``, ``use_case``, and ``prompt``. All
    three files are written one JSON object per line, sorted by ``id``, with
    ``ensure_ascii=True``.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    references_path = out_dir / "references.holdout.jsonl"
    eval_path = out_dir / "eval_set.jsonl"
    prompts_path = out_dir / "prompts.eval.jsonl"

    holdout_sorted = sorted(holdout, key=lambda item: item["id"])
    eval_sorted = sorted(eval_set, key=lambda item: item["id"])

    _write_jsonl(
        references_path,
        (
            {
                "id": sample["id"],
                "text": sample["text"],
                "source": "holdout-2.2",
                "file": sample["source_path"],
            }
            for sample in holdout_sorted
        ),
    )
    _write_jsonl(eval_path, eval_sorted)
    _write_jsonl(
        prompts_path,
        (
            {
                "id": sample["id"],
                "use_case": sample["use_case"],
                "prompt": build_prompt(sample),
            }
            for sample in eval_sorted
        ),
    )
    return {
        "references_holdout": references_path,
        "eval_set": eval_path,
        "prompts_eval": prompts_path,
    }
