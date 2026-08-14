"""Data types and expected errors for named style profiles."""

from dataclasses import dataclass
from pathlib import Path


class ProfileError(Exception):
    """An expected profile build, load, or lookup error."""


# Bump when corpus-statistic semantics change (for example the syllable
# heuristic). Profiles built with a different version must be rebuilt so
# stored statistics stay comparable with freshly computed draft metrics.
METRICS_VERSION = 1


@dataclass(frozen=True)
class Profile:
    """A loaded style profile and its reference corpus path."""

    name: str
    directory: Path
    references_path: Path
    data: dict

    @property
    def statistics(self) -> dict:
        return self.data.get("statistics", {})
