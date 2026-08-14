# Changelog

All notable changes to `writing-eval` are documented here.

## [Unreleased]

### Added

- Optional `rules/anti-ai.yaml` overlay extending the builtin rule set with
  reader-facing AI-writing tells: narrative cliches, significance-marking meta
  commentary, generation artifacts, and additive connector openers, plus widened
  phrase coverage for six builtin rules.

## [0.1.0] - 2026-08-14

Initial public release.

### Added

- Deterministic, local CPU-based writing evaluation.
- Reusable style profiles built from Markdown and plain-text reference prose.
- Profile-relative draft checks for clarity, readability, sentence rhythm, vocabulary, and writing patterns.
- Human-readable Markdown reports and structured JSON output.
- Corpus evaluation for comparing generated outputs with a reference corpus.
- Deterministic metrics, style-rule auditing, preservation checks, and report generation.
- `writing-eval --version` for reporting the installed package version.
