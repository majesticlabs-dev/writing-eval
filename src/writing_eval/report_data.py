"""Build deterministic structured writing-evaluation reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib
from typing import Any

from .metrics import (
    mtld,
    paragraph_stats,
    repeated_opening_corpus_rate,
    tell_rate,
    tell_rates_by_severity,
    tokenize,
)
from .metrics_distribution import (
    token_1gram_l2_from_counts,
    top_overrepresented_from_counts,
)
from .metrics_quality import readability_scores
from .metrics_structure import sentence_length_stats

_TOOL_NAME = "writing-eval"
_SOURCE_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _tool_version() -> str:
    try:
        return version(_TOOL_NAME)
    except PackageNotFoundError:
        with _SOURCE_PYPROJECT.open("rb") as handle:
            project_version = tomllib.load(handle).get("project", {}).get("version")
        if not isinstance(project_version, str) or not project_version.strip():
            raise ValueError(
                f"could not determine {_TOOL_NAME} version from {_SOURCE_PYPROJECT}"
            ) from None
        return project_version


def _flatten_findings(findings_per_text: Any) -> list[Any]:
    groups = (
        findings_per_text.values()
        if isinstance(findings_per_text, Mapping)
        else findings_per_text or []
    )
    return [finding for group in groups for finding in (group or [])]


def _severity(finding: Any) -> str:
    if isinstance(finding, Mapping):
        return str(finding.get("severity", "unknown"))
    return str(getattr(finding, "severity", "unknown"))


def _rule_id(finding: Any) -> str:
    if isinstance(finding, Mapping):
        return str(finding.get("rule_id", "unknown"))
    return str(getattr(finding, "rule_id", "unknown"))


def _combine_documents(texts: Sequence[str]) -> str:
    cleaned = [text.strip().rstrip(".!?") for text in texts if text and text.strip()]
    return ". ".join(cleaned) + ("." if cleaned else "")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_provenance(
    reference_path: str | Path,
    reference_records: Sequence[Mapping[str, Any]],
    rules_path: str | Path,
    rule_count: int,
    rules_version: Any,
    fingerprint: str,
) -> dict[str, Any]:
    """Build deterministic source metadata for a report."""

    reference_word_count = sum(
        len(tokenize(str(record.get("text", "")))) for record in reference_records
    )
    return {
        "tool": {
            "name": _TOOL_NAME,
            "version": _tool_version(),
        },
        "reference_corpus": {
            "path": str(reference_path),
            "record_count": len(reference_records),
            "word_count": reference_word_count,
            "sha256": _sha256_file(reference_path),
        },
        "rule_set": {
            "path": str(rules_path),
            "version": rules_version,
            "rule_count": rule_count,
            "sha256": _sha256_file(rules_path),
            "fingerprint": fingerprint,
        },
    }


def build_report(
    system_name: str,
    texts: Iterable[str],
    reference_corpus: Iterable[str],
    findings_per_text: Any,
) -> dict[str, Any]:
    """Build deterministic, JSON-ready report data for one system."""

    text_list = list(texts)
    reference_list = list(reference_corpus)
    findings = _flatten_findings(findings_per_text)
    output_text = _combine_documents(text_list)
    paragraph_text = "\n\n".join(text_list)
    output_counts = Counter(tokenize(output_text))
    reference_counts = Counter(
        token for text in reference_list for token in tokenize(text)
    )
    word_count = sum(output_counts.values())
    sentence_mean, sentence_variance = sentence_length_stats(output_text)
    reading_ease, reading_grade = readability_scores(output_text)
    severity_counts = dict(sorted(Counter(_severity(item) for item in findings).items()))
    rule_counts = dict(sorted(Counter(_rule_id(item) for item in findings).items()))
    return {
        "system_name": system_name,
        "document_count": len(text_list),
        "word_count": word_count,
        "finding_count": len(findings),
        "findings_by_severity": severity_counts,
        "findings_by_rule": rule_counts,
        "tell_rates_by_severity": tell_rates_by_severity(findings, word_count),
        "metrics": {
            "tell_rate": tell_rate(findings, word_count),
            "token_1gram_l2": token_1gram_l2_from_counts(
                output_counts, reference_counts
            ),
            "mean_sentence_length": sentence_mean,
            "sentence_length_variance": sentence_variance,
            "repeated_opening_rate": repeated_opening_corpus_rate(text_list),
        },
        "quality_metrics": {
            "flesch_reading_ease": reading_ease,
            "flesch_kincaid_grade": reading_grade,
            "mtld": mtld(output_text),
            "paragraph_stats": paragraph_stats(paragraph_text),
        },
        "top_overrepresented": [
            {"token": token, "rate_difference": difference}
            for token, difference in top_overrepresented_from_counts(
                output_counts, reference_counts, n=10
            )
        ],
    }
