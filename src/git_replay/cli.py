"""Command-line interface for git-replay."""

from __future__ import annotations

import argparse
from pathlib import Path

from git_replay.config import Config, load_config
from git_replay.fetch import discover_repos, dump_log


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
