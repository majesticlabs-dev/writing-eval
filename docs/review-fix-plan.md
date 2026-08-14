# Review Fix Plan

Status: revised 2026-08-14 after plan review, not yet approved for
implementation.

Scope: fix all verified findings from the full project review (353 tests passing at
review time). The Codex generation subsystem is kept while the owner evaluates it,
but its verified hardening issues are fixed. Benchmark wrapper exit codes stay at 2.
Decision-gate hardening is approved.

Observable contract changes are limited to the following:

- Style-rule exceptions suppress only a candidate's own context and are compared
  case-insensitively.
- A zero assessment deduction renders as `0 points` without a minus sign.
- Existing profiles gain a metric-version field and profiles built with older metric
  semantics must be rebuilt before use.
- Unknown top-level commands return a focused user error instead of being parsed as
  flat eval arguments.
- `writing-eval check -` reads standard input as UTF-8 regardless of the process
  locale.
- `benchmark/generate_runs.py` gains `--timeout`; generation diagnostics gain a
  `failure_kind` field for per-record subprocess failures.
- Decision-gate failure takes precedence over a blocked criterion. Existing verdict
  strings remain `sufficient`, `insufficient`, and `blocked`.
- Profile listing can report skipped corrupt profile directories on stderr through
  an explicit CLI callback. Library callers remain silent by default.

All other public CLI behavior, JSON field names, report fields, ordering, and exit
codes stay unchanged. Cache sidecar fields are internal and may change as specified
below.

Benchmark compatibility note: changes to the builtin rule set alter future benchmark
finding counts because the benchmark wrapper currently defaults to that rule set.
The syllable change also alters readability values in future reports. Historical
thresholds, official reports, noise floors, and recorded verdicts are not rewritten.
Before any new official benchmark run, record that its rule fingerprint and metric
version differ from earlier runs and follow the registration order in
`benchmark/THRESHOLDS.md`. This implementation does not claim direct comparability
with earlier official outputs.

## Phase 1: Scoring correctness

1. `src/writing_eval/assessment_rules.py:34-39`. Replace the float round-trip
   allowance with exact integer ceiling
   `-(-profile_count * draft_word_count // profile_word_count)` while keeping
   `profile_rate_per_1000` as a float for display. Remove the now-unused `math`
   import. Add regression tests for the verified off-by-one cases: 1 occurrence,
   229 profile words, and 229 draft words gives allowance 1; 15 occurrences, 233
   profile words, and 233 draft words gives allowance 15.
2. `src/writing_eval/assessment_render.py:34`. Render `Deduction: 0 points` when
   the deduction is zero. Keep the existing minus-prefixed form for positive
   deductions. Add a test for both branches.
3. `src/writing_eval/assessment_core.py:42-48`. Validate `tolerance < cap` before
   the early return in `scaled_deduction`; invalid parameters raise `ValueError`
   even when `gap` is `None` or already within tolerance. Add boundary tests for
   equality, reversed bounds, and a valid call.
4. `src/writing_eval/assessment_core.py` and
   `src/writing_eval/assessment_build.py`. Add `SECTION_MAXIMUM = 25` and derive
   `ASSESSMENT_MAXIMUM = len(SECTION_DEFINITIONS) * SECTION_MAXIMUM`. Replace every
   literal section or total maximum with these constants. Replace the stripped
   `assert` with `RuntimeError("assessment deduction totals are inconsistent")`.
   Add a test that score and section maxima come from the shared constants.
5. `assessment_build.py`, `assessment_profile.py`, and
   `assessment_statistics.py`. Move the empty-draft unscored decision before
   profile-issue construction, but preserve the full assessment shape.
   `statistics` continues to contain every known statistic ID. A missing gap emits
   `value: null`, `target: null`, and `interpretation: unavailable`; it is never
   hidden. A profile issue that needs one or more absent gaps is skipped. The
   unscored score object keeps all section IDs and derived maxima. Add tests for an
   empty draft with an incomplete gap map and for a scored draft missing one metric.

## Phase 2: Detection and metric correctness

