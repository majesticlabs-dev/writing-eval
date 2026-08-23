"""Data types and expected errors for named style profiles."""

from dataclasses import dataclass
from pathlib import Path


class ProfileError(Exception):
    """An expected profile build, load, or lookup error."""


# Version 2 changes curly-apostrophe openers, markdown-aware readability word
# counts, and MTLD tail, threshold, and sequence-input semantics. Rebuild older
# profiles so stored statistics stay comparable with fresh draft metrics.
METRICS_VERSION = 2


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
