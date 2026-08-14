"""Compatibility facade for rule-based style auditing."""

from .style_audit_engine import StyleAuditor, audit_text
from .style_audit_models import Finding, Rule, VALID_SEVERITIES
from .style_audit_paths import BUILTIN_RULES_PATH
from .style_audit_rules import load_rules, rules_fingerprint

__all__ = [
    "BUILTIN_RULES_PATH",
    "Finding",
    "Rule",
    "StyleAuditor",
    "VALID_SEVERITIES",
    "audit_text",
    "load_rules",
    "rules_fingerprint",
]
