"""Compatibility facade for structured and Markdown reports."""

from .report_data import build_provenance, build_report
from .report_markdown import render_markdown

__all__ = ["build_provenance", "build_report", "render_markdown"]
