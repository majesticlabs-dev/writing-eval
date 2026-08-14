"""Corpus-builder CLI tests."""

from pathlib import Path

from tests.helpers_corpus import run_cli, write_manifest, write_sample

def test_cli_exits_2_on_malformed_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, [{"path": "a.md", "use_case": "bogus", "title": "A"}])
    result = run_cli(
        "--manifest",
        manifest,
        "--root",
        tmp_path,
        "--out-dir",
        tmp_path / "out",
    )
    assert result.returncode == 2
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr


def test_cli_exits_2_on_missing_manifest_file(tmp_path: Path) -> None:
    result = run_cli(
        "--manifest",
        tmp_path / "missing.jsonl",
        "--root",
        tmp_path,
        "--out-dir",
        tmp_path / "out",
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_cli_success_prints_summary_and_writes_files(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    records = []
    for use_case, prefix in (
        ("article_section", "art"),
        ("product_writing", "prod"),
        ("exec_communication", "exec"),
    ):
        for index in range(2):
            relative = f"{prefix}{index}.md"
            write_sample(tmp_path, relative, f"Real prose sample number {index} for {use_case}.")
            records.append({"path": relative, "use_case": use_case, "title": f"{prefix}{index}"})
    write_manifest(manifest, records)

    out_dir = tmp_path / "out"
    result = run_cli(
        "--manifest",
        manifest,
        "--root",
        tmp_path,
        "--out-dir",
        out_dir,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout.strip() != ""
    assert (out_dir / "references.holdout.jsonl").is_file()
    assert (out_dir / "eval_set.jsonl").is_file()
    assert (out_dir / "prompts.eval.jsonl").is_file()
