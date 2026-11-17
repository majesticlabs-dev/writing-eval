# Changelog

All notable changes to `writing-eval` are documented here.

## [0.3.0] - Unreleased

### Added

- List-aware diagnostics for shared opening words (`list_shared_lead`) and
  label or end-punctuation outliers (`list_inconsistent_form`). Both are
  informational review candidates, not deductions or grammatical judgments.
- `check` JSON includes `item_sets`; plain text reports each detected set.
- Corpus reports include order-independent `record_openings` counts outside
  the scored metrics and decision gate.

### Changed

- Repeated-opening detection, profile locations, and rates skip sentence pairs
  entering Markdown list items. Sentences within an item still count. Profile
  metric semantics are version 3; rebuild older profiles before use.
- Mixed-document rates can rise when list pairs leave the denominator. Profile
  alignment scores can move in either direction. With zero eligible pairs,
  the raw repeated-opening metric stays 0.0 but its assessment statistic is
  unavailable and produces no comparison or deduction. Assessment schema and
  rubric versions remain unchanged.
- The builtin set now has 36 rules. Rule fingerprints and reference caches
  change; refresh caches with `./writing-eval profile cache <name>` (plus
  `--rules PATH` for custom rules). Checks recompute missing reference counts.
- The new informational findings enter generation revision guidance and may
  trigger a revision call; the existing loop still stops on zero warn findings.

### Compatibility

- Reports and noise floors from 0.2.0 and 0.3.0 are not directly comparable:
  both repeated-opening semantics and aggregate tell rates can change. Future
  experiments must remeasure noise floors before official generation in the
  registration order required by `benchmark/THRESHOLDS.md`. Sealed records
  and historical verdicts are unchanged.
- `record_openings.shared_lead_record_rate` for empty or wholly tokenless
  corpora is `null` (`n/a` in Markdown), not a passing zero.

### Fixed

- Repeated-opening advice allows deliberate repetition. List advice preserves
  useful parallelism rather than asking writers to substitute synonyms.
- Task checkboxes and hyphenated words no longer distort list lead units;
  URL-led and code-led items do not receive shared-lead rewriting advice.
  Existing metric tokenization is unchanged.
- List summaries omit emphasis markup while finding spans retain source
  offsets. Form-outlier spans omit trailing whitespace and carriage returns.
  Indented fences remain inside their parent list; colon-only parent items
  are not labels. Plain-text shared leads use consistent JSON quoting.

## [0.2.0] - 2026-08-22

### Added

- Optional `rules/anti-ai.yaml` overlay extending the builtin rule set with
  reader-facing AI-writing tells: narrative cliches, significance-marking meta
  commentary, generation artifacts, and additive connector openers, plus widened
  phrase coverage for six builtin rules.
- Report JSON provenance records the tool name `writing-eval` and the installed
  package version, in addition to reference-corpus and rule-set identity.
- Generation `meta.json` records all three frozen decoding fields: `model`,
  `reasoning_effort`, and `system_prompt`.
- `profile.json` stores `references_sha256` for the paired `references.jsonl`
  file. A missing, invalid, or mismatched digest is a profile error with a
  rebuild instruction.

### Changed

- Profile metric semantics are version 2. Existing profiles must be rebuilt
  before use. Version 2 covers curly-apostrophe (U+2019) sentence openers,
  markdown-aware readability word counts, and MTLD tail, threshold, and
  sequence-input lowercase behavior.
- An unfinished MTLD tail that stays above the type-token threshold counts as
  one factor. A fully unique 10-token input returns 10.0. Inputs below 10
  tokens remain `n/a`. The threshold must be a finite value in `(0, 1)`.
- Style-rule exceptions match with Unicode `casefold()` on the candidate's own
  context.
- `profile list` includes only profiles that load successfully. The CLI prints
  a skip note on stderr for each rejected directory.
- Profile names must be exactly one non-absolute path component and must not be
  `.` or `..`.
- `generation_artifacts` flags bracketed scaffolding tokens (`insert`, `todo`,
  `tbd`, `placeholder`, `xxx`), chatgpt.com tracking parameters, and model
  self-reference. Ordinary spans such as `[your account]` are not flagged.
- Token 1-gram L2 is `n/a` when either side has zero tokens.
- Prompt records must include a `use_case` of `article_section`,
  `product_writing`, or `exec_communication`.
- Standalone rule files reject unknown keys and empty exception strings.
- Benchmark comparison rejects non-finite metric and floor values. Eval-set
  loaders reject duplicate IDs and negative word counts.

### Fixed

- Malformed, unreadable, or zero-word profile references during `check --style`
  produce exit 1 with a message instead of a traceback.
- CLI rule loading no longer converts unexpected programming errors into user
  errors. Boundary errors remain exit 1.
- Profile writes use temporary files and `os.replace`, so an interrupted write
  does not leave a truncated `profile.json` or `references.jsonl`.
- Removed the leftover `profile_io.py.current` packaging copy.

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