6. `src/writing_eval/style_audit_engine.py:21-22,43-55`. Check exceptions against
   `text[context_start:context_end]`, not the whole line, and compare the candidate
   context and exception strings with `casefold()`. For regex rules this context is
   the match span. Delete `_line_context` after the cutover. Update
   `test_exception_string_in_match_context_suppresses_finding` to the new contract,
   keep the other-line test, and add regressions that a distant same-line exception
   does not suppress and that a capitalized in-context exception does suppress.
   The sentence "The code was written by the team and he was interested in art."
   keeps its passive-voice finding. Existing `interested` and `a kind of` overlap
   cases stay green.
7. `src/writing_eval/rules/style-audit.yaml:202` (`false_range`). Add `(?m)` so
   `$` matches at line ends. Add a line-final-range test and retain an end-of-string
   test.
8. `style-audit.yaml:184` (`theatrical_opener`). Require exactly one colon or comma
   after `real talk` with `real talk[:,]`. Add tests that `Real talk:` and
   `Real talk,` are flagged and `Real talk about scaling follows.` is not.
9. `style-audit.yaml:53` (`passive_voice`). Restrict only the regular `\w+ed`
   branch with a lookahead that requires either end punctuation/end of line/end of
   string or whitespace followed by one of these relationship words:
   `by`, `with`, `in`, `on`, `at`, `to`, `from`, `for`, `as`, `after`, `before`,
   `during`, `through`, `into`, `under`, `over`, `within`, or `without`. Keep the
   explicit irregular-participle branch unchanged. Add `indeed`, `naked`,
   `beloved`, `wicked`, and `ragged` to exceptions. Tests cover a regular
   participle at punctuation, regular participles followed by `by` and a supported
   preposition, an irregular participle, all five added exceptions, and a
   capitalized exception. The precision-first limitation for unlisted continuations
   is documented in a YAML comment. Add YAML comments that the participle lists in
   `passive_voice` and `subjectless_fragment` are intentionally separate and that
   `negative_parallelism` and `negative_listing` overlap by design.
10. `src/writing_eval/metrics_quality.py:9-24`. Apply at most one new terminal
    suffix adjustment after the existing vowel-group count. Subtract one for
    terminal `-es` when the stem does not end in `s`, `z`, `x`, `ch`, or `sh`,
    except for words ending in consonant-plus-`les`. Subtract one for terminal
    `-ed` when the stem does not end in `t` or `d`. Keep the final minimum of one
    syllable. Pin existing words (`the`, `cake`, `apple`, `table`, `syllable`,
    `quick`, `brown`, `fox`) and add `makes = 1`, `likes = 1`, `catches = 2`,
    `boxes = 2`, `tables = 2`, `liked = 1`, `walked = 1`, `wanted = 2`, and
    `needed = 2`. Remove the dead `if group` filter in `paragraph_stats`.
11. `src/writing_eval/profile_io.py` and profile tests. Add a numeric
    `metrics_version` field to newly built `profile.json` files and require the
    current version in `load_profile`. A missing or older value raises
    `ProfileError` with a direct `profile build` rebuild instruction. This prevents
    old syllable-derived profile statistics from being compared with new draft
    metrics. Update profile fixtures and README profile-schema documentation.
12. README metrics and rule-schema sections. Document the suffix heuristic,
    candidate-scoped case-insensitive exceptions, the precision-first regular
    passive-voice branch, and the profile rebuild requirement.

## Phase 3: Profile cache code binding

13. `src/writing_eval/profile_cache.py`. Compute one deterministic SHA-256 code
    digest at import from the bytes of `style_audit_detectors.py`,
    `style_audit_engine.py`, and `segmentation.py`, in that fixed order with the
    relative filename included before each payload. Store `code_sha256` in both
    cache entries and require equality during validation. A missing field is a
    cache miss and causes one-time recomputation. The shared digest intentionally
    allows an audit-engine-only change to invalidate the token cache in exchange
    for one simple cache contract. Tests patch the digest to prove missing and
    changed values invalidate both entry types.
14. Replace `_atomic_write_json` with `tempfile.mkstemp` in the destination
    directory followed by `os.replace`. Always close the descriptor and remove an
    uninstalled temporary file after any write or replace failure. After the new
    rules cache is installed, prune `rules-*.json` siblings except the current
    filename. A prune failure raises `ProfileError`; it does not remove the valid
    current cache. Tests cover replacement, temporary-file cleanup, and pruning.
