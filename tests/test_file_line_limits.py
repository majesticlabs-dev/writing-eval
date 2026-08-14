"""Keep first-party Python modules small enough to review comfortably."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 300


def _tracked_python_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "src",
            "scripts",
            "tests",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(
        ROOT / relative
        for relative in result.stdout.splitlines()
        if relative.endswith(".py") and (ROOT / relative).is_file()
    )


def _physical_line_count(path: Path) -> int:
    content = path.read_bytes()
    return content.count(b"\n") + int(bool(content) and not content.endswith(b"\n"))


def test_first_party_python_files_do_not_exceed_line_limit() -> None:
    violations = [
        (path.relative_to(ROOT), _physical_line_count(path))
        for path in _tracked_python_files()
        if _physical_line_count(path) > MAX_LINES
    ]
    details = "\n".join(f"{path}: {count} lines" for path, count in violations)
    assert not violations, f"Python files exceed {MAX_LINES} lines:\n{details}"
