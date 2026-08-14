# Writing Eval Repository Instructions

<task>
Maintain a deterministic, local Python tool for writing analysis. Make the smallest complete change that satisfies the user's request. Preserve public CLI behavior, JSON schemas, report determinism, and benchmark provenance unless the task explicitly changes one of those contracts.
</task>

<instruction_priority>
Apply instructions in this order:

1. The user's stated task and acceptance criteria.
2. The behavioral and data contracts in this file.
3. The documented public interface in `README.md`.
4. Existing tests and implementation details.

Use current code and focused tests to resolve internal details. Historical benchmark planning and status notes are not an active backlog and do not override the current CLI, tests, or user request.
</instruction_priority>

<default_follow_through_policy>
- Default to a reasonable low-risk interpretation and continue without asking routine questions.
- Ask only when missing information changes correctness, data safety, benchmark validity, or an irreversible action.
- Inspect the relevant implementation, tests, and documented interface before editing.
- Complete implementation, caller migration, tests, documentation, and verification in the same task.
- Do not stop at a plan, partial fix, plausible explanation, or passing focused test.
</default_follow_through_policy>

<repository_map>
## Runtime and entry points

- Python 3.11 or newer, managed with `uv`.
- `writing-eval` and `src/writing_eval/cli.py` expose the command-line interface.
- `scripts/run_eval.py` is the corpus evaluation wrapper. `scripts/` holds only this file and `dry_run.sh` (the product-facing corpus path).
- `scripts/dry_run.sh` exercises the bundled end-to-end sample.
- `benchmark/` is the closed internal benchmark harness, including its scripts, frozen `eval-config.json`, and provenance records. See `benchmark/README.md`.

## Core package

- `cli_check.py`, `cli_check_render.py`, `cli_profile.py`, and `cli_eval.py` implement command families. Keep `cli.py` as the thin dispatcher and shared CLI boundary.
- `style_audit*.py` contains rule models, loading, detection, and audit execution. `style_audit_paths.py` holds `BUILTIN_RULES_PATH`, the one default rule-set path every entry point uses. `style_audit_overlay.py` resolves `extends` overlay chains into one merged raw rule list before validation.
- `metrics*.py` and `segmentation.py` contain deterministic text measurements.
- `assessment*.py` builds and renders single-document assessments.
- `profile*.py` and `profiles.py` manage local style profiles.
- `report*.py` builds deterministic corpus report data and Markdown.
- `comparison*.py` implements system comparison, noise floors, and the decision gate.
- `generation*.py` implements generation input, prompting, and run orchestration; `benchmark/codex_runner.py` holds the Codex provider subprocess.
- Small modules such as `style_audit.py`, `metrics.py`, `assessment.py`, `comparison.py`, `profiles.py`, and `report.py` are public facades. Keep logic in the focused implementation modules instead of growing the facades.

## Data, rules, and records

- `tests/` contains behavior-focused pytest coverage.
- `src/writing_eval/rules/style-audit.yaml` is the single builtin rule set, shipped inside the installed package. Users add, override, or disable rules with an `extends` overlay file passed to `--rules` instead of forking this file.
- `rules/anti-ai.yaml` is the optional repository-level overlay (`extends: builtin`) that appends four AI-tell rules and widens six builtin ones for opt-in single-draft checks. It never ships inside the package and is never a default; corpus evaluation and benchmark runs keep the builtin rules.
- `tests/fixtures/` contains small, nonconfidential, deterministic test inputs.
- `benchmark/eval-config.json` holds three frozen-decoding fields (model, reasoning_effort, system_prompt) read by `benchmark/generate_runs.py`; every other field in it is unread.
- `benchmark/THRESHOLDS.md` and `benchmark/SAMPLES.md` are sealed historical provenance records, matching `benchmark/README.md`. They record how the closed experiment was run and do not define live tool behavior.
- `docs/profile-size-study.md` records the measurement behind the corpus-size recommendation in `README.md`. Unlike the benchmark records, it is live documentation: update it when the measurement changes.
- `docs/profile_size_study.py` reproduces all three experiments in that document from a built profile's `references.jsonl`. Every published table must reproduce from `--references` alone. Changing the script's defaults, sampling, or seed invalidates the published tables, so re-verify all three before committing such a change.
- `docs/banner.png` is the README banner image.
- Style-profile corpus sizing comes from `docs/profile-size-study.md`. The sample-count and word-count language in `benchmark/SAMPLES.md` describes the closed benchmark's reference corpus and does not govern style-profile sizing.
- `data/` and `runs/` hold local corpora and generated runs. Most content in these paths is intentionally git-ignored.
- `reports/` holds benchmark outputs as git-ignored local files.
</repository_map>

