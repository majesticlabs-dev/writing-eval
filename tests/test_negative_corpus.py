"""Regression guard: the style auditor must stay quiet on legitimate human prose."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor

RULES_PATH = BUILTIN_RULES_PATH
CORPUS_PATH = Path(__file__).parent / "fixtures" / "negative_corpus.jsonl"

# The 2026-08-14 rule hardening restored the original legitimate prose. The negative
# corpus has 12 info findings; its passive-voice findings are intentional info-severity
# review candidates. This ceiling is a regression guard, not a benchmark threshold.
MAX_INFO_FINDINGS = 12

REQUIRED_CATEGORIES = {
    "polished_prose",
    "formal_vocabulary",
    "mixed_register",
    "single_transition",
    "single_hedge",
    "emphatic_short_sentence",
    "curly_quotes",
    "attributive_hyphenation",
    "genuine_range",
    "passive_by_necessity",
    "list_prose",
    "quoted_ai_text",
}


def load_corpus() -> list[dict[str, str]]:
    lines = CORPUS_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def auditor() -> StyleAuditor:
    return StyleAuditor.from_yaml(RULES_PATH)


@pytest.fixture(scope="module")
def corpus() -> list[dict[str, str]]:
    return load_corpus()


def test_corpus_ids_are_unique(corpus: list[dict[str, str]]) -> None:
    ids = [record["id"] for record in corpus]
    assert len(ids) == len(set(ids))


def test_corpus_covers_every_required_category(corpus: list[dict[str, str]]) -> None:
    categories = {record["category"] for record in corpus}
    assert REQUIRED_CATEGORIES <= categories


def test_corpus_has_no_warn_findings(
    auditor: StyleAuditor, corpus: list[dict[str, str]]
) -> None:
    warn_findings = []
    for record in corpus:
        for finding in auditor.audit(record["text"]):
            if finding.severity == "warn":
                warn_findings.append((record["id"], finding.rule_id, finding.matched_text))
    assert not warn_findings, warn_findings


def test_corpus_info_findings_stay_within_ceiling(
    auditor: StyleAuditor, corpus: list[dict[str, str]]
) -> None:
    info_count = sum(
        1
        for record in corpus
        for finding in auditor.audit(record["text"])
        if finding.severity == "info"
    )
    assert info_count <= MAX_INFO_FINDINGS
