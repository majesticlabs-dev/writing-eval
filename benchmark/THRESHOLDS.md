Closed internal benchmark record. Some paths identify historical artifacts that no longer exist. It does not constrain current product behavior.

# Pre-registered acceptance thresholds

Registered 2026-07-17. Re-registered 2026-07-22 (corpus expansion): criterion 5
(length adequacy) was added, and the criterion 3 noise floor is re-measured on
the larger corpus per the original provenance rule. See "Re-registration
2026-07-22" below. Re-registered 2026-07-23 (frozen system prompt changed to fix
the recurring length collapse): all five criteria and their thresholds are
UNCHANGED, but every noise floor is void for future runs and is re-measured under
the new config before the official run. See "Re-registration 2026-07-23" below.

These thresholds are committed before any benchmark generation exists. The
2026-07-17 criteria (1 to 4 and the labeling rule) were fixed before the first
Phase 3 benchmark run and are unchanged in substance. The 2026-07-22 additions
(criterion 5, and the criterion 3 re-measurement slot) were committed before any
generation on the expanded corpus existed. Every numeric noise floor is measured,
not chosen.

## Criteria

Applied to the hermes-audited system over the current evaluation set. ALL of
criteria 1 to 5 must hold for the audit-plus-revision control to be judged
sufficient at the Phase 4 decision gate.

1. Hard findings: zero hard-severity findings across the entire evaluation set.
2. Tell rate: overall tell rate (all severities combined) at most 2.0 findings per 1,000 words, computed by the existing `tell_rate` metric over the whole set.
3. Voice distance: mean token 1-gram L2 of hermes-audited must not exceed that of hermes-current by more than the per-metric noise floor from item 2.4.
   - Slot (2026-07-23 config): noise floor = 0.00500314427711171. Filled by the item 2.4 re-measurement under the new frozen system prompt (see "Re-registration 2026-07-23" and "Measured noise floors (2026-07-23 config)" below), inserted before any official generation on this config existed, measured not chosen. It is the maximum cross-run spread of the mean per-record token 1-gram L2 (hermes-audited, whose per-run means ranged 0.068051 to 0.073054) across the five 2026-07-23 runs. It is roughly one-seventh of the 2026-07-22 slot value (0.034370): that prior floor was inflated by an 11-word length collapse in run-1, and under the new prompt the collapse is gone (per-run minimum record word counts 157, 177, 169, 170, 165), so criterion 3 is materially stricter under this config. This value is the number criterion 3 now uses; it is written to runs/refreeze-2026-07-23/noise-floor.refreeze.json under token_1gram_l2.floor. The 2026-07-22 value in the next paragraph is void for runs under the 2026-07-23 config and is retained only as history.
   - Slot (2026-07-22 corpus): noise floor = 0.034370360061. This value was inserted from the item 2.4 re-measurement on the expanded corpus (five hermes-current runs and five revision passes under the frozen decoding config), before the official benchmark runs, and is measured, not chosen. It is the maximum cross-run spread of the mean per-record token 1-gram L2 (hermes-audited, whose per-run means ranged 0.072007 to 0.106377). The floor is inflated by run-1, in which the hermes-current record sample-85e9c876d9d5 collapsed to 11 words (per-record L2 0.296927), lifting run-1's mean per-record L2 to about 0.106 against about 0.073 in runs 2 to 5. All five runs are retained because the item 2.4 procedure was pre-registered over five runs, so dropping a run would be an un-registered post-hoc adjustment; the consequence is a more lenient criterion 3. This slot supersedes the 2026-07-17 value 0.043794, which was measured on the provisional 13-sample corpus.
   - Metric definition, fixed 2026-07-17 and unchanged: "mean token 1-gram L2" means the mean of per-record L2 values, as the decision gate implements. The corpus-aggregate L2 reading of the same runs is reported alongside for context but is not the quantity criterion 3 tests.
   - Provenance: measured on the 2026-07-22 corpus (22 samples, 15 holdout, still below the documented minimum, see `benchmark/SAMPLES.md`), via the unchanged item 2.4 procedure. The 2026-07-17 registration required re-measuring this floor with the same procedure whenever the corpus changes, so this re-measurement is that pre-registered step, not a post-hoc adjustment.
   - Rationale: the revision pass must remove tells without drifting the voice further from the reference corpus.
