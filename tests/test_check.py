import hashlib
import json
from pathlib import Path
import subprocess
import sys

from tests.helpers_cli import run_cli
from tests.helpers_profiles import _build_demo


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_eval.py"

EM_DASH = chr(0x2014)


def write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_clean_file_exits_zero(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")
    result = run_cli("check", draft)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "metrics:" in result.stdout
    assert "word_count:" in result.stdout

def test_default_check_reports_json_findings(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("I hope this helps. The steps are below.\n", encoding="utf-8")
    result = run_cli("check", draft, "--format", "json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert any(
        finding["rule_id"] == "collaborative_artifacts"
        for finding in payload["findings"]
    )


def test_em_dash_file_exits_zero_with_position(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("Clear" + EM_DASH + "concise.\n", encoding="utf-8")
    result = run_cli("check", draft)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert f"{draft}:1:6 [warn] em_dash_ban:" in result.stdout
    assert "| span:" in result.stdout


def test_stdin_input_is_read(tmp_path: Path) -> None:
    result = run_cli("check", "-", stdin="Use this tool to leverage the data.\n")
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "<stdin>:1:" in result.stdout
    assert "polish_vocab" in result.stdout


def test_json_format_schema(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("Clear" + EM_DASH + "concise. We revise it.\n", encoding="utf-8")
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "ref-1", "text": "Editors write clearly."}])
    result = run_cli(
        "check",
        draft,
        "--references",
        references,
        "--format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {"file", "findings", "metrics", "quality_metrics"}
    assert payload["file"] == str(draft)
    assert isinstance(payload["findings"], list)
    finding = payload["findings"][0]
    assert set(finding) == {
        "rule_id", "severity", "message", "line", "column", "span", "within_allowance",
    }
    assert finding["rule_id"] == "em_dash_ban"
    assert finding["line"] == 1
    assert finding["column"] == 6
    assert finding["within_allowance"] is False
    metrics = payload["metrics"]
    assert set(metrics) == {
        "word_count",
        "tell_rates_by_severity",
        "mean_sentence_length",
        "sentence_length_variance",
        "repeated_opening_rate",
        "token_1gram_l2",
    }
    assert isinstance(metrics["token_1gram_l2"], float)


def test_missing_references_prints_note_and_na(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")
    result = run_cli("check", draft, "--format", "json")
    assert result.returncode == 0, result.stderr
    assert "no references provided" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["metrics"]["token_1gram_l2"] is None


def test_missing_references_text_format_renders_na(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")
    result = run_cli("check", draft)
    assert result.returncode == 0, result.stderr
    assert "token_1gram_l2: n/a" in result.stdout


def test_empty_file_handled_without_crash(tmp_path: Path) -> None:
    draft = tmp_path / "empty.md"
    draft.write_text("", encoding="utf-8")
    result = run_cli("check", draft)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "metrics:" in result.stdout
    assert "word_count: 0" in result.stdout


def test_json_file_output_written(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")
    json_path = tmp_path / "out.json"
    result = run_cli("check", draft, "--json", json_path)
    assert result.returncode == 0, result.stderr
    assert json_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["file"] == str(draft)
    assert "metrics" in payload


def test_missing_input_file_is_usage_error(tmp_path: Path) -> None:
    result = run_cli("check", tmp_path / "missing.md")
    assert result.returncode == 1
    assert "input file not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_legacy_flat_eval_invocation_still_works(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system-a.jsonl", [{"id": "one", "text": "We write. We revise."}])
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "one", "text": "Editors write clearly."}])
    report = tmp_path / "report.md"
    result = run_cli(
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        report,
    )
    assert result.returncode == 0, result.stderr
    assert report.is_file()
    assert "## System: system-a" in report.read_text(encoding="utf-8")


def test_eval_subcommand_invocation_works(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    write_jsonl(outputs / "system-a.jsonl", [{"id": "one", "text": "We write. We revise."}])
    references = tmp_path / "references.jsonl"
    write_jsonl(references, [{"id": "one", "text": "Editors write clearly."}])
    report = tmp_path / "report.md"
    result = run_cli(
        "eval",
        "--outputs",
        outputs,
        "--references",
        references,
        "--report",
        report,
    )
    assert result.returncode == 0, result.stderr
    assert report.is_file()


def test_stdin_reads_utf8_bytes_regardless_of_locale() -> None:
    import os

    draft = "Café draft with plain sentences. More prose follows here."
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LC_", "PYTHON"))
    }
    env["LANG"] = "C"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check", "-"],
        input=draft.encode("utf-8"),
        capture_output=True,
        cwd=ROOT,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert b"could not read standard input" not in result.stderr
    assert b"Traceback" not in result.stderr


def test_stdin_rejects_malformed_utf8_cleanly() -> None:
    import os

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LC_", "PYTHON"))
    }
    env["LANG"] = "C"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check", "-"],
        input=b"\xff\xfe not utf8\n",
        capture_output=True,
        cwd=ROOT,
        check=False,
        env=env,
    )
    assert result.returncode == 1
    assert b"could not read standard input" in result.stderr
    assert b"Traceback" not in result.stderr


def test_unwritable_json_output_is_clean_user_error(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("Draft prose with plain sentences.", encoding="utf-8")
    blocker = tmp_path / "blocker"
    blocker.write_text("file blocks the directory", encoding="utf-8")

    result = run_cli("check", draft, "--json", blocker / "out.json")

    assert result.returncode == 1
    assert "could not write" in result.stderr
    assert "Traceback" not in result.stderr


def test_malformed_profile_references_are_clean_user_error(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    profile_dir = root / "demo"
    cache_dir = profile_dir / "cache"
    if cache_dir.is_dir():
        for child in cache_dir.iterdir():
            child.unlink()
    malformed_refs = b'{"id": "alpha", "text": "bad \xff byte"}\n'
    (profile_dir / "references.jsonl").write_bytes(malformed_refs)
    profile_path = profile_dir / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["references_sha256"] = hashlib.sha256(malformed_refs).hexdigest()
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")

    result = run_cli(
        "check",
        draft,
        "--style",
        "demo",
        "--profiles-root",
        root,
        "--format",
        "json",
    )

    assert result.returncode == 1
    assert "could not decode" in result.stderr
    assert "UTF-8" in result.stderr
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
