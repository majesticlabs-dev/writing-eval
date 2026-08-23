"""Overlay error handling, post-merge validation, and rule fingerprints."""

from pathlib import Path

import pytest

from writing_eval.style_audit import load_rules, rules_fingerprint
from writing_eval.style_audit_overlay import resolve_raw_rules

from tests.helpers_rules_overlay import BASE_YAML, base_file, ids_of, write


@pytest.fixture
def rules_root(tmp_path: Path) -> Path:
    """Fully resolved scratch directory; overlay paths are resolved on load."""

    return tmp_path.resolve()


def test_disable_of_unknown_id_is_rejected(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: nowhere\n    enabled: false\n",
    )
    with pytest.raises(ValueError, match="'enabled: false' on unknown id 'nowhere'"):
        resolve_raw_rules(overlay)


def test_new_rule_missing_required_fields_is_rejected(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: partial\n    severity: warn\n",
    )
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(overlay)
    message = str(error.value)
    assert "'partial'" in message
    assert "detector" in message
    assert "message" in message


def test_unknown_overlay_field_is_rejected(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    sevrity: warn\n",
    )
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(overlay)
    message = str(error.value)
    assert "'alpha'" in message
    assert "sevrity" in message
    assert str(overlay) in message
    assert "allowed fields are: id, severity, detector, message, exceptions, enabled" in message


def test_duplicate_id_within_one_overlay_is_rejected(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\n"
        "rules:\n"
        "  - id: alpha\n"
        "    severity: info\n"
        "  - id: alpha\n"
        "    severity: warn\n",
    )
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(overlay)
    assert "Duplicate overlay rule id 'alpha'" in str(error.value)
    assert str(overlay) in str(error.value)


def test_missing_extends_target_is_rejected(rules_root: Path) -> None:
    overlay = write(
        rules_root / "overlay.yaml",
        "extends: absent.yaml\nrules:\n  - id: alpha\n    severity: info\n",
    )
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(overlay)
    message = str(error.value)
    assert str(overlay) in message
    assert str(rules_root / "absent.yaml") in message


def test_circular_extends_chain_is_rejected(rules_root: Path) -> None:
    first = rules_root / "first.yaml"
    second = rules_root / "second.yaml"
    write(first, "extends: second.yaml\nrules: []\n")
    write(second, "extends: first.yaml\nrules: []\n")
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(first)
    message = str(error.value)
    assert "Circular" in message
    assert str(second) in message
    assert str(first) in message


def _write_chain(rules_root: Path, length: int) -> Path:
    write(rules_root / "link0.yaml", BASE_YAML)
    for index in range(1, length + 1):
        write(
            rules_root / f"link{index}.yaml",
            f"extends: link{index - 1}.yaml\nrules: []\n",
        )
    return rules_root / f"link{length}.yaml"


def test_chain_at_the_depth_limit_is_accepted(rules_root: Path) -> None:
    top = _write_chain(rules_root, 16)
    assert ids_of(resolve_raw_rules(top)) == ["alpha", "beta", "gamma"]


def test_chain_beyond_the_depth_limit_is_rejected(rules_root: Path) -> None:
    top = _write_chain(rules_root, 17)
    with pytest.raises(ValueError) as error:
        resolve_raw_rules(top)
    message = str(error.value)
    assert "maximum depth of 16" in message
    assert str(rules_root / "link0.yaml") in message


def test_bad_severity_in_an_override_raises_only_after_merge(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    severity: bogus\n",
    )
    merged = resolve_raw_rules(overlay)
    assert merged[0]["severity"] == "bogus"
    with pytest.raises(ValueError, match="invalid severity 'bogus'"):
        load_rules(overlay)


def test_uncompilable_detector_in_an_override_raises_only_after_merge(
    rules_root: Path,
) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    detector: '([unclosed'\n",
    )
    merged = resolve_raw_rules(overlay)
    assert merged[0]["detector"] == "([unclosed"
    with pytest.raises(ValueError, match="Rule 'alpha' has invalid regex detector"):
        load_rules(overlay)


def test_fingerprint_is_stable_across_repeated_loads(rules_root: Path) -> None:
    path = base_file(rules_root)
    assert rules_fingerprint(load_rules(path)) == rules_fingerprint(load_rules(path))


def test_fingerprint_changes_on_override_addition_and_removal(rules_root: Path) -> None:
    base = base_file(rules_root)
    baseline = rules_fingerprint(load_rules(base))
    overridden = write(
        rules_root / "override.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    severity: info\n",
    )
    added = write(
        rules_root / "added.yaml",
        f"extends: {base.name}\n"
        "rules:\n"
        "  - id: delta\n"
        "    severity: info\n"
        "    detector: '(?i)\\bdelta\\b'\n"
        "    message: Delta message.\n",
    )
    removed = write(
        rules_root / "removed.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    enabled: false\n",
    )
    digests = {
        baseline,
        rules_fingerprint(load_rules(overridden)),
        rules_fingerprint(load_rules(added)),
        rules_fingerprint(load_rules(removed)),
    }
    assert len(digests) == 4


def test_blank_exception_in_an_override_is_rejected_after_merge(rules_root: Path) -> None:
    base = base_file(rules_root)
    overlay = write(
        rules_root / "overlay.yaml",
        f"extends: {base.name}\nrules:\n  - id: alpha\n    exceptions: ['']\n",
    )
    with pytest.raises(ValueError, match="empty strings"):
        load_rules(overlay)
