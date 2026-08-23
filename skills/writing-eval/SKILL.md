---
name: writing-eval
description: "Use the local writing-eval CLI to audit Markdown or plain-text drafts, compare writing with a named style profile, build profiles from authorized prose, produce JSON assessments, and compare output corpora. Use when a user asks to check writing style, match an editorial voice, find AI writing tendencies, score a draft, build or update a style profile, compare generated writing systems, or run a repeatable writing regression check."
license: Elastic-2.0
metadata:
  author: Majestic Labs
  version: "0.1.0"
---

# Writing Eval

Use `writing-eval` as the evidence source for writing analysis. It is a local,
CPU-only, deterministic CLI. It does not call a hosted model or upload the text.
It requires a local repository checkout, Python 3.11 or newer, and uv.

## Locate the tool

Run commands from the repository root. The root contains all of these paths:

- `writing-eval`
- `pyproject.toml`
- `src/writing_eval/rules/style-audit.yaml` (the builtin rule set)
- `rules/anti-ai.yaml` (optional overlay with extra AI-writing tells)

Use `./writing-eval` in commands below. If the checkout is missing, do not invent
results or silently substitute another writing tool. Tell the user that this
skill requires the repository and give these setup commands:

```bash
git clone https://github.com/majesticlabs-dev/writing-eval.git
cd writing-eval
uv sync
```

Do not clone or install software without the user's approval.

## Choose the workflow

| User request | Workflow |
|---|---|
| Audit, review, lint, or score one draft | Single-draft check |
| Compare a draft with an author or editorial voice | Profile check |
| Create or refresh an editorial baseline | Build a profile |
| Compare models, prompts, or writing systems | Corpus evaluation |
| Consume results in automation | JSON output |
| Rewrite or fix a draft | Check, edit, and recheck |

Do not use corpus evaluation when the user only needs one document checked. Do
not build a profile when the user has not identified an authorized source
corpus.

## Single-draft check

Check Markdown or plain text with the default review rules:

```bash
./writing-eval check path/to/draft.md
```

Read from standard input when no file should be created:

```bash
cat path/to/draft.md | ./writing-eval check -
```

Use a reference JSONL corpus only when the user explicitly wants distributional
comparison without a named profile:

```bash
./writing-eval check path/to/draft.md \
  --references path/to/references.jsonl
```

For reliable machine parsing, request JSON instead of parsing the human report:

```bash
./writing-eval check path/to/draft.md --format json
```

To keep the human report on standard output and also write JSON:

```bash
./writing-eval check path/to/draft.md --json /tmp/writing-eval-result.json
```

The default rules are the builtin rule set shipped inside the package
(`src/writing_eval/rules/style-audit.yaml`). Do not select another rule set
unless the user requests it or the existing project workflow requires it.

One repository-provided option is the anti-ai overlay. When the user asks to
find AI-writing tendencies, review machine-assisted copy, or wants stricter
tell coverage, add it on top of the default rules:

```bash
./writing-eval check path/to/draft.md --rules rules/anti-ai.yaml
```

The overlay keeps the builtin rules and appends four more (`narrative_cliches`
for stock phrases, `significance_markers` for meta commentary that labels a
moment, `generation_artifacts` for bracketed scaffolding tokens (`insert`,
`todo`, `tbd`, `placeholder`, `xxx`) plus chatgpt.com tracking links,
`connector_openers` for sentence-initial furthermore, moreover, additionally)
while widening six builtin rules. Output format and exit codes are unchanged,
and it combines with `--style` and `--format json`. Use it for single-draft
checks only: keep the builtin rules for corpus evaluation, because rule
fingerprints identify comparable runs.

## Profile check

List available profiles before choosing one when the user did not name it:

```bash
./writing-eval profile list
```

The list includes only profiles that load successfully. Skipped directories
are reported on stderr.

If exactly one relevant profile exists, use it. If several profiles represent
materially different authors, brands, or registers, ask the user which one to
use.

Run the check:

```bash
./writing-eval check path/to/draft.md --style PROFILE_NAME
```

Use `--profiles-root PATH` only when the profiles are outside the default
`data/profiles` directory.

`--style` and `--references` are mutually exclusive. Never pass both.

A profile check returns a heuristic alignment assessment. Report:

1. Whether the assessment is scored or unscored.
2. The total score and label when scored.
3. Section scores.
4. Improvement issues in priority order, with deductions and source locations.
5. Review candidates separately from scored issues.
6. Relevant current and target measurements.

