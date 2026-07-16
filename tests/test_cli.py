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

_ALPHA_LOG = """\
@1700000000\tAda\tBootstrap core
120\t4\tsrc/core.py
@1700120000\tAda\tAdd parser
88\t12\tsrc/parse.py
-\t-\tassets/logo.png
@1700620000\tAda\tShip replay panel
310\t44\tsrc/page.py
"""

_BETA_LOG = """\
@1700200000\tLin\tWire CLI
64\t8\tbeta/cli.py
@1700400000\tLin\tHeatmap layout
200\t18\tbeta/heatmap.py
@1700460000\trenovate[bot]\tBump pytest
2\t2\tpyproject.toml
"""

_BUILD_OUTPUTS = ("index.html", "replay.svg", "heatmap.svg", "repos.svg", "stat.svg")


def _write_logs(logs_dir: Path) -> None:
    """Populate ``logs_dir`` with two fixture log files.

    Args:
        logs_dir: Directory to write the fixture logs into.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "TurboCoder13__alpha.log").write_text(_ALPHA_LOG, encoding="utf-8")
    (logs_dir / "TurboCoder13__beta.log").write_text(_BETA_LOG, encoding="utf-8")


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


def test_build_writes_page_and_four_svgs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The build command writes index.html plus the four SVG widgets."""
    logs_dir = tmp_path / "logs"
    out_dir = tmp_path / "dist"
    _write_logs(logs_dir=logs_dir)

    exit_code = cli.main(["build", "--logs", str(logs_dir), "--out", str(out_dir)])

    assert_that(exit_code).is_equal_to(0)
    for name in _BUILD_OUTPUTS:
        output = out_dir / name
        assert_that(output.exists()).is_true()
        # Non-trivial output: every file carries real, rendered markup.
        assert_that(len(output.read_text(encoding="utf-8"))).is_greater_than(500)
    assert_that(capsys.readouterr().out).contains("Wrote 5 file(s)")

    index = (out_dir / "index.html").read_text(encoding="utf-8")
    assert_that(index).starts_with("<!doctype html>")
    assert_that(index).contains("commits, replayed")
    for svg_name in ("replay.svg", "heatmap.svg", "repos.svg", "stat.svg"):
        svg = (out_dir / svg_name).read_text(encoding="utf-8")
        assert_that(svg).contains("<svg").contains("</svg>")


def test_build_applies_config_aliases(tmp_path: Path) -> None:
    """A supplied config merges author aliases before aggregation."""
    logs_dir = tmp_path / "logs"
    out_dir = tmp_path / "dist"
    _write_logs(logs_dir=logs_dir)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[alias_map]\n"Lin" = "Ada"\n',
        encoding="utf-8",
    )

    cli.main(
        [
            "build",
            "--logs",
            str(logs_dir),
            "--out",
            str(out_dir),
            "--config",
            str(config_path),
        ],
    )

    repos = (out_dir / "stat.svg").read_text(encoding="utf-8")
    # Lin folds into Ada, so only two human authors remain plus the bot.
    assert_that(repos).contains("agent-authored")


def test_build_rejects_empty_logs_dir(tmp_path: Path) -> None:
    """Building from a directory with no commits is an error."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    with pytest.raises(ValueError):
        cli.main(
            ["build", "--logs", str(logs_dir), "--out", str(tmp_path / "dist")],
        )