15. Validate every nonblank record in `_reference_texts`: it must be a JSON object
    with a nonempty string `id` and string `text`, and IDs must be unique. Convert
    `OSError`, `UnicodeDecodeError`, `JSONDecodeError`, and record-shape errors to
    line-specific `ProfileError` messages. Tests cover each error class. README
    notes that caches invalidate when detector or tokenizer code changes.

## Phase 4: Input, CLI, and generation hardening

16. Convert UTF-8 decode failures to clean boundary errors using the pattern in
    `cli_check.py:53-58`: `cli.py` JSONL loading, both JSONL readers in `corpus.py`,
    `profile_io.py`, `profile_cache.py`, and `generation_io.py`. Tests exercise an
    invalid-UTF-8 eval reference, eval output, corpus input, profile metadata,
    profile references, generation prompt manifest, and generation config.
17. `cli_check.py:44-49`. Before reading `-`, call
    `sys.stdin.reconfigure(encoding="utf-8", errors="strict")` when the stream
    provides `reconfigure`. Keep test-stream compatibility when it does not. Add a
    bytes-input subprocess test under a C locale that includes non-ASCII UTF-8 and
    a second test for malformed UTF-8.
18. `cli.py:18-35,86-121`. Remove the yaml and style-audit import fallbacks,
    `_audit_function`, signature sniffing, and `inspect`. Use direct imports of
    PyYAML, `load_rules`, and `audit_text`. Keep user-facing wrapping only around
    rule-file loading, audit execution, and metadata parsing. Do not catch import
    or internal programming errors broadly.
19. `cli.py:204-212`. If the first token is not `check`, `profile`, or `eval` and
    does not start with `-`, print
    `error: unknown command '<token>'; expected one of: check, profile, eval` and
    return 1. Flat eval options and `--help` keep their current behavior. Tests pin
    the message, exit code, flat invocation, and all three subcommands.
20. `corpus.py:224-228`. Use destination-directory `mkstemp`, flush and close the
    temporary file, then `os.replace` for JSONL writes. Remove the temporary file
    on failure. Tests cover successful replacement and write failure cleanup.
21. `report_markdown.py:90`. Render `unknown` only when the rules version is
    `None`; preserve numeric zero and empty string verbatim. Test all three values
    with a version-less YAML case.
22. `profile_io.list_profiles` gains an optional keyword-only `on_skip` callback
    that receives the profile path and error text. It remains silent when the
    callback is absent. `cli_profile.py` supplies a callback that prints one stderr
    note for each unreadable, invalid-UTF-8, or malformed profile directory. Tests
    cover silent library use and CLI stderr output.
23. `preservation.py`. Validate source and revised record collections before
    constructing ID maps. In both collections, every record must have a nonempty
    string `id`, a string `text`, and a unique ID. Raise `ValueError` that names
    the collection and record index or duplicate ID. Tests cover duplicate source
    and revised IDs, missing fields, empty IDs, and wrong field types.
24. `benchmark/codex_runner.py:29-72`, `benchmark/generate_runs.py`, and
    `generation_runner.py`. Add `--timeout` in seconds with default `600.0`, require
    a finite value greater than zero, and pass it to `subprocess.run`. A timeout is
    retried under the existing two-attempt policy and produces per-record
    diagnostics with `failure_kind: timeout`, `returncode: null`, and captured
    stdout/stderr when available. Nonzero exit and successful exit with empty
    output use `failure_kind: nonzero_exit` and `failure_kind: empty_output`.
    Final stderr messages name the failure kind. `FileNotFoundError` for the Codex
    executable and `OSError` or `UnicodeDecodeError` while reading an existing
    last-message file become immediate `UsageError` messages without a traceback.
    A missing or whitespace-only last-message file after exit 0 is the per-record
    `empty_output` failure above. Tests use the existing fake-Codex harness for
    timeout, nonzero exit, empty output, unreadable last-message output, and a
    missing executable.
25. `generation_runner.py` validates arguments before loading inputs: reject
    `--source` in generate mode, require `--source` in revise mode, require
    nonnegative `--max-records` and `--sleep`, and require finite positive
    `--timeout`. Add generate and revise tests. Resume-mode `meta.json` shape drift
    (`revision_iterations` and `residual_findings` omitted for resumed IDs) remains
    explicitly deferred while Codex is under evaluation.

