---
shaping: true
---

# Optional Jev voice assessment

Status: implementation plan. No product code changed.
Base: `74dcd16`, from the current `feature/jev` checkout.

## Scope

Implement J3 only: compare a draft with the target profile's reference prose for tone, directness, and reader address. The calling LLM writes, revises, and decides when to stop. writing-eval returns measurements and typed feedback. Each call evaluates the current draft independently.

The user specified: "The Jev usage should be optional." The user also specified: "the writer should be responsible to verify it preserve the meaning."

Meaning preservation (J1), brief coverage (J2), and claim support (J4) are excluded. No revision history, rewrite loop, human approval step, corpus evaluation changes, or benchmark changes are included.

## Requirements and fit

Shape A adds an optional provider call after the existing profile assessment. All choices below are proposed implementation defaults.

| ID | Requirement | Status | A |
|---|---|---|---|
| R1 | Without explicit opt-in, preserve local execution, output, scores, and exit codes. | Required | Pass |
| R2 | Use existing style profiles and their reference prose without rebuilding profiles. | Required | Pass |
| R3 | Assess tone, directness, and reader address relative to the target voice. | Required | Pass |
| R4 | Return separate structured feedback that the calling LLM can use without a person. | Required | Pass |
| R5 | Keep reference selection stable across revisions of the same draft. | Required | Pass |
| R6 | Expose missing evidence and provider failure without presenting them as success. | Required | Pass |
| R7 | Record the model, rubric, reference selection, and input identities. | Required | Pass |
| R8 | Verify the integration and measure its usefulness separately. | Required | Pass |

These are design fits, not completed acceptance checks. Jev's usefulness for this task remains unverified.

## A1: Command and configuration

```bash
./writing-eval check draft.md --style acme --jev --format json
./writing-eval check draft.md --style acme --jev --json /tmp/voice-result.json
```

