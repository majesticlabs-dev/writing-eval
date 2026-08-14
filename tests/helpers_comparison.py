"""Shared comparison-test data builders."""

from writing_eval.style_audit import BUILTIN_RULES_PATH

RULES_PATH = BUILTIN_RULES_PATH

REFERENCE_CORPUS = [
    "Clear plans use direct words and stay specific.",
    "Editors write with care, focus, and plain structure.",
]


def base_metrics(**overrides: float | None) -> dict[str, float | None]:
    values: dict[str, float | None] = {
        "tell_rate": 1.0,
        "token_1gram_l2": 0.5,
        "mean_sentence_length": 10.0,
        "sentence_length_variance": 4.0,
        "repeated_opening_rate": 0.0,
    }
    values.update(overrides)
    return values


def make_system(
    name: str,
    metrics: dict[str, float | None],
    findings_by_severity: dict[str, int] | None = None,
    word_count: int = 100,
) -> dict:
    return {
        "system_name": name,
        "document_count": 1,
        "word_count": word_count,
        "finding_count": sum((findings_by_severity or {}).values()),
        "findings_by_severity": findings_by_severity or {},
        "findings_by_rule": {},
        "tell_rates_by_severity": {},
        "metrics": metrics,
        "top_overrepresented": [],
    }


def make_report(systems: list[dict]) -> dict:
    return {"provenance": {}, "systems": systems}

CLEAN_LONG_TEXT = (
    "The team shipped the update on Monday morning after a short review. "
    "Customers can now export their records without opening a support ticket. "
    "We wrote plain notes that explain the change and its effect. "
    "Nobody needs to guess what happened or why. "
    "The rollout stayed calm because every step was clear and small and "
    "tested well before release today."
)
