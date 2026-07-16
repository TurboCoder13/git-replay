"""Commit model and git-log parsing for git-replay.

Parses the output of ``git log`` formatted as ``@<ts>\\t<author>\\t<subject>``
header lines followed by ``--numstat`` lines (``<ins>\\t<dels>\\t<path>``), where
``-`` marks a binary file's churn. The module is pure data: no rendering, scaling,
or presentation logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

_NL_SUFFIX = " (NL)"


@dataclass(frozen=True)
class Commit:
    """A single non-merge commit with its churn totals.

    Attributes:
        t: Author timestamp as Unix epoch seconds.
        author: Normalized (alias-merged) author name.
        subject: Commit subject line.
        repo: Name of the repository the commit belongs to.
        ins: Total inserted lines across all files (binary files excluded).
        dels: Total deleted lines across all files (binary files excluded).
    """

    t: int
    author: str
    subject: str
    repo: str
    ins: int = 0
    dels: int = 0


def normalize_author(
    author: str,
    aliases: dict[str, str],
) -> str:
    """Normalize a raw author name for aggregation.

    Strips surrounding whitespace and a trailing ``" (NL)"`` locale suffix, then
    resolves the result through the alias map so that multiple author spellings
    collapse to a single canonical identity.

    Args:
        author: Raw author name from a log header line.
        aliases: Mapping of raw author name to canonical name.

    Returns:
        The canonical author name, or the cleaned raw name if no alias matches.
    """
    cleaned = author.strip()
    if cleaned.endswith(_NL_SUFFIX):
        cleaned = cleaned[: -len(_NL_SUFFIX)]
    return aliases.get(cleaned, cleaned)


def _parse_header(
    line: str,
    repo: str,
    aliases: dict[str, str],
) -> Commit:
    """Build a zero-churn commit from a ``@ts\\tauthor\\tsubject`` header line.

    Args:
        line: Header line including its leading ``@`` marker.
        repo: Repository name to attach to the commit.
        aliases: Mapping of raw author name to canonical name.

    Returns:
        A commit with zeroed insertion and deletion counts.
    """
    ts, author, subject = line[1:].split("\t", 2)
    return Commit(
        t=int(ts),
        author=normalize_author(author=author, aliases=aliases),
        subject=subject,
        repo=repo,
    )


def _apply_numstat(
    commit: Commit,
    line: str,
) -> Commit:
    """Fold a single ``--numstat`` line into a commit's churn totals.

    Lines that are not three tab-separated fields are ignored (e.g. multi-line
    subject continuations). Binary files, marked ``-``, contribute no churn.

    Args:
        commit: Commit being accumulated.
        line: Candidate numstat line.

    Returns:
        The commit with insertions and deletions updated, or unchanged if the
        line is not a numstat row.
    """
    parts = line.split("\t")
    if len(parts) != 3:
        return commit
    ins_raw, dels_raw, _path = parts
    ins = commit.ins + (int(ins_raw) if ins_raw != "-" else 0)
    dels = commit.dels + (int(dels_raw) if dels_raw != "-" else 0)
    return replace(commit, ins=ins, dels=dels)


@dataclass
class _LogAccumulator:
    """Mutable helper that folds log lines into a list of commits."""

    repo: str
    aliases: dict[str, str]
    commits: list[Commit] = field(default_factory=list)
    _current: Commit | None = None

    def feed(
        self,
        line: str,
    ) -> None:
        """Process one raw log line.

        Args:
            line: A single line from the log, without its trailing newline.
        """
        if line.startswith("@"):
            self._flush()
            self._current = _parse_header(
                line=line,
                repo=self.repo,
                aliases=self.aliases,
            )
        elif line.strip() and self._current is not None:
            self._current = _apply_numstat(commit=self._current, line=line)

    def _flush(self) -> None:
        """Append the in-progress commit, if any, to the result list."""
        if self._current is not None:
            self.commits.append(self._current)
            self._current = None

    def finish(self) -> list[Commit]:
        """Flush any pending commit and return the accumulated list.

        Returns:
            All parsed commits in log order.
        """
        self._flush()
        return self.commits


def parse_log(
    path: Path,
    repo: str,
    aliases: dict[str, str],
) -> list[Commit]:
    """Parse a formatted git-log file into commits.

    The log is a sequence of ``@<ts>\\t<author>\\t<subject>`` header lines, each
    optionally followed by ``--numstat`` lines. Author names are normalized via
    :func:`normalize_author`.

    Args:
        path: Path to the log file to read.
        repo: Repository name to attach to every parsed commit.
        aliases: Mapping of raw author name to canonical name.

    Returns:
        The parsed commits in the order they appear in the log.
    """
    accumulator = _LogAccumulator(repo=repo, aliases=aliases)
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        accumulator.feed(raw_line)
    return accumulator.finish()