- `--jev` enables the hosted call for this invocation only. It requires `--style`. Keep `--references` support outside this first implementation.
- Read `TYPESAFE_API_KEY` only when enabled. Do not infer opt-in from an environment variable or an installed dependency.
- Add `--jev-model`, defaulting to the versioned ID `jev-1.13.0`, and `--jev-timeout`, defaulting to 30 seconds. Reject these options without `--jev`. Validate a finite, positive timeout. Require a versioned model ID rather than a moving alias.
- Use the TypeSafe HTTP API at `https://api.typesafe.ai/v1/systemone`, with bearer authentication. Use standard-library HTTP and JSON support; no runtime dependency or general provider framework is needed. The endpoint and response contract are documented in the [API reference](https://docs.typesafe.ai/api).
- Make one request containing the independent questions. Do not retry automatically in the first implementation. The caller controls retry policy and cost.
- Use normal TLS verification, refuse redirects, and keep credentials and provider response bodies out of error messages.

The default model is listed in the live [model documentation](https://docs.typesafe.ai/models). Recheck availability at implementation time. An unavailable pinned model must produce an explicit error, not silently move to another model. Account access has not been checked and no authenticated call was made during planning.

## A2: Reference input

`profile.json` stores numeric statistics. The paired `references.jsonl` stores the prose that Jev needs. `load_profile` already validates the pair's digest. Reuse that validation and the existing JSONL loader. Leave profile files and their versions unchanged.

Use a small, versioned selection rule, `voice-excerpts-v1`:

1. Sort valid source records by stable ID. Select up to six evenly spaced records, including the first and last when at least two are selected. For N records and K selected records, use indices `floor(i * (N - 1) / (K - 1))`; select index zero when K is one.
2. For each selected source, use the existing sentence spans to collect opening, middle, and ending excerpts. Use up to 400 UTF-8 bytes per excerpt, at most 1,200 per source. Include complete sentence spans only, preserve source order, and remove duplicate spans.
3. For each position, start at the first, middle, or last sentence respectively. Extend with adjacent complete spans within the budget. Skip a span that cannot fit; do not split a character or silently clip a sentence. If a source has no eligible spans, record that omission. If no source yields prose, return `unscored` without a request.
4. Do not use draft vocabulary, topic similarity, Jev rankings, or the previous response to select references. The same profile must produce the same sample across revisions.
5. Record the corpus digest, selection version, source and excerpt counts, omitted source count, source IDs, original character offsets, and selected text. Sort the manifest by source ID and offset.

Send the full draft with the selected reference passages as separate named fields. Identify excerpts with neutral request IDs; keep the mapping to local source IDs in the result. Treat all prose as data, including embedded instructions. The rubric must explicitly ignore topic agreement, truth, and content completeness.

Cap the serialized request at 24,000 UTF-8 bytes, including rubric and JSON structure. If it exceeds that limit, return an explicit input error. Do not silently shorten the draft, resample the references, or claim a complete assessment of partial text. This is a conservative application limit, not an exact token count. Provider context-limit errors remain explicit failures.

Six sources and the excerpt budgets are provisional engineering limits. They do not establish that the sample represents the whole profile. Test sensitivity to the selected passages before claiming profile-wide voice accuracy. Do not apply the local profile-size study's conclusions to Jev.

## A3: Rubric and actionable output

Use `jev-voice-v1`, with three dimensions in a fixed order. Each dimension has one Score question for alignment and one Choice question for the direction of a difference. Ask all six questions in one request. Questions cannot depend on each other's answers.

| Dimension | Comparison | Directional Choice outcomes |
|---|---|---|
| `tone` | Register and emotional intensity relative to reference prose | `aligned`, `more_formal`, `more_casual`, `more_promotional`, `more_restrained`, `mixed`, `insufficient_evidence` |
| `directness` | How directly the draft states its points relative to reference prose | `aligned`, `more_indirect`, `more_abrupt`, `mixed`, `insufficient_evidence` |
| `reader_address` | How the draft addresses or includes the reader relative to reference prose | `aligned`, `more_distant`, `more_familiar`, `mixed`, `insufficient_evidence` |

Specify full definitions and counterexamples for these outcomes in the rubric. `mixed` includes competing differences or reference passages that do not establish one target. Do not equate directness with short sentences or assume that every profile should be informal and address the reader as "you".

Each Score uses three standalone descriptions: a sustained mismatch, a mixture of matching and differing passages, and alignment with the observed reference range. Customize the descriptions for each dimension. Keep raw scores on their documented 0 to 2 scale; do not add a combined voice total or convert them into deductions from the existing score. TypeSafe documents the [Score structure and descriptive criteria](https://docs.typesafe.ai/primitives/score).

Map specific Choice outcomes to fixed suggestions. For example, `more_formal` maps to "Use a less formal register consistent with the reference passages." `more_indirect` maps to "State the point earlier and reduce introductory framing to match the references."

Return the choice, all probabilities, provider confidence, and the suggestion as advisory evidence. No confidence cutoff creates a pass/fail or triggers an edit. For `aligned`, return no suggested change. For `mixed` or `insufficient_evidence`, return no instruction and a dimension status of `unscored`; keep the provider answer for inspection but expose the dimension score as null. If Score and Choice disagree about alignment, use `inconclusive` with a null score and instruction. Compare their most probable categories, treating a tie as inconclusive.

Jev does not generate explanations or rewrites. Use fixed messages and supplied reference excerpts. A document-level judgment must not invent an offending line or a quoted rationale. The report identifies these suggestions as document-level. This follows the [System One output contract](https://docs.typesafe.ai/concepts/system-one).

## A4: Report and error contract

Add one top-level `voice_assessment` object only when `--jev` is supplied. Preserve every existing result field and the existing assessment schema. The new object has its own `schema_version: 1`.

| Field | Meaning |
|---|---|
| `status` | `completed`, `unscored`, or `unavailable` |
| `provider`, `requested_model`, `returned_model` | Provider identity and the model requested and reported |
| `rubric_version`, `rubric_sha256`, `selection_version` | Exact comparison definitions |
| `draft_sha256`, `references_sha256`, `request_sha256` | Identity of the source inputs and canonical request |
| `reference_sample` | Selected prose, source IDs, offsets, and coverage counts |
| `dimensions` | Ordered scores, directions, statuses, probabilities, confidence, and fixed suggestions |
| `usage` | Provider token counts, or null if unavailable |
| `error` | Null or a stable error code and sanitized message |

For `completed`, at least one dimension is scored; individual dimensions can still be unscored or inconclusive. If no dimension is scorable, use top-level `unscored`. All three dimension IDs remain present, with null values where necessary. These statuses describe execution and evidence, not whether a draft is good.

Validate required answer IDs, types, expected Choice keys and Score levels, finite numeric values, probability bounds and sums, score ranges, and model identity. Reject missing or malformed responses as `unavailable`. Validate that each Score matches its probability-weighted levels within a documented numeric tolerance. Do not coerce booleans or strings into numbers.

| Condition | Result | Exit |
|---|---|---|
| Jev disabled | Existing report only; no provider configuration or network access | Existing behavior |
| Invalid flags, missing key, invalid profile, oversized request | Clear input error before a provider call | 1 |
| Draft has no scorable prose, or no usable reference excerpts | Local report plus `voice_assessment.status = unscored`; no request | 0 |
| Valid response, including mixed or insufficient evidence | Local report plus completed or unscored voice assessment | 0 |
| Timeout, transport failure, HTTP error, invalid provider response | Preserve the local report; add `unavailable` and an error code | 1 |

Render a separate "Voice assessment (Jev)" section in text output. `render_check_text` currently returns immediately when an assessment exists; append the new section after that render. Preserve JSON stdout and `--json` file parity, including unavailable results. Standard error can contain a short error summary, never credentials or source prose.

The calling LLM reads the deterministic assessment and voice dimensions, revises as it chooses, and calls the same command again. The tool does not accept or reject a revision, request human review, or decide when to stop.

Use existing `--json` persistence. Store the raw validated provider answers in the new object as `provider_answers`, including answers suppressed from actionable output. No automatic disk cache or additional profile files are needed. Saved results can be rendered repeatedly; fresh hosted calls are not promised to be deterministic. Compare runs only when model, rubric, and reference selection match.

## A5: Code changes and implementation order

| Order | Files | Observable completion |
|---|---|---|
| P1 | New `voice_references.py`, `voice_rubric.py`; focused tests | Stable bounded reference samples and a complete request can be built from an existing profile. |
| P2 | New `jev_client.py`, `voice_assessment.py`; focused tests | One provider request produces validated dimensions or an explicit unavailable result. |
| P3 | `cli_check.py`, `cli_check_render.py`, new `voice_render.py`; CLI tests | `check --style ... --jev` works for files and stdin, in text and JSON. Disabled output remains identical. |
| P4 | `README.md`, `skills/writing-eval/SKILL.md`, `AGENTS.md`; validation evidence | The automated writer can discover opt-in usage, interpret output and errors, and understand the hosted-data boundary. |

Keep each new production module below 200 lines. Keep HTTP transport in the provider adapter and preserve the current public facades. Reuse the existing serializers, profile loader, source spans, and user-error boundary. No edits are planned to deterministic metric or scoring code.

Update documentation claims that currently state all execution is local and deterministic. State that the default remains local and the optional command sends the draft and selected reference text to TypeSafe. Update the repository guidance for the explicitly optional exception. Do not change sealed benchmark records or add Jev to generation, corpus evaluation, or decision gates.

Implement in a separate worktree. After checks pass, review the diff, commit, push the feature branch, and open a draft PR under the existing implementation authorization. No merge or deployment is part of this plan.

## A6: Verification and evidence

Use small synthetic prose and fake provider responses in normal tests. Tests must not require credentials or make live calls.

| ID | Acceptance check |
|---|---|
| T1 | Disabled commands have byte-identical output and zero provider calls, even if credentials exist. Existing score arithmetic is unchanged. |
| T2 | A built profile works without migration. Selection stays identical across draft revisions and source-record order changes. Counts, byte limits, offsets, duplicates, Unicode, and unusable spans are correct. |
| T3 | A fake valid response produces separate dimension scores and directional suggestions in both formats. Specific mismatches, aligned, mixed, insufficient evidence, tied answers, and conflicting answers map correctly. |
| T4 | Missing credentials, invalid model or timeout options, no style, empty prose, malformed answers, non-finite numbers, HTTP failures, redirects, and timeouts follow the stated output and exit contract. No secret appears in output. |
| T5 | File input, stdin, custom profile roots, optional rule overlays, and JSON stdout/file parity work. An unavailable Jev result preserves the completed local assessment. |
| T6 | A synthetic live call proves authentication, the pinned model, response parsing, and report wiring. It does not establish editorial accuracy. |
| T7 | A fixed set of synthetic profiles and drafts tests each dimension independently, including different topics with matching voice, same-topic mismatches, and mixed references. Register expected directions before observing Jev outputs. Repeat calls to measure variation and record latency and token use. |

Run focused tests, then the full suite:

```bash
uv run pytest -q tests/test_voice_references.py tests/test_jev_client.py tests/test_voice_assessment.py tests/test_check_jev.py
uv run pytest -q tests/test_check.py tests/test_profiles_cli.py tests/test_assessment_scoring.py
uv run pytest -q
git diff --check
```

Run environment-dependent commands through `zsh -lc 'source ~/.zshrc && <command>'`, from the implementation worktree root. New test filenames above are planned files. The existing suite names were verified during planning.

For T6 and T7, use only authorized synthetic text, verify the intended TypeSafe account and endpoint, and require an available API key. Document an explicit live-test invocation in the new test module, excluded from ordinary pytest runs. Save raw results under the ignored `reports/` directory. Do not upload local author corpora as a smoke test. No live call is authorized by this planning task alone.

Assess usefulness separately from software correctness: report directional agreement, false mismatch reports, inconclusive counts, topic sensitivity, sample sensitivity, repeat variation, latency, and token use. These tests need no human step during normal operation. Do not choose acceptance thresholds after viewing the results or claim that integration tests prove voice accuracy.

## Result of planning

The implementation boundary is defined. The remaining empirical unknown is whether the chosen model and rubric produce useful voice feedback for the selected reference sample. No product code, scoring rules, profile files, or benchmark records have changed.