## Phase 5: Decision gate hardening

26. `src/writing_eval/comparison_gate.py:93-94`. Criterion 2 is `fail` when
    `combined_word_count == 0`; degenerate input cannot vacuously pass. Preserve
    the measured tell rate and word count fields. Add a zero-word regression.
27. `comparison_gate.py:164-170`. Preserve verdict vocabulary and use this exact
    precedence: any criterion with status `fail` gives verdict `insufficient`;
    otherwise any `blocked` gives `blocked`; otherwise all criteria are `pass` and
    the verdict is `sufficient`. Do not add an `inconclusive` verdict. Keep the
    existing blocked test and add a fixture containing both a failure and a blocked
    criterion to prove failure precedence.

## Phase 6: Benchmark CLI deduplication

28. Move `_load_jsonl` from `cli.py` and the equivalent `UserError`, `Parser`,
    `_load_json`, and `_write_text` helpers from `benchmark/decision_gate.py`,
    `benchmark/noise_floor.py`, and `benchmark/compare_systems.py` into
    `writing_eval.cli_support`. The four modules import the shared helpers. Preserve
    exact messages, deterministic writes, and product versus benchmark exit codes
    (`writing-eval` uses 1; benchmark wrappers use 2). Shared readers convert
    `UnicodeDecodeError` to the same `could not decode ... as UTF-8` form.
29. Add `tests/test_benchmark_cli.py` with happy-path, malformed JSON,
    invalid-UTF-8, missing-file, and unwritable-output subprocess cases for all
    three wrappers, following the `helpers_corpus` subprocess pattern. Pin exit 2
    and stderr messages.

## Phase 7: Performance and code deduplication

30. `style_audit_engine.py`. Precompute newline offsets once per `audit_text` call
    and use `bisect_right` to calculate finding line numbers. Exception contexts
    remain candidate-owned slices from Phase 2 and do not use line-boundary
    searches. Add equality tests for findings at the first line, after one newline,
    and after multiple newlines.
31. `metrics_structure.py`. Add
    `sentence_length_stats(text) -> tuple[float, float]`, returning mean and
    population variance from one `segment()` pass. Existing
    `mean_sentence_length` and `sentence_length_variance` keep their signatures and
    delegate to it. Joint callers (`cli_check._check_result`,
    `profile_analysis.profile_statistics`, `profile_analysis.build_style_gap`, and
    `report_data.build_report`) call the tuple API once while preserving metric
    field order.
32. `metrics_quality.py`. Add
    `readability_scores(text) -> tuple[float | None, float | None]`, returning
    reading ease and grade from one tokenize plus segment pass. Existing public
    single-score functions keep their signatures and delegate. Update the same
    joint callers once per text.
33. `report_data.py`. Build `Counter` objects for output tokens and reference
    tokens once, then call `token_1gram_l2_from_counts` and
    `top_overrepresented_from_counts`. Reuse the output token count for
    `word_count`. Preserve sorted-vocabulary summation and byte-identical JSON and
    Markdown output.
34. `metrics_distribution.py`. Add an optional `exclude: Collection[str] | None`
    parameter to `normalized_from_counts` and
    `top_overrepresented_from_counts`. Filtering occurs before the normalization
    denominator is calculated. `profile_analysis._top_overrepresented_content`
    delegates with `_STOPWORDS` and the already computed draft counts, removing
    duplicate tokenization and copied ranking logic. `_STOPWORDS` remains importable
    from `writing_eval.profiles`.
35. `segmentation.py` exposes `LIST_MARKER_RE`; `style_audit_detectors.py` imports
    it for list-item detection. Remove `opener is None` branches only inside loops
    over `segment()` output, whose contract guarantees a letter-led opener. Replace
    the duplicated `run_count >= 2` end flush in `detect_negative_listing` with one
    sentinel span. Existing finding spans and ordering must remain byte-identical.
36. `metrics.py` stops importing private `_count_syllables`.
    `tests/test_quality_metrics.py` imports it directly from
    `writing_eval.metrics_quality`. Public `__all__` remains unchanged.
