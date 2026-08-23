#!/usr/bin/env bash
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/writing-eval-dry-run.XXXXXX")" || {
  printf 'Failure: could not create a temporary report directory.\n' >&2
  exit 1
}
REPORT_PATH="${REPORT_DIR}/writing-eval-report.md"

cleanup() {
  rm -rf "$REPORT_DIR"
}
trap cleanup EXIT

cd "$PROJECT_ROOT" || {
  printf 'Failure: could not enter project root: %s\n' "$PROJECT_ROOT" >&2
  exit 1
}

if ! uv run python scripts/run_eval.py --outputs tests/fixtures/sample_outputs --references tests/fixtures/references.sample.jsonl --report "$REPORT_PATH"; then
  printf 'Failure: evaluation command failed.\n' >&2
  exit 1
fi

if [[ ! -s "$REPORT_PATH" ]]; then
  printf 'Failure: report was not created or is empty: %s\n' "$REPORT_PATH" >&2
  exit 1
fi

assert_contains() {
  needle="$1"
  if ! grep -F -q -- "$needle" "$REPORT_PATH"; then
    printf 'Failure: report missing expected text: %s\n' "$needle" >&2
    exit 1
  fi
}

assert_contains '# Writing Evaluation Report'
assert_contains '## Provenance'
assert_contains '### Reference Corpus'
assert_contains '### Rule Set'
assert_contains '- SHA-256: '
assert_contains '- Fingerprint: '

printf 'Success: writing evaluation report created at %s\n' "$REPORT_PATH"
