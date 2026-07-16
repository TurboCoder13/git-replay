"""Tests for commit aggregation: buckets, daily counts, and breakdowns."""

from __future__ import annotations

from datetime import date, timezone

import pytest
from assertpy import assert_that

from git_replay.aggregate import (
    Bucket,
    bucketize,
    daily_counts,
    per_author,
    per_repo,
    split_authors,
)
from git_replay.model import Commit


def _commit(
    t: int,
    author: str = "Dev",
    repo: str = "repo",
    ins: int = 0,
    dels: int = 0,
) -> Commit:
    """Build a commit with sensible defaults for aggregation tests.

    Args:
        t: Commit timestamp in epoch seconds.
        author: Author name.
        repo: Repository name.
        ins: Insertions.
        dels: Deletions.

    Returns:
        A constructed :class:`Commit`.
    """
    return Commit(
        t=t,
        author=author,
        subject="subject",
        repo=repo,
        ins=ins,
        dels=dels,
    )


def test_bucketize_empty_returns_empty() -> None:
    """No commits produce no buckets."""
    assert_that(bucketize(commits=[], n_buckets=4)).is_empty()


def test_bucketize_rejects_non_positive_buckets() -> None:
    """A non-positive bucket count is a programming error."""
    with pytest.raises(ValueError):
        bucketize(commits=[_commit(t=1)], n_buckets=0)


def test_bucketize_distributes_and_sums_churn() -> None:
    """Commits land in their time bucket with churn aggregated."""
    commits = [
        _commit(t=0, ins=1, dels=1),
        _commit(t=100, ins=2, dels=0),
        _commit(t=200, ins=4, dels=3),
    ]
    buckets = bucketize(commits=commits, n_buckets=2)
    assert_that(buckets).is_length(2)
    assert_that(buckets[0].count).is_equal_to(1)
    assert_that(buckets[0].ins).is_equal_to(1)
    assert_that(buckets[1].count).is_equal_to(2)
    assert_that(buckets[1].ins).is_equal_to(6)
    assert_that(buckets[1].dels).is_equal_to(3)


def test_bucketize_edge_commit_at_t1_lands_in_last_bucket() -> None:
    """A commit exactly at ``t1`` is placed in the final bucket."""
    commits = [_commit(t=0), _commit(t=100), _commit(t=400)]
    buckets = bucketize(commits=commits, n_buckets=4)
    assert_that(buckets).is_length(4)
    assert_that(buckets[-1].count).is_equal_to(1)
    assert_that(buckets[-1].end).is_equal_to(400.0)


def test_bucketize_all_same_timestamp() -> None:
    """When every commit shares a timestamp they collapse into bucket zero."""
    commits = [_commit(t=42), _commit(t=42), _commit(t=42)]
    buckets = bucketize(commits=commits, n_buckets=3)
    assert_that(buckets[0]).is_equal_to(
        Bucket(start=42.0, end=42.0, count=3, ins=0, dels=0),
    )
    assert_that(buckets[1].count).is_equal_to(0)


def test_daily_counts_groups_by_local_day() -> None:
    """Commits are tallied per local calendar date."""
    commits = [
        _commit(t=0),
        _commit(t=3600),
        _commit(t=90000),
    ]
    counts = daily_counts(commits=commits, tz=timezone.utc)
    assert_that(counts[date(1970, 1, 1)]).is_equal_to(2)
    assert_that(counts[date(1970, 1, 2)]).is_equal_to(1)


def test_per_repo_counts() -> None:
    """Commits are tallied per repository."""
    commits = [
        _commit(t=1, repo="a"),
        _commit(t=2, repo="a"),
        _commit(t=3, repo="b"),
    ]
    assert_that(per_repo(commits=commits)).is_equal_to({"a": 2, "b": 1})


def test_per_author_counts() -> None:
    """Commits are tallied per author."""
    commits = [
        _commit(t=1, author="X"),
        _commit(t=2, author="Y"),
        _commit(t=3, author="X"),
    ]
    assert_that(per_author(commits=commits)).is_equal_to({"X": 2, "Y": 1})


def test_split_authors_separates_service_bots() -> None:
    """Names containing ``[bot]`` are classified as service bots."""
    totals = {
        "TurboCoder13": 40,
        "renovate[bot]": 5,
        "github-actions[bot]": 3,
    }
    agent_authored, service_bots = split_authors(totals=totals)
    assert_that(agent_authored).is_equal_to({"TurboCoder13": 40})
    assert_that(service_bots).is_equal_to(
        {"renovate[bot]": 5, "github-actions[bot]": 3},
    )
