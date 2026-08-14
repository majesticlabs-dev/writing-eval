"""Compatibility facade for profile-relative scored assessments."""

from .assessment_build import build_assessment
from .assessment_core import relative_gap as _relative_gap
from .assessment_core import scaled_deduction as _scaled_deduction
from .assessment_render import render_assessment
from .assessment_rules import build_rule_baseline

__all__ = ["build_assessment", "build_rule_baseline", "render_assessment"]
