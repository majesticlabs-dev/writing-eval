import json
from pathlib import Path

from tests.helpers_profiles import _build_demo, _write_sources, run_cli


def test_cli_profile_build_and_list(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path / "sources")
    root = tmp_path / "profiles"
    build = run_cli("profile", "build", "demo", "--from", sources, "--profiles-root", root)
    assert build.returncode == 0, build.stderr
    assert (root / "demo" / "profile.json").is_file()
    assert (root / "demo" / "references.jsonl").is_file()
    assert "2 sources" in build.stdout

    listing = run_cli("profile", "list", "--profiles-root", root)
    assert listing.returncode == 0, listing.stderr
    assert "demo: 2 sources" in listing.stdout


def test_cli_check_style_json_has_style_gap(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early. We win markets often.\n", encoding="utf-8")
    result = run_cli(
        "check", draft, "--style", "demo", "--profiles-root", root, "--format", "json"
    )
    assert result.returncode == 0, result.stderr
    assert "no references provided" not in result.stderr
    payload = json.loads(result.stdout)
    assert "style_gap" in payload
    gap = payload["style_gap"]
    assert gap["profile"] == "demo"
    assert set(gap) == {"profile", "metrics", "token_1gram_l2", "top_overrepresented"}
    assert set(gap["metrics"][0]) == {"metric", "draft", "profile", "delta"}
    assessment = payload["assessment"]
    assert assessment["schema_version"] == 2
    assert assessment["rubric_version"] == "profile-alignment-v2"
    assert assessment["basis"] == "rules_and_target_profile"
    assert assessment["profile"] == {"id": "demo"}
    assert assessment["score"]["total"] == sum(
        section["score"] for section in assessment["score"]["sections"]
    )
    baseline = assessment["rule_baseline"]
    assert baseline["basis"] == "profile_reference_corpus"
    assert baseline["profile_word_count"] > 0
    assert baseline["rules"] == sorted(baseline["rules"], key=lambda item: item["id"])


def test_cli_profile_rule_baseline_allows_profile_dash_but_rejects_excess(
    tmp_path: Path,
) -> None:
    profiles_root = tmp_path / "profiles"
    sources = tmp_path / "sources"
    sources.mkdir()
    dash = chr(0x2014)
    (sources / "voice.md").write_text(
        f"Clear{dash}direct writing keeps teams aligned today.\n",
        encoding="utf-8",
    )
    built = run_cli(
        "profile",
        "build",
        "dashed",
        "--from",
        sources,
        "--profiles-root",
        profiles_root,
    )
    assert built.returncode == 0, built.stderr

    aligned_draft = tmp_path / "aligned.md"
    aligned_draft.write_text(f"Clear{dash}direct notes keep teams aligned.\n", encoding="utf-8")
    aligned = run_cli(
        "check",
        aligned_draft,
        "--style",
        "dashed",
        "--profiles-root",
        profiles_root,
        "--format",
        "json",
    )
    assert aligned.returncode == 0, aligned.stderr
    aligned_payload = json.loads(aligned.stdout)
    assert any(
        finding["rule_id"] == "em_dash_ban"
        for finding in aligned_payload["findings"]
    )
    dash_baseline = next(
        entry
        for entry in aligned_payload["assessment"]["rule_baseline"]["rules"]
        if entry["id"] == "em_dash_ban"
    )
    assert dash_baseline["allowance"] == 1
    assert dash_baseline["excess"] == 0
    assert not any(
        issue["id"] == "em_dash_ban"
        for issue in aligned_payload["assessment"]["issues"]
    )

    excess_draft = tmp_path / "excess.md"
    excess_draft.write_text(
        f"Clear{dash}direct notes stay short{dash}and specific.\n",
        encoding="utf-8",
    )
    excess = run_cli(
        "check",
        excess_draft,
        "--style",
        "dashed",
        "--profiles-root",
        profiles_root,
        "--format",
        "json",
    )
    assert excess.returncode == 0, excess.stderr
    excess_payload = json.loads(excess.stdout)
    issue = next(
        issue
        for issue in excess_payload["assessment"]["issues"]
        if issue["id"] == "em_dash_ban"
    )
    assert issue["deduction"] == 2
    assert issue["comparisons"][0]["delta"] == 1


def test_cli_check_style_text_section(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early. We win markets often.\n", encoding="utf-8")
    result = run_cli("check", draft, "--style", "demo", "--profiles-root", root)
    assert result.returncode == 0, result.stderr
    assert "# Writing Evaluation" in result.stdout
    assert "## Article score (heuristic)" in result.stdout
    assert "## Issues to improve" in result.stdout
    assert "## General statistics" in result.stdout
    assert "target profile" in result.stdout.lower()
    assert "overall content quality" in result.stdout
    assert "demo" not in result.stdout


def test_cli_check_without_style_has_no_style_gap(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We write clearly. Editors revise carefully.\n", encoding="utf-8")
    result = run_cli("check", draft, "--format", "json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "style_gap" not in payload
    assert "assessment" not in payload


def test_cli_json_stdout_and_json_path_share_assessment(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early. We win markets often.\n", encoding="utf-8")
    stdout_result = run_cli(
        "check",
        draft,
        "--style",
        "demo",
        "--profiles-root",
        root,
        "--format",
        "json",
    )
    json_path = tmp_path / "assessment.json"
    file_result = run_cli(
        "check",
        draft,
        "--style",
        "demo",
        "--profiles-root",
        root,
        "--json",
        json_path,
    )

    assert stdout_result.returncode == 0, stdout_result.stderr
    assert file_result.returncode == 0, file_result.stderr
    stdout_payload = json.loads(stdout_result.stdout)
    file_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert stdout_payload["assessment"] == file_payload["assessment"]
    assert "# Writing Evaluation" in file_result.stdout


def test_cli_check_style_empty_draft_is_unscored(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    draft = tmp_path / "empty.md"
    draft.write_text("", encoding="utf-8")
    text_result = run_cli(
        "check", draft, "--style", "demo", "--profiles-root", root
    )
    json_result = run_cli(
        "check",
        draft,
        "--style",
        "demo",
        "--profiles-root",
        root,
        "--format",
        "json",
    )

    assert text_result.returncode == 0, text_result.stderr
    unscored_message = (
        "**Unscored " + chr(0x2014) + " Draft has no scorable prose sentences.**"
    )
    assert unscored_message in text_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["assessment"]["status"] == "unscored"
    assert payload["assessment"]["score"]["total"] is None


def test_cli_check_style_and_references_is_usage_error(tmp_path: Path) -> None:
    references = tmp_path / "refs.jsonl"
    references.write_text(
        json.dumps({"id": "ref-1", "text": "Editors write clearly."}) + "\n",
        encoding="utf-8",
    )
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early.\n", encoding="utf-8")
    result = run_cli(
        "check",
        draft,
        "--style",
        "demo",
        "--profiles-root",
        tmp_path / "profiles",
        "--references",
        references,
    )
    assert result.returncode == 1
    assert "mutually exclusive" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_check_unknown_profile_is_usage_error(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("We ship early.\n", encoding="utf-8")
    result = run_cli(
        "check", draft, "--style", "ghost", "--profiles-root", tmp_path / "profiles"
    )
    assert result.returncode == 1
    assert "profile not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_profile_list_reports_invalid_summary(tmp_path: Path) -> None:
    root = _build_demo(tmp_path)
    invalid = root / "invalid"
    invalid.mkdir()
    (invalid / "profile.json").write_text(
        '{"sources": 3, "total_words": 100}',
        encoding="utf-8",
    )

    result = run_cli("profile", "list", "--profiles-root", root)

    assert result.returncode == 0
    assert "demo: 2 sources" in result.stdout
    assert result.stderr.count("skipped unreadable profile") == 1
    assert "invalid" in result.stderr
    assert "sources field is not a list" in result.stderr
    assert "Traceback" not in result.stderr
