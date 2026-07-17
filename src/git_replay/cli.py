"""Command-line interface for git-replay."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

from git_replay.aggregate import (
    bucketize,
    daily_counts,
    per_author,
    per_repo,
    split_authors,
)
from git_replay.config import Config, load_config
from git_replay.fetch import discover_repos, dump_log
from git_replay.model import Commit, parse_log
from git_replay.render import heatmap_svg, page, repos_svg, stat_svg
from git_replay.render.replay_svg import ReplayMeta
from git_replay.render.replay_svg import render as render_replay

# Fixed display timezone for local-day bucketing (Europe/Amsterdam, matching the
# prototype's UTC+2 baseline). Kept as a fixed offset to stay dependency-free and
# deterministic across hosts.
_DISPLAY_TZ: tzinfo = timezone(timedelta(hours=2))

_BUILD_BUCKETS = 240
_LOG_GLOBS = ("*.log", "*.txt")


def _fetch(config: Config, out_dir: Path) -> list[Path]:
    """Discover configured repositories and dump each commit log.

    Args:
        config: The loaded configuration.
        out_dir: Directory into which log files are written.

    Returns:
        The paths of the written log files.
    """
    excluded = set(config.exclude)
    written: list[Path] = []
    for owner in config.owners:
        for repo in discover_repos(owner):
            if repo.name in excluded:
                continue
            written.append(dump_log(repo=repo, out_dir=out_dir))
    return written


def _repo_name(log_path: Path) -> str:
    """Derive a repository name from a log filename.

    Log files dumped by :func:`git_replay.fetch.dump_log` are named
    ``{owner}__{name}.log``; the repository name is the final ``__``-delimited
    segment of the filename stem. Fixture-style names without an owner prefix are
    used verbatim.

    Args:
        log_path: Path to the log file.

    Returns:
        The repository name.
    """
    return log_path.stem.split("__")[-1]


def _load_commits(logs_dir: Path, aliases: dict[str, str]) -> list[Commit]:
    """Parse every log file under ``logs_dir`` into a flat list of commits.

    Args:
        logs_dir: Directory holding formatted git-log files.
        aliases: Mapping of raw author name to canonical name.

    Returns:
        All parsed commits across every log file, in file-then-log order.
    """
    paths = sorted(
        {path for pattern in _LOG_GLOBS for path in logs_dir.glob(pattern)},
    )
    commits: list[Commit] = []
    for path in paths:
        commits.extend(
            parse_log(path=path, repo=_repo_name(log_path=path), aliases=aliases),
        )
    return commits


def _date_label(timestamp: int, tz: tzinfo) -> str:
    """Render a Unix timestamp as a ``"Mon D, YYYY"`` local-date label.

    Args:
        timestamp: Unix epoch seconds.
        tz: Timezone used to resolve the local date.

    Returns:
        The formatted local date.
    """
    return datetime.fromtimestamp(timestamp, tz).strftime("%b %-d, %Y")


def _write_svgs(commits: list[Commit], out_dir: Path) -> None:
    """Render and write the four standalone SVG widgets into ``out_dir``.

    Args:
        commits: The commits to summarize; must be non-empty.
        out_dir: Directory into which the SVG files are written.
    """
    times = [commit.t for commit in commits]
    t0, t1 = min(times), max(times)
    span_days = round((t1 - t0) / 86_400)

    buckets = bucketize(commits=commits, n_buckets=_BUILD_BUCKETS)
    meta = ReplayMeta(
        first_label=_date_label(timestamp=t0, tz=_DISPLAY_TZ),
        last_label=_date_label(timestamp=t1, tz=_DISPLAY_TZ),
        span_days=span_days,
    )

    totals = per_author(commits=commits)
    agent, bots = split_authors(totals=totals)
    agent_total = sum(agent.values())
    bot_total = sum(bots.values())
    total = len(commits)
    agent_pct = round(agent_total / total * 100)

    (out_dir / "replay.svg").write_text(
        render_replay(buckets=buckets, meta=meta),
        encoding="utf-8",
    )
    (out_dir / "heatmap.svg").write_text(
        heatmap_svg.render(
            daily_counts=daily_counts(commits=commits, tz=_DISPLAY_TZ),
            tz=_DISPLAY_TZ,
        ),
        encoding="utf-8",
    )
    (out_dir / "repos.svg").write_text(
        repos_svg.render(per_repo=per_repo(commits=commits)),
        encoding="utf-8",
    )
    (out_dir / "stat.svg").write_text(
        stat_svg.render(
            agent_pct=agent_pct,
            agent_total=agent_total,
            bot_total=bot_total,
        ),
        encoding="utf-8",
    )


def _build(logs_dir: Path, out_dir: Path, config: Config | None) -> list[Path]:
    """Assemble the replay page and the four SVG widgets from dumped logs.

    Args:
        logs_dir: Directory holding formatted git-log files.
        out_dir: Directory into which ``index.html`` and the SVGs are written.
        config: Optional configuration supplying an author alias map.

    Returns:
        The paths of every written output file.

    Raises:
        ValueError: If no commits are found under ``logs_dir``.
    """
    aliases = config.alias_map if config is not None else {}
    label = config.label if config is not None else "TurboCoder13"
    commits = _load_commits(logs_dir=logs_dir, aliases=aliases)
    if not commits:
        raise ValueError(f"no commits found under {logs_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    index.write_text(
        page.render(commits=commits, tz=_DISPLAY_TZ, org_label=label),
        encoding="utf-8",
    )
    _write_svgs(commits=commits, out_dir=out_dir)
    return [
        index,
        out_dir / "replay.svg",
        out_dir / "heatmap.svg",
        out_dir / "repos.svg",
        out_dir / "stat.svg",
    ]


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="git-replay",
        description="Animated git-history replay widgets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser(
        "fetch",
        help="Discover repositories and dump commit logs.",
    )
    fetch.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the TOML configuration file.",
    )
    fetch.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Directory to write commit-log files into.",
    )

    build = subparsers.add_parser(
        "build",
        help="Assemble the replay page and SVG widgets from dumped logs.",
    )
    build.add_argument(
        "--logs",
        required=True,
        type=Path,
        help="Directory holding the dumped commit-log files.",
    )
    build.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Directory to write index.html and the SVG widgets into.",
    )
    build.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional TOML config supplying an author alias map.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the git-replay command-line interface.

    Args:
        argv: Optional argument vector; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    args = _build_parser().parse_args(argv)
    if args.command == "fetch":
        config = load_config(args.config)
        written = _fetch(config=config, out_dir=args.out)
        print(f"Wrote {len(written)} log file(s) to {args.out}")
    elif args.command == "build":
        config = load_config(args.config) if args.config is not None else None
        written = _build(logs_dir=args.logs, out_dir=args.out, config=config)
        print(f"Wrote {len(written)} file(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
