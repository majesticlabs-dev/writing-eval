Closed internal benchmark record. Some paths identify historical artifacts that no longer exist. It does not constrain current product behavior.

# Sample corpus: inclusion, IDs, split, and sizing

This document covers roadmap items 2.2 (collect real samples with a holdout
split) and 2.3 (re-scope the reference corpus). The tooling lives in
`src/writing_eval/corpus.py` and `benchmark/build_corpus.py`.

## Inclusion criteria

A sample qualifies when it is:

- Genuine human authored prose written by the corpus owner, not model
  generated text, not edited machine output, and not a mix where the
  human contribution cannot be separated out.
- Flowing paragraphs: connected sentences forming prose, not fragments,
  outlines, or tables standing in for prose.
- One of the three evaluation use cases: `article_section`,
  `product_writing`, or `exec_communication`.
- Roughly 80 words minimum after frontmatter is stripped, so a sample
  carries enough signal to be worth a slot in a small corpus.

Excluded:

- Knowledge base notes (research summaries, source tables, evidence
  packets): these are working notes, not the target writing voice.
- Agent generated artifacts, including lightly edited model drafts.
- Transcripts (calls, interviews, meetings): spoken register, not the
  target written voice.
- Code, code comments, and technical reference docs (API docs, runbooks,
  configuration references).

The exclusion of knowledge base notes is why item 2.3 exists:
`fixtures/references.real.jsonl` was roughly 97 percent KB notes, so a
token 1-gram L2 measured against it rewarded KB vocabulary rather than the
prose voice the eval is meant to measure. The holdout built by this
tooling replaces that corpus.

## Stable ID scheme

Each sample's ID is `sample-` followed by the first 12 hex characters of
`sha256(source_path)`, where `source_path` is the sample file's path
relative to the collection root, exactly as written to `source_path` in
the eval set record and to `file` in the reference holdout record. The ID
depends only on that relative path string, so:

- The same manifest and root always produce the same ID for the same
  file, run after run.
- Renaming or moving a sample file changes its ID; content edits with the
  path unchanged do not.
- `collect_samples` rejects a manifest that would produce two identical
  IDs (two entries resolving to the same relative path).

## Split method

`split_holdout` (in `src/writing_eval/corpus.py`) performs a deterministic,
stratified split:

1. Samples are grouped by `use_case`.
2. Within each group, samples are sorted by `id`, then shuffled with
   `random.Random(seed)` (default seed `20260717`).
3. `round(len(group) * eval_fraction)` samples (default fraction `0.4`)
   go to eval, the rest to holdout, with two guarantees: a non-empty group
   always sends at least one sample to eval, and a group with two or more
   samples always keeps at least one sample in holdout. This is why every
   use case with at least two samples appears in both splits.
4. Before returning, the two ID sets are asserted disjoint and their union
   is asserted to equal the full sample set. A violation raises rather
   than silently producing an overlapping split.

Because the split is deterministic and disjoint, the reference corpus
(built from holdout only, see below) and the evaluation set never share a
sample. L2 distance between an eval output and the reference corpus is
therefore never measuring a corpus against itself.

Re-running `benchmark/build_corpus.py` with the same manifest, root, seed,
and fraction reproduces the identical split; changing any of those inputs
is expected to change it.

### Holdout-only samples

A manifest record may set the optional boolean `holdout_only` (default
false). A flagged sample is assigned directly to the holdout list and
never enters the eval set; the eval-fraction split, the stratification
guarantee, and the min-1-eval-per-group rule all apply to the unflagged
pool only. A use case whose samples are all flagged simply has no eval
entries. The disjointness and coverage assertions still cover every
sample, flagged or not.

Rationale: the frozen decoding config caps generation at `max_tokens`
2048, about 1500 words, so a sample longer than that can never be an eval
target: the generator cannot satisfy its target-length prompt. Its text is
still valuable reference bulk, so it stays in the holdout. Guidance: mark
`holdout_only` any sample over 1200 words.

## Reference corpus source

`references.holdout.jsonl` is built from the holdout split only, never
from the eval set. Building it from the eval set would let a system's
output be compared against the very sample used to prompt it (or a sample
from the same source), inflating apparent voice similarity.

## Minimum corpus size

Before treating an L2 baseline computed from this corpus as stable:

- At least 30 samples total, spread across the 3 use cases.
- At least 15,000 words in the holdout (reference) side specifically,
  since that is the side L2 is computed against.

