"""Compatibility facade for comparison and decision-gate analysis."""

from .comparison_gate import decision_gate, render_gate_markdown
from .comparison_noise import aggregate_runs, noise_floor, render_noise_floor_markdown
from .comparison_systems import compare_systems, render_comparison_markdown

__all__ = [
    "aggregate_runs",
    "compare_systems",
    "decision_gate",
    "noise_floor",
    "render_comparison_markdown",
    "render_gate_markdown",
    "render_noise_floor_markdown",
]