Do not describe the score as overall writing quality. It measures detected style
patterns and alignment with the selected profile. It does not establish factual
accuracy, originality, argument strength, or reader preference.

## Build or update a profile

Build a profile from local `.md` and `.txt` files:

```bash
./writing-eval profile build PROFILE_NAME --from path/to/prose [--rules PATH]
```

Directories are scanned recursively. Selected files can also be listed after
`--from`. `--rules` selects the rule file used to precompute the profile
cache (default: the builtin rule set).

Before building:

- Confirm that the user is permitted to process the source prose.
- Keep private or third-party prose under the git-ignored `data/` tree.
- Prefer prose from one author, genre, and register.
- Explain that 25 articles is a measured minimum and 40 or more is the
  preferred target, not a strict requirement, and that article count matters
  more than total word count. Below about 25 articles the score depends
  noticeably on which articles were included; 25 covers 7 in 10 drafts tested,
  40 covers 9 in 10. Treat a score difference under 3 points as noise. See
  `docs/profile-size-study.md`.

Rebuilding a profile replaces it. There is no append operation. Always pass the
complete authoritative corpus when updating an existing profile. Never rebuild
from only the new file unless the user intends to replace the profile with that
file.

After building, report the profile name, source count, word count, and output
path exactly as the command reports them.

## Refresh a profile cache

After a rule change, refresh the precomputed reference cache without
rebuilding the profile:

```bash
./writing-eval profile cache PROFILE_NAME
./writing-eval profile cache PROFILE_NAME --rules rules/anti-ai.yaml
```

`--rules` must match the rule file that later `check` runs will use. Use
`--profiles-root PATH` when the profile is not under `data/profiles`.

## Corpus evaluation

Use corpus evaluation only for multiple output systems represented as JSONL:

```bash
./writing-eval eval \
  --outputs path/to/output-directory \
  --references path/to/references.jsonl \
  --report path/to/report.md \
  --json path/to/report.json
```

Input requirements:

- Each JSONL line is one object.
- Every record has a nonempty, stable `id` and nonempty `text`.
- IDs are unique within each file.
- Every output file has the same prompt ID set.
- The output directory contains one `.jsonl` file per system.

Corpus evaluation uses the same builtin rule set by default. Rule fingerprints,
not rule filenames, identify comparable runs. Do not switch rules, thresholds,
noise floors, fixtures, or frozen configuration as part of a routine
evaluation.

Summarize the generated report and preserve its provenance, missing data,
degenerate results, and decision-gate verdict. Never convert missing or
inconclusive data into a pass.

## Check, edit, and recheck

When the user asks to improve or fix a draft:

1. Run the relevant check before editing.
2. Read the issue instruction, success criteria, current value, target value,
   and source locations.
3. Edit the source of the issue while preserving facts, citations, literals,
   intent, and deliberate voice.
4. Do not mechanically force every metric to the profile mean.
5. Run the same command again.
6. Report the before and after evidence.

Do not rewrite a file when the user asked only for analysis. Do not change a
profile, rule file, threshold, or benchmark input to make a draft pass.

## Interpret exit codes

The check command uses these exit codes:

- `0`: the check completed. Warn and info findings can still be present.
- `1`: usage or input error.

Always inspect the completed report. For exit code `1`, fix the path or input
when the answer is available from the repository. Otherwise, report the exact
error.

## Privacy and integrity

- Keep drafts, reference corpora, profiles, and generated reports local unless
  the user explicitly asks to publish them.
- Never commit private profiles or third-party prose.
- Never quote private source prose at length in the response.
- Do not claim that deterministic means unbiased or universally correct.
- Treat findings as review evidence, not universal writing errors.
- Keep raw JSON precision when another tool will consume the result.
- Preserve stable ordering and provenance in reports.

## Response format

Lead with the result. Then provide the strongest evidence and the next concrete
action.

For a draft check, use this compact structure:

```text
Result: SCORE/LABEL or unscored

Main issues:
1. ISSUE, current VALUE, target VALUE, location LINE:COLUMN
2. ISSUE, current VALUE, target VALUE, location LINE:COLUMN

Review candidates:
- ITEM

Next action: SPECIFIC EDIT OR DECISION
```

Omit empty sections. When no profile is used, report findings and metrics without
inventing a score. Name the profile in your response only when it helps the user,
even though the human CLI report intentionally labels it as `Target profile`.