4. Degenerate outputs: any record whose token 1-gram L2 is None (no tokens) is an automatic fail of the whole gate, regardless of other metrics.
5. Length adequacy (added 2026-07-22): every audited output record must have at least 50 words AND at least 30 percent of the word count of its corresponding eval-set reference text. The corresponding reference is the `eval_set.jsonl` sample, keyed by record id, whose title and target length generated the prompt. A record whose id is absent from the eval set is held to the 50-word floor only. Any record below its threshold is an automatic fail of the whole gate.
   - Justification: in the 2026-07-17 official run one exec_communication output collapsed to 18 words against a 373-word reference, yet passed every pre-registered criterion. Criterion 4 catches only empty (null-L2) outputs, and a terse record trivially carries zero style findings, so criteria 1 to 4 never test length. 18 words is 4.8 percent of that 373-word reference and far below any usable section length. The 50-word absolute floor rejects a degenerate stub regardless of reference length. The 30-percent-of-reference floor rejects an output that is grossly short for the length its prompt requested (18 of 373 words fails at the 111.9 words required). 30 percent is deliberately lenient: it flags collapse, not ordinary concision, so a genuinely tight answer at roughly half the reference length still passes.
   - Scope: applied to the hermes-audited system, matching criteria 1 to 3. The frozen decoding config preserves length across the revision pass (the audited record inherits the current record's length), so an audited collapse implies a current collapse. Implemented in `writing_eval.comparison.decision_gate` and enforced by `benchmark/decision_gate.py --eval-set`.
6. Labeling rule (item 5 at the 2026-07-17 registration; renumbered here after criterion 5 was added): deltas smaller than the 2.4 noise floor are inconclusive, never evidence of improvement. This labels criterion 3 (as `inconclusive`, `conclusive`, or `n/a`) and does not itself pass or fail.

## Re-registration 2026-07-22

- Corpus: the reference corpus was rebuilt from 13 to 22 samples (15 holdout, about 13.9K words; 7 eval) by adding nine of the author's published blog posts, all `article_section`, which for the first time gives that use case holdout coverage. The corpus is still below its documented minimums (30 to 50 samples, 15,000 holdout words), so L2 floors from it stay provisional. See `benchmark/SAMPLES.md` for curation and split.
- Floor provenance note (b): every noise floor inserted below comes from the 2026-07-22 corpus at its new size, measured with the unchanged item 2.4 procedure (frozen decoding config in eval-config.json, five hermes-current runs plus five revision passes, `benchmark/generate_runs.py` then `benchmark/noise_floor.py`). Corpus-aggregate spreads come straight from `benchmark/noise_floor.py`; the criterion 3 floor is the maximum cross-run spread of the mean per-record token 1-gram L2, the quantity the decision gate tests, computed by the same five runs.
- Rule-set pin (c): the benchmark rule set stays pinned to `rules/style-audit-v1.yaml` (the frozen AI-tell set backing this gate). The v2 and v3 rule sets are single-document `check` linters only and remain out of benchmark scope; no benchmark or floor run uses them.

## Re-registration 2026-07-23

Reason: the 2026-07-22 official benchmark returned verdict insufficient solely on
criterion 5 (length adequacy). One exec_communication record (sample-85e9c876d9d5,
509-word reference) collapsed to 12 words, and the same collapse recurred across
independent runs (18 words in the 2026-07-17 official run, 11 words in phase B
noise-floor run-1, 12 words here). The cause is the frozen system prompt itself:
"Give the shortest complete answer" invites a one-line reply to a memo-length
prompt. The user approved fixing the test harness: change the frozen system prompt,
re-register, and re-run.

- Frozen system prompt changed (in eval-config.json frozen_decoding.system_prompt):
  - OLD (2026-07-17 freeze): "You are a concise assistant. Give the shortest complete answer; skip filler, caveats, and throat-clearing."
  - NEW (2026-07-23 freeze): "You are a precise writing assistant. Write the complete deliverable the prompt asks for, at the length the deliverable naturally requires. Be direct and skip filler, hedging, and throat-clearing, but never truncate, outline, or summarize instead of writing the piece."
  - The new prompt requires the complete deliverable at its natural length (fixing
    the collapse) while retaining the anti-filler intent. All other decoding fields
    (model, provider, reasoning_effort, temperature 1.0, max_tokens 2048) are
    unchanged.
- Criteria UNCHANGED: all five criteria (1 hard findings, 2 tell rate at most 2.0,
  3 voice distance within the noise floor, 4 no degenerate/null-L2 outputs, 5 length
  adequacy at least 50 words AND at least 30 percent of the eval-set reference) and
  their thresholds are identical to the 2026-07-22 registration. The rule set stays
  pinned to rules/style-audit-v1.yaml. Nothing about what is measured or the pass
  bars changed; only the generation-side system prompt changed.
- Noise floors void for future runs: because the frozen config changed, every noise
  floor measured under a prior config (the 2026-07-17 and 2026-07-22 floors) is void
  for any run under this config. Per the standing provenance rule, all floors MUST be
  and WILL be re-measured under the new config with the unchanged item 2.4 procedure
  (five hermes-current generations plus five revision passes via
  benchmark/generate_runs.py, then benchmark/noise_floor.py, on the current corpus)
  BEFORE the official benchmark run. The criterion 3 floor is again the maximum
  cross-run spread of the mean per-record token 1-gram L2, the quantity the decision
  gate tests. The re-measured floors are inserted below and in criterion 3's slot
  before any official generation on this config exists.
- Comparability warning: results under the 2026-07-23 config are NOT directly
  comparable to any pre-2026-07-23 run, by design, because the system prompt changed.

## Measured noise floors (2026-07-22 corpus)

Measured from `benchmark/noise_floor.py` over the five 2026-07-22 item 2.4 runs
(`runs/phaseB/report-run-{1..5}.json`), before the official benchmark, per the
provenance note above. The full floor file is `runs/phaseB/noise-floor.phaseB.json`.
All floors have `n_runs_min` 5 (not bound-only). Corpus-aggregate spreads come
straight from `benchmark/noise_floor.py`:

| Metric | Corpus-aggregate floor | System |
| --- | ---: | --- |
| tell_rate | 4.995406529927299 | hermes-current |
| token_1gram_l2 (corpus-aggregate) | 0.005221135957282824 | hermes-current |
| mean_sentence_length | 1.0297780413419169 | hermes-audited |
| sentence_length_variance | 10.345062308102726 | hermes-audited |
| repeated_opening_rate | 0.057300908047176705 | hermes-current |

The criterion 3 floor is not the corpus-aggregate L2 spread above. It is the
maximum cross-run spread of the mean per-record token 1-gram L2 (the quantity the
decision gate tests), computed against `data/corpus/references.holdout.jsonl` over
the same five runs: 0.034370360061 (hermes-audited). This per-record floor is the
value written to `noise-floor.phaseB.json` under `token_1gram_l2.floor` and is the
number criterion 3 above uses. See that file's note for the run-1 collapse that
inflates it.

## Measured noise floors (2026-07-23 config)

Measured from `benchmark/noise_floor.py` over the five 2026-07-23 item 2.4 runs
(`runs/refreeze-2026-07-23/report-run-{1..5}.json`) under the re-frozen system
prompt (eval-config.json, frozen 2026-07-23), on the same 22-sample, 15-holdout
corpus. The assembled floor file is
`runs/refreeze-2026-07-23/noise-floor.refreeze.json` (raw `benchmark/noise_floor.py`
output preserved in `noise-floor.aggregate.json`). All floors have `n_runs_min` 5
(not bound-only). Corpus-aggregate spreads come straight from
`benchmark/noise_floor.py`:

| Metric | Corpus-aggregate floor | System |
| --- | ---: | --- |
| tell_rate | 4.314287275466 | hermes-current |
| token_1gram_l2 (corpus-aggregate) | 0.005697004113 | hermes-current |
| mean_sentence_length | 1.390873558726 | hermes-audited |
| sentence_length_variance | 16.897444572841 | hermes-audited |
| repeated_opening_rate | 0.062790697674 | hermes-current |

The criterion 3 floor is not the corpus-aggregate L2 spread above. It is the
maximum cross-run spread of the mean per-record token 1-gram L2 (the quantity the
decision gate tests), against `data/corpus/references.holdout.jsonl` over the same
five runs: 0.00500314427711171 (hermes-audited). This per-record floor is the
value written to `noise-floor.refreeze.json` under `token_1gram_l2.floor` and is
the number criterion 3 above uses.

Length-collapse check (the failure mode that motivated the re-freeze). Under the
new prompt the collapse is gone across all five runs. Per-run minimum record word
counts (project tokenizer) and per-run mean per-record L2, for both systems:

| Run | Min words current | Min words audited | Shortest record | Mean per-record L2 current | Mean per-record L2 audited |
| --- | ---: | ---: | --- | ---: | ---: |
| 1 | 157 | 157 | sample-509213b62598 | 0.068778 | 0.068051 |
| 2 | 177 | 177 | sample-509213b62598 | 0.070390 | 0.069442 |
| 3 | 169 | 169 | sample-509213b62598 | 0.069962 | 0.069062 |
| 4 | 170 | 170 | sample-509213b62598 | 0.072302 | 0.071676 |
| 5 | 165 | 165 | sample-509213b62598 | 0.073499 | 0.073054 |

Every run's shortest record is at least 157 words. Checked directly: across all
70 records in the five runs (both systems), none fell below its criterion 5
threshold (max of 50 words and 30 percent of its eval-set reference). The record
that collapsed to 11 to 18 words under the prior prompt (sample-85e9c876d9d5, a
509-word reference) is no longer the shortest and is at full length in every run.
Because the collapse is gone, the criterion 3 floor (0.005003) is about seven
times tighter than the collapse-inflated 2026-07-22 floor (0.034370), so criterion
3 is materially stricter under this config.

## If any criterion fails

Phase 4 re-opens the question of whether the audit-plus-revision control is
sufficient if this gate fails. QLoRA or training work remains out of scope unless
the gate proves the control insufficient.
