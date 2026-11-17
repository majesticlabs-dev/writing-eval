"""Data types and expected errors for named style profiles."""

from dataclasses import dataclass
from pathlib import Path


class ProfileError(Exception):
    """An expected profile build, load, or lookup error."""


# Version 3 excludes pairs entering list items from repeated-opening rates.
# Rebuild older profiles so stored statistics match fresh draft metrics.
METRICS_VERSION = 3


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