<engineering_contract>
## Design

- Prefer the standard library. PyYAML is the only runtime dependency. Add a dependency only when the requested behavior cannot be implemented cleanly without it.
- Keep evaluation CPU-only, local, and deterministic unless the user explicitly approves a broader architecture.
- Preserve stable ordering in findings, rankings, JSON, and Markdown.
- Keep public facades small. Reuse the existing module boundary instead of creating a second convention.
- Use immutable dataclasses where they fit the existing model layer.
- Avoid avoidable allocations, repeated tokenization, repeated file reads, and whole-corpus copies.

## Python

- Use four-space indentation, type hints, short module docstrings, and existing naming conventions.
- Use `snake_case` for functions and variables, `PascalCase` for classes, and a leading underscore for private symbols.
- Handle malformed input at the boundary and return clear user-facing errors. Do not hide internal programming errors with broad catch-all fallbacks.
- No formatter or linter is configured. Match nearby code and avoid unrelated reformatting.

## Change discipline

- Fix the source of a defect. Do not special-case one fixture or suppress the visible symptom.
- Before changing a public symbol, schema field, CLI option, or report field, find and migrate every caller and test.
- Remove obsolete paths after migration. Do not leave compatibility aliases or parallel implementations unless the user requires compatibility.
- Keep changes scoped. Do not combine the task with unrelated refactors, renames, or cleanup.
- Do not add placeholders, stubs, silent fallbacks, or deferred `TODO` work.
</engineering_contract>

<data_and_benchmark_contract>
## JSONL and fixtures

- Store one JSON object per line.
- IDs must be nonempty, stable, and unique within each file.
- Corpora compared as multiple output systems must use the same prompt ID set.
- Keep fixtures small and deterministic. Do not place secrets, private prose, or confidential source text in fixtures.
- Keep real prose and generated runs in the intended git-ignored `data/` and `runs/` paths.

## Benchmark integrity

- Do not edit thresholds, noise floors, frozen configuration, official reports, or recorded verdicts as incidental cleanup.
- Never choose or revise a threshold after viewing the result it will judge.
- A corpus, metric, rule-set, or frozen generation-config change can invalidate existing comparability and noise floors. Read `benchmark/THRESHOLDS.md` and preserve its required registration order before generation.
- Reports and decision gates must expose degenerate or missing data. Do not convert `None`, missing IDs, short outputs, or malformed records into passing values.
</data_and_benchmark_contract>

<implementation_workflow>
1. Restate the observable contract from the request.
2. Read the relevant implementation section, its focused tests, and the matching `README.md` section.
3. For a bug, add or identify a focused regression test that fails for the reported behavior.
4. Implement the smallest source-level fix and migrate all affected callers.
5. Update tests for changed observable behavior, not implementation details.
6. Update `README.md` when commands, options, schemas, or user-visible output change. Update benchmark documents only when the task changes their recorded contract.
7. Run focused verification, then the required broader checks.
8. Review the final result against the request. Remove temporary artifacts and obsolete code.
</implementation_workflow>

<verification_loop>
Run commands from the repository root so fixture, rule, and configuration paths resolve correctly.

## Required checks by change type

- Focused Python change: `uv run pytest -q tests/test_<relevant_area>.py`
- Any completed code change: `uv run pytest -q`
- Corpus evaluation, report, metric, or fixture change: `scripts/dry_run.sh`
- Direct corpus CLI smoke test:
  `uv run python scripts/run_eval.py --outputs tests/fixtures/sample_outputs --references tests/fixtures/references.sample.jsonl --report /tmp/writing-eval-report.md`
- Shell script change: `bash -n <script>` followed by execution of the changed path when safe.
- Packaging or entry-point change: `uv build` and an invocation that uses the built or installed artifact.
- Documentation-only change: verify paths, commands, and claims against the repository. Do not run pytest only to validate prose.

For a bug fix, reproduce the failure before the fix and confirm the same path no longer fails. If a check fails, fix the cause and rerun that check. Do not report broader coverage than the commands actually exercised.
</verification_loop>

<writing_and_output_contract>
- Use plain technical English and concise imperative wording.
- Do not introduce literal em dash or en dash characters in code, documentation, rules, or fixtures. Tests for those characters should construct them with code points.
- Keep comments focused on invariants or non-obvious constraints.
- In the final response, state the changed files, the observable result, and the exact verification commands and outcomes.
- Label unverified claims or remaining external blockers explicitly. Do not claim completion while actionable work remains.
</writing_and_output_contract>

<action_safety>
Keep changes local and reversible. Do not delete user data, rewrite benchmark history, publish artifacts, change frozen experimental inputs, or make network calls unless the task explicitly requires that action.
</action_safety>
