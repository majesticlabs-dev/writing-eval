"""Decision-gate tests."""

from __future__ import annotations

from writing_eval.comparison import decision_gate, render_gate_markdown
from tests.helpers_comparison import CLEAN_LONG_TEXT, REFERENCE_CORPUS, RULES_PATH

def test_decision_gate_passing_case() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses == {1: "pass", 2: "pass", 3: "pass", 4: "pass"}
    assert gate["verdict"] == "sufficient"


def test_decision_gate_fails_criterion_1_warn_findings() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans" + chr(0x2014) + "direct and simple today."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[1] == "fail"
    criterion_1 = next(c for c in gate["criteria"] if c["id"] == 1)
    assert criterion_1["description"] == (
        "Zero warn-severity findings across the audited set."
    )
    assert criterion_1["measured"] == {"warn_finding_count": 1}
    assert gate["verdict"] == "insufficient"


def test_decision_gate_fails_criterion_2_tell_rate() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "The report was written today."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[1] == "pass"
    assert statuses[2] == "fail"
    assert gate["verdict"] == "insufficient"


def test_decision_gate_fails_criterion_3_l2_drift() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Xylophone quokka bizarre nebula perpendicular octagon."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 0.001, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[1] == "pass"
    assert statuses[2] == "pass"
    assert statuses[3] == "fail"
    assert gate["verdict"] == "insufficient"
    criterion_3 = next(c for c in gate["criteria"] if c["id"] == 3)
    assert criterion_3["measured"]["delta"] > 0.001


def test_decision_gate_fails_criterion_4_degenerate_output() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "??? !!! ..."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[4] == "fail"
    assert gate["verdict"] == "insufficient"
    criterion_4 = next(c for c in gate["criteria"] if c["id"] == 4)
    assert criterion_4["measured"]["n_null_audited"] == 1
    assert criterion_4["measured"]["n_null_current"] == 0


def test_decision_gate_blocked_when_noise_floor_is_none() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, None, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[3] == "blocked"
    assert gate["verdict"] == "blocked"


def test_decision_gate_label_marks_delta_below_floor_inconclusive() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    criterion_3 = next(c for c in gate["criteria"] if c["id"] == 3)
    assert criterion_3["label"] == "inconclusive"

def test_decision_gate_omits_criterion_5_without_word_counts() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    ids = {criterion["id"] for criterion in gate["criteria"]}
    assert ids == {1, 2, 3, 4}


def test_decision_gate_criterion_5_passes_for_adequate_length() -> None:
    current = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    audited = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    gate = decision_gate(
        current,
        audited,
        REFERENCE_CORPUS,
        RULES_PATH,
        10.0,
        tell_rate_threshold=2.0,
        eval_reference_word_counts={"a1": 100},
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses == {1: "pass", 2: "pass", 3: "pass", 4: "pass", 5: "pass"}
    assert gate["verdict"] == "sufficient"


def test_decision_gate_criterion_5_fails_below_absolute_floor() -> None:
    current = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current,
        audited,
        REFERENCE_CORPUS,
        RULES_PATH,
        10.0,
        tell_rate_threshold=2.0,
        eval_reference_word_counts={"a1": 100},
    )
    criterion_5 = next(c for c in gate["criteria"] if c["id"] == 5)
    assert criterion_5["status"] == "fail"
    assert criterion_5["measured"]["below_threshold_count"] == 1
    assert criterion_5["measured"]["shortest_words"] == 9
    assert gate["verdict"] == "insufficient"


def test_decision_gate_criterion_5_fails_below_reference_fraction() -> None:
    current = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    audited = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    gate = decision_gate(
        current,
        audited,
        REFERENCE_CORPUS,
        RULES_PATH,
        10.0,
        tell_rate_threshold=2.0,
        eval_reference_word_counts={"a1": 400},
    )
    criterion_5 = next(c for c in gate["criteria"] if c["id"] == 5)
    # 59 words is above the 50-word floor but below 30 percent of 400 (120).
    assert criterion_5["status"] == "fail"
    assert criterion_5["measured"]["below_threshold_count"] == 1
    assert gate["verdict"] == "insufficient"


def test_decision_gate_criterion_5_missing_id_uses_absolute_floor() -> None:
    current = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    audited = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    gate = decision_gate(
        current,
        audited,
        REFERENCE_CORPUS,
        RULES_PATH,
        10.0,
        tell_rate_threshold=2.0,
        eval_reference_word_counts={},
    )
    criterion_5 = next(c for c in gate["criteria"] if c["id"] == 5)
    # No reference length is known, so only the 50-word floor applies; 59 clears it.
    assert criterion_5["status"] == "pass"
    assert gate["verdict"] == "sufficient"


def test_gate_markdown_renders_criterion_5_without_dashes() -> None:
    current = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    audited = [{"id": "a1", "text": CLEAN_LONG_TEXT}]
    gate = decision_gate(
        current,
        audited,
        REFERENCE_CORPUS,
        RULES_PATH,
        10.0,
        tell_rate_threshold=2.0,
        eval_reference_word_counts={"a1": 100},
    )
    markdown = render_gate_markdown(gate)
    assert "## Criterion 5" in markdown
    assert "Length adequacy" in markdown
    assert chr(0x2014) not in markdown
    assert chr(0x2013) not in markdown


def test_gate_markdown_is_deterministic() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans use direct words and stay specific here."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    first = render_gate_markdown(gate)
    second = render_gate_markdown(gate)
    assert first == second
    assert "Verdict: sufficient" in first
    assert chr(0x2014) not in first
    assert chr(0x2013) not in first


def test_decision_gate_reports_literal_preservation_without_changing_verdict() -> None:
    current = [{"id": "a1", "text": "The rollout reached 200 users."}]
    audited = [{"id": "a1", "text": "The rollout reached 300 users."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    preservation = gate["diagnostics"]["literal_preservation"]
    assert preservation["status"] == "fail"
    assert preservation["missing_literal_count"] == 1
    assert preservation["added_literal_count"] == 1
    assert gate["verdict"] == "sufficient"

    markdown = render_gate_markdown(gate)
    assert "## Informational diagnostics" in markdown
    assert "normalized quoted spans" in markdown
    assert "does not affect the registered decision-gate verdict" in markdown


def test_decision_gate_zero_word_audited_set_fails_criterion_2() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited: list[dict] = []
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, 10.0, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[2] == "fail"
    criterion_2 = next(c for c in gate["criteria"] if c["id"] == 2)
    assert criterion_2["measured"]["tell_rate"] == 0.0
    assert criterion_2["measured"]["word_count"] == 0
    assert gate["verdict"] == "insufficient"


def test_decision_gate_failure_outranks_blocked_criterion() -> None:
    current = [{"id": "c1", "text": "Clear plans use direct words and stay specific today."}]
    audited = [{"id": "a1", "text": "Clear plans" + chr(0x2014) + "direct and simple today."}]
    gate = decision_gate(
        current, audited, REFERENCE_CORPUS, RULES_PATH, None, tell_rate_threshold=2.0
    )
    statuses = {criterion["id"]: criterion["status"] for criterion in gate["criteria"]}
    assert statuses[1] == "fail"
    assert statuses[3] == "blocked"
    assert gate["verdict"] == "insufficient"
