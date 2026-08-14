"""Shared style-profile test data and subprocess helpers."""

from pathlib import Path

from writing_eval.profiles import build_profile

from tests.helpers_cli import run_cli  # noqa: F401  (re-exported for profile tests)

PROSE_ONE = (
    "The founder writes with restless energy. Momentum favors builders who "
    "ship early and often.\n\n"
    "Networks compound advantage over time. Distribution beats a clever feature "
    "almost every quarter."
)
PROSE_TWO = (
    "Attention is the scarcest resource a young company owns. Guard it and "
    "spend it deliberately.\n\n"
    "A flywheel turns slowly at first. Patience and repetition make the loop "
    "spin faster later."
)


def _write_sources(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "alpha.md").write_text(PROSE_ONE, encoding="utf-8")
    (directory / "beta.txt").write_text(PROSE_TWO, encoding="utf-8")
    return directory


def _build_demo(tmp_path: Path, name: str = "demo") -> Path:
    sources = _write_sources(tmp_path / f"src-{name}")
    root = tmp_path / "profiles"
    build_profile(name, [sources], root / name, "2026-07-23")
    return root
