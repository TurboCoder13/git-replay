"""GitHub repository discovery and commit-log extraction."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - git is invoked with fixed argv lists, no shell
import tempfile
import urllib.request
from pathlib import Path

from git_replay.repo import Repo

_API_ROOT = "https://api.github.com"
_PER_PAGE = 100
_LOG_FORMAT = "@%at%x09%an%x09%s"


def discover_repos(owner: str) -> list[Repo]:
    """Discover the public, non-fork repositories owned by ``owner``.

    Results from the GitHub REST API are hard-filtered: any repository that is
    private or a fork is dropped unconditionally, regardless of configuration.

    Args:
        owner: The GitHub login whose repositories are listed.

    Returns:
        The public, non-fork repositories owned by ``owner``.
    """
    repos: list[Repo] = []
    page = 1
    while True:
        payload = _get_json(
            url=(
                f"{_API_ROOT}/users/{owner}/repos"
                f"?per_page={_PER_PAGE}&page={page}&type=owner"
            ),
        )
        if not payload:
            break
        repos.extend(_select(owner=owner, payload=payload))
        if len(payload) < _PER_PAGE:
            break
        page += 1
    return repos


def _select(owner: str, payload: list[dict[str, object]]) -> list[Repo]:
    """Convert a REST page into repositories, dropping private and fork repos.

    Args:
        owner: The GitHub login whose repositories are being processed.
        payload: The decoded JSON array for a single results page.

    Returns:
        The retained repositories from the page.
    """
    selected: list[Repo] = []
    for item in payload:
        # HARD, unconditional filter: never include private or fork repos.
        if item.get("private") or item.get("fork"):
            continue
        selected.append(
            Repo(
                owner=owner,
                name=str(item["name"]),
                clone_url=str(item["clone_url"]),
                default_branch=str(item.get("default_branch", "main")),
            ),
        )
    return selected


def _get_json(url: str) -> list[dict[str, object]]:
    """Fetch and decode a JSON array from the GitHub REST API.

    A ``GH_TOKEN`` environment variable, when set, is sent as a bearer token.

    Args:
        url: The fully qualified request URL.

    Returns:
        The decoded JSON array.

    Raises:
        ValueError: If ``url`` is not an ``https`` URL.
    """
    if not url.startswith("https://"):
        raise ValueError("only https URLs are permitted")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "git-replay",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(  # nosec B310 - https-only, guarded above
        url=url,
        headers=headers,
    )
    with urllib.request.urlopen(request) as response:  # nosec B310 nosemgrep
        payload: list[dict[str, object]] = json.loads(
            response.read().decode("utf-8"),
        )
        return payload


def dump_log(repo: Repo, out_dir: str | Path) -> Path:
    """Clone ``repo`` shallowly and write its commit log to ``out_dir``.

    The repository is cloned as a blobless bare mirror, then a merge-free log is
    written in the ``@<unix-time>\\t<author>\\t<subject>`` format followed by
    per-commit ``--numstat`` lines.

    Args:
        repo: The repository to extract.
        out_dir: Directory into which the log file is written.

    Returns:
        The path of the written log file.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    log_file = out_path / f"{repo.owner}__{repo.name}.log"
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / f"{repo.name}.git"
        _run(
            args=[
                "git",
                "clone",
                "--filter=blob:none",
                "--bare",
                repo.clone_url,
                str(clone_dir),
            ],
        )
        log = _run(
            args=[
                "git",
                f"--git-dir={clone_dir}",
                "log",
                "--no-merges",
                "--date=unix",
                f"--format={_LOG_FORMAT}",
                "--numstat",
            ],
        )
    log_file.write_text(log, encoding="utf-8")
    return log_file


def _run(args: list[str]) -> str:
    """Run a git command and return its captured stdout.

    Args:
        args: The full argument vector to execute.

    Returns:
        The command's standard output.

    Raises:
        subprocess.CalledProcessError: If the command exits non-zero.
    """
    result = subprocess.run(  # nosec B603 B607 - fixed git argv, no shell
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
