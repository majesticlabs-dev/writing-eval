"""Overlay merge semantics for `extends` rule files."""

from pathlib import Path

import pytest

from writing_eval.style_audit import BUILTIN_RULES_PATH
from writing_eval.style_audit_overlay import resolve_raw_rules

from tests.helpers_rules_overlay import BASE_YAML, base_file, ids_of, write


@pytest.fixture
def rules_root(tmp_path: Path) -> Path:
    """Fully resolved scratch directory; overlay paths are resolved on load."""

    return tmp_path.resolve()


def test_replace_mode_without_extends_returns_file_rules(rules_root: Path) -> None:
    path = base_file(rules_root)
    assert ids_of(resolve_raw_rules(path)) == ["alpha", "beta", "gamma"]


def test_bare_list_document_is_accepted(rules_root: Path) -> None:
    path = write(
        rules_root / "list.yaml",
        "- id: solo\n  severity: warn\n  detector: '(?i)solo'\n  message: Solo.\n",
    )
    assert ids_of(resolve_raw_rules(path)) == ["solo"]


def test_mapping_without_rules_key_is_rejected(rules_root: Path) -> None:
    path = write(rules_root / "bad.yaml", "version: 1\nother: 3\n")
    with pytest.raises(ValueError, match="must contain a 'rules' list"):
        resolve_raw_rules(path)


def test_new_rule_is_appended_after_the_base_rules(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\n"
        "rules:\n"
        "  - id: new_one\n"
        "    severity: warn\n"
        "    detector: '(?i)\\bjargon\\b'\n"
        "    message: Use plain language.\n"
        "  - id: new_two\n"
        "    severity: info\n"
        "    detector: '(?i)\\bsynergy\\b'\n"
        "    message: Say what happened.\n",
    )
    merged = resolve_raw_rules(overlay)
    assert ids_of(merged) == ["alpha", "beta", "gamma", "new_one", "new_two"]
    assert merged[3]["severity"] == "warn"


def test_partial_override_keeps_position_and_unspecified_fields(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: beta\n    severity: warn\n",
    )
    merged = resolve_raw_rules(overlay)
    assert ids_of(merged) == ["alpha", "beta", "gamma"]
    assert merged[1]["severity"] == "warn"
    assert merged[1]["message"] == "Beta message."
    assert merged[1]["detector"] == "(?i)\\bbeta\\b"
    assert merged[1]["exceptions"] == ["beta exception"]


def test_disable_removes_the_rule_and_keeps_other_positions(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: beta\n    enabled: false\n",
    )
    assert ids_of(resolve_raw_rules(overlay)) == ["alpha", "gamma"]


def test_override_disable_and_append_combine_in_declaration_order(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\n"
        "rules:\n"
        "  - id: delta\n"
        "    severity: warn\n"
        "    detector: '(?i)\\bdelta\\b'\n"
        "    message: Delta message.\n"
        "  - id: alpha\n"
        "    enabled: false\n"
        "  - id: gamma\n"
        "    severity: info\n",
    )
    merged = resolve_raw_rules(overlay)
    assert ids_of(merged) == ["beta", "gamma", "delta"]
    assert merged[1]["severity"] == "info"


def test_recursive_overlays_merge_in_chain_order(rules_root: Path) -> None:
    base = base_file(rules_root)
    middle = write(
        rules_root / "middle.yaml",
        f"extends: {base.name}\n"
        "rules:\n"
        "  - id: middle_rule\n"
        "    severity: info\n"
        "    detector: '(?i)\\bmiddle\\b'\n"
        "    message: Middle message.\n",
    )
    top = write(
        rules_root / "top.yaml",
        f"extends: {middle.name}\nrules:\n  - id: middle_rule\n    severity: warn\n",
    )
    merged = resolve_raw_rules(top)
    assert ids_of(merged) == ["alpha", "beta", "gamma", "middle_rule"]
    assert merged[3]["severity"] == "warn"


def test_builtin_extends_is_cwd_independent(
    rules_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay = write(
        rules_root / "overlay.yaml",
        "extends: builtin\nrules:\n  - id: passive_voice\n    enabled: false\n",
    )
    elsewhere = rules_root / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    merged = resolve_raw_rules(overlay)
    builtin_ids = ids_of(resolve_raw_rules(BUILTIN_RULES_PATH))
    assert ids_of(merged) == [rule_id for rule_id in builtin_ids if rule_id != "passive_voice"]


def test_relative_extends_resolves_against_the_overlay_directory(
    rules_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = rules_root / "nested"
    nested.mkdir()
    write(nested / "base.yaml", BASE_YAML)
    overlay = write(
        nested / "overlay.yaml",
        "extends: base.yaml\nrules:\n  - id: alpha\n    severity: info\n",
    )
    monkeypatch.chdir(rules_root)
    merged = resolve_raw_rules(overlay)
    assert ids_of(merged) == ["alpha", "beta", "gamma"]
    assert merged[0]["severity"] == "info"
