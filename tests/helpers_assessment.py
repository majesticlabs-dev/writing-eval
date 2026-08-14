"""Shared assessment-test data builders."""

_DEFAULT_VALUES = {
    "mean_sentence_length": (10.0, 10.0),
    "sentence_length_variance": (20.0, 20.0),
    "repeated_opening_rate": (0.1, 0.1),
    "flesch_reading_ease": (60.0, 60.0),
    "flesch_kincaid_grade": (8.0, 8.0),
    "mtld": (70.0, 70.0),
}


def _style_gap(
    overrides: dict[str, tuple[float | None, float | None]] | None = None,
) -> dict:
    values = dict(_DEFAULT_VALUES)
    values.update(overrides or {})
    metrics = []
    for metric, (draft, profile) in values.items():
        delta = None if draft is None or profile is None else draft - profile
        metrics.append(
            {
                "metric": metric,
                "draft": draft,
                "profile": profile,
                "delta": delta,
            }
        )
    return {
        "profile": "demo",
        "metrics": metrics,
        "token_1gram_l2": 0.1,
        "top_overrepresented": [],
    }

def _metrics(word_count: int = 20) -> dict:
    return {
        "word_count": word_count,
        "tell_rates_by_severity": {},
        "mean_sentence_length": 10.0,
        "sentence_length_variance": 20.0,
        "repeated_opening_rate": 0.1,
        "token_1gram_l2": 0.1,
    }


def _quality(reading_ease: float | None = 60.0) -> dict:
    return {
        "flesch_reading_ease": reading_ease,
        "flesch_kincaid_grade": 8.0 if reading_ease is not None else None,
        "mtld": 70.0,
        "paragraph_stats": {
            "paragraph_count": 1.0,
            "mean_paragraph_sentence_count": 2.0,
            "single_sentence_paragraph_rate": 0.0,
        },
    }


def _profile_statistics() -> dict:
    return {
        "paragraph_stats": {
            "paragraph_count": 10.0,
            "mean_paragraph_sentence_count": 2.0,
            "single_sentence_paragraph_rate": 0.0,
        }
    }
