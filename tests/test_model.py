"""Tests for git-log parsing and the commit model."""

from __future__ import annotations

from pathlib import Path

from assertpy import assert_that

from git_replay.model import Commit, normalize_author, parse_log


def test_parse_log_reads_all_commits(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """parse_log yields one commit per header line in order."""
    commits = parse_log(
        path=logs_dir / "alpha.txt",
        repo="alpha",
        aliases=aliases,
    )
    assert_that(commits).is_length(4)
    assert_that([commit.t for commit in commits]).is_equal_to([1000, 2000, 3000, 4000])
    assert_that(commits[0].repo).is_equal_to("alpha")


def test_parse_log_sums_numstat_and_skips_binary(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """Binary ``-`` numstat rows contribute no churn to a commit."""
    commits = parse_log(
        path=logs_dir / "alpha.txt",
        repo="alpha",
        aliases=aliases,
    )
    initial = commits[0]
    assert_that(initial.subject).is_equal_to("Initial commit")
    assert_that(initial.ins).is_equal_to(10)
    assert_that(initial.dels).is_equal_to(2)


def test_parse_log_ignores_wrapped_subject_lines(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """Non-numstat continuation lines do not affect churn totals."""
    commits = parse_log(
        path=logs_dir / "alpha.txt",
        repo="alpha",
        aliases=aliases,
    )
    feature = commits[1]
    assert_that(feature.ins).is_equal_to(5)
    assert_that(feature.dels).is_equal_to(1)


def test_parse_log_merges_aliases_including_nl_suffix(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """Alias lookup runs after stripping the ``" (NL)"`` locale suffix."""
    commits = parse_log(
        path=logs_dir / "alpha.txt",
        repo="alpha",
        aliases=aliases,
    )
    authors = [commit.author for commit in commits]
    assert_that(authors).is_equal_to(
        ["TurboCoder13", "TurboCoder13", "renovate[bot]", "Someone Else"],
    )


def test_parse_log_empty_file_yields_no_commits(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """An empty log parses to an empty commit list."""
    commits = parse_log(
        path=logs_dir / "empty.txt",
        repo="empty",
        aliases=aliases,
    )
    assert_that(commits).is_empty()


def test_parse_log_single_commit(
    logs_dir: Path,
    aliases: dict[str, str],
) -> None:
    """A single-commit log flushes the final in-progress commit."""
    commits = parse_log(
        path=logs_dir / "single.txt",
        repo="solo",
        aliases=aliases,
    )
    assert_that(commits).is_length(1)
    only = commits[0]
    assert_that(only).is_equal_to(
        Commit(
            t=5000,
            author="Solo Dev",
            subject="Only commit",
            repo="solo",
            ins=7,
            dels=7,
        ),
    )


def test_normalize_author_strips_nl_suffix_before_alias() -> None:
    """The ``" (NL)"`` suffix is removed before the alias map is consulted."""
    result = normalize_author(
        author="Eitel (NL)",
        aliases={"Eitel": "TurboCoder13"},
    )
    assert_that(result).is_equal_to("TurboCoder13")


def test_normalize_author_passes_through_unknown_names() -> None:
    """A name with no alias is returned cleaned but otherwise unchanged."""
    result = normalize_author(author="  Nobody  ", aliases={})
    assert_that(result).is_equal_to("Nobody")