`fixtures/references.real.jsonl` held roughly 405,000 words (almost
entirely KB notes, per the inclusion criteria above). Shrinking the
reference corpus to a genuine-prose holdout of a few tens of thousands of
words is a deliberate size reduction, and it changes the variance
character of the L2 metric: a smaller reference vocabulary has higher
sampling variance, so L2 deltas that would have been noise against the
405K-word corpus can look larger against a 15 to 50K-word holdout. Treat
early L2 numbers from the new corpus as provisional until the noise floor
from roadmap item 2.4 is measured against it.

## Build command

```bash
uv run python benchmark/build_corpus.py \
  --manifest path/to/manifest.jsonl \
  --root path/to/sample/root \
  --out-dir fixtures \
  --eval-fraction 0.4 \
  --seed 20260717
```

The manifest is JSONL; each line is an object with `path` (absolute, or
relative to `--root`), `use_case` (one of the three values above), and
`title`, plus the optional boolean `holdout_only` described above. The
command writes three files under `--out-dir`:

- `references.holdout.jsonl`: `id`, `text`, `source` (`"holdout-2.2"`),
  `file`.
- `eval_set.jsonl`: the full sample record (`id`, `use_case`, `title`,
  `source_path`, `text`, `word_count`).
- `prompts.eval.jsonl`: `id`, `use_case`, `prompt`, one generation prompt
  per eval-set sample.

It prints a one-line summary with per-use-case holdout and eval counts on
success, and exits with status 2 and a message on stderr (no traceback)
for expected errors such as a missing manifest, a malformed manifest
record, or an empty sample file.

## Curation record (2026-07-17)

### Source sweep

An exhaustive sweep of the knowledge base and Google Drive found 13
usable, genuinely human-authored prose samples against the 30 to 50
target set by the minimum corpus size below. All machine-readable
sources are exhausted: clearing the target requires user-supplied
samples, not further searching.

### Exclusions

Excluded during curation, all per the inclusion criteria above:

- All agent-ghostwritten knowledge base content (an agent persona drafts
  the user's article-length content, so it is not the user's own prose).
- One business letter withheld for third-party sensitivity.
- Tax and immigration documents (never opened).
- Two slide decks (format, not prose).
- Journal template documents.
- One unfinished 96-word draft fragment.

### Artifact repair

One included sample, the angel-email tips article
(`drive-angel-email-tips.md`, `article_section`, eval split), contained
Google Docs suggestion-mode export garble (backslash-escaped punctuation
and similar token-level corruption). Ten token-level artifacts were
repaired, with a documented before and after list. One residual
word-level merge and stray punctuation clusters (for example a missing
space before a dash) were left as-is, per the faithfulness rule: repair
export corruption, do not rewrite the author's prose.

### Split composition

`benchmark/build_corpus.py` (seed 20260717, eval fraction 0.4, stratified
by `use_case`) split the 13 samples into 8 holdout and 5 eval, including
the `holdout_only` RFC (`drive-rails-llm-benchmark-rfc.md`, 5,272 words,
longer than frozen `max_tokens` 2048, about 1,500 words, can generate, so
it is reference bulk only):

| Use case | Holdout | Eval |
|---|---|---|
| article_section | 0 | 1 |
| exec_communication | 5 | 2 |
| product_writing | 3 | 2 |

Holdout: about 6.9K words. Eval: about 2.0K words. `article_section` has
only 1 sample total (the eval-side angel-email tips article), so it has
no holdout representation yet.

### Below minimum

13 samples and about 6.9K holdout words are both below the documented
minimums (30 to 50 samples, 15,000 holdout words). Treat
`references.holdout.jsonl` and any L2 baseline computed against it as
provisional until the minimum is cleared. Clearing it requires the user
to supply additional writing samples; the knowledge base and Google
Drive sweep is exhausted.

## Curation record (2026-07-22 blog expansion)

### Source

The user (David Paluy) authorized using their own published blog posts
from `https://majesticlabs.dev`. All 24 posts were enumerated from the
site's `sitemap-blog.xml`, fetched, and converted from the server
rendered `<div class="blog-content">` article body to Markdown with
pandoc. Navigation, header, byline, reading-time, related-posts, and
footer chrome were stripped during extraction.

### Method and cleaning

Per the inclusion criteria above, each post was read for genuine
first-person authored prose. For every included post the extraction kept
headings and flowing body prose and removed material that pollutes
token-distribution metrics or is not the author's prose voice:

- Fenced code blocks and command listings were removed. A lead-in
  sentence may therefore refer to an omitted block or table.
- One pricing table in the OCR post was removed (tables are not flowing
  prose).
