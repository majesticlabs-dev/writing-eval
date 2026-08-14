# Closed internal benchmark

This directory reproduces a closed internal benchmark experiment. It is not
required to use the `writing-eval` linter.

Product-facing entry points stay outside this directory: the main CLI at the
repository root (`writing-eval`) and the corpus wrapper `scripts/run_eval.py`.
`scripts/dry_run.sh` exercises the bundled sample end to end.

`generate_runs.py` uses the external OpenAI Codex CLI to generate benchmark
responses and run style-audit revision passes. These operations require an
authenticated Codex installation, the git-ignored `data/` corpus, and the three
frozen-decoding fields read from `eval-config.json`. Use `--codex-cmd` to select
a Codex executable other than `codex`. Each Codex call runs under `--timeout`
(default 600 seconds; the value must be finite and greater than zero). A timed
out call is retried once under the same policy as other failures and, when it
fails, records per-record diagnostics with `failure_kind: timeout`; non-zero
exits and empty last-message output record `failure_kind: nonzero_exit` and
`failure_kind: empty_output`.

Codex is not required for the other benchmark scripts when their input corpora
already exist. `THRESHOLDS.md` preserves the pre-registered decision criteria
and noise-floor provenance. `SAMPLES.md` preserves corpus selection and split
provenance.
