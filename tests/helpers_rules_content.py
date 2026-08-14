"""Shared auditor construction for builtin rule-set behavior tests."""

from writing_eval.style_audit import BUILTIN_RULES_PATH, StyleAuditor


def builtin_auditor() -> StyleAuditor:
    return StyleAuditor.from_yaml(BUILTIN_RULES_PATH)


def findings_for(auditor: StyleAuditor, rule_id: str, text: str):
    return [finding for finding in auditor.audit(text) if finding.rule_id == rule_id]
