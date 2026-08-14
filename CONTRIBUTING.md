# Contributing to writing-eval

Thank you for helping improve `writing-eval`. Contributions should preserve its
local, deterministic behavior and its stable CLI, JSON, report, and benchmark
contracts.

## Before you start

For a small fix, open a focused pull request. For a new command, schema change,
rule-family change, benchmark change, or large refactor, open an issue first so
we can agree on the observable contract.

Do not include private prose, customer data, secrets, generated run data, or
third-party text that you do not have permission to redistribute. Use small,
synthetic fixtures for tests.

## Development setup

Requirements:

- Python 3.11 or newer
- `uv`

Install dependencies and run the suite:

```bash
uv sync
uv run pytest -q
```

Run the bundled end-to-end sample for changes to corpus evaluation, reports,
metrics, or fixtures:

```bash
scripts/dry_run.sh
```

## Change requirements

- Make the smallest complete change that solves the problem.
- Keep evaluation CPU-only, local, deterministic, and stably ordered.
- Preserve public CLI behavior and JSON schemas unless the change explicitly
  updates those contracts.
- Keep the registered corpus benchmark pinned to the built-in rule content and
  preserve its provenance.
- Add behavior-focused tests for new observable behavior and regressions.
- Update `README.md` when commands, options, schemas, or user-visible output
  change.
- Do not change frozen thresholds, noise floors, fixtures, reports, or verdicts
  as incidental cleanup.
- Do not add private or confidential text to fixtures.

## Pull requests

A pull request should include:

1. The problem and observable result.
2. The files and public contracts changed.
3. The exact verification commands and outcomes.
4. Any benchmark or compatibility effect.

Keep unrelated refactors out of the pull request. Maintainers may ask you to
split a change when independent behavior is mixed together.

## Contributor License Agreement

Majestic Labs LLC operates the public project and may provide an official hosted
or managed service. To use the same contributions in both, every contributor
must accept the [Contributor License Agreement](CLA.md).

Check the CLA acceptance box in your pull request. By checking it and submitting
the pull request, you confirm that you have read and accepted the agreement and
have authority to grant its rights. If your employer or client may own your
work, obtain written permission before contributing.

## License

The public project is source available under the
[Elastic License 2.0](LICENSE). Contributions merged into the public project
remain available under the public license in effect on their submission date,
subject to the Contributor License Agreement.
