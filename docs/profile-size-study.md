# How many articles does a style profile need?

This document records the measurement behind the corpus-size recommendation in
[README.md](../README.md#recommended-corpus-size). It replaces an earlier
recommendation of "at least 30 articles and at least 15,000 words," which was a
judgment call carried over from the benchmark corpus notes and was never
measured.

The primary result is a 24-draft run (experiment 1). An earlier 6-draft run
(experiment 1, first pass) reached a different headline number by reporting
only the mean. The first pass is kept below, marked superseded, with the
reason the mean misled.

## The question

A style profile aggregates statistics over a set of articles. If the profile is
small, the score it assigns to a draft depends partly on which articles happened
to be included. The practical question is not "is the profile accurate," since
there is no ground truth to be accurate against. It is:

> Hold the draft fixed. Change only which N articles form the profile. How much
> does the score move?

Once that movement is smaller than the smallest unit the score can express, a
larger corpus buys nothing a user can see. The rubric deducts 2 points per
excess `warn` occurrence, so 2 points is that unit.

## Method

- **Corpus.** 101 articles, 280,055 words, long-form nonfiction by a single
  author. Mean article length 2,772 words, median 2,309.
- **Held-out drafts.** 24 articles were removed from the pool and used as the
  drafts to be scored, so a draft is never inside its own profile corpus. The
  sampling pool for building profiles is the remaining 77 articles.
- **Sampling.** For each profile size N, 30 subsamples of N articles were drawn
  without replacement from the pool, each with a fixed seed.
- **Scoring.** Each subsample was scored through the production path:
  `profile_statistics`, `build_rule_baseline`, `build_style_gap`, and
  `build_assessment`, with the builtin rule set. Token counts, rule counts, and
  word counts are additive over a sample, so they were precomputed per article.
- **Statistic.** The standard deviation of the 30 scores for a fixed draft,
  computed separately for each of the 24 drafts, then summarized as a mean,
  median, and worst value across drafts. Reporting per-draft values, not only
  their mean, matters here: the first pass below reported only a mean and it
  hid which drafts were still noisy at a given N.

The first pass (6 held-out drafts, 40 subsamples per N, sizes 3 through 70)
used the same corpus and the same production scoring path. Its method
differences are noted where its table appears below.

## Experiment 1: score noise against profile size

This is the primary result. Statistic: the standard deviation of one draft's
score across 30 profiles of size N, computed per draft and then summarized
across the 24 held-out drafts. The rubric deducts 2 points per excess `warn`
occurrence, so 2 points is the resolution below which sampling noise is
invisible to the score.

| N | Mean sd | Median sd | Worst sd | Drafts at or under 2 pts |
|---:|---:|---:|---:|---:|
| 10 | 2.82 | 2.61 | 6.46 | 33.3% |
| 15 | 2.48 | 2.45 | 5.82 | 37.5% |
| 20 | 2.37 | 1.85 | 6.59 | 54.2% |
| 25 | 2.05 | 1.61 | 6.94 | 70.8% |
| 30 | 1.97 | 1.47 | 5.96 | 66.7% |
| 40 | 1.51 | 1.21 | 4.90 | 87.5% |
| 50 | 1.19 | 1.07 | 3.55 | 95.8% |
| 60 | 0.97 | 0.92 | 2.50 | 95.8% |

Per-draft crossing points (the N at which a draft's own sd first falls to or
below 2 points): 17 of 24 drafts cross by N = 25, 18 of 24 by N = 30, and 23 of
24 by N = 50. One draft, 4,588 words, is still at 2.50 with 60 articles in the
profile.

Findings:

1. **The median draft crosses the 2-point resolution at N = 20, but the
   distribution has a long tail.** A recommendation has to be set against
   coverage (the share of drafts that have settled), not against the mean.
   N = 25 covers 7 in 10 drafts. N = 40 covers 9 in 10. N = 50 covers 24 of 25.
2. **"Prefer 30" is not supported by this run.** N = 30 covers 66.7% of drafts
   against N = 25's 70.8%, a difference inside trial noise. The real gains sit at
   N = 40 and N = 50.
3. **Reporting only the mean sd, which is what the first pass below did, hides
   this tail.** The first pass's mean at N = 25 read 1.79, comfortably under 2
   points, and said nothing about the roughly 3 in 10 drafts still above it
   here. The first pass is kept below rather than deleted: it shows exactly
   what the mean view hides, which is itself worth recording.
4. **Some drafts sit near several deduction boundaries at once and never
   settle at any corpus size tested here.** Their score depends on which side
   of a boundary a `warn` count lands on, not on how much profile evidence
   backs it.
5. **One rule holds at every corpus size tested, and it is the most useful
   thing for a user to carry away: treat a score difference under 3 points as
   noise**, whether between two drafts or between two runs of the same draft.

## Experiment 1, first pass (superseded)

This run used 6 held-out drafts, 40 subsamples per N, sizes 3 through 70, and
reported only the mean sd. It produced the original "at least 25, prefer 30"
recommendation. It is kept here because the 24-draft run above found the mean
alone was misleading, not because this table is still the recommendation.

| N articles | Mean words | Mean score | Score stdev | Mean range | p90 spread |
|---:|---:|---:|---:|---:|---:|
| 3 | 7,240 | 88.9 | 4.00 | 16.7 | 12.5 |
| 5 | 13,298 | 89.6 | 3.58 | 16.0 | 9.5 |
| 8 | 23,258 | 90.1 | 3.12 | 12.7 | 9.3 |
| 10 | 28,466 | 89.7 | 2.59 | 11.8 | 8.0 |
| 15 | 42,514 | 90.3 | 2.53 | 10.7 | 7.3 |
| 20 | 57,053 | 90.6 | 2.18 | 8.0 | 6.5 |
| 25 | 72,280 | 90.6 | 1.79 | 7.0 | 5.0 |
| 30 | 84,295 | 90.5 | 1.65 | 6.5 | 4.8 |
| 40 | 112,615 | 90.5 | 1.54 | 5.8 | 4.7 |
| 50 | 140,166 | 90.4 | 1.22 | 5.3 | 3.7 |
| 60 | 169,222 | 90.6 | 1.06 | 4.8 | 3.0 |
| 70 | 198,376 | 90.7 | 0.81 | 3.0 | 2.7 |

Findings from the first pass, kept for context and superseded by experiment 1
above:

1. There is no elbow. Noise falls smoothly, close to the 1 over root N shape
   you would expect from sampling. This part of the finding still holds in the
   24-draft run.
2. The mean crossed 2 points between N = 20 and N = 25, which produced the
   earlier recommendation of at least 25, prefer 30. The 24-draft run shows
   this crossing describes the median draft, not most drafts, and that N = 30
   buys nothing over N = 25 once trial noise is accounted for.
3. The mean score is stable from N = 8 onward, moving only between 89.7 and
   90.7. Small profiles are not biased. They are noisy. This still holds.
4. Worst case stays wide for a long time. At N = 30 the middle 90 percent of
   outcomes still spans 4.8 points. The 24-draft run's worst-sd column shows
   this more directly: some drafts are still above 5 points of noise at N = 30.

## Experiment 2: articles or words?

The corpus above has long articles, so article count and word count rose
together and experiment 1 cannot separate them. The pool (77 articles, after
holding out the 24 drafts) was split at the median article length (2,309
words) into a short arm (39 articles, mean 1,444 words) and a long arm (38
articles, mean 3,966 words). Articles were then drawn from each arm until a
fixed word budget was reached, 20 trials per cell.

| Word budget | Arm | Articles used | Actual words | Score stdev |
|---:|---|---:|---:|---:|
| 10,000 | short | 7.6 | 10,818 | 3.75 |
| 10,000 | long | 3.0 | 12,649 | 3.57 |
| 20,000 | short | 14.4 | 20,738 | 2.07 |
| 20,000 | long | 5.8 | 22,183 | 3.16 |
| 40,000 | short | 28.3 | 40,648 | 1.29 |
| 40,000 | long | 10.7 | 41,557 | 2.51 |
| 60,000 | short | insufficient corpus | n/a | n/a |
| 60,000 | long | 16.0 | 62,722 | 2.04 |
| 90,000 | short | insufficient corpus | n/a | n/a |
| 90,000 | long | 23.1 | 92,305 | 1.64 |

From 20,000 words upward the short arm is more stable at every matched budget
the corpus can reach, and the gap widens as the budget grows. At 40,000 words,
the largest budget both arms can reach, 28.3 short articles gave 1.29 while
10.7 long articles gave 2.51, roughly half the noise from article count alone.
The short arm does not contain enough words to reach the 60,000 or 90,000
word budgets at all, so those rows show insufficient corpus for short rather
than a number; the 43-article, 0.60-stdev result reported in an earlier
version of this document came from a 95-article pool (a 6-draft holdout) and
is not reachable under the current 24-draft holdout. At the smallest budget,
10,000 words, the long arm is marginally lower than the short arm, consistent
with both being dominated by noise at 3 to 7 articles.

**Conclusion: the profile's stability is governed by how many documents it
aggregates, not how many words.** This is what you would expect once you note
that the sampling unit is the document. It also means the old 15,000-word
minimum measured the wrong quantity. A 15,000-word corpus of four long essays
sits at roughly 3.5 points of noise, which is worse than the rubric's resolution.

## Experiment 3: does article length matter at fixed article count?

Experiment 2 held the word budget fixed and varied article count. This is the
complement: hold article count fixed and vary how long each article is.

**Method.** Same 101-article corpus and the same production scoring path. 24
held-out drafts, the same selection as experiment 1, leaving a pool of 77. The
pool was split into tertiles by article length, and each trial drew its N
articles from within one tertile only, 30 trials per cell:

- short: 26 articles, mean 1,176 words, range 517 to 1,665
- mid: 26 articles, mean 2,350 words, range 1,693 to 3,200
- long: 25 articles, mean 4,615 words, range 3,225 to 11,610

An exhaustion guard capped the usable N at 0.66 times arm size (17.2, 17.2, and
16.5 for short, mid, and long). N = 20 exceeded that cap in all three arms and
was skipped everywhere, so only N = 8, 10, 12, and 15 were tested. The guard
exists because an earlier attempt at this experiment, using a two-way split
with 25-to-26-article arms sampled up to N = 25, drove one cell to a standard
deviation of exactly 0.00 by sampling nearly the whole arm; that run was
discarded. This table always uses 30 trials per cell; it does not follow the
script's `--trials` flag, so the published numbers reproduce regardless of
what a caller passes for the other two experiments.

**Results.** Mean sd across the 24 held-out drafts, and the share of drafts at
or under the 2-point tolerance:

| N | short 1,176 w | mid 2,350 w | long 4,615 w | short cov | mid cov | long cov |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | 3.35 | 2.42 | 2.85 | 25.0% | 41.7% | 33.3% |
| 10 | 2.63 | 2.28 | 2.40 | 25.0% | 41.7% | 45.8% |
| 12 | 2.53 | 1.92 | 2.24 | 33.3% | 62.5% | 50.0% |
| 15 | 2.15 | 1.73 | 1.98 | 50.0% | 75.0% | 66.7% |

Findings:

1. **The short arm is noisiest at every tested N, without exception.** Its gap
   against the average of the mid and long arms is 0.72, 0.29, 0.45, and 0.30
   points at N = 8, 10, 12, and 15, a mean of 0.44 points. A 6-draft first pass
   of this experiment put the gap at 0.86; the 24-draft run about halves it.
   The direction survived, the magnitude did not.
2. **Mid is consistently a little lower than long, not indistinguishable from
   it.** At 24 drafts, mid beats long at all four N, by 0.43, 0.12, 0.32, and
   0.25 points, a mean of 0.28. The 6-draft first pass had called mid and long
   indistinguishable with the sign flipping across N; that was an artifact of
   too few drafts. Call the ordering weak but consistent. The practical
   consequence is unchanged and now stronger: length past roughly 2,350 words
   per article buys no further stability, and the 4,615-word arm is marginally
   worse than the 2,350-word arm, not better. "Longer is better" is dead.
3. **The short-arm penalty is broad, not a tail artifact.** Three of the 24
   drafts exceed sd 3.0 in the short arm at every tested N, but removing them
   moves the short-arm mean by only 0.21 to 0.32 points, for example 2.15 to
   1.90 at N = 15. Most of the effect is spread across most drafts, not
   concentrated in a few.
4. **One draft shows genuine short-profile-specific instability.** Its
   short-arm sd runs 4.4 to 7.6 across all four N, while the same draft in the
   mid and long arms stays under 2.6, falling to 0.69 to 1.14 at N = 15. This
   draft is unusually sensitive to which short articles happen to be sampled,
   specifically.
5. **A different draft is noisy in every arm at N = 8**, at 5.82, 5.37, and
   8.65 for short, mid, and long. That draft is inherently volatile at small N
   regardless of article length, and should not be double-counted as evidence
   for the length effect.
6. **No numeric word floor is supported by this data.** The shortest article in
   the corpus is 517 words, so the study cannot see where the floor actually
   sits. The floor itself is unknown. Do not treat any number here as a
   minimum.

## Limitations

- One corpus, one author, one genre. The direction of the findings should
  generalize, since they follow from the sampling unit being the document, but
  the coverage percentages at each N are specific to this material.
- The shortest article in the corpus is 517 words and the tenth percentile is
  818, so the study says nothing about profiles built from short posts of a few
  hundred words. A word floor may still be needed there. It has not been
  measured.
- The 2-point tolerance is a choice. It is defensible because it matches the
  rubric's own granularity, but a team that wants to compare drafts within 1
  point needs a larger corpus than this recommends.
- Coverage never reaches 100% at the sizes tested. One draft (4,588 words) is
  still at 2.50 points of noise with 60 articles in the profile. Some drafts
  sit near several deduction boundaries and may not settle at any practical
  corpus size, which the mean-only first pass could not show.
- Score noise is not the only thing corpus size affects. Token 1-gram L2 and
  overrepresented terms are reported separately and are more sensitive to corpus
  composition than the score is.
- Experiment 3 could not test N = 20 or above. Its tertile arms are only 25 to
  26 articles, and the exhaustion guard excludes any N past 0.66 times arm
  size. The experiment says nothing about length effects at larger profile
  sizes.

## Reproducing this

The script is at [`profile_size_study.py`](profile_size_study.py). It
implements all three experiments. Point it at any built profile's
`references.jsonl`:

```bash
uv run python docs/profile_size_study.py \
  --references data/profiles/<name>/references.jsonl
```

It prints all three tables. Runtime is several minutes for a 100-article
corpus. The seed is fixed, so repeated runs on the same corpus give identical
output.
