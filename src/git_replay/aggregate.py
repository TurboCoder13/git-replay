"""Aggregation of commits into buckets and per-key totals for git-replay.

Pure data reductions over :class:`~git_replay.model.Commit` sequences: time
bucketing for the replay timeline, daily counts for the heatmap, and per-repo,
per-author, and bot/agent breakdowns for the panels. Any presentation scaling
(for example the √ bar scale) lives in the renderers, not here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from git_replay.model import Commit

_BOT_MARKER = "[bot]"


@dataclass(frozen=True)
class Bucket:
    """One slice of the replay timeline over ``[start, end]``.

    Attributes:
        start: Bucket start timestamp as Unix epoch seconds.
        end: Bucket end timestamp as Unix epoch seconds.
        count: Number of commits that fall in the bucket.
        ins: Total insertions across the bucket's commits.
        dels: Total deletions across the bucket's commits.
    """

    start: float
    end: float
    count: int = 0
    ins: int = 0
    dels: int = 0


def bucketize(
    commits: list[Commit],
    n_buckets: int,
) -> list[Bucket]:
    """Distribute commits into evenly spaced time buckets over ``[t0, t1]``.

    ``t0`` and ``t1`` are the earliest and latest commit timestamps. A commit
    landing exactly on ``t1`` is placed in the final bucket rather than
    overflowing past it. When all commits share a timestamp, every commit falls
    into the single first bucket.

    Args:
        commits: Commits to bucket; need not be sorted.
        n_buckets: Number of buckets to produce.

    Returns:
        A list of ``n_buckets`` buckets in chronological order, or an empty list
        when ``commits`` is empty.

    Raises:
        ValueError: If ``n_buckets`` is not positive.
    """
    if n_buckets < 1:
        raise ValueError("n_buckets must be a positive integer")
    if not commits:
        return []

    times = [commit.t for commit in commits]
    t0, t1 = min(times), max(times)
    width = (t1 - t0) / n_buckets

    counts = [0] * n_buckets
    inserts = [0] * n_buckets
    deletes = [0] * n_buckets
    for commit in commits:
        index = 0 if width == 0 else min(n_buckets - 1, int((commit.t - t0) / width))
        counts[index] += 1
        inserts[index] += commit.ins
        deletes[index] += commit.dels

    return [
        Bucket(
            start=t0 + i * width,
            end=t0 + (i + 1) * width,
            count=counts[i],
            ins=inserts[i],
            dels=deletes[i],
        )
        for i in range(n_buckets)
    ]


def daily_counts(
    commits: list[Commit],
    tz: tzinfo,
) -> dict[date, int]:
    """Count commits per local calendar day.

    Args:
        commits: Commits to bucket by day.
        tz: Timezone used to resolve each commit's local calendar date.

    Returns:
        A mapping of local date to commit count.
    """
    counts: dict[date, int] = defaultdict(int)
    for commit in commits:
        day = datetime.fromtimestamp(commit.t, tz).date()
        counts[day] += 1
    return dict(counts)


def per_repo(
    commits: list[Commit],
) -> dict[str, int]:
    """Count commits per repository.

    Args:
        commits: Commits to tally.

    Returns:
        A mapping of repository name to commit count.
    """
    counts: dict[str, int] = defaultdict(int)
    for commit in commits:
        counts[commit.repo] += 1
    return dict(counts)


def per_author(
    commits: list[Commit],
) -> dict[str, int]:
    """Count commits per (normalized) author.

    Args:
        commits: Commits to tally.

    Returns:
        A mapping of author name to commit count.
    """
    counts: dict[str, int] = defaultdict(int)
    for commit in commits:
        counts[commit.author] += 1
    return dict(counts)


def split_authors(
    totals: dict[str, int],
) -> tuple[dict[str, int], dict[str, int]]:
    """Partition author totals into agent-authored and service-bot totals.

    Names containing ``"[bot]"`` (for example ``renovate[bot]`` or
    ``github-actions[bot]``) are treated as service bots; everything else is
    considered agent-authored.

    Args:
        totals: Mapping of author name to commit count.

    Returns:
        A ``(agent_authored, service_bots)`` pair of name-to-count mappings.
    """
    agent_authored: dict[str, int] = {}
    service_bots: dict[str, int] = {}
    for name, count in totals.items():
        if _BOT_MARKER in name:
            service_bots[name] = count
        else:
            agent_authored[name] = count
    return agent_authored, service_bots