37. Test hygiene: add a `stdin` parameter to `helpers_cli.run_cli` and reuse it from
    `test_check.py` and `helpers_profiles.py`; remove dead imports in
    `tests/test_profiles_cli.py` and `tests/test_profiles_build.py`; add a test for
    the `could not write` `--json` branch. Do not combine unrelated formatting.

## Phase 8: Documentation

38. `skills/writing-eval/SKILL.md:22,85-87,172-174`. Replace the fictional
    `rules/style-audit-v3.yaml` and `style-audit-v1.yaml` references with the
    in-package builtin rule set (`src/writing_eval/rules/style-audit.yaml`, the
    current default for both `check` and benchmark evaluation). Keep the guidance
    not to change rules during one comparison. State that rule fingerprints, not
    fictional filenames, identify comparable runs.
39. `AGENTS.md:53,55`. Describe `benchmark/THRESHOLDS.md` and
    `benchmark/SAMPLES.md` as sealed historical provenance records, matching
    `benchmark/README.md`, and correct the `reports/` claim to git-ignored local
    outputs.
40. Apply the README updates from Phases 2 and 3: syllable wording, exception scope,
    passive-voice precision limit, profile metric-version rebuilds, and cache code
    invalidation. `benchmark/README.md` documents `--timeout 600`, positive-value
    validation, timeout retry behavior, and the new diagnostic `failure_kind`
    values.
41. Leave `benchmark/THRESHOLDS.md`, `benchmark/SAMPLES.md`, frozen generation
    configuration, official reports, noise-floor files, and recorded verdicts
    untouched. These are the actual sealed records; there is no `benchmark/docs/`
    target.

## Verification

Reproduce each bug with its focused regression before the source fix, then run the
same test after the fix.

- Phase 1:
  `uv run pytest -q tests/test_assessment_scoring.py tests/test_profiles_cli.py`.
- Phase 2:
  `uv run pytest -q tests/test_style_audit.py tests/test_style_audit_rules_content.py tests/test_quality_metrics.py`.
- Phase 3:
  `uv run pytest -q tests/test_profile_cache.py tests/test_profiles_build.py tests/test_profiles_cli.py`.
- Phase 4:
  `uv run pytest -q tests/test_check.py tests/test_corpus_cli.py tests/test_corpus_manifest.py tests/test_corpus_outputs.py tests/test_generate_runs_generate.py tests/test_generate_runs_revise.py tests/test_profiles_cli.py`.
- Phases 5 and 6:
  `uv run pytest -q tests/test_comparison_gate.py tests/test_benchmark_cli.py`.
- Phase 7:
  `uv run pytest -q tests/test_metrics.py tests/test_quality_metrics.py tests/test_style_audit.py tests/test_report.py tests/test_profiles_analysis.py`.
- Full run: `uv run pytest -q`.
- Corpus path: `scripts/dry_run.sh` and
  `uv run python scripts/run_eval.py --outputs tests/fixtures/sample_outputs --references tests/fixtures/references.sample.jsonl --report /tmp/writing-eval-report.md`.
- Direct CLI smoke tests cover `check` with a UTF-8 stdin stream, unknown-command
  handling, profile listing with one corrupt profile, and generation argument
  validation without invoking the network.
- `bash -n scripts/dry_run.sh` followed by `scripts/dry_run.sh`.
- Because `cli.py` and the installed command behavior change, run `uv build`, install
  or invoke the built artifact in an isolated environment, and confirm the running
  `writing-eval` command comes from that artifact before testing `--help`, an
  unknown command, and one successful `check` invocation.
- Compare representative report JSON and Markdown before and after Phase 7 to prove
  byte-identical output outside the intentional metric changes from Phase 2.

## Decisions recorded during planning

- The Codex generation subsystem is kept while the owner evaluates it. Only its
  verified hardening issues are fixed. Resume metadata shape drift is deferred.
- Benchmark wrapper exit codes stay 2. Product CLI user errors stay 1.
- Decision-gate hardening is approved: a zero-word criterion 2 fails, and a failing
  criterion produces `insufficient` even when another criterion is blocked.
- Verdict strings remain `sufficient`, `insufficient`, and `blocked`.
- Historical benchmark records are not rewritten. Future runs must record changed
  rule fingerprints and metric versions before claiming comparability.
- The metric-version cutover is clean. Existing profiles must be rebuilt; no legacy
  compatibility alias or silent fallback is added.
