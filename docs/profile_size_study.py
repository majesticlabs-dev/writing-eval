"""Measure how style-profile corpus size affects score stability.

Holds a draft fixed, varies only which articles form the profile, and reports
the spread of the resulting scores. See docs/profile-size-study.md for the
method, results, and limitations.

Usage:
    uv run python docs/profile_size_study.py \
        --references data/profiles/<name>/references.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from writing_eval.assessment import build_assessment, build_rule_baseline
from writing_eval.cli_check import _check_result, _mark_within_allowance
from writing_eval.profile_analysis import build_style_gap, profile_statistics
from writing_eval.segmentation import tokenize
from writing_eval.style_audit import BUILTIN_RULES_PATH, audit_text, load_rules
from writing_eval.style_audit_engine import StyleAuditor

SIZES = (3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 70)
BUDGETS = (10_000, 20_000, 40_000, 60_000, 90_000)
LENGTH_SIZES = (8, 10, 12, 15, 20)
SEED = 20260818

# The rubric deducts 2 points per excess warn occurrence, so 2 points is the
# smallest difference the score can express. Noise below it is invisible.
TOLERANCE = 2.0

# Drafts whose score stdev exceeds this, in the tertile-length experiment,
# are flagged as part of the noisy tail for that (arm, size) cell.
NOISE_THRESHOLD = 3.0

# Skip a tertile-length cell when the sample size exceeds this fraction of the
# arm's article count. Drawing most of a small arm on every trial collapses
# the between-trial variance the measurement depends on, which understates
# noise rather than showing a genuine drop.
EXHAUSTION_GUARD = 0.66

# The tertile-length table always uses this many trials per cell, regardless
# of --trials, so the published numbers reproduce no matter what a caller
# passes for the other two experiments.
LENGTH_TRIALS = 30


class Corpus:
    """Per-article counts, precomputed once because they are additive."""

    def __init__(self, texts: list[str], rules) -> None:
        auditor = StyleAuditor(rules)
        self.texts = texts
        self.tokens = [Counter(tokenize(t)) for t in texts]
        self.rules = [Counter(f.rule_id for f in auditor.audit(t)) for t in texts]
        self.words = [sum(c.values()) for c in self.tokens]

    def aggregate(self, picks):
        tok, rul, words = Counter(), Counter(), 0
        for i in picks:
            tok.update(self.tokens[i])
            rul.update(self.rules[i])
            words += self.words[i]
        return tok, rul, words


def score_drafts(corpus: Corpus, picks, drafts) -> list[int]:
    stats = profile_statistics([corpus.texts[i] for i in picks])
    tok, rul, words = corpus.aggregate(picks)
    scores = []
    for text, findings, word_count in drafts:
        result = _check_result("draft", text, findings, word_count, None)
        baseline = build_rule_baseline(
            rul, words, result["findings"], result["metrics"]["word_count"]
        )
        _mark_within_allowance(result["findings"], baseline)
        gap = build_style_gap("sample", text, stats, tok)
        assessment = build_assessment(
            text, result["findings"], result["metrics"],
            result["quality_metrics"], gap, stats, baseline,
        )
        scores.append(assessment["score"]["total"])
    return scores


def spread(by_draft: list[list[int]]) -> tuple[float, float, float]:
    sd = statistics.mean(statistics.stdev(s) for s in by_draft)
    rng = statistics.mean(max(s) - min(s) for s in by_draft)
    p90 = []
    for s in by_draft:
        ordered = sorted(s)
        lo = ordered[int(0.05 * len(ordered))]
        hi = ordered[int(0.95 * len(ordered)) - 1]
        p90.append(hi - lo)
    return sd, rng, statistics.mean(p90)


def by_article_count(corpus, pool, drafts, trials):
    header = (f"\n{'N':>4} {'words':>9} {'score':>7} {'mean_sd':>8} {'median_sd':>10} "
              f"{'worst_sd':>9} {'range':>7} {'p90':>7} {'pct_sd<=tol':>12}")
    print(header)
    print("-" * len(header.strip()))
    crossing = None
    crossed_at = [None] * len(drafts)
    sds_60 = None
    for size in SIZES:
        if size > len(pool):
            continue
        by_draft = [[] for _ in drafts]
        sample_words = []
        mean_scores = []
        for trial in range(trials):
            rng = random.Random(SEED + size * 1000 + trial)
            picks = rng.sample(pool, size)
            sample_words.append(sum(corpus.words[i] for i in picks))
            scores = score_drafts(corpus, picks, drafts)
            mean_scores.append(statistics.mean(scores))
            for d, value in enumerate(scores):
                by_draft[d].append(value)
        sd, rng_, p90 = spread(by_draft)
        sds = [statistics.stdev(s) for s in by_draft]
        median_sd = statistics.median(sds)
        worst_sd = max(sds)
        pct_le_tol = 100.0 * sum(1 for s in sds if s <= TOLERANCE) / len(sds)
        for d, value in enumerate(sds):
            if crossed_at[d] is None and value <= TOLERANCE:
                crossed_at[d] = size
        if size == 60:
            sds_60 = sds
        if crossing is None and sd <= TOLERANCE:
            crossing = size
        print(f"{size:>4} {statistics.mean(sample_words):>9,.0f} "
              f"{statistics.mean(mean_scores):>7.1f} {sd:>8.2f} {median_sd:>10.2f} "
              f"{worst_sd:>9.2f} {rng_:>7.1f} {p90:>7.1f} {pct_le_tol:>11.1f}%")
    if crossing is None:
        print(f"\nscore stdev never fell to {TOLERANCE} within the tested sizes")
    else:
        print(f"\nscore stdev falls below {TOLERANCE} points at N = {crossing} articles")

    print(f"\nper-draft crossing points (first N at which a draft's own sd falls "
          f"to or below {TOLERANCE}):")
    for size in SIZES:
        if size > len(pool):
            continue
        crossed = sum(1 for c in crossed_at if c is not None and c <= size)
        print(f"  N={size:>2}: {crossed} of {len(drafts)} drafts crossed")
    never = sum(1 for c in crossed_at if c is None)
    if never:
        print(f"  never crossed within tested sizes: {never} of {len(drafts)} drafts")

    if sds_60 is not None:
        stragglers = [(d, drafts[d][2], s) for d, s in enumerate(sds_60) if s > TOLERANCE]
        print(f"\ndrafts still above {TOLERANCE} points of noise at N = 60:")
        if not stragglers:
            print(f"  none: all {len(drafts)} drafts are at or under tolerance")
        for d, words, s in sorted(stragglers, key=lambda t: -t[2]):
            print(f"  draft#{d}: {words:,} words, sd={s:.2f}")


def by_word_budget(corpus, pool, drafts, trials):
    lengths = [corpus.words[i] for i in pool]
    median = statistics.median(lengths)
    arms = {
        "short": [i for i in pool if corpus.words[i] <= median],
        "long": [i for i in pool if corpus.words[i] > median],
    }
    print(f"\nmedian article length: {median:,.0f} words")
    for name, arm in arms.items():
        print(f"  {name} arm: {len(arm)} articles, "
              f"mean {statistics.mean(corpus.words[i] for i in arm):,.0f} words")
    print(f"\n{'budget':>8} {'arm':>6} {'articles':>9} {'words':>9} {'stdev':>7}")
    print("-" * 45)
    for budget in BUDGETS:
        for name, arm in arms.items():
            if sum(corpus.words[i] for i in arm) < budget:
                print(f"{budget:>8,} {name:>6} {'insufficient corpus':>28}")
                continue
            by_draft = [[] for _ in drafts]
            used, totals = [], []
            for trial in range(trials):
                rng = random.Random(SEED + budget + trial + (0 if name == "short" else 7))
                order = arm[:]
                rng.shuffle(order)
                picks, total = [], 0
                for i in order:
                    picks.append(i)
                    total += corpus.words[i]
                    if total >= budget:
                        break
                used.append(len(picks))
                totals.append(total)
                for d, value in enumerate(score_drafts(corpus, picks, drafts)):
                    by_draft[d].append(value)
            sd, _, _ = spread(by_draft)
            print(f"{budget:>8,} {name:>6} {statistics.mean(used):>9.1f} "
                  f"{statistics.mean(totals):>9,.0f} {sd:>7.2f}")


def by_article_length(corpus: Corpus, pool: list[int], drafts, trials: int) -> None:
    """Hold profile size fixed, vary only average article length.

    Splits pool into word-count tertiles (short, mid, long) and repeats the
    by_article_count measurement within each arm at matched N. A (arm, N)
    cell is skipped when N exceeds EXHAUSTION_GUARD times the arm's article
    count: drawing most of a small arm on every trial collapses the
    between-trial variance the measurement depends on, which understates
    noise instead of showing a genuine drop.
    """
    pool_sorted = sorted(pool, key=lambda i: corpus.words[i])
    third, remainder = divmod(len(pool_sorted), 3)
    sizes = [third, third, third]
    for k in range(remainder):
        sizes[k] += 1
    arms = {
        "short": pool_sorted[: sizes[0]],
        "mid": pool_sorted[sizes[0]: sizes[0] + sizes[1]],
        "long": pool_sorted[sizes[0] + sizes[1]:],
    }

    print("\ntertile arms (recomputed from this pool):")
    for name, arm in arms.items():
        lens = [corpus.words[i] for i in arm]
        print(f"  {name:>5}: n={len(arm):>3} mean_words={statistics.mean(lens):>8,.0f} "
              f"min={min(lens):>6,} max={max(lens):>6,}")

    header = (f"\n{'arm':>6} {'N':>4} {'arm_n':>6} {'mean_sd':>8} {'median_sd':>10} "
              f"{'worst_sd':>9} {'pct_sd<=tol':>12}")
    print(header)
    print("-" * len(header.strip()))

    arm_offset = {"short": 0, "mid": 1, "long": 2}
    by_arm_size_sds: dict[tuple[str, int], list[float]] = {}
    for name, arm in arms.items():
        cap = EXHAUSTION_GUARD * len(arm)
        for size in LENGTH_SIZES:
            if size > cap:
                print(f"{name:>6} {size:>4} {len(arm):>6}  skipped: N > "
                      f"{EXHAUSTION_GUARD} * arm ({cap:.1f})")
                continue
            by_draft = [[] for _ in drafts]
            for trial in range(trials):
                rng = random.Random(SEED + arm_offset[name] * 100_000 + size * 1000 + trial)
                picks = rng.sample(arm, size)
                for d, value in enumerate(score_drafts(corpus, picks, drafts)):
                    by_draft[d].append(value)
            sds = [statistics.stdev(s) for s in by_draft]
            by_arm_size_sds[(name, size)] = sds
            mean_sd = statistics.mean(sds)
            median_sd = statistics.median(sds)
            worst_sd = max(sds)
            pct_le_tol = 100.0 * sum(1 for s in sds if s <= TOLERANCE) / len(sds)
            print(f"{name:>6} {size:>4} {len(arm):>6} {mean_sd:>8.2f} {median_sd:>10.2f} "
                  f"{worst_sd:>9.2f} {pct_le_tol:>11.1f}%")

    # Persistent tail: drafts above NOISE_THRESHOLD at every tested size in
    # the short arm. A small drop in mean_sd once these are removed means the
    # arm-level penalty is broad rather than carried by a handful of drafts.
    short_sets = [
        {i for i, v in enumerate(sds) if v > NOISE_THRESHOLD}
        for (name, _size), sds in by_arm_size_sds.items() if name == "short"
    ]
    persistent_tail = set.intersection(*short_sets) if short_sets else set()
    print(f"\npersistent short-arm tail (sd > {NOISE_THRESHOLD} at every tested size): "
          f"{len(persistent_tail)} of {len(drafts)} drafts")
    for (name, size), sds in by_arm_size_sds.items():
        if name != "short":
            continue
        kept = [v for i, v in enumerate(sds) if i not in persistent_tail]
        if not kept:
            continue
        print(f"  size={size:>2}: mean_sd incl_tail={statistics.mean(sds):.2f}  "
              f"excl_tail(n={len(kept)})={statistics.mean(kept):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, required=True,
                        help="references.jsonl from a built profile")
    parser.add_argument("--rules", type=Path, default=BUILTIN_RULES_PATH)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--heldout", type=int, default=24,
                        help="articles reserved as drafts, never in a profile")
    args = parser.parse_args()

    texts = []
    with args.references.open() as handle:
        for line in handle:
            if line.strip():
                texts.append(json.loads(line)["text"])
    if len(texts) < args.heldout + max(SIZES[0], 3):
        raise SystemExit(f"corpus too small: {len(texts)} articles")

    rules = load_rules(args.rules)
    corpus = Corpus(texts, rules)
    print(f"corpus: {len(texts)} articles, {sum(corpus.words):,} words")

    order = list(range(len(texts)))
    random.Random(SEED).shuffle(order)
    draft_idx, pool = order[:args.heldout], order[args.heldout:]
    drafts = [(texts[i], audit_text(texts[i], rules), corpus.words[i]) for i in draft_idx]
    print(f"pool: {len(pool)} articles, {len(drafts)} held-out drafts, "
          f"{args.trials} trials per size")

    by_article_count(corpus, pool, drafts, args.trials)
    by_word_budget(corpus, pool, drafts, max(20, args.trials // 2))
    by_article_length(corpus, pool, drafts, LENGTH_TRIALS)


if __name__ == "__main__":
    main()