- Screenshots and inline images were removed.
- Inline citation links were flattened to their anchor text, and bare
  URL and trailing "Sources" or "References" link lists were dropped, so
  the samples stay URL-free and consistent with the existing corpus.
- The pandoc-introduced `\$` escape was restored to `$`.

The included posts contain no em or en dashes (the source site itself
avoids them), so no dash normalization was needed. The post title is
prepended as a single H1, matching the existing sample file format.
Files are saved as `data/samples/blog-<slug>.md` and appended to
`data/samples.manifest.jsonl`; IDs are derived from the relative path by
the existing scheme.

### Included (9 samples, all article_section)

Word counts are `word_count` from `collect_samples`.

| File | Words | Note |
|---|---|---|
| blog-automations-turn-follow-up-into-background-work.md | 585 | |
| blog-building-private-ai-evals.md | 2,491 | holdout_only (over 1,200 words) |
| blog-codex-is-becoming-a-workspace-not-a-chatbot.md | 581 | |
| blog-codex-operating-manual-for-knowledge-workers.md | 580 | |
| blog-ocr-is-a-routing-problem-now.md | 1,829 | holdout_only (over 1,200 words) |
| blog-the-chief-of-staff-thread.md | 677 | |
| blog-the-self-driving-company-still-needs-people.md | 703 | |
| blog-worktrees-for-knowledge-work.md | 589 | |
| blog-yaml-is-the-workflow-layer-for-ai-agents.md | 361 | |

All nine are classified `article_section`: they are published
thought-leadership essays. This lifts `article_section` from 1 sample to
10, so for the first time that use case will have holdout representation
when `benchmark/build_corpus.py` is re-run.

### Exclusions (15 posts)

Excluded per the inclusion criteria above and the task's link-list,
stub, and mostly-code rules:

- `enabling-autonomous-ai-agents-to-make-payments`: agent-generated
  research report (about 18,000 words, "This report examines" register,
  a trailing citation dump of source-fragment URLs), not the author's
  own prose voice.
- `mastering-ai-model-fine-tuning`: generic model-draft register ("In
  the evolving landscape of artificial intelligence", inflated
  abstractions) inconsistent with the author's plain first-person voice.
- `exploring-agentic-workflow-patterns`: same generic model-draft
  register, plus a code-heavy pattern reference.
- `portable-agent-ops-reduces-coding-harness-switching-cost`:
  configuration and tooling reference dominated by file names, config
  keys (over 100 inline-code spans), code-block repo trees, and
  per-section source-link lists rather than flowing prose.
- `codex-cli-configuration-guide`: configuration reference (code-dense).
- `codex-cli-developer-guide`: mostly code (22 fenced blocks).
- `mastering-cursor-rules-jan-2025`: Cursor rules configuration
  reference (code-dense, table-of-contents lead).
- `when-third-party-apis-go-rogue-strategies-for-building-bulletproof-integrations`:
  technical integration reference (table of contents plus Ruby code
  examples).
- `polymorphic-model-resource-finder-in-ruby-on-rails`: Rails code
  tutorial, mostly code.
- `publishable-enum-in-ruby-on-rails-with-postgresql`: Rails code
  tutorial, mostly code (about 150 prose words).
- `the-ultimate-guide-to-dokku-and-ruby-on-rails-5`: setup runbook of
  shell commands.
- `5-must-have-actions-to-make-your-emails-more-trusted`: SPF, DKIM, and
  DMARC DNS configuration reference.
- `the-practical-guide-to-gmail-productivity`: screenshot and link heavy
  tool roundup; genuine voice but dominated by external links, tool
  names, and images rather than flowing prose.
- `9-great-questions-to-ask-during-the-hiring-interview`: interview
  question outline (questions as headings) with thin, generic
  explanations, closer to an outline than flowing prose.
- `7-web-tools-for-perfect-naming-for-your-startup-or-products`: link
  list roundup of naming tools.

`portable-agent-ops` and `the-practical-guide-to-gmail-productivity` are
the closest calls: both are genuinely the author's writing, but both are
dominated by non-prose material (config-key or link and image density)
that would pollute token-distribution metrics, so they are held out of
the corpus. They can be revisited if the criteria are relaxed.

### Corpus size after expansion

The corpus grows from 13 to 22 samples, adding about 8,400 words of
`article_section` prose (of which the two `holdout_only` posts,
about 4,300 words, are reference-only bulk). This is still below the
documented minimums (30 to 50 samples, 15,000 holdout words), but it is
materially closer and gives `article_section` real coverage on both
splits. Re-run `benchmark/build_corpus.py` to regenerate the holdout, eval
set, and prompts from the updated manifest.
