#!/usr/bin/env bash
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="/tmp/writing-eval-report.md"

cd "$PROJECT_ROOT" || {
  printf 'Failure: could not enter project root: %s\n' "$PROJECT_ROOT" >&2
  exit 1
}

rm -f "$REPORT_PATH"

if ! uv run python scripts/run_eval.py --outputs tests/fixtures/sample_outputs --references tests/fixtures/references.sample.jsonl --report /tmp/writing-eval-report.md; then
  printf 'Failure: evaluation command failed.\n' >&2
  exit 1
fi

if [[ ! -s "$REPORT_PATH" ]]; then
  printf 'Failure: report was not created or is empty: %s\n' "$REPORT_PATH" >&2
  exit 1
fi

printf 'Success: writing evaluation report created at %s\n' "$REPORT_PATH"
