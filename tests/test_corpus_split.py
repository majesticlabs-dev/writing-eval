"""Corpus holdout-splitting tests."""

from pathlib import Path

from writing_eval.corpus import split_holdout
from tests.helpers_corpus import flag_holdout_only, make_samples, mixed_samples

def test_split_holdout_is_deterministic(tmp_path: Path) -> None:
    samples = mixed_samples()
    first = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    second = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    assert first == second


def test_split_holdout_disjoint_and_covers_all(tmp_path: Path) -> None:
    samples = mixed_samples()
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    holdout_ids = {s["id"] for s in holdout}
    eval_ids = {s["id"] for s in eval_set}
    all_ids = {s["id"] for s in samples}
    assert holdout_ids.isdisjoint(eval_ids)
    assert holdout_ids | eval_ids == all_ids


def test_split_holdout_stratifies_each_use_case(tmp_path: Path) -> None:
    samples = mixed_samples()
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    for use_case in ("article_section", "product_writing", "exec_communication"):
        assert any(s["use_case"] == use_case for s in holdout)
        assert any(s["use_case"] == use_case for s in eval_set)


def test_split_holdout_min_one_eval_per_nonempty_group(tmp_path: Path) -> None:
    samples = make_samples("article_section", 1, "solo")
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    assert len(eval_set) == 1
    assert len(holdout) == 0


def test_split_holdout_output_sorted_by_id(tmp_path: Path) -> None:
    samples = mixed_samples()
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    assert [s["id"] for s in holdout] == sorted(s["id"] for s in holdout)
    assert [s["id"] for s in eval_set] == sorted(s["id"] for s in eval_set)

def test_split_holdout_forces_flagged_into_holdout_deterministically(
    tmp_path: Path,
) -> None:
    flagged_ids = {"sample-art00", "sample-prod01"}
    samples = flag_holdout_only(mixed_samples(), flagged_ids)
    first = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    second = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    assert first == second
    holdout, eval_set = first
    holdout_ids = {s["id"] for s in holdout}
    eval_ids = {s["id"] for s in eval_set}
    assert flagged_ids <= holdout_ids
    assert not (flagged_ids & eval_ids)
    assert holdout_ids.isdisjoint(eval_ids)
    assert holdout_ids | eval_ids == {s["id"] for s in samples}


def test_split_holdout_eval_fraction_over_unflagged_pool_only(tmp_path: Path) -> None:
    samples = make_samples("article_section", 5, "art")
    flagged_ids = {"sample-art00", "sample-art01"}
    samples = flag_holdout_only(samples, flagged_ids)
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    # Pool of 3 unflagged samples: round(3 * 0.4) = 1 eval, 2 pool holdout,
    # plus the 2 forced holdout samples.
    assert len(eval_set) == 1
    assert len(holdout) == 4
    assert eval_set[0]["id"] not in flagged_ids


def test_split_holdout_all_flagged_use_case_has_no_eval_entries(tmp_path: Path) -> None:
    exec_samples = flag_holdout_only(
        make_samples("exec_communication", 3, "exec"),
        {"sample-exec00", "sample-exec01", "sample-exec02"},
    )
    samples = make_samples("article_section", 3, "art") + exec_samples
    holdout, eval_set = split_holdout(samples, eval_fraction=0.4, seed=20260717)
    assert all(s["use_case"] != "exec_communication" for s in eval_set)
    assert sum(1 for s in holdout if s["use_case"] == "exec_communication") == 3
    assert any(s["use_case"] == "article_section" for s in eval_set)
    holdout_ids = {s["id"] for s in holdout}
    eval_ids = {s["id"] for s in eval_set}
    assert holdout_ids.isdisjoint(eval_ids)
    assert holdout_ids | eval_ids == {s["id"] for s in samples}
