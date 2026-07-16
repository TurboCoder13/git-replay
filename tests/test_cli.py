"""Tests for the git-replay command-line interface."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay import cli
from git_replay.repo import Repo

_CONFIG = """
owners = ["TurboCoder13"]
exclude = ["ui-framework"]
"""


def test_fetch_command_dumps_non_excluded_repos(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The fetch command dumps every discovered, non-excluded repository."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(_CONFIG, encoding="utf-8")
    out_dir = tmp_path / "logs"

    discovered = [
        Repo(
            owner="TurboCoder13",
            name="git-replay",
            clone_url="https://github.com/TurboCoder13/git-replay.git",
            default_branch="main",
        ),
        Repo(
            owner="TurboCoder13",
            name="ui-framework",
            clone_url="https://github.com/TurboCoder13/ui-framework.git",
            default_branch="main",
        ),
    ]
    dumped: list[str] = []

    def fake_dump(repo: Repo, out_dir: Path) -> Path:
        dumped.append(repo.name)
        return Path(repo.name)

    monkeypatch.setattr(cli, "discover_repos", lambda owner: discovered)
    monkeypatch.setattr(cli, "dump_log", fake_dump)

    exit_code = cli.main(
        ["fetch", "--config", str(config_path), "--out", str(out_dir)],
    )

    assert_that(exit_code).is_equal_to(0)
    assert_that(dumped).is_equal_to(["git-replay"])
    assert_that(capsys.readouterr().out).contains("Wrote 1 log file(s)")


def test_fetch_requires_config_and_out() -> None:
    """The fetch subcommand requires both --config and --out."""
    with pytest.raises(SystemExit):
        cli.main(["fetch"])


def test_main_requires_a_subcommand() -> None:
    """Invoking the CLI without a command exits non-zero."""
    with pytest.raises(SystemExit):
        cli.main([])
